"""
Consolidacion de personas embargadas a nivel documento.

Este modulo recibe predicciones realizadas por GLiNER sobre fragmentos
y consolida las distintas evidencias para determinar que personas deben
considerarse embargadas.

Principios:

1. GLiNER trabaja fragmento por fragmento.
2. Un mismo embargado puede aparecer con variantes de nombre.
3. RapidFuzz ayuda a reconocer variantes del mismo nombre.
4. DNI y CUIT/CUIL son evidencia fuerte, pero NO fusionan por si solos
   nombres incompatibles.
5. Si un mismo identificador aparece asociado a nombres incompatibles,
   se registra un conflicto para revision.
6. Se utilizan señales juridicas positivas y negativas del contexto.
7. No se fuerza un unico embargado: pueden existir varios.
8. Se conserva trazabilidad de evidencias, variantes y descartes.

Este modulo NO ejecuta GLiNER.
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
ESTADO_REVISAR = "REVISAR"


# ============================================================
# CONFIGURACION
# ============================================================

# Dos nombres muy similares.
FUZZY_THRESHOLD_STRICT = 90.0

# Nombre parcial contenido en uno mas completo.
FUZZY_THRESHOLD_PARTIAL = 85.0

# No fusionar automaticamente por inclusion un solo apellido.
MIN_TOKENS_PARTIAL_MATCH = 2

# Score minimo general.
MIN_SCORE_EMBARGADO = 6.0

# Evidencia especialmente fuerte.
SCORE_EVIDENCIA_FUERTE = 10.0

# Cuando un documento contiene varios candidatos,
# exigimos algo mas de evidencia para aceptar candidatos
# sin contexto juridico positivo explicito.
MIN_SCORE_MULTIPLE_SIN_CONTEXTO = 10.0


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

    r"\bretenci[oó]n\s+(?:directa\s+)?de\b",
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
# CONTEXTO DE TERCEROS
#
# Penalizacion mas fuerte.
#
# No contiene nombres concretos.
# ============================================================

PATRONES_TERCERO_FUERTE = (
    # Personas autorizadas para diligenciar.
    r"\bautorizad[oa]s?\s+para\s+diligenciar\b",
    r"\bautorizad[oa]s?\s+al\s+diligenciamiento\b",
    r"\bse\s+encuentran?\s+autorizad[oa]s?\b",

    # Profesionales / representantes.
    r"\blos\s+dres?\b",
    r"\blas\s+dras?\b",
    r"\bdr\.?\s",
    r"\bdra\.?\s",
    r"\bletrad[oa]s?\b",
    r"\babogad[oa]s?\b",
    r"\bapoderad[oa]s?\b",

    # Funcionarios judiciales.
    r"\bjuez\b",
    r"\bjueza\b",
    r"\bsecretari[oa]\b",
    r"\bauxiliar\s+letrado\b",

    # Firmantes.
    r"\bfirmado\s+por\b",
    r"\bfirma\s+digital\b",
    r"\bcertificado\s+correcto\b",

    # Destino de fondos.
    r"\bcuenta\s+de\s+dep[oó]sito\b",
    r"\bcuenta\s+receptora\b",

    # Entidades que administran/prestan servicios.
    r"\badministrado\s+por\b",
    r"\badministrada\s+por\b",
    r"\bservicio\s+de\s+procesamiento\b",
)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Evidencia:
    """Prediccion individual obtenida de un fragmento."""

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


@dataclass
class GrupoPersona:
    """Conjunto de evidencias que parecen pertenecer a la misma persona."""

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

    return str(value).strip()


def _normalizar_texto(
    value: Any,
) -> str:
    """
    Normalizacion usada exclusivamente para comparacion.

    No modifica el valor original que se exporta.
    """

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
    """
    Normaliza DNI / CUIT / CUIL.

    Ejemplos:

        34.436.998
        34436998

    producen:

        34436998
    """

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

    normalizado = (
        _normalizar_texto(
            nombre
        )
    )

    return [
        token
        for token in normalizado.split()
        if token
    ]


# ============================================================
# NOMBRE VALIDO
# ============================================================

def _nombre_es_util(
    nombre: Any,
) -> bool:

    text = _texto_seguro(
        nombre
    )

    if not text:
        return False

    if (
        text.lower()
        in VALORES_VACIOS
    ):
        return False

    normalizado = (
        _normalizar_texto(
            text
        )
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

    # Evita:
    #
    # D.
    # A c.
    # etc.
    if len(letras) < 4:
        return False

    return True


# ============================================================
# COMPARACION DE NOMBRES
# ============================================================

def _nombres_equivalentes(
    nombre_a: str,
    nombre_b: str,
) -> bool:
    """
    Determina si dos variantes parecen representar
    la misma persona.

    Se consideran:

    - igualdad normalizada;
    - mismos tokens en distinto orden;
    - RapidFuzz;
    - nombre parcial de al menos dos tokens.
    """

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

    # --------------------------------------------------------
    # Mismos tokens en distinto orden
    # --------------------------------------------------------

    if (
        tokens_a
        and tokens_a == tokens_b
    ):
        return True

    token_sort = (
        fuzz.token_sort_ratio(
            a,
            b,
        )
    )

    token_set = (
        fuzz.token_set_ratio(
            a,
            b,
        )
    )

    # --------------------------------------------------------
    # Coincidencia fuerte
    # --------------------------------------------------------

    if (
        token_sort >= FUZZY_THRESHOLD_STRICT
        and token_set >= FUZZY_THRESHOLD_STRICT
    ):
        return True

    # --------------------------------------------------------
    # Nombre parcial
    #
    # Ejemplo:
    #
    # ESTEFANIA MIHANOVICH
    # NORMA ESTEFANIA MIHANOVICH
    # --------------------------------------------------------

    if len(
        tokens_a
    ) <= len(
        tokens_b
    ):
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
    """
    Inverso conservador de equivalencia.

    Se usa para impedir que un DNI/CUIT mal asociado
    fusione dos nombres completamente diferentes.
    """

    if _nombres_equivalentes(
        nombre_a,
        nombre_b,
    ):
        return False

    a = _normalizar_texto(
        nombre_a
    )

    b = _normalizar_texto(
        nombre_b
    )

    if not a or not b:
        return False

    tokens_a = set(
        a.split()
    )

    tokens_b = set(
        b.split()
    )

    interseccion = (
        tokens_a
        & tokens_b
    )

    # Si no comparten absolutamente ningun token,
    # son claramente incompatibles.
    if not interseccion:
        return True

    # Si solo comparten una fraccion muy pequena
    # tambien los consideramos incompatibles.
    union = (
        tokens_a
        | tokens_b
    )

    if union:
        ratio_tokens = (
            len(interseccion)
            / len(union)
        )

        if ratio_tokens < 0.25:
            return True

    return False


# ============================================================
# IDENTIFICADORES
# ============================================================

def _dni_normalizado(
    evidencia: Evidencia,
) -> str:

    return _normalizar_identificador(
        evidencia.dni
    )


def _cuit_normalizado(
    evidencia: Evidencia,
) -> str:

    return _normalizar_identificador(
        evidencia.cuit_cuil
    )


def _identificador_compartido(
    evidencia_a: Evidencia,
    evidencia_b: Evidencia,
) -> tuple[
    str | None,
    str | None,
]:
    """
    Devuelve:

        ("dni", valor)

    o:

        ("cuit_cuil", valor)

    cuando ambas evidencias comparten un identificador.
    """

    dni_a = _dni_normalizado(
        evidencia_a
    )

    dni_b = _dni_normalizado(
        evidencia_b
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

    cuit_a = _cuit_normalizado(
        evidencia_a
    )

    cuit_b = _cuit_normalizado(
        evidencia_b
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
    """
    Si ambos tienen un DNI real y son distintos,
    evita fusionar solamente por nombre.

    Lo mismo para CUIT/CUIL.
    """

    dni_a = _dni_normalizado(
        evidencia_a
    )

    dni_b = _dni_normalizado(
        evidencia_b
    )

    if (
        dni_a
        and dni_b
        and dni_a != dni_b
    ):
        return True

    cuit_a = _cuit_normalizado(
        evidencia_a
    )

    cuit_b = _cuit_normalizado(
        evidencia_b
    )

    if (
        cuit_a
        and cuit_b
        and cuit_a != cuit_b
    ):
        return True

    return False


# ============================================================
# MISMA PERSONA
# ============================================================

def _evidencias_misma_persona(
    evidencia_a: Evidencia,
    evidencia_b: Evidencia,
) -> bool:
    """
    Regla central de identidad.

    IMPORTANTE:

    Un DNI/CUIT igual ya NO fusiona automaticamente.

    Si el identificador coincide pero los nombres son
    incompatibles, se mantienen separados y posteriormente
    se registra el conflicto.
    """

    # --------------------------------------------------------
    # Identificadores contradictorios
    # --------------------------------------------------------

    if _identificadores_contradictorios(
        evidencia_a,
        evidencia_b,
    ):
        return False

    tipo_id, valor_id = (
        _identificador_compartido(
            evidencia_a,
            evidencia_b,
        )
    )

    # --------------------------------------------------------
    # Mismo identificador
    # --------------------------------------------------------

    if (
        tipo_id
        and valor_id
    ):
        # Identificador igual + nombres compatibles.
        return _nombres_equivalentes(
            evidencia_a.nombre,
            evidencia_b.nombre,
        )

    # --------------------------------------------------------
    # Sin identificador comparable.
    #
    # Se decide por similitud de nombre.
    # --------------------------------------------------------

    return _nombres_equivalentes(
        evidencia_a.nombre,
        evidencia_b.nombre,
    )


# ============================================================
# CONTEXTO LOCAL
# ============================================================

def _extraer_contexto_local(
    fragmento: str,
    nombre: str,
    start: int | None,
    end: int | None,
    radio: int = 120,
) -> str:
    """
    Extrae una ventana alrededor del nombre.

    Es importante porque un fragmento puede contener
    varias personas distintas.
    """

    if not fragmento:
        return ""

    if (
        isinstance(
            start,
            int,
        )
        and isinstance(
            end,
            int,
        )
        and 0 <= start < len(
            fragmento
        )
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

    # --------------------------------------------------------
    # Fallback por busqueda literal
    # --------------------------------------------------------

    if nombre:
        match = re.search(
            re.escape(
                nombre
            ),
            fragmento,
            flags=re.IGNORECASE,
        )

        if match:
            inicio = max(
                0,
                match.start() - radio,
            )

            fin = min(
                len(fragmento),
                match.end() + radio,
            )

            return fragmento[
                inicio:fin
            ]

    return fragmento


# ============================================================
# TERCEROS
# ============================================================

def _es_contexto_tercero_fuerte(
    contexto: str,
) -> bool:

    contexto = (
        _texto_seguro(
            contexto
        )
        .lower()
    )

    if not contexto:
        return False

    return any(
        re.search(
            pattern,
            contexto,
            flags=re.IGNORECASE,
        )
        is not None
        for pattern
        in PATRONES_TERCERO_FUERTE
    )


# ============================================================
# SCORE CONTEXTUAL
# ============================================================

def _score_contexto(
    evidencia: Evidencia,
) -> float:

    contexto = (
        _texto_seguro(
            evidencia.contexto_local
        )
        .lower()
    )

    if not contexto:
        return 0.0

    score = 0.0

    # --------------------------------------------------------
    # Positivo
    # --------------------------------------------------------

    for pattern in (
        PATRONES_CONTEXTO_POSITIVO
    ):
        if re.search(
            pattern,
            contexto,
            flags=re.IGNORECASE,
        ):
            score += 1.5

    # --------------------------------------------------------
    # Negativo
    # --------------------------------------------------------

    for pattern in (
        PATRONES_CONTEXTO_NEGATIVO
    ):
        if re.search(
            pattern,
            contexto,
            flags=re.IGNORECASE,
        ):
            score -= 2.0

    # --------------------------------------------------------
    # Tercero fuerte
    # --------------------------------------------------------

    evidencia.tercero_fuerte = (
        _es_contexto_tercero_fuerte(
            contexto
        )
    )

    if evidencia.tercero_fuerte:
        score -= 6.0

    return score


# ============================================================
# SCORE DE EVIDENCIA
# ============================================================

def _score_evidencia(
    evidencia: Evidencia,
) -> float:

    score = 1.0

    # --------------------------------------------------------
    # Nombre
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # DNI
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CUIT/CUIL
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Rol
    # --------------------------------------------------------

    rol = (
        _normalizar_texto(
            evidencia.rol
        )
        .lower()
    )

    if rol:
        if rol in ROLES_POSITIVOS:
            score += 1.5
        else:
            score += 0.25

    # --------------------------------------------------------
    # Contexto
    # --------------------------------------------------------

    contexto_score = (
        _score_contexto(
            evidencia
        )
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

    evidencias: list[
        Evidencia
    ] = []

    numero_archivo = (
        _texto_seguro(
            documento.get(
                "numero_archivo"
            )
        )
    )

    id_documento = (
        _texto_seguro(
            documento.get(
                "id"
            )
        )
    )

    resultados = (
        documento.get(
            "resultados",
            [],
        )
        or []
    )

    for resultado in resultados:

        fragmento = (
            _texto_seguro(
                resultado.get(
                    "fragmento"
                )
            )
        )

        candidates = (
            resultado.get(
                "candidates",
                [],
            )
            or []
        )

        for candidate in candidates:

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

            dni = _texto_seguro(
                candidate.get(
                    "dni_embargado"
                )
                or candidate.get(
                    "dni"
                )
            )

            cuit_cuil = _texto_seguro(
                candidate.get(
                    "cuit_cuil_embargado"
                )
                or candidate.get(
                    "cuil_cuit"
                )
            )

            rol = _texto_seguro(
                candidate.get(
                    "rol_embargado"
                )
            )

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

            contexto = (
                _extraer_contexto_local(
                    fragmento=fragmento,
                    nombre=nombre,
                    start=start,
                    end=end,
                )
            )

            evidencia = Evidencia(
                numero_archivo=numero_archivo,
                id_documento=id_documento,

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
                dni=dni,
                cuit_cuil=cuit_cuil,
                rol=rol,

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

                contexto_local=contexto,
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

    for existente in (
        grupo.evidencias
    ):
        if _evidencias_misma_persona(
            evidencia,
            existente,
        ):
            return True

    return False


def _agrupar_evidencias(
    evidencias: list[Evidencia],
) -> list[GrupoPersona]:

    grupos: list[
        GrupoPersona
    ] = []

    for evidencia in evidencias:

        grupo_encontrado = None

        for grupo in grupos:

            if _grupo_coincide(
                evidencia,
                grupo,
            ):
                grupo_encontrado = (
                    grupo
                )
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

        fragment_key = (
            evidencia.contador_interno
            or evidencia.fragmento
        )

        grupo_encontrado.fragmentos_soporte.add(
            fragment_key
        )

        grupo_encontrado.score_total += (
            _score_evidencia(
                evidencia
            )
        )

    return grupos


# ============================================================
# CONFLICTOS DE IDENTIFICADORES
# ============================================================

def _identificadores_grupo(
    grupo: GrupoPersona,
) -> dict[str, set[str]]:

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

    return {
        "dni": dnis,
        "cuit_cuil": cuits,
    }


def _detectar_conflictos_identificadores(
    grupos: list[GrupoPersona],
) -> list[dict[str, Any]]:
    """
    Detecta cuando dos grupos con nombres incompatibles
    comparten el mismo DNI o CUIT/CUIL.

    Esto suele indicar una asociacion erronea producida
    por el modelo en un fragmento con varias personas.
    """

    conflictos: list[
        dict[str, Any]
    ] = []

    vistos: set[
        tuple[
            str,
            str,
            str,
            str,
        ]
    ] = set()

    for index_a in range(
        len(grupos)
    ):

        grupo_a = grupos[
            index_a
        ]

        nombre_a = (
            _nombre_canonico(
                grupo_a
            )
        )

        ids_a = (
            _identificadores_grupo(
                grupo_a
            )
        )

        for index_b in range(
            index_a + 1,
            len(grupos),
        ):

            grupo_b = grupos[
                index_b
            ]

            nombre_b = (
                _nombre_canonico(
                    grupo_b
                )
            )

            if not _nombres_incompatibles(
                nombre_a,
                nombre_b,
            ):
                continue

            ids_b = (
                _identificadores_grupo(
                    grupo_b
                )
            )

            for tipo in (
                "dni",
                "cuit_cuil",
            ):

                compartidos = (
                    ids_a[tipo]
                    & ids_b[tipo]
                )

                for valor in (
                    compartidos
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
# NOMBRE CANONICO
# ============================================================

def _nombre_canonico(
    grupo: GrupoPersona,
) -> str:
    """
    Elige la variante mas completa disponible.

    Nunca inventa ni reconstruye un nombre.
    Siempre devuelve una variante realmente extraida.
    """

    mejores: list[
        tuple[
            int,
            float,
            str,
        ]
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

        confidence = (
            max(
                confidencias
            )
            if confidencias
            else 0.0
        )

        mejores.append(
            (
                tokens,
                confidence,
                variante,
            )
        )

    if not mejores:
        return ""

    mejores.sort(
        reverse=True
    )

    return mejores[0][2]


# ============================================================
# VALOR MAS FRECUENTE
# ============================================================

def _valor_mas_frecuente(
    values: list[str],
) -> str:

    values = [
        value
        for value in values
        if value
    ]

    if not values:
        return ""

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

        key = (
            _normalizar_identificador(
                value
            )
        )

        if not key:
            continue

        counts[key] += 1

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
# VALIDACION DE GRUPOS
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

    cantidad_tercero = sum(
        1
        for evidencia
        in grupo.evidencias
        if evidencia.tercero_fuerte
    )

    # Si la mayoria de sus evidencias proviene
    # de contextos claramente de terceros.
    return (
        cantidad_tercero
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
    """
    Decide si el grupo tiene evidencia suficiente.

    Cuando existen varios candidatos dentro del documento
    se aplica una regla mas estricta.
    """

    cantidad_fragmentos = len(
        grupo.fragmentos_soporte
    )

    tiene_id = (
        _grupo_tiene_identificador(
            grupo
        )
    )

    tiene_contexto = (
        _grupo_tiene_contexto_positivo(
            grupo
        )
    )

    negativo_fuerte = (
        _grupo_tiene_contexto_negativo_fuerte(
            grupo
        )
    )

    tercero_fuerte = (
        _grupo_tiene_tercero_fuerte(
            grupo
        )
    )

    # --------------------------------------------------------
    # Terceros claros
    # --------------------------------------------------------

    if tercero_fuerte:
        return False

    # --------------------------------------------------------
    # Contexto predominantemente negativo
    # --------------------------------------------------------

    if negativo_fuerte:
        return False

    # --------------------------------------------------------
    # Score minimo
    # --------------------------------------------------------

    if (
        grupo.score_total
        < MIN_SCORE_EMBARGADO
    ):
        return False

    # ========================================================
    # DOCUMENTO CON VARIOS CANDIDATOS
    # ========================================================

    if total_grupos > 1:

        # Contexto juridico positivo + identificador.
        if (
            tiene_contexto
            and tiene_id
        ):
            return True

        # Evidencia repetida.
        if (
            cantidad_fragmentos >= 2
            and tiene_id
            and grupo.score_total
            >= MIN_SCORE_MULTIPLE_SIN_CONTEXTO
        ):
            return True

        # Contexto positivo repetido, aunque falte ID.
        if (
            cantidad_fragmentos >= 2
            and tiene_contexto
            and grupo.score_total
            >= SCORE_EVIDENCIA_FUERTE
        ):
            return True

        return False

    # ========================================================
    # DOCUMENTO CON UN SOLO CANDIDATO
    # ========================================================

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

        "fragmento":
            evidencia.fragmento,

        "contexto_local":
            evidencia.contexto_local,
    }


def _serializar_grupo(
    grupo: GrupoPersona,
) -> dict[str, Any]:

    nombre = (
        _nombre_canonico(
            grupo
        )
    )

    dni = (
        _valor_mas_frecuente(
            [
                evidencia.dni
                for evidencia
                in grupo.evidencias
            ]
        )
    )

    cuit_cuil = (
        _valor_mas_frecuente(
            [
                evidencia.cuit_cuil
                for evidencia
                in grupo.evidencias
            ]
        )
    )

    return {
        "nombre_embargado":
            nombre,

        "dni_embargado":
            dni,

        "cuit_cuil_embargado":
            cuit_cuil,

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

        "evidencias": [
            _serializar_evidencia(
                evidencia
            )
            for evidencia
            in grupo.evidencias
        ],
    }


# ============================================================
# CONSOLIDACION DE DOCUMENTO
# ============================================================

def consolidar_documento(
    documento: dict[str, Any],
) -> dict[str, Any]:

    evidencias = (
        _extraer_evidencias_documento(
            documento
        )
    )

    grupos = (
        _agrupar_evidencias(
            evidencias
        )
    )

    # --------------------------------------------------------
    # Conflictos DNI/CUIT
    # --------------------------------------------------------

    conflictos = (
        _detectar_conflictos_identificadores(
            grupos
        )
    )

    # --------------------------------------------------------
    # Validar grupos
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Estado
    # --------------------------------------------------------

    if not personas_embargadas:

        estado = (
            ESTADO_NO_RESUELTO
        )

    elif len(
        personas_embargadas
    ) == 1:

        estado = (
            ESTADO_RESUELTO
        )

    else:

        estado = (
            ESTADO_RESUELTO_MULTIPLE
        )

    # --------------------------------------------------------
    # Descartados
    # --------------------------------------------------------

    grupos_descartados = [
        _serializar_grupo(
            grupo
        )
        for grupo in grupos
        if grupo not in grupos_validos
    ]

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

        "estado":
            estado,

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

        # ----------------------------------------------------
        # NUEVO
        # ----------------------------------------------------

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
# CONSOLIDACION COMPLETA
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
    }

    for resultado in resultados:

        estado = (
            resultado.get(
                "estado"
            )
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

    return resumen