"""
Consolidacion de personas embargadas a nivel documento.

Esta etapa recibe predicciones realizadas sobre FRAGMENTOS.

Responsabilidades:

1. Agrupar variantes de una misma persona.
2. Consolidar nombre, DNI, CUIT/CUIL y roles.
3. Detectar terceros evidentes.
4. Detectar conflictos de identificadores.
5. Admitir multiples embargados.
6. Evaluar si el resultado posee evidencia suficiente.
7. Conservar trazabilidad completa para etapas posteriores.

IMPORTANTE:

- texto_completo se conserva, pero NO se utiliza en esta etapa.
- Un resultado "suficiente" NO significa "correcto".
- Significa que no hace falta ejecutar el fallback sobre texto completo.
"""

from __future__ import annotations

import re
import unicodedata

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz


# ============================================================
# ESTADOS
# ============================================================

ESTADO_RESUELTO = "RESUELTO"
ESTADO_RESUELTO_MULTIPLE = "RESUELTO_MULTIPLE"
ESTADO_NO_RESUELTO = "NO_RESUELTO"


# ============================================================
# CONFIGURACION
# ============================================================

FUZZY_THRESHOLD_STRICT = 90.0
FUZZY_THRESHOLD_PARTIAL = 85.0

MIN_TOKENS_PARTIAL_MATCH = 2

MIN_SCORE_EMBARGADO = 6.0
SCORE_EVIDENCIA_FUERTE = 10.0

MIN_SCORE_MULTIPLE_SIN_CONTEXTO = 10.0


# ------------------------------------------------------------
# SUFICIENCIA
# ------------------------------------------------------------

# Nombre de un solo token:
#
# GONZALEZ
#
# No necesariamente esta mal, pero no queremos considerarlo
# suficiente para evitar el fallback al texto completo.

MIN_TOKENS_NOMBRE_SUFICIENTE = 2

# Si hay demasiadas personas aceptadas dentro del documento,
# preferimos pedir una segunda extracción sobre texto completo.

MAX_EMBARGADOS_SIN_REVISION = 5

# Un candidato de una sola evidencia debe superar este score
# para considerarse fuerte.
MIN_SCORE_EVIDENCIA_UNICA = 8.0


# ============================================================
# ROLES POSITIVOS
# ============================================================

ROLES_POSITIVOS = {
    "demandado",
    "demandada",
    "embargado",
    "embargada",
    "ejecutado",
    "ejecutada",
    "deudor",
    "deudora",
    "titular",
}


# ============================================================
# VALORES INVALIDOS
# ============================================================

VALORES_VACIOS = {
    "",
    "none",
    "null",
    "nan",
    "n/a",
    "na",
    "no encontrado",
    "no_encontrado",
    "no resuelto",
    "no_resuelto",
    "unknown",
    "desconocido",
}


EXPRESIONES_NO_NOMBRE = {
    "usuario incorrecto",
    "parte demandada",
    "el demandado",
    "la demandada",
    "el embargado",
    "la embargada",
    "parte ejecutada",
    "parte ejecutante",
}


# ============================================================
# CONTEXTO POSITIVO
# ============================================================

PATRONES_CONTEXTO_POSITIVO = (
    r"\bembargado\b\s*:?",
    r"\bembargada\b\s*:?",

    r"\bdemandado\b",
    r"\bdemandada\b",

    r"\bejecutado\b",
    r"\bejecutada\b",

    r"\bdeudor\b",
    r"\bdeudora\b",

    r"\bembargar\s+(?:las|los|sus)?\s*"
    r"(?:cuentas|fondos|haberes)",

    r"\bembargo\s+sobre\b",

    r"\btr[aá]base\s+embargo\b",
    r"\btr[aá]bese\s+embargo\b",

    r"\bretenci[oó]n\s+"
    r"(?:directa\s+)?"
    r"(?:de|del|de\s+la|de\s+los|de\s+las|sobre)\b",

    r"\bretener\s+"
    r"(?:el|la|los|las)?\s*"
    r"(?:haberes|fondos|sumas|porcentaje)",

    r"\bperciba\s+el\s+sr\b",
    r"\bperciba\s+la\s+sra\b",
)


# ============================================================
# CONTEXTO NEGATIVO
# ============================================================

PATRONES_CONTEXTO_NEGATIVO = (
    r"\bdepositarse\b",
    r"\bdepositar(?:se)?\b",

    r"\bcuenta\s+abierta\s+a\s+nombre\s+de\b",
    r"\bcuenta\s+judicial\b",

    r"\btransferir\b",
    r"\btransferencia\b",

    r"\bdestinatari[oa]s?\b",
    r"\ba\s+favor\s+de\b",
)


# ============================================================
# TERCEROS
# ============================================================

PATRONES_LISTA_TERCEROS = (
    r"\bautorizad[oa]s?\s+para\s+diligenciar\b",
    r"\bautorizad[oa]s?\s+al\s+diligenciamiento\b",
    r"\bse\s+encuentran?\s+autorizad[oa]s?\b",
    r"\bquedan?\s+autorizad[oa]s?\b",
    r"\bautor[ií]zase\s+a\b",
    r"\bse\s+autoriza\s+a\b",
    r"\bpersonas?\s+autorizad[oa]s?\b",
    r"\bprofesionales?\s+autorizad[oa]s?\b",
    r"\bletrad[oa]s?\s+autorizad[oa]s?\b",
    r"\babogad[oa]s?\s+autorizad[oa]s?\b",
    r"\blos\s+dres?\.?\b",
    r"\blas\s+dras?\.?\b",
    r"\bdres?\.?\b",
    r"\bdras?\.?\b",
    r"\babogad[oa]s?\b",
    r"\bletrad[oa]s?\b",
    r"\bapoderad[oa]s?\b",
    r"\bprocurador(?:a|es)?\b",
    r"\bmandatari[oa]s?\b",
    r"\bdiligenciador(?:a|es)?\b",
    r"\bpersonas?\s+facultad[oa]s?\b",
    r"\bfacultad[oa]s?\s+para\s+diligenciar\b",
)


PATRONES_TERCERO_INDIVIDUAL = (
    r"\bfirmado\s+por\b",
    r"\bfirmado\s+y\s+notificado\s+por\b",
    r"\bjuez\b",
    r"\bjueza\b",
    r"\bsecretari[oa]\b",
    r"\bauxiliar\s+letrado\b",
    r"\bactuari[oa]\b",
)


PATRONES_ROL_CERCANO_POSITIVO = (
    r"\bdemandado\b",
    r"\bdemandada\b",
    r"\bembargado\b",
    r"\bembargada\b",
    r"\bejecutado\b",
    r"\bejecutada\b",
    r"\bdeudor\b",
    r"\bdeudora\b",
    r"\bparte\s+demandada\b",
    r"\bpartes\s+demandadas\b",
    r"\bembargo\s+sobre\b",
    r"\btr[aá]base\s+embargo\b",
    r"\btr[aá]bese\s+embargo\b",
    r"\bretenci[oó]n\b",
)


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class Evidencia:
    numero_archivo: str
    id_documento: str

    contador_interno: str
    palabra_clave: str
    categoria: str

    fragmento: str

    nombre: str
    dni: str = ""
    cuit_cuil: str = ""
    rol: str = ""

    nombre_confidence: float | None = None
    dni_confidence: float | None = None
    cuit_cuil_confidence: float | None = None
    rol_confidence: float | None = None

    nombre_span_inicio: int | None = None
    nombre_span_fin: int | None = None

    contexto_local: str = ""

    score_contextual: float = 0.0

    tercero_fuerte: bool = False
    motivo_tercero: str = ""

    tipo_entrada: str = "fragmento"


@dataclass
class GrupoPersona:
    evidencias: list[Evidencia] = field(
        default_factory=list
    )

    variantes_nombre: set[str] = field(
        default_factory=set
    )

    dni_encontrados: set[str] = field(
        default_factory=set
    )

    cuit_cuil_encontrados: set[str] = field(
        default_factory=set
    )

    roles_encontrados: set[str] = field(
        default_factory=set
    )

    fragmentos_soporte: set[str] = field(
        default_factory=set
    )

    score_total: float = 0.0


# ============================================================
# NORMALIZACION
# ============================================================

def _texto_seguro(
    value: Any,
) -> str:

    if value is None:
        return ""

    return str(
        value
    ).strip()


def _normalizar_texto(
    value: Any,
) -> str:

    text = _texto_seguro(
        value
    )

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(
            char
        )
    )

    text = text.upper()

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _normalizar_identificador(
    value: Any,
) -> str:

    return re.sub(
        r"\D",
        "",
        _texto_seguro(
            value
        ),
    )


def _tokens_nombre(
    nombre: str,
) -> list[str]:

    return [
        token
        for token in _normalizar_texto(
            nombre
        ).split()
        if token
    ]


# ============================================================
# NOMBRE
# ============================================================

def _nombre_es_util(
    nombre: Any,
) -> bool:

    text = _texto_seguro(
        nombre
    )

    if not text:
        return False

    if text.lower() in VALORES_VACIOS:
        return False

    normalizado = _normalizar_texto(
        text
    )

    if (
        normalizado.lower()
        in EXPRESIONES_NO_NOMBRE
    ):
        return False

    if not re.search(
        r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]",
        text,
    ):
        return False

    letras = re.sub(
        r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]",
        "",
        text,
    )

    return len(
        letras
    ) >= 4


def _nombre_extremadamente_incompleto(
    nombre: str,
) -> bool:
    """
    Evalua solamente suficiencia.

    Un apellido unico como:

        GONZALEZ

    puede ser un candidato real, por lo que NO se elimina.

    Pero no es suficiente para evitar buscar el documento completo.
    """

    tokens = _tokens_nombre(
        nombre
    )

    return (
        len(tokens)
        < MIN_TOKENS_NOMBRE_SUFICIENTE
    )


# ============================================================
# RAPIDFUZZ
# ============================================================

def _nombres_equivalentes(
    nombre_a: str,
    nombre_b: str,
) -> bool:

    a = _normalizar_texto(
        nombre_a
    )

    b = _normalizar_texto(
        nombre_b
    )

    if not a or not b:
        return False

    if a == b:
        return True

    tokens_a = set(
        a.split()
    )

    tokens_b = set(
        b.split()
    )

    if (
        tokens_a
        and tokens_a == tokens_b
    ):
        return True

    token_sort = fuzz.token_sort_ratio(
        a,
        b,
    )

    token_set = fuzz.token_set_ratio(
        a,
        b,
    )

    if (
        token_sort >= FUZZY_THRESHOLD_STRICT
        and token_set >= FUZZY_THRESHOLD_STRICT
    ):
        return True

    if len(tokens_a) <= len(tokens_b):
        smaller = tokens_a
        larger = tokens_b
    else:
        smaller = tokens_b
        larger = tokens_a

    if (
        len(smaller)
        >= MIN_TOKENS_PARTIAL_MATCH
        and smaller.issubset(
            larger
        )
        and token_set
        >= FUZZY_THRESHOLD_PARTIAL
    ):
        return True

    return False


def _nombres_incompatibles(
    nombre_a: str,
    nombre_b: str,
) -> bool:

    if _nombres_equivalentes(
        nombre_a,
        nombre_b,
    ):
        return False

    tokens_a = set(
        _normalizar_texto(
            nombre_a
        ).split()
    )

    tokens_b = set(
        _normalizar_texto(
            nombre_b
        ).split()
    )

    if not tokens_a or not tokens_b:
        return False

    interseccion = (
        tokens_a
        & tokens_b
    )

    if not interseccion:
        return True

    union = (
        tokens_a
        | tokens_b
    )

    return (
        len(interseccion)
        / len(union)
    ) < 0.25


# ============================================================
# IDENTIFICADORES
# ============================================================

def _identificador_compartido(
    evidencia_a: Evidencia,
    evidencia_b: Evidencia,
) -> tuple[str | None, str | None]:

    dni_a = _normalizar_identificador(
        evidencia_a.dni
    )

    dni_b = _normalizar_identificador(
        evidencia_b.dni
    )

    if (
        dni_a
        and dni_b
        and dni_a == dni_b
    ):
        return (
            "dni",
            dni_a,
        )

    cuit_a = _normalizar_identificador(
        evidencia_a.cuit_cuil
    )

    cuit_b = _normalizar_identificador(
        evidencia_b.cuit_cuil
    )

    if (
        cuit_a
        and cuit_b
        and cuit_a == cuit_b
    ):
        return (
            "cuit_cuil",
            cuit_a,
        )

    return (
        None,
        None,
    )


def _identificadores_contradictorios(
    evidencia_a: Evidencia,
    evidencia_b: Evidencia,
) -> bool:

    dni_a = _normalizar_identificador(
        evidencia_a.dni
    )

    dni_b = _normalizar_identificador(
        evidencia_b.dni
    )

    if (
        dni_a
        and dni_b
        and dni_a != dni_b
    ):
        return True

    cuit_a = _normalizar_identificador(
        evidencia_a.cuit_cuil
    )

    cuit_b = _normalizar_identificador(
        evidencia_b.cuit_cuil
    )

    if (
        cuit_a
        and cuit_b
        and cuit_a != cuit_b
    ):
        return True

    return False


def _evidencias_misma_persona(
    evidencia_a: Evidencia,
    evidencia_b: Evidencia,
) -> bool:

    if _identificadores_contradictorios(
        evidencia_a,
        evidencia_b,
    ):
        return False

    tipo_id, valor_id = _identificador_compartido(
        evidencia_a,
        evidencia_b,
    )

    if tipo_id and valor_id:
        return _nombres_equivalentes(
            evidencia_a.nombre,
            evidencia_b.nombre,
        )

    return _nombres_equivalentes(
        evidencia_a.nombre,
        evidencia_b.nombre,
    )


# ============================================================
# CONTEXTO
# ============================================================

def _extraer_contexto_local(
    fragmento: str,
    nombre: str,
    start: int | None,
    end: int | None,
    radio: int = 120,
) -> str:

    if not fragmento:
        return ""

    if (
        isinstance(start, int)
        and isinstance(end, int)
        and 0 <= start < len(fragmento)
    ):
        inicio = max(
            0,
            start - radio,
        )

        fin = min(
            len(fragmento),
            end + radio,
        )

        return fragmento[
            inicio:fin
        ]

    if nombre:
        match = re.search(
            re.escape(
                nombre
            ),
            fragmento,
            flags=re.IGNORECASE,
        )

        if match:
            return fragmento[
                max(
                    0,
                    match.start() - radio,
                ):
                min(
                    len(fragmento),
                    match.end() + radio,
                )
            ]

    return fragmento


def _buscar_posicion_nombre(
    evidencia: Evidencia,
) -> tuple[int | None, int | None]:

    if (
        isinstance(
            evidencia.nombre_span_inicio,
            int,
        )
        and isinstance(
            evidencia.nombre_span_fin,
            int,
        )
        and 0
        <= evidencia.nombre_span_inicio
        < len(evidencia.fragmento)
    ):
        return (
            evidencia.nombre_span_inicio,
            evidencia.nombre_span_fin,
        )

    match = re.search(
        re.escape(
            evidencia.nombre
        ),
        evidencia.fragmento,
        flags=re.IGNORECASE,
    )

    if not match:
        return (
            None,
            None,
        )

    return (
        match.start(),
        match.end(),
    )


def _contexto_previo_nombre(
    evidencia: Evidencia,
    chars: int = 280,
) -> str:

    start, _ = _buscar_posicion_nombre(
        evidencia
    )

    if start is None:
        return ""

    return evidencia.fragmento[
        max(
            0,
            start - chars,
        ):
        start
    ]


def _contexto_inmediato_nombre(
    evidencia: Evidencia,
    chars_antes: int = 90,
    chars_despues: int = 50,
) -> str:

    start, end = _buscar_posicion_nombre(
        evidencia
    )

    if (
        start is None
        or end is None
    ):
        return evidencia.contexto_local

    return evidencia.fragmento[
        max(
            0,
            start - chars_antes,
        ):
        min(
            len(evidencia.fragmento),
            end + chars_despues,
        )
    ]


# ============================================================
# TERCEROS
# ============================================================

def _tiene_rol_positivo_cercano(
    evidencia: Evidencia,
) -> bool:

    contexto = _contexto_inmediato_nombre(
        evidencia
    ).lower()

    return any(
        re.search(
            pattern,
            contexto,
            flags=re.IGNORECASE,
        )
        is not None
        for pattern
        in PATRONES_ROL_CERCANO_POSITIVO
    )


def _esta_en_lista_de_terceros(
    evidencia: Evidencia,
) -> bool:

    previo = _contexto_previo_nombre(
        evidencia
    ).lower()

    if not previo:
        return False

    if _tiene_rol_positivo_cercano(
        evidencia
    ):
        return False

    for pattern in PATRONES_LISTA_TERCEROS:

        matches = list(
            re.finditer(
                pattern,
                previo,
                flags=re.IGNORECASE,
            )
        )

        if not matches:
            continue

        ultimo = matches[-1]

        distancia = (
            len(previo)
            - ultimo.end()
        )

        if distancia <= 220:
            return True

    return False


def _es_tercero_individual(
    evidencia: Evidencia,
) -> bool:

    contexto = _contexto_inmediato_nombre(
        evidencia,
        chars_antes=100,
        chars_despues=60,
    ).lower()

    if _tiene_rol_positivo_cercano(
        evidencia
    ):
        return False

    return any(
        re.search(
            pattern,
            contexto,
            flags=re.IGNORECASE,
        )
        is not None
        for pattern
        in PATRONES_TERCERO_INDIVIDUAL
    )


def _evaluar_tercero(
    evidencia: Evidencia,
) -> tuple[bool, str]:

    if _esta_en_lista_de_terceros(
        evidencia
    ):
        return (
            True,
            "lista_autorizados_profesionales",
        )

    if _es_tercero_individual(
        evidencia
    ):
        return (
            True,
            "funcionario_firmante_profesional",
        )

    return (
        False,
        "",
    )


# ============================================================
# SCORE
# ============================================================

def _score_contexto(
    evidencia: Evidencia,
) -> float:

    contexto = _texto_seguro(
        evidencia.contexto_local
    ).lower()

    if not contexto:
        return 0.0

    score = 0.0

    for pattern in PATRONES_CONTEXTO_POSITIVO:
        if re.search(
            pattern,
            contexto,
            flags=re.IGNORECASE,
        ):
            score += 1.5

    for pattern in PATRONES_CONTEXTO_NEGATIVO:
        if re.search(
            pattern,
            contexto,
            flags=re.IGNORECASE,
        ):
            score -= 2.0

    tercero, motivo = _evaluar_tercero(
        evidencia
    )

    evidencia.tercero_fuerte = tercero
    evidencia.motivo_tercero = motivo

    if tercero:
        score -= 6.0

    return score


def _score_evidencia(
    evidencia: Evidencia,
) -> float:

    score = 1.0

    if isinstance(
        evidencia.nombre_confidence,
        (int, float),
    ):
        score += (
            float(
                evidencia.nombre_confidence
            )
            * 3.0
        )

    if evidencia.dni:
        score += 2.5

        if isinstance(
            evidencia.dni_confidence,
            (int, float),
        ):
            score += (
                float(
                    evidencia.dni_confidence
                )
                * 0.5
            )

    if evidencia.cuit_cuil:
        score += 3.0

        if isinstance(
            evidencia.cuit_cuil_confidence,
            (int, float),
        ):
            score += (
                float(
                    evidencia.cuit_cuil_confidence
                )
                * 0.5
            )

    rol = _normalizar_texto(
        evidencia.rol
    ).lower()

    if rol:

        if rol in ROLES_POSITIVOS:
            score += 1.5
        else:
            score += 0.25

    contexto_score = _score_contexto(
        evidencia
    )

    evidencia.score_contextual = (
        contexto_score
    )

    score += contexto_score

    return score


# ============================================================
# EXTRAER EVIDENCIAS
# ============================================================

def _extraer_evidencias_documento(
    documento: dict[str, Any],
) -> list[Evidencia]:

    evidencias: list[Evidencia] = []

    for resultado in (
        documento.get(
            "resultados",
            [],
        )
        or []
    ):

        fragmento = _texto_seguro(
            resultado.get(
                "fragmento"
            )
        )

        for candidate in (
            resultado.get(
                "candidates",
                [],
            )
            or []
        ):

            nombre = _texto_seguro(
                candidate.get(
                    "nombre_embargado"
                )
                or candidate.get(
                    "nombre"
                )
            )

            if not _nombre_es_util(
                nombre
            ):
                continue

            start = candidate.get(
                "nombre_embargado_span_inicio"
            )

            if start is None:
                start = candidate.get(
                    "nombre_span_inicio"
                )

            end = candidate.get(
                "nombre_embargado_span_fin"
            )

            if end is None:
                end = candidate.get(
                    "nombre_span_fin"
                )

            evidencia = Evidencia(
                numero_archivo=_texto_seguro(
                    documento.get(
                        "numero_archivo"
                    )
                ),

                id_documento=_texto_seguro(
                    documento.get(
                        "id"
                    )
                ),

                contador_interno=_texto_seguro(
                    resultado.get(
                        "contador_interno"
                    )
                ),

                palabra_clave=_texto_seguro(
                    resultado.get(
                        "palabra_clave"
                    )
                ),

                categoria=_texto_seguro(
                    resultado.get(
                        "categoria"
                    )
                ),

                fragmento=fragmento,

                nombre=nombre,

                dni=_texto_seguro(
                    candidate.get(
                        "dni_embargado"
                    )
                    or candidate.get(
                        "dni"
                    )
                ),

                cuit_cuil=_texto_seguro(
                    candidate.get(
                        "cuit_cuil_embargado"
                    )
                    or candidate.get(
                        "cuil_cuit"
                    )
                ),

                rol=_texto_seguro(
                    candidate.get(
                        "rol_embargado"
                    )
                ),

                nombre_confidence=(
                    candidate.get(
                        "nombre_embargado_confidence"
                    )
                    or candidate.get(
                        "nombre_confidence"
                    )
                ),

                dni_confidence=(
                    candidate.get(
                        "dni_embargado_confidence"
                    )
                    or candidate.get(
                        "dni_confidence"
                    )
                ),

                cuit_cuil_confidence=(
                    candidate.get(
                        "cuit_cuil_embargado_confidence"
                    )
                    or candidate.get(
                        "cuil_cuit_confidence"
                    )
                ),

                rol_confidence=(
                    candidate.get(
                        "rol_embargado_confidence"
                    )
                ),

                nombre_span_inicio=start,
                nombre_span_fin=end,

                contexto_local=_extraer_contexto_local(
                    fragmento,
                    nombre,
                    start,
                    end,
                ),

                tipo_entrada="fragmento",
            )

            evidencias.append(
                evidencia
            )

    return evidencias


# ============================================================
# AGRUPACION
# ============================================================

def _grupo_coincide(
    evidencia: Evidencia,
    grupo: GrupoPersona,
) -> bool:

    return any(
        _evidencias_misma_persona(
            evidencia,
            existente,
        )
        for existente
        in grupo.evidencias
    )


def _agrupar_evidencias(
    evidencias: list[Evidencia],
) -> list[GrupoPersona]:

    grupos: list[GrupoPersona] = []

    for evidencia in evidencias:

        grupo_encontrado = None

        for grupo in grupos:

            if _grupo_coincide(
                evidencia,
                grupo,
            ):
                grupo_encontrado = grupo
                break

        if grupo_encontrado is None:

            grupo_encontrado = (
                GrupoPersona()
            )

            grupos.append(
                grupo_encontrado
            )

        grupo_encontrado.evidencias.append(
            evidencia
        )

        grupo_encontrado.variantes_nombre.add(
            evidencia.nombre
        )

        if evidencia.dni:
            grupo_encontrado.dni_encontrados.add(
                evidencia.dni
            )

        if evidencia.cuit_cuil:
            grupo_encontrado.cuit_cuil_encontrados.add(
                evidencia.cuit_cuil
            )

        if evidencia.rol:
            grupo_encontrado.roles_encontrados.add(
                evidencia.rol
            )

        grupo_encontrado.fragmentos_soporte.add(
            evidencia.contador_interno
            or evidencia.fragmento
        )

        grupo_encontrado.score_total += (
            _score_evidencia(
                evidencia
            )
        )

    return grupos


# ============================================================
# NOMBRE CANONICO
# ============================================================

def _nombre_canonico(
    grupo: GrupoPersona,
) -> str:

    mejores: list[
        tuple[int, float, str]
    ] = []

    for variante in (
        grupo.variantes_nombre
    ):

        tokens = len(
            _tokens_nombre(
                variante
            )
        )

        confidencias = [
            evidencia.nombre_confidence
            for evidencia
            in grupo.evidencias
            if (
                evidencia.nombre
                == variante
                and isinstance(
                    evidencia.nombre_confidence,
                    (int, float),
                )
            )
        ]

        mejores.append(
            (
                tokens,
                max(
                    confidencias
                )
                if confidencias
                else 0.0,
                variante,
            )
        )

    if not mejores:
        return ""

    mejores.sort(
        reverse=True
    )

    return mejores[
        0
    ][
        2
    ]


# ============================================================
# CONFLICTOS
# ============================================================

def _identificadores_grupo(
    grupo: GrupoPersona,
) -> dict[str, set[str]]:

    return {
        "dni": {
            _normalizar_identificador(
                value
            )
            for value
            in grupo.dni_encontrados
            if _normalizar_identificador(
                value
            )
        },

        "cuit_cuil": {
            _normalizar_identificador(
                value
            )
            for value
            in grupo.cuit_cuil_encontrados
            if _normalizar_identificador(
                value
            )
        },
    }


def _detectar_conflictos_identificadores(
    grupos: list[GrupoPersona],
) -> list[dict[str, Any]]:

    conflictos: list[
        dict[str, Any]
    ] = []

    vistos: set[
        tuple[str, str, str, str]
    ] = set()

    for index_a in range(
        len(grupos)
    ):

        grupo_a = grupos[
            index_a
        ]

        nombre_a = _nombre_canonico(
            grupo_a
        )

        ids_a = _identificadores_grupo(
            grupo_a
        )

        for index_b in range(
            index_a + 1,
            len(grupos),
        ):

            grupo_b = grupos[
                index_b
            ]

            nombre_b = _nombre_canonico(
                grupo_b
            )

            if not _nombres_incompatibles(
                nombre_a,
                nombre_b,
            ):
                continue

            ids_b = _identificadores_grupo(
                grupo_b
            )

            for tipo in (
                "dni",
                "cuit_cuil",
            ):

                for valor in (
                    ids_a[tipo]
                    & ids_b[tipo]
                ):

                    key = (
                        tipo,
                        valor,
                        nombre_a,
                        nombre_b,
                    )

                    if key in vistos:
                        continue

                    vistos.add(
                        key
                    )

                    conflictos.append(
                        {
                            "tipo_identificador":
                                tipo,

                            "valor_normalizado":
                                valor,

                            "nombre_a":
                                nombre_a,

                            "nombre_b":
                                nombre_b,

                            "variantes_a":
                                sorted(
                                    grupo_a.variantes_nombre
                                ),

                            "variantes_b":
                                sorted(
                                    grupo_b.variantes_nombre
                                ),
                        }
                    )

    return conflictos


# ============================================================
# IDENTIDAD INTERNA INCONSISTENTE
# ============================================================

def _grupo_tiene_identidad_inconsistente(
    grupo: GrupoPersona,
) -> bool:

    dnis = {
        _normalizar_identificador(
            value
        )
        for value
        in grupo.dni_encontrados
        if _normalizar_identificador(
            value
        )
    }

    cuits = {
        _normalizar_identificador(
            value
        )
        for value
        in grupo.cuit_cuil_encontrados
        if _normalizar_identificador(
            value
        )
    }

    return (
        len(dnis) > 1
        or len(cuits) > 1
    )


# ============================================================
# VALOR MAS FRECUENTE
# ============================================================

def _valor_mas_frecuente(
    values: list[str],
) -> str:

    counts: defaultdict[
        str,
        int,
    ] = defaultdict(
        int
    )

    original: dict[
        str,
        str,
    ] = {}

    for value in values:

        key = _normalizar_identificador(
            value
        )

        if not key:
            continue

        counts[
            key
        ] += 1

        original.setdefault(
            key,
            value,
        )

    if not counts:
        return ""

    winner = max(
        counts,
        key=lambda key: counts[key],
    )

    return original[
        winner
    ]


# ============================================================
# VALIDACION GRUPO
# ============================================================

def _grupo_tiene_identificador(
    grupo: GrupoPersona,
) -> bool:

    return bool(
        grupo.dni_encontrados
        or grupo.cuit_cuil_encontrados
    )


def _grupo_tiene_contexto_positivo(
    grupo: GrupoPersona,
) -> bool:

    return any(
        evidencia.score_contextual > 0
        for evidencia
        in grupo.evidencias
    )


def _grupo_tiene_tercero_fuerte(
    grupo: GrupoPersona,
) -> bool:

    if not grupo.evidencias:
        return False

    cantidad = sum(
        1
        for evidencia
        in grupo.evidencias
        if evidencia.tercero_fuerte
    )

    return (
        cantidad
        > len(
            grupo.evidencias
        ) / 2
    )


def _grupo_tiene_contexto_negativo_fuerte(
    grupo: GrupoPersona,
) -> bool:

    positivos = sum(
        1
        for evidencia
        in grupo.evidencias
        if evidencia.score_contextual > 0
    )

    negativos = sum(
        1
        for evidencia
        in grupo.evidencias
        if evidencia.score_contextual < 0
    )

    return (
        negativos > positivos
        and negativos > 0
    )


def _grupo_es_embargado(
    grupo: GrupoPersona,
    total_grupos: int,
) -> bool:

    cantidad_fragmentos = len(
        grupo.fragmentos_soporte
    )

    tiene_id = _grupo_tiene_identificador(
        grupo
    )

    tiene_contexto = (
        _grupo_tiene_contexto_positivo(
            grupo
        )
    )

    if _grupo_tiene_tercero_fuerte(
        grupo
    ):
        return False

    if _grupo_tiene_contexto_negativo_fuerte(
        grupo
    ):
        return False

    if (
        grupo.score_total
        < MIN_SCORE_EMBARGADO
    ):
        return False

    if total_grupos > 1:

        if (
            tiene_contexto
            and tiene_id
        ):
            return True

        if (
            cantidad_fragmentos >= 2
            and tiene_id
            and grupo.score_total
            >= MIN_SCORE_MULTIPLE_SIN_CONTEXTO
        ):
            return True

        if (
            cantidad_fragmentos >= 2
            and tiene_contexto
            and grupo.score_total
            >= SCORE_EVIDENCIA_FUERTE
        ):
            return True

        return False

    if (
        cantidad_fragmentos >= 2
        and (
            tiene_id
            or tiene_contexto
        )
    ):
        return True

    if (
        cantidad_fragmentos == 1
        and tiene_id
        and tiene_contexto
    ):
        return True

    if (
        grupo.score_total
        >= SCORE_EVIDENCIA_FUERTE
        and tiene_contexto
    ):
        return True

    return False


# ============================================================
# SERIALIZACION
# ============================================================

def _serializar_evidencia(
    evidencia: Evidencia,
) -> dict[str, Any]:

    return {
        "tipo_entrada":
            evidencia.tipo_entrada,

        "contador_interno":
            evidencia.contador_interno,

        "palabra_clave":
            evidencia.palabra_clave,

        "categoria":
            evidencia.categoria,

        "nombre_detectado":
            evidencia.nombre,

        "dni_detectado":
            evidencia.dni,

        "cuit_cuil_detectado":
            evidencia.cuit_cuil,

        "rol_detectado":
            evidencia.rol,

        "nombre_confidence":
            evidencia.nombre_confidence,

        "score_contextual":
            round(
                evidencia.score_contextual,
                3,
            ),

        "tercero_fuerte":
            evidencia.tercero_fuerte,

        "motivo_tercero":
            evidencia.motivo_tercero,

        "fragmento":
            evidencia.fragmento,

        "contexto_local":
            evidencia.contexto_local,
    }


def _serializar_grupo(
    grupo: GrupoPersona,
) -> dict[str, Any]:

    return {
        "nombre_embargado":
            _nombre_canonico(
                grupo
            ),

        "dni_embargado":
            _valor_mas_frecuente(
                [
                    evidencia.dni
                    for evidencia
                    in grupo.evidencias
                ]
            ),

        "cuit_cuil_embargado":
            _valor_mas_frecuente(
                [
                    evidencia.cuit_cuil
                    for evidencia
                    in grupo.evidencias
                ]
            ),

        "roles_detectados":
            sorted(
                grupo.roles_encontrados
            ),

        "variantes_nombre":
            sorted(
                grupo.variantes_nombre
            ),

        "cantidad_fragmentos_soporte":
            len(
                grupo.fragmentos_soporte
            ),

        "cantidad_evidencias":
            len(
                grupo.evidencias
            ),

        "score_total":
            round(
                grupo.score_total,
                3,
            ),

        "identidad_inconsistente":
            _grupo_tiene_identidad_inconsistente(
                grupo
            ),

        "evidencias": [
            _serializar_evidencia(
                evidencia
            )
            for evidencia
            in grupo.evidencias
        ],
    }

def _conflicto_afecta_persona_aceptada(
    conflictos_identificador: list[
        dict[str, Any]
    ],
    personas_embargadas: list[
        dict[str, Any]
    ],
) -> bool:
    """
    Devuelve True solamente si algun conflicto de identificador
    involucra a una persona que fue aceptada como embargada.

    Los conflictos que ocurren exclusivamente entre grupos
    descartados no obligan a ejecutar el fallback.
    """

    nombres_aceptados = {
        _normalizar_texto(
            persona.get(
                "nombre_embargado",
                "",
            )
        )
        for persona
        in personas_embargadas
        if persona.get(
            "nombre_embargado"
        )
    }

    if not nombres_aceptados:
        return False

    for conflicto in conflictos_identificador:

        nombre_a = _normalizar_texto(
            conflicto.get(
                "nombre_a",
                "",
            )
        )

        nombre_b = _normalizar_texto(
            conflicto.get(
                "nombre_b",
                "",
            )
        )

        if (
            nombre_a in nombres_aceptados
            or nombre_b in nombres_aceptados
        ):
            return True

    return False


# ============================================================
# SUFICIENCIA
# ============================================================

def evaluar_suficiencia(
    estado: str,
    personas_embargadas: list[
        dict[str, Any]
    ],
    grupos_descartados: list[
        dict[str, Any]
    ],
    conflictos_identificador: list[
        dict[str, Any]
    ],
) -> tuple[
    bool,
    list[str],
]:
    """
    Decide si la evidencia de fragmentos es suficiente.

    IMPORTANTE:

    suficiente=True NO significa que el candidato sea
    definitivamente correcto.

    Significa:

        "hay evidencia suficiente como para NO ejecutar
         otra extraccion sobre texto_completo".

    Qwen verificara el resultado posteriormente.
    """

    motivos: list[str] = []

    # --------------------------------------------------------
    # 1. NO RESUELTO
    # --------------------------------------------------------

    if estado == ESTADO_NO_RESUELTO:
        motivos.append(
            "no_resuelto"
        )

    # --------------------------------------------------------
    # 2. NINGUNA PERSONA ACEPTADA
    # --------------------------------------------------------

    if not personas_embargadas:
        motivos.append(
            "sin_persona_embargada"
        )

    # --------------------------------------------------------
    # 3. SOLO HUBO DESCARTADOS
    # --------------------------------------------------------

    if (
        not personas_embargadas
        and grupos_descartados
    ):
        motivos.append(
            "solo_candidatos_descartados"
        )

    # --------------------------------------------------------
    # 4. CONFLICTOS DE IDENTIFICADORES
    #
    # Solo vuelve insuficiente al documento si el conflicto
    # afecta a alguna persona aceptada.
    #
    # Los conflictos exclusivamente entre grupos descartados
    # se conservan para auditoria, pero no activan fallback.
    # --------------------------------------------------------

    if _conflicto_afecta_persona_aceptada(
        conflictos_identificador,
        personas_embargadas,
    ):
        motivos.append(
        "conflicto_identificador"
    )

    # --------------------------------------------------------
    # 5. DEMASIADOS EMBARGADOS
    # --------------------------------------------------------

    if (
        len(
            personas_embargadas
        )
        > MAX_EMBARGADOS_SIN_REVISION
    ):
        motivos.append(
            "cantidad_embargados_anormal"
        )

    # --------------------------------------------------------
    # 6. ANALISIS INDIVIDUAL DE PERSONAS
    # --------------------------------------------------------

    for index, persona in enumerate(
        personas_embargadas,
        start=1,
    ):

        nombre = _texto_seguro(
            persona.get(
                "nombre_embargado"
            )
        )

        cantidad_evidencias = int(
            persona.get(
                "cantidad_evidencias",
                0,
            )
        )

        score_total = float(
            persona.get(
                "score_total",
                0.0,
            )
        )

        roles = (
            persona.get(
                "roles_detectados",
                [],
            )
            or []
        )

        evidencias = (
            persona.get(
                "evidencias",
                [],
            )
            or []
        )

        # ----------------------------------------------------
        # Nombre incompleto
        # ----------------------------------------------------

        if _nombre_extremadamente_incompleto(
            nombre
        ):
            motivos.append(
                f"persona_{index}:nombre_incompleto"
            )

        # ----------------------------------------------------
        # Identidad internamente inconsistente
        # ----------------------------------------------------

        if persona.get(
            "identidad_inconsistente",
            False,
        ):
            motivos.append(
                f"persona_{index}:identidad_inconsistente"
            )

        # ----------------------------------------------------
        # Evidencia unica demasiado debil
        # ----------------------------------------------------

        if (
            cantidad_evidencias <= 1
            and score_total
            < MIN_SCORE_EVIDENCIA_UNICA
        ):
            motivos.append(
                f"persona_{index}:evidencia_unica_debil"
            )

        # ----------------------------------------------------
        # Sin roles juridicos
        # ----------------------------------------------------

        if not roles:

            tiene_contexto_positivo = any(
                float(
                    evidencia.get(
                        "score_contextual",
                        0.0,
                    )
                    or 0.0
                )
                > 0
                for evidencia
                in evidencias
            )

            if not tiene_contexto_positivo:

                motivos.append(
                    f"persona_{index}:sin_senal_juridica"
                )

    # --------------------------------------------------------
    # DEDUPLICAR MANTENIENDO ORDEN
    # --------------------------------------------------------

    motivos = list(
        dict.fromkeys(
            motivos
        )
    )

    return (
        len(motivos) == 0,
        motivos,
    )


# ============================================================
# CONSOLIDAR DOCUMENTO
# ============================================================

def consolidar_documento(
    documento: dict[str, Any],
) -> dict[str, Any]:

    evidencias = _extraer_evidencias_documento(
        documento
    )

    grupos = _agrupar_evidencias(
        evidencias
    )

    conflictos = (
        _detectar_conflictos_identificadores(
            grupos
        )
    )

    grupos_validos = [
        grupo
        for grupo in grupos
        if _grupo_es_embargado(
            grupo,
            total_grupos=len(
                grupos
            ),
        )
    ]

    grupos_validos.sort(
        key=lambda grupo: (
            grupo.score_total,
            len(
                grupo.fragmentos_soporte
            ),
        ),
        reverse=True,
    )

    personas_embargadas = [
        _serializar_grupo(
            grupo
        )
        for grupo
        in grupos_validos
    ]

    if not personas_embargadas:
        estado = ESTADO_NO_RESUELTO

    elif len(
        personas_embargadas
    ) == 1:
        estado = ESTADO_RESUELTO

    else:
        estado = ESTADO_RESUELTO_MULTIPLE

    grupos_descartados = [
        _serializar_grupo(
            grupo
        )
        for grupo
        in grupos
        if grupo not in grupos_validos
    ]

    suficiente, motivos = (
        evaluar_suficiencia(
            estado=estado,
            personas_embargadas=(
                personas_embargadas
            ),
            grupos_descartados=(
                grupos_descartados
            ),
            conflictos_identificador=(
                conflictos
            ),
        )
    )

    return {
        "id":
            documento.get(
                "id"
            ),

        "numero_archivo":
            documento.get(
                "numero_archivo"
            ),

        "nombre_documento":
            documento.get(
                "nombre"
            ),

        # Se conserva para fallback posterior.
        "texto_completo":
            documento.get(
                "texto_completo",
                "",
            ),

        "tipo_consolidacion":
            "fragmentos",

        "estado":
            estado,

        # ----------------------------------------------------
        # NUEVO
        # ----------------------------------------------------

        "suficiente":
            suficiente,

        "requiere_fallback_documento_completo":
            not suficiente,

        "motivos_insuficiencia":
            motivos,

        # ----------------------------------------------------

        "cantidad_embargados":
            len(
                personas_embargadas
            ),

        "personas_embargadas":
            personas_embargadas,

        "cantidad_grupos_candidatos":
            len(
                grupos
            ),

        "cantidad_grupos_descartados":
            len(
                grupos_descartados
            ),

        "grupos_descartados":
            grupos_descartados,

        "requiere_revision":
            bool(
                conflictos
            ),

        "cantidad_conflictos_identificador":
            len(
                conflictos
            ),

        "conflictos_identificador":
            conflictos,
    }


# ============================================================
# TODOS LOS DOCUMENTOS
# ============================================================

def consolidar_documentos(
    documentos: list[
        dict[str, Any]
    ],
) -> list[
    dict[str, Any]
]:

    return [
        consolidar_documento(
            documento
        )
        for documento
        in documentos
    ]


# ============================================================
# RESUMEN
# ============================================================

def resumir_consolidacion(
    resultados: list[
        dict[str, Any]
    ],
) -> dict[str, int]:

    resumen = {
        "total_documentos":
            len(
                resultados
            ),

        ESTADO_RESUELTO:
            0,

        ESTADO_RESUELTO_MULTIPLE:
            0,

        ESTADO_NO_RESUELTO:
            0,

        "total_personas_embargadas":
            0,

        "documentos_requieren_revision":
            0,

        "total_conflictos_identificador":
            0,

        # NUEVO
        "SUFICIENTES":
            0,

        "INSUFICIENTES":
            0,
    }

    for resultado in resultados:

        estado = resultado.get(
            "estado"
        )

        if estado in resumen:
            resumen[
                estado
            ] += 1

        resumen[
            "total_personas_embargadas"
        ] += int(
            resultado.get(
                "cantidad_embargados",
                0,
            )
        )

        if resultado.get(
            "requiere_revision",
            False,
        ):
            resumen[
                "documentos_requieren_revision"
            ] += 1

        resumen[
            "total_conflictos_identificador"
        ] += int(
            resultado.get(
                "cantidad_conflictos_identificador",
                0,
            )
        )

        if resultado.get(
            "suficiente",
            False,
        ):
            resumen[
                "SUFICIENTES"
            ] += 1
        else:
            resumen[
                "INSUFICIENTES"
            ] += 1

    return resumen