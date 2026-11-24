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
# ROLES JURIDICOS
# ============================================================

# Roles que, cuando GLiNER los detecta, constituyen una señal
# semántica fuerte de que la persona puede ser sujeto de la
# medida de embargo.

ROLES_JURIDICOS_FUERTES = {
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

# Por ahora no hay roles de apoyo separados.
#
# "titular" pasa a considerarse rol fuerte porque en los oficios
# analizados aparece de forma recurrente en expresiones como
# "cuenta de titularidad de" o "fondos de titularidad de", donde
# identifica directamente al sujeto sobre cuyos fondos recae la
# medida.
#
# Se conserva el conjunto para mantener la estructura del
# diagnóstico y permitir agregar roles de apoyo en el futuro.

ROLES_JURIDICOS_APOYO: set[str] = set()

# Se mantiene este conjunto por compatibilidad con el score
# histórico. El score_total continúa exportándose como dato de
# diagnóstico, pero ya no será la señal principal de aceptación.

ROLES_POSITIVOS = (
    ROLES_JURIDICOS_FUERTES
    | ROLES_JURIDICOS_APOYO
)


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


EXPRESIONES_NOMBRE_GENERICO = {
    "dato",
    "datos",
    "persona",
    "personas",
    "nombre",
    "titular",
    "demandado",
    "demandada",
    "embargado",
    "embargada",
    "ejecutado",
    "ejecutada",
    "deudor",
    "deudora",
}



# ============================================================
# ESTRUCTURA VALIDA DE NOMBRE / RAZON SOCIAL
# ============================================================

# La validación se usa en la etapa de decisión de la consolidación,
# no durante la extracción de evidencias. De esta manera un candidato
# inválido sigue quedando visible en "grupos_descartados" para auditoría.

PATRONES_PERSONA_JURIDICA = (
    r"\bS\.?\s*A\.?\s*S\.?\b",                # S.A.S.
    r"\bS\.?\s*R\.?\s*L\.?\b",                # S.R.L.
    r"\bS\.?\s*A\.?\b",                       # S.A.
    r"\bS\.?\s*C\.?\s*S\.?\b",                # S.C.S.
    r"\bS\.?\s*C\.?\s*A\.?\b",                # S.C.A.
    r"\bS\.?\s*C\.?\b",                       # S.C.
    r"\bSOCIEDAD\s+ANONIMA\b",
    r"\bSOCIEDAD\s+DE\s+RESPONSABILIDAD\s+LIMITADA\b",
    r"\bSOCIEDAD\s+POR\s+ACCIONES\s+SIMPLIFICADA\b",
)


def _nombre_tiene_estructura_valida(
    nombre: Any,
) -> bool:
    """
    Valida que el candidato tenga estructura plausible de persona
    física o jurídica.

    Persona física:
        requiere al menos dos tokens alfabéticos útiles.

    Persona jurídica:
        acepta razones sociales reconocibles, por ejemplo:
        "OSCAR S.R.L." o "PLAN ROMBO S.A.".

    Esta regla evita aceptar términos aislados y genéricos como:
        "dato"
    aun cuando GLiNER les haya asignado un rol jurídico.
    """

    text = _texto_seguro(
        nombre
    )

    if not text:
        return False

    normalizado = _normalizar_texto(
        text
    )

    if not normalizado:
        return False

    if (
        normalizado.lower()
        in EXPRESIONES_NOMBRE_GENERICO
    ):
        return False

    # --------------------------------------------------------
    # PERSONA JURIDICA
    # --------------------------------------------------------

    if any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        is not None
        for pattern
        in PATRONES_PERSONA_JURIDICA
    ):
        # Debe existir al menos algún nombre antes/además de la
        # forma societaria. Evita aceptar solamente "S.A.".
        tokens_utiles = [
            token
            for token
            in _tokens_nombre(
                text
            )
            if len(token) >= 2
            and token not in {
                "SA",
                "SAS",
                "SRL",
                "SC",
                "SCS",
                "SCA",
                "SOCIEDAD",
                "ANONIMA",
                "RESPONSABILIDAD",
                "LIMITADA",
                "ACCIONES",
                "SIMPLIFICADA",
            }
        ]

        return bool(
            tokens_utiles
        )

    # --------------------------------------------------------
    # PERSONA FISICA
    # --------------------------------------------------------

    tokens = [
        token
        for token
        in _tokens_nombre(
            text
        )
        if re.search(
            r"[A-ZÁÉÍÓÚÜÑ]",
            token,
            flags=re.IGNORECASE,
        )
    ]

    # Para una persona física exigimos al menos dos componentes
    # (por ejemplo nombre + apellido, o apellido + nombre).
    if len(tokens) < 2:
        return False

    # Evita casos formados solamente por iniciales.
    tokens_contenido = [
        token
        for token
        in tokens
        if len(token) >= 2
    ]

    return len(
        tokens_contenido
    ) >= 2


# ============================================================
# CONTEXTO POSITIVO
# ============================================================

PATRONES_CONTEXTO_POSITIVO = (
    # Roles jurídicos explícitos cerca de la persona.
    r"\bembargado\b\s*:?\s*",
    r"\bembargada\b\s*:?\s*",
    r"\bdemandado\b",
    r"\bdemandada\b",
    r"\bejecutado\b",
    r"\bejecutada\b",
    r"\bdeudor\b",
    r"\bdeudora\b",
    r"\bparte\s+demandada\b",
    r"\bpartes\s+demandadas\b",

    # Fórmulas habituales que ordenan o describen el embargo.
    r"\bse\s+ha\s+decretado\s+el\s+embargo\b",
    r"\bse\s+ha\s+decretado\s+embargo\b",
    r"\bdecretad[oa]\s+el\s+embargo\b",
    r"\bdecr[eé]t(?:a|e)se\s+embargo\b",

    # Cumplimiento de una medida de embargo ya ordenada,
    # dispuesta o decretada. Esta familia cubre variantes
    # como "dar cumplimiento con el embargo ordenado",
    # "cumplimiento del embargo dispuesto" o
    # "cumplimiento al embargo decretado" sin depender
    # de una frase exacta del documento.
    r"\b(?:dar\s+)?cumplimiento\s+"
    r"(?:con\s+el|del|al)\s+embargo\s+"
    r"(?:ordenad[oa]|dispuest[oa]|decretad[oa])\b",

    r"\bembargo\s+sobre\b",
    r"\btr[aá]base\s+embargo\b",
    r"\btr[aá]bese\s+embargo\b",
    r"\bproceda\s+a\s+embargar\b",
    r"\bproceder\s+a\s+embargar\b",
    r"\bembargar\s+(?:las|los|sus)?\s*(?:cuentas|fondos|haberes|sumas)\b",

    # Embargo sobre dinero/cuentas a nombre de una persona.
    r"\bembargo\s+de\s+dinero\s+depositado\s+en\s+"
    r"cuenta(?:/s|s)?\s+a\s+nombre\s+de\b",

    r"\bembargo\s+(?:de|sobre)\s+"
    r"(?:dinero|fondos|sumas|cuentas?)\b",

    r"\b(?:dinero|fondos|sumas)\s+"
    r"(?:depositad[oa]s?|existentes?)\s+"
    r"en\s+cuenta(?:/s|s)?\s+a\s+nombre\s+de\b",

    # Frases frecuentes que vinculan fondos/cuentas con el sujeto
    # aun cuando la palabra "embargo" quedó fuera del fragmento.
    r"\b(?:fondos|sumas|cantidades|cuentas|haberes|saldos|activos|dinero|dep[oó]sitos)\b"
    r".{0,160}\b"
    r"(?:que\s+)?"
    r"(?:posea|posean|tenga|tengan|detente|detenten|perciba|perciban|"
    r"pertenezca|pertenezcan)\b",

    r"\b(?:cantidades|sumas|fondos)\s+"
    r"presentes\s+(?:y|o|y/o)\s+futuras\b",

    r"\bcuentas?\s+que\s+posea\b",
    r"\bfondos\s+que\s+posea\b",
    r"\bsumas\s+de\s+dinero\s+que\s+tenga\b",

    # Fragmentos truncados que pueden haber perdido la palabra
    # "cantidades" al inicio.
    r"\bpresentes\s+o\s+futuras\s+"
    r"que\s+(?:tenga|tengan)\s+depositad[oa]s?\b",

    # Fondos explícitamente asociados a demandados/embargados.
    r"\bfondos\s+que\s+"
    r"(?:el|la|los|las)?\s*"
    r"(?:demandad[oa]s?|embargad[oa]s?|ejecutad[oa]s?)\b",

    # Fondos ya retenidos de cuentas de titularidad de la persona.
    r"\bretenid[oa]s?\b.{0,120}"
    r"\bcuentas?\s+de\s+titularidad\b",

    # Vinculación de fondos/cuentas/sumas con "a nombre de".
    r"\b(?:fondos|cuentas?|sumas|cantidades)\b"
    r".{0,120}\ba\s+nombre\s+de\b",

    # Retenciones.
    r"\bretenci[oó]n\s+(?:directa\s+)?"
    r"(?:de|del|de\s+la|de\s+los|de\s+las|sobre)\b",

    r"\bretener\s+(?:el|la|los|las)?\s*"
    r"(?:haberes|fondos|sumas|porcentaje)\b",

    r"\bperciba\s+el\s+sr\b",
    r"\bperciba\s+la\s+sra\b",
)

# ============================================================
# CONTEXTO NEGATIVO
# ============================================================

PATRONES_CONTEXTO_NEGATIVO = (
    # Evitamos expresiones demasiado generales como
    # "depositar", "transferencia" o "a favor de", porque
    # también aparecen en el texto normal de un embargo y pueden
    # penalizar al verdadero embargado.

    r"\bcuenta\s+abierta\s+a\s+nombre\s+de\b",
    r"\bbeneficiari[oa]\b",
    r"\bdestinatari[oa]s?\b",
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
    r"\bfacultad[oa]s?\s+para\s+el\s+diligenciamiento\b",
    r"\bse\s+encuentran?\s+facultad[oa]s?\s+para\s+(?:el\s+)?diligenciamiento\b",
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

    # Trazabilidad del enriquecimiento deterministico.
    nombre_original_gliner: str = ""
    dni_original_gliner: str = ""
    cuit_cuil_original_gliner: str = ""
    nombre_recuperado: bool = False
    dni_recuperado: bool = False
    cuit_cuil_recuperado: bool = False
    metodos_recuperacion: list[str] = field(default_factory=list)
    etiqueta_identificador_original: str = ""
    recuperacion_bloqueada_motivo: str = ""

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
# RECUPERACION LOCAL DETERMINISTICA
# ============================================================

TOKENS_NO_APELLIDO_RECUPERABLE = {
    "SR", "SRA", "SRTA", "DR", "DRA",
    "DNI", "CUIT", "CUIL", "CBU", "CVU",
    "ACTOR", "ACTORA", "DEMANDADO", "DEMANDADA",
    "EMBARGADO", "EMBARGADA", "EJECUTADO", "EJECUTADA",
    "DEUDOR", "DEUDORA", "TITULAR", "PARTE",
    "DE", "DEL", "EL", "LA", "LOS", "LAS",
}

TOKENS_ADMINISTRATIVOS_NOMBRE = {
    "DNI", "CUIT", "CUIL", "CBU", "CVU",
    "NRO", "NUMERO", "DOCUMENTO",
}


def _posicion_nombre_texto(
    fragmento: str,
    nombre: str,
) -> tuple[int, int] | None:
    """Localiza literalmente un nombre dentro del fragmento."""
    if not fragmento or not nombre:
        return None
    match = re.search(
        re.escape(nombre),
        fragmento,
        flags=re.IGNORECASE,
    )
    return (match.start(), match.end()) if match else None


def _tipo_identificador_por_formato(valor: str) -> str:
    """Clasifica por estructura; no corrige formatos dudosos."""
    digitos = _normalizar_identificador(valor)
    if len(digitos) in (7, 8):
        return "dni"
    if len(digitos) == 11:
        return "cuit_cuil"
    return ""


def _normalizar_etiqueta_identificador(etiqueta: str) -> str:
    valor = _normalizar_texto(etiqueta).replace(" ", "")
    if valor == "DNI":
        return "dni"
    if valor in {"CUIT", "CUIL", "CUITCUIL", "CUILCUIT"}:
        return "cuit_cuil"
    if valor in {"DNICUIT", "CUITDNI", "DNICUIL", "CUILDNI"}:
        return "mixto"
    return ""


def _tipo_identificador_compatible(etiqueta: str, valor: str) -> str:
    """Devuelve dni/cuit_cuil solo si etiqueta y estructura son coherentes."""
    tipo_formato = _tipo_identificador_por_formato(valor)
    tipo_etiqueta = _normalizar_etiqueta_identificador(etiqueta)
    if not tipo_formato or not tipo_etiqueta:
        return ""
    if tipo_etiqueta == "mixto":
        return tipo_formato
    if tipo_etiqueta == tipo_formato:
        return tipo_formato
    return ""


def _patron_identificador_local() -> re.Pattern[str]:
    return re.compile(
        r"\s*(?:[,;:()\-–—]\s*)*"
        r"(?P<etiqueta>"
        r"D\.?\s*N\.?\s*I\.?(?:\s*/\s*(?:C\.?\s*U\.?\s*I\.?\s*T\.?|C\.?\s*U\.?\s*I\.?\s*L\.?))?"
        r"|C\.?\s*U\.?\s*I\.?\s*T\.?(?:\s*/\s*D\.?\s*N\.?\s*I\.?)?"
        r"|C\.?\s*U\.?\s*I\.?\s*L\.?(?:\s*/\s*D\.?\s*N\.?\s*I\.?)?"
        r")"
        r"\s*(?:N[°ºo.]*(?:ro\.?)?|n[uú]mero)?\s*[:#°º.\-]*\s*"
        r"(?P<valor>[0-9][0-9.\- ]{5,18}[0-9])(?!\d)",
        re.IGNORECASE,
    )


def _identificador_local_despues_nombre(
    fragmento: str,
    nombre: str,
    max_chars: int = 70,
) -> dict[str, str] | None:
    """Busca un identificador inmediatamente asociado al nombre."""
    posicion = _posicion_nombre_texto(fragmento, nombre)
    if not posicion:
        return None
    _, fin = posicion
    tramo = fragmento[fin:fin + max_chars]
    match = _patron_identificador_local().match(tramo)
    if not match:
        return None
    etiqueta = match.group("etiqueta")
    valor = match.group("valor").strip()
    return {
        "etiqueta": etiqueta,
        "valor": valor,
        "tipo": _tipo_identificador_compatible(etiqueta, valor),
    }


def _recuperar_apellido_antes_nombre(fragmento: str, nombre: str) -> str | None:
    """Amplia NOMBRE a APELLIDO, NOMBRE solo con evidencia local literal."""
    if not fragmento or not nombre:
        return None
    patron = re.compile(
        r"(?<![\w])(?P<apellido>[A-ZÁÉÍÓÚÜÑ]{2,})\s*,\s*"
        r"(?P<nombre>" + re.escape(nombre) + r")",
        re.IGNORECASE,
    )
    hallazgos: list[str] = []
    for match in patron.finditer(fragmento):
        apellido = match.group("apellido")
        if apellido != apellido.upper():
            continue
        if _normalizar_texto(apellido) in TOKENS_NO_APELLIDO_RECUPERABLE:
            continue
        nombre_completo = fragmento[match.start("apellido"):match.end("nombre")]
        if not _identificador_local_despues_nombre(fragmento, nombre_completo):
            continue
        hallazgos.append(nombre_completo)
    unicos = list(dict.fromkeys(hallazgos))
    return unicos[0] if len(unicos) == 1 else None


def _recuperar_token_antes_nombre_sin_coma(fragmento: str, nombre: str) -> str | None:
    """Recuperacion mas estricta para APELLIDO NOMBRE sin coma."""
    if not fragmento or not nombre:
        return None
    patron = re.compile(
        r"(?<![\w])(?P<prefijo>[A-ZÁÉÍÓÚÜÑ]{2,})\s+"
        r"(?P<nombre>" + re.escape(nombre) + r")",
        re.IGNORECASE,
    )
    hallazgos: list[str] = []
    for match in patron.finditer(fragmento):
        prefijo = match.group("prefijo")
        if prefijo != prefijo.upper():
            continue
        if _normalizar_texto(prefijo) in TOKENS_NO_APELLIDO_RECUPERABLE:
            continue
        nombre_completo = fragmento[match.start("prefijo"):match.end("nombre")]
        if not _identificador_local_despues_nombre(fragmento, nombre_completo):
            continue
        hallazgos.append(nombre_completo)
    unicos = list(dict.fromkeys(hallazgos))
    return unicos[0] if len(unicos) == 1 else None


def _recuperar_identificador_local(
    fragmento: str,
    nombre: str,
    dni_actual: str,
    cuit_actual: str,
) -> dict[str, Any]:
    """Enriquece un candidato existente; nunca crea una identidad desde cero."""
    salida: dict[str, Any] = {
        "dni": dni_actual,
        "cuit_cuil": cuit_actual,
        "dni_recuperado": False,
        "cuit_cuil_recuperado": False,
        "etiqueta": "",
        "metodo": "",
        "bloqueada": "",
    }
    encontrado = _identificador_local_despues_nombre(fragmento, nombre)
    if not encontrado:
        return salida
    salida["etiqueta"] = encontrado["etiqueta"]
    valor = encontrado["valor"]
    tipo = encontrado["tipo"]
    if not tipo:
        salida["bloqueada"] = "etiqueta_identificador_incompatible"
        return salida
    if tipo == "dni" and not dni_actual:
        salida["dni"] = valor
        salida["dni_recuperado"] = True
        salida["metodo"] = "dni_local_adyacente"
    elif tipo == "cuit_cuil" and not cuit_actual:
        salida["cuit_cuil"] = valor
        salida["cuit_cuil_recuperado"] = True
        salida["metodo"] = "cuit_cuil_local_adyacente"
    return salida


def _identificador_cerca_nombre(evidencia: Evidencia) -> bool:
    """Comprueba asociacion local; no reescribe identificadores."""
    encontrado = _identificador_local_despues_nombre(
        evidencia.fragmento,
        evidencia.nombre,
    )
    if not encontrado or not encontrado["tipo"]:
        return False
    valor = _normalizar_identificador(encontrado["valor"])
    if encontrado["tipo"] == "dni":
        return bool(evidencia.dni) and valor == _normalizar_identificador(evidencia.dni)
    if encontrado["tipo"] == "cuit_cuil":
        return bool(evidencia.cuit_cuil) and valor == _normalizar_identificador(evidencia.cuit_cuil)
    return False


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

    for resultado in (documento.get("resultados", []) or []):
        fragmento = _texto_seguro(resultado.get("fragmento"))

        for candidate in (resultado.get("candidates", []) or []):
            # Ancla obligatoria de GLiNER: nunca se crea una persona desde regex.
            nombre_original = _texto_seguro(
                candidate.get("nombre_embargado")
                or candidate.get("nombre")
            )

            if not _nombre_es_util(nombre_original):
                continue

            dni_original = _texto_seguro(
                candidate.get("dni_embargado")
                or candidate.get("dni")
            )
            cuit_original = _texto_seguro(
                candidate.get("cuit_cuil_embargado")
                or candidate.get("cuil_cuit")
            )

            nombre = nombre_original
            nombre_recuperado = False
            metodos_recuperacion: list[str] = []

            # No ampliar candidatos de un solo token. Esos casos son
            # demasiado ambiguos y ya tienen tratamiento de suficiencia.
            if len(_tokens_nombre(nombre_original)) >= 2:
                nombre_con_apellido = _recuperar_apellido_antes_nombre(
                    fragmento,
                    nombre,
                )
                if nombre_con_apellido:
                    nombre = nombre_con_apellido
                    nombre_recuperado = True
                    metodos_recuperacion.append("apellido_antes_nombre")
                else:
                    nombre_sin_coma = _recuperar_token_antes_nombre_sin_coma(
                        fragmento,
                        nombre,
                    )
                    if nombre_sin_coma:
                        nombre = nombre_sin_coma
                        nombre_recuperado = True
                        metodos_recuperacion.append(
                            "token_anterior_literal_con_identificador"
                        )

            recuperacion_id = _recuperar_identificador_local(
                fragmento=fragmento,
                nombre=nombre,
                dni_actual=dni_original,
                cuit_actual=cuit_original,
            )

            # Para no fortalecer candidatos historicos que ya eran estables,
            # la recuperacion de un identificador omitido se activa cuando:
            #   a) el nombre tambien fue completado localmente, o
            #   b) la etiqueta textual es mixta (DNI/CUIT, CUIT/DNI, etc.).
            etiqueta_recuperada = _texto_seguro(recuperacion_id["etiqueta"])
            etiqueta_mixta = (
                _normalizar_etiqueta_identificador(etiqueta_recuperada)
                == "mixto"
            )
            permitir_recuperacion_id = (
                nombre_recuperado
                or etiqueta_mixta
            )

            if not permitir_recuperacion_id:
                recuperacion_id["dni"] = dni_original
                recuperacion_id["cuit_cuil"] = cuit_original
                recuperacion_id["dni_recuperado"] = False
                recuperacion_id["cuit_cuil_recuperado"] = False
                recuperacion_id["metodo"] = ""

            dni = _texto_seguro(recuperacion_id["dni"])
            cuit_cuil = _texto_seguro(recuperacion_id["cuit_cuil"])
            if recuperacion_id["metodo"]:
                metodos_recuperacion.append(recuperacion_id["metodo"])

            # Si se amplio el nombre, los spans originales de GLiNER ya no
            # representan la entidad completa y se recalculan por busqueda local.
            start = None
            end = None
            if not nombre_recuperado:
                start = candidate.get("nombre_embargado_span_inicio")
                if start is None:
                    start = candidate.get("nombre_span_inicio")
                end = candidate.get("nombre_embargado_span_fin")
                if end is None:
                    end = candidate.get("nombre_span_fin")

            evidencia = Evidencia(
                numero_archivo=_texto_seguro(documento.get("numero_archivo")),
                id_documento=_texto_seguro(documento.get("id")),
                contador_interno=_texto_seguro(resultado.get("contador_interno")),
                palabra_clave=_texto_seguro(resultado.get("palabra_clave")),
                categoria=_texto_seguro(resultado.get("categoria")),
                fragmento=fragmento,
                nombre=nombre,
                dni=dni,
                cuit_cuil=cuit_cuil,
                rol=_texto_seguro(candidate.get("rol_embargado")),

                nombre_original_gliner=(nombre_original if nombre_recuperado else ""),
                dni_original_gliner=(dni_original if recuperacion_id["dni_recuperado"] else ""),
                cuit_cuil_original_gliner=(cuit_original if recuperacion_id["cuit_cuil_recuperado"] else ""),
                nombre_recuperado=nombre_recuperado,
                dni_recuperado=bool(recuperacion_id["dni_recuperado"]),
                cuit_cuil_recuperado=bool(recuperacion_id["cuit_cuil_recuperado"]),
                metodos_recuperacion=metodos_recuperacion,
                etiqueta_identificador_original=_texto_seguro(recuperacion_id["etiqueta"]),
                recuperacion_bloqueada_motivo=_texto_seguro(recuperacion_id["bloqueada"]),

                nombre_confidence=(
                    candidate.get("nombre_embargado_confidence")
                    or candidate.get("nombre_confidence")
                ),
                dni_confidence=(
                    candidate.get("dni_embargado_confidence")
                    or candidate.get("dni_confidence")
                ),
                cuit_cuil_confidence=(
                    candidate.get("cuit_cuil_embargado_confidence")
                    or candidate.get("cuil_cuit_confidence")
                ),
                rol_confidence=candidate.get("rol_embargado_confidence"),
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

            evidencias.append(evidencia)

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

def _grupos_coinciden(
    grupo_a: GrupoPersona,
    grupo_b: GrupoPersona,
) -> bool:
    """
    Dos grupos representan potencialmente a la misma persona
    cuando al menos una evidencia de un grupo es compatible
    con alguna evidencia del otro.

    Reutiliza exactamente la misma lógica existente de
    _evidencias_misma_persona(), por lo que NO fusiona
    automáticamente solo por compartir DNI/CUIT.
    """

    return any(
        _evidencias_misma_persona(
            evidencia_a,
            evidencia_b,
        )
        for evidencia_a
        in grupo_a.evidencias
        for evidencia_b
        in grupo_b.evidencias
    )


def _fusionar_grupos(
    grupo_destino: GrupoPersona,
    grupo_origen: GrupoPersona,
) -> None:
    """
    Fusiona toda la información de grupo_origen dentro
    de grupo_destino.
    """

    grupo_destino.evidencias.extend(
        grupo_origen.evidencias
    )

    grupo_destino.variantes_nombre.update(
        grupo_origen.variantes_nombre
    )

    grupo_destino.dni_encontrados.update(
        grupo_origen.dni_encontrados
    )

    grupo_destino.cuit_cuil_encontrados.update(
        grupo_origen.cuit_cuil_encontrados
    )

    grupo_destino.roles_encontrados.update(
        grupo_origen.roles_encontrados
    )

    grupo_destino.fragmentos_soporte.update(
        grupo_origen.fragmentos_soporte
    )

    grupo_destino.score_total += (
        grupo_origen.score_total
    )

def _agrupar_evidencias(
    evidencias: list[Evidencia],
) -> list[GrupoPersona]:

    grupos: list[GrupoPersona] = []

    # ========================================================
    # PRIMERA PASADA
    #
    # Mantiene exactamente la lógica actual:
    # cada evidencia entra en el primer grupo compatible.
    # ========================================================

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

    # ========================================================
    # SEGUNDA PASADA
    #
    # Fusion transitiva.
    #
    # Ejemplo:
    #
    #   Grupo A: Sr. GOMEZ
    #   Grupo B: CLAUDIO LEONARDO
    #
    # Si Grupo A contiene tambien:
    #
    #   Sr. GOMEZ, CLAUDIO LEONARDO
    #
    # entonces A y B deben terminar siendo un solo grupo.
    #
    # Se repite hasta que ya no existan grupos fusionables.
    # ========================================================

    hubo_fusion = True

    while hubo_fusion:

        hubo_fusion = False

        for indice_a in range(
            len(grupos)
        ):

            if hubo_fusion:
                break

            for indice_b in range(
                indice_a + 1,
                len(grupos),
            ):

                grupo_a = grupos[
                    indice_a
                ]

                grupo_b = grupos[
                    indice_b
                ]

                if not _grupos_coinciden(
                    grupo_a,
                    grupo_b,
                ):
                    continue

                _fusionar_grupos(
                    grupo_a,
                    grupo_b,
                )

                del grupos[
                    indice_b
                ]

                hubo_fusion = True
                break

    return grupos


# ============================================================
# NOMBRE CANONICO
# ============================================================

def _nombre_canonico(
    grupo: GrupoPersona,
) -> str:
    """Prioriza variantes completas pero penaliza ruido administrativo."""
    mejores: list[tuple[int, int, float, str]] = []

    for variante in grupo.variantes_nombre:
        tokens_lista = _tokens_nombre(variante)
        tokens_admin = sum(
            1
            for token in tokens_lista
            if token in TOKENS_ADMINISTRATIVOS_NOMBRE
        )
        tokens_limpios = len(tokens_lista) - tokens_admin

        confidencias = [
            evidencia.nombre_confidence
            for evidencia in grupo.evidencias
            if (
                evidencia.nombre == variante
                and isinstance(evidencia.nombre_confidence, (int, float))
            )
        ]

        mejores.append(
            (
                tokens_limpios,
                -tokens_admin,
                max(confidencias) if confidencias else 0.0,
                variante,
            )
        )

    if not mejores:
        return ""

    mejores.sort(reverse=True)
    return mejores[0][3]


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


def _roles_normalizados_grupo(
    grupo: GrupoPersona,
) -> set[str]:
    """Devuelve los roles GLiNER normalizados del grupo."""

    return {
        _normalizar_texto(rol).lower()
        for rol in grupo.roles_encontrados
        if _normalizar_texto(rol)
    }


def _grupo_tiene_rol_juridico_fuerte(
    grupo: GrupoPersona,
) -> bool:
    """
    Señal semántica fuerte de GLiNER: embargado, demandado,
    ejecutado, deudor o titular (incluyendo variantes de género).
    """

    return bool(
        _roles_normalizados_grupo(grupo)
        & ROLES_JURIDICOS_FUERTES
    )


def _grupo_tiene_rol_juridico_apoyo(
    grupo: GrupoPersona,
) -> bool:
    """Roles de apoyo configurados, si existieran."""

    return bool(
        _roles_normalizados_grupo(grupo)
        & ROLES_JURIDICOS_APOYO
    )


def _grupo_tiene_repeticion(
    grupo: GrupoPersona,
) -> bool:
    """La misma persona aparece en dos o más fragmentos."""

    return len(grupo.fragmentos_soporte) >= 2


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


def _evaluar_grupo_embargado(
    grupo: GrupoPersona,
    total_grupos: int,
) -> tuple[
    bool,
    list[str],
    dict[str, Any],
]:
    """
    Evalua un grupo utilizando señales separadas y explicables.

    Señales principales:

    1. rol_juridico_fuerte:
       GLiNER devolvio embargado/demandado/ejecutado/deudor/titular.

    2. identificador:
       existe DNI o CUIT/CUIL consolidado.

    3. contexto_juridico:
       el texto cercano contiene una formula que vincula a la
       persona con la medida de embargo.

    4. repeticion:
       la misma persona aparece en dos o mas fragmentos.

    IMPORTANTE:

    - La repeticion funciona como refuerzo.
    - rol fuerte + identificador, por si solos, NO alcanzan
      cuando falta tanto contexto juridico como repeticion.
    - score_total se conserva como dato de diagnostico,
      pero no gobierna por si solo la decision.
    """

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

    tiene_rol_fuerte = (
        _grupo_tiene_rol_juridico_fuerte(
            grupo
        )
    )

    tiene_rol_apoyo = (
        _grupo_tiene_rol_juridico_apoyo(
            grupo
        )
    )

    tiene_repeticion = (
        _grupo_tiene_repeticion(
            grupo
        )
    )

    tercero_fuerte = (
        _grupo_tiene_tercero_fuerte(
            grupo
        )
    )

    contexto_negativo_fuerte = (
        _grupo_tiene_contexto_negativo_fuerte(
            grupo
        )
    )

    identidad_inconsistente = (
        _grupo_tiene_identidad_inconsistente(
            grupo
        )
    )

    nombre_canonico = _nombre_canonico(
        grupo
    )

    nombre_estructura_valida = (
        _nombre_tiene_estructura_valida(
            nombre_canonico
        )
    )

    roles_normalizados = sorted(
        _roles_normalizados_grupo(
            grupo
        )
    )

    roles_fuertes_detectados = sorted(
        set(roles_normalizados)
        & ROLES_JURIDICOS_FUERTES
    )

    roles_apoyo_detectados = sorted(
        set(roles_normalizados)
        & ROLES_JURIDICOS_APOYO
    )

    senales = {
        "rol_juridico_fuerte":
            tiene_rol_fuerte,

        "roles_fuertes_detectados":
            roles_fuertes_detectados,

        "rol_juridico_apoyo":
            tiene_rol_apoyo,

        "roles_apoyo_detectados":
            roles_apoyo_detectados,

        "tiene_identificador":
            tiene_id,

        "contexto_juridico_positivo":
            tiene_contexto,

        "repeticion":
            tiene_repeticion,

        "cantidad_fragmentos":
            cantidad_fragmentos,
    }

    detalle = {
        "score_total":
            round(
                grupo.score_total,
                3,
            ),

        "total_grupos_documento":
            total_grupos,

        "senales_consolidacion":
            senales,

        "tercero_fuerte":
            tercero_fuerte,

        "contexto_negativo_fuerte":
            contexto_negativo_fuerte,

        "identidad_inconsistente":
            identidad_inconsistente,

        "nombre_estructura_valida":
            nombre_estructura_valida,
    }

    # ========================================================
    # DESCARTES FUERTES
    # ========================================================

    # Un nombre que no tiene estructura plausible de persona
    # física ni de razón social nunca debe resolverse como
    # embargado, aunque tenga rol o contexto positivo.
    if not nombre_estructura_valida:
        return (
            False,
            [
                "nombre_no_valido"
            ],
            detalle,
        )

    if tercero_fuerte:
        return (
            False,
            [
                "tercero_fuerte"
            ],
            detalle,
        )

    if identidad_inconsistente:
        return (
            False,
            [
                "identidad_inconsistente"
            ],
            detalle,
        )

    if contexto_negativo_fuerte:
        return (
            False,
            [
                "contexto_negativo_fuerte"
            ],
            detalle,
        )

    # ========================================================
    # REGLAS POSITIVAS
    # ========================================================

    # Contexto juridico + rol juridico fuerte.
    if (
        tiene_contexto
        and tiene_rol_fuerte
    ):
        motivos = [
            "contexto_juridico",
            "rol_juridico_fuerte",
        ]

        if tiene_id:
            motivos.append(
                "identificador"
            )

        if tiene_repeticion:
            motivos.append(
                "repeticion"
            )

        return (
            True,
            motivos,
            detalle,
        )

    # Contexto juridico + identificador.
    if (
        tiene_contexto
        and tiene_id
    ):
        motivos = [
            "contexto_juridico",
            "identificador",
        ]

        if tiene_repeticion:
            motivos.append(
                "repeticion"
            )

        return (
            True,
            motivos,
            detalle,
        )

    # Rol fuerte + identificador solamente se acepta si existe
    # repeticion. Esto evita aceptar una unica mencion aislada
    # cuando GLiNER asigno un rol incorrecto.
    if (
        tiene_rol_fuerte
        and tiene_id
        and tiene_repeticion
    ):
        return (
            True,
            [
                "rol_juridico_fuerte",
                "identificador",
                "repeticion",
            ],
            detalle,
        )

    # ========================================================
    # INSUFICIENTE
    # ========================================================

    motivos = [
        "senales_insuficientes"
    ]

    if not tiene_rol_fuerte:
        motivos.append(
            "sin_rol_juridico_fuerte"
        )

    if not tiene_id:
        motivos.append(
            "sin_identificador"
        )

    if not tiene_contexto:
        motivos.append(
            "sin_contexto_juridico"
        )

    if not tiene_repeticion:
        motivos.append(
            "sin_repeticion"
        )

    return (
        False,
        motivos,
        detalle,
    )


def _grupo_es_embargado(
    grupo: GrupoPersona,
    total_grupos: int,
) -> bool:
    """
    Mantiene la interfaz anterior.

    La decision real se realiza en
    _evaluar_grupo_embargado(), que ahora tambien
    genera informacion de diagnostico.
    """

    aceptado, _, _ = (
        _evaluar_grupo_embargado(
            grupo,
            total_grupos,
        )
    )

    return aceptado


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

        "nombre_original_gliner":
            evidencia.nombre_original_gliner,

        "dni_detectado":
            evidencia.dni,

        "dni_original_gliner":
            evidencia.dni_original_gliner,

        "cuit_cuil_detectado":
            evidencia.cuit_cuil,

        "cuit_cuil_original_gliner":
            evidencia.cuit_cuil_original_gliner,

        "rol_detectado":
            evidencia.rol,

        "nombre_recuperado":
            evidencia.nombre_recuperado,

        "dni_recuperado":
            evidencia.dni_recuperado,

        "cuit_cuil_recuperado":
            evidencia.cuit_cuil_recuperado,

        "metodos_recuperacion":
            list(evidencia.metodos_recuperacion),

        "etiqueta_identificador_original":
            evidencia.etiqueta_identificador_original,

        "recuperacion_bloqueada_motivo":
            evidencia.recuperacion_bloqueada_motivo,

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
# REVISION MANUAL EXPLICABLE
# ============================================================

def _generar_revision_manual(
    conflictos_identificador: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, str]], str]:
    """Agrega notas sin cambiar la semantica historica de revision."""
    motivos: list[dict[str, str]] = []

    if conflictos_identificador:
        motivos.append({
            "codigo": "conflicto_identificador",
            "descripcion": (
                "Se detectaron identidades incompatibles que comparten "
                "un DNI o CUIT/CUIL. Revisar las asociaciones antes de "
                "utilizar el resultado."
            ),
        })

    requiere = bool(motivos)
    descripcion = " ".join(
        motivo["descripcion"]
        for motivo in motivos
    )
    return requiere, motivos, descripcion


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

    # --------------------------------------------------------
    # EVALUACION + DIAGNOSTICO DE CADA GRUPO
    #
    # IMPORTANTE:
    # no cambia las reglas de aceptacion actuales.
    # Solo conserva el motivo por el que cada grupo fue
    # aceptado o descartado.
    # --------------------------------------------------------

    evaluaciones_grupos: list[
        dict[str, Any]
    ] = []

    for grupo in grupos:

        (
            aceptado,
            motivos_decision,
            detalle_decision,
        ) = _evaluar_grupo_embargado(
            grupo,
            total_grupos=len(
                grupos
            ),
        )

        evaluaciones_grupos.append(
            {
                "grupo":
                    grupo,

                "aceptado":
                    aceptado,

                "motivos":
                    motivos_decision,

                "detalle":
                    detalle_decision,
            }
        )

    evaluaciones_validas = [
        evaluacion
        for evaluacion
        in evaluaciones_grupos
        if evaluacion[
            "aceptado"
        ]
    ]

    # Se conserva el mismo orden anterior para los grupos
    # aceptados: score y cantidad de fragmentos, descendente.
    evaluaciones_validas.sort(
        key=lambda evaluacion: (
            evaluacion[
                "grupo"
            ].score_total,
            len(
                evaluacion[
                    "grupo"
                ].fragmentos_soporte
            ),
        ),
        reverse=True,
    )

    personas_embargadas: list[
        dict[str, Any]
    ] = []

    for evaluacion in evaluaciones_validas:

        persona = _serializar_grupo(
            evaluacion[
                "grupo"
            ]
        )

        persona[
            "decision_consolidacion"
        ] = {
            "aceptado":
                True,

            "motivos":
                evaluacion[
                    "motivos"
                ],

            "detalle":
                evaluacion[
                    "detalle"
                ],
        }

        personas_embargadas.append(
            persona
        )

    if not personas_embargadas:
        estado = ESTADO_NO_RESUELTO

    elif len(
        personas_embargadas
    ) == 1:
        estado = ESTADO_RESUELTO

    else:
        estado = ESTADO_RESUELTO_MULTIPLE

    grupos_descartados: list[
        dict[str, Any]
    ] = []

    for evaluacion in evaluaciones_grupos:

        if evaluacion[
            "aceptado"
        ]:
            continue

        grupo_descartado = (
            _serializar_grupo(
                evaluacion[
                    "grupo"
                ]
            )
        )

        grupo_descartado[
            "decision_consolidacion"
        ] = {
            "aceptado":
                False,

            "motivos":
                evaluacion[
                    "motivos"
                ],

            "detalle":
                evaluacion[
                    "detalle"
                ],
        }

        grupos_descartados.append(
            grupo_descartado
        )

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

    (
        requiere_revision,
        revision_manual_motivos,
        revision_manual_descripcion,
    ) = _generar_revision_manual(
        conflictos
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
        # SUFICIENCIA
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
            requiere_revision,

        "revision_manual_motivos":
            revision_manual_motivos,

        "revision_manual_descripcion":
            revision_manual_descripcion,

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