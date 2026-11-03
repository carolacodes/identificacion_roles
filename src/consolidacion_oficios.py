"""
Consolidacion de personas objeto de oficios a nivel documento.

Esta etapa recibe predicciones realizadas sobre FRAGMENTOS.

Responsabilidades:

1. Agrupar variantes de una misma persona consultada.
2. Consolidar nombre, DNI, CUIT/CUIL y roles.
3. Detectar terceros evidentes.
4. Detectar conflictos de identificadores.
5. Admitir multiples sujetos consultados.
6. Evaluar si el resultado posee evidencia suficiente.
7. Conservar trazabilidad completa para etapas posteriores.

IMPORTANTE:

- texto_completo se conserva, pero NO se utiliza en esta etapa.
- La categoria Datos_Embargado es SOLO un filtro de fragmentos; no indica
  que el sujeto del oficio sea un embargado.
- El estado de suficiencia mide necesidad de fallback, no exactitud.
- El archivo espera el JSON predicciones_por_documento de oficios con claves
  nombre_persona, dni_persona, cuit_cuil_persona, rol_persona.
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

MIN_SCORE_PERSONA = 6.0
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

MAX_PERSONAS_SIN_REVISION = 50

# Un candidato de una sola evidencia debe superar este score
# para considerarse fuerte.
MIN_SCORE_EVIDENCIA_UNICA = 8.0


# ============================================================
# ROLES JURIDICOS
# Una condicion procesal NO prueba por si sola que una persona sea objeto
# del pedido. La aceptacion tambien exige evidencia del requerimiento.
# Incluye personas que NO son demandadas ni consultadas.
ROLES_JURIDICOS_FUERTES = {
    "actor", "actora", "demandado", "demandada", "embargado", "embargada",
    "ejecutado", "ejecutada", "deudor", "deudora", "titular", "causante",
    "beneficiario", "beneficiaria", "tercero", "tercera", "otro", "contribuyente",
}
ROLES_JURIDICOS_APOYO: set[str] = set()
ROLES_POSITIVOS = ROLES_JURIDICOS_FUERTES | ROLES_JURIDICOS_APOYO

# ============================================================


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
    "parte actora",
    "la actora",
    "el actor",
    "personal policial",
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
    "actor", "actora", "causante", "beneficiario", "beneficiaria",
    "persona consultada", "objeto del oficio",
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
# Frases que vinculan a una persona con el objeto del oficio,
# no meras menciones en caratula o firmas.
PATRONES_CONTEXTO_POSITIVO = (
    r"\ba\s+fin\s+de\s+(?:que\s+)?(?:informe|informar|solicitar)",
    r"\b(?:solicito|solicita|solicitarle|sirva)\b.{0,110}\binform",
    r"\b(?:informe|informar|informen)\b.{0,110}\b(?:si|sobre|respecto|acerca)",
    r"\b(?:posee|posea|posean)\s+(?:cuenta|cuentas|billetera|billeteras|fondos)",
    r"\b(?:cuenta|cuentas|fondos|saldos|movimientos|transferencias)\b.{0,100}\b(?:a\s+nombre\s+de|titular|respecto\s+de|de\s+la|del)",
    r"\b(?:titular\s+del?\s+(?:dni|cuil|cuit|cvu|cuenta)|correspondiente\s+al\s+cuil)",
    r"\b(?:fondos\s+depositados\s+a\s+favor\s+del?\s+causante)",
    r"\b(?:transferencias\s+percibidas\s+por|le\s+ha\s+transferido|le\s+transfirio)",
    r"\b(?:respecto\s+del?\s+(?:actor|actora|peticionante)|sobre\s+la\s+cuenta)",
    r"\bpersonal\s+policial\s+a\s+verificar\b",
    r"\b(?:personas|efectivos|usuarios|titulares)\s+a\s+verificar\b",
    r"\b(?:embargo\s+trabado|embargo\s+sobre|se\s+ha\s+decretado\s+el\s+embargo)",
)
# 'beneficiario', 'transferencia', 'a favor de' y 'titular'
# NO son negativos globales: pueden ser sujetos reales del pedido.
PATRONES_CONTEXTO_NEGATIVO: tuple[str, ...] = ()

# ============================================================
# TERCEROS
# ============================================================
PATRONES_LISTA_TERCEROS = (
    r"\bautorizad[oa]s?\s+para\s+diligenciar\b",
    r"\bautorizad[oa]s?\s+al\s+diligenciamiento\b",
    r"\bse\s+encuentran?\s+autorizad[oa]s?\b",
    r"\bquedan?\s+autorizad[oa]s?\b",
    r"\bse\s+autoriza\s+a\b",
    r"\bpersonas?\s+autorizad[oa]s?\b",
    r"\bprofesionales?\s+autorizad[oa]s?\b",
    r"\bletrad[oa]s?\s+autorizad[oa]s?\b",
    r"\babogad[oa]s?\s+autorizad[oa]s?\b",
    r"\bfacultad[oa]s?\s+para\s+diligenciar\b",
)
PATRONES_TERCERO_INDIVIDUAL = (
    r"\bfirmado\s+(?:y\s+notificado\s+)?por\b",
    r"\bjuez(?:a)?\b", r"\bsecretari[oa]\b", r"\bauxiliar\s+letrado\b",
)
# Cautela: 'abogada' NO significa tercero (archivo 10: abogada consultada).
PATRONES_ROL_CERCANO_POSITIVO = (
    r"\b(?:actor|actora|demandado|demandada|embargado|embargada|causante|titular)\b",
    r"\b(?:informe|informar|posee|posea|movimientos|cuenta)\b",
    r"\ba\s+nombre\s+de\b",
)

# ============================================================


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
    nombre_original_gliner: str = ""
    origen_recuperacion_lista: str = ""
    origen_recuperacion_v12: str = ""
    dni: str = ""
    dni_original_ocr: str = ""
    dni_original_gliner_lista: str = ""
    motivo_correccion_lista: str = ""
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



# ------------------------------------------------------------
# Evidencia vinculante: se comprueba cerca del nombre, no por una
# frase positiva que casualmente aparezca en otro punto del fragmento.
# ------------------------------------------------------------
PATRONES_PEDIDO_EXPLICITO = (
    r"\b(?:informe|informar|informen|informen\s+sobre|identifique|verificar|detalle|acreditaciones|compras|transferencias|movimientos)\b",
    r"\b(?:cuentas?|billeteras?|fondos|saldos|cvu|cuit|cuil|dni|alimentante|demandad[oa]|actor[ao]|empleado)\b",
)
PATRONES_ENCABEZADO_LISTA = (
    r"\bPERSONAL\s+(?:POLICIAL\s+A\s+VERIFICAR|SUJETO\s+A\s+RELEVAMIENTO)\s*:",
    r"\b(?:PERSONAS|EFECTIVOS|USUARIOS|TITULARES)\s+A\s+(?:VERIFICAR|RELEVAR|CONSULTAR)\s*:",
)


def _posicion_nombre_texto(fragmento: str, nombre: str) -> tuple[int, int] | None:
    match = re.search(re.escape(nombre), fragmento, re.I)
    return (match.start(), match.end()) if match else None


def _identificador_cerca_nombre(evidencia: Evidencia) -> bool:
    """Comprueba identificadores de la misma cláusula, sin reescribirlos.

    Si la posición no permite verificar un identificador, devuelve False;
    la ausencia de verificación NO constituye por sí sola prueba de error.
    """
    ini, fin = _buscar_posicion_nombre(evidencia)
    if ini is None or fin is None:
        return False
    ids = {_normalizar_identificador(v) for v in
           (evidencia.dni, evidencia.cuit_cuil) if v}
    if not ids:
        return False
    posterior = evidencia.fragmento[fin:fin + 145]
    patron = (r"\b(?:D\.?N\.?I\.?|DOCUMENTO\s+NACIONAL\s+DE\s+IDENTIDAD|"
              r"C\.?U\.?I\.?T\.?(?:/CUIL)?|CUIL(?:/CUIT)?)\s*(?:N[°ºo.]*(?:ro\.?)?|"
              r"n[uú]mero)?\s*[:°º.]?\s*([0-9][0-9.\- ]{5,18}[0-9])")
    encontrados = list(re.finditer(patron, posterior, re.I))
    if not encontrados:
        return False
    # El primer identificador etiquetado posterior debe pertenecer
    # a esta persona. Puede seguir un segundo ID de la misma persona.
    primero = _normalizar_identificador(encontrados[0].group(1))
    return primero in ids


def _nombre_parcial_en_lista(evidencia: Evidencia) -> bool:
    """Detecta apellidos ausentes en líneas tipo '1. BENITEZ, HUGO ORLANDO'."""
    posicion = _buscar_posicion_nombre(evidencia)
    if posicion[0] is None:
        return False
    ini = posicion[0]
    linea_inicio = evidencia.fragmento.rfind("\n", 0, ini) + 1
    prefijo = evidencia.fragmento[linea_inicio:ini]
    # No tratar 'DNI' o el número ordinal como parte de un apellido.
    prefijo = re.sub(r"^\s*\d+[.)]\s*", "", prefijo)
    return bool(re.search(r"[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ]+\s*,\s*$", prefijo))


def _evidencia_lista_explicita(evidencia: Evidencia) -> bool:
    fragmento = evidencia.fragmento
    posicion = _buscar_posicion_nombre(evidencia)
    if posicion[0] is None:
        return False
    ini = posicion[0]
    if any(re.search(p, fragmento[:ini], re.I) for p in PATRONES_ENCABEZADO_LISTA):
        return True
    # Listados enumerados: encabezado sobre productos financieros y filas n. NOMBRE - DNI.
    linea_inicio = fragmento.rfind("\n", 0, ini) + 1
    prefijo = fragmento[linea_inicio:ini]
    return bool(re.search(r"^\s*\d+[.)]\s*", prefijo) and
                re.search(r"\b(?:inform|financiero|cuenta|mercado pago|plataforma)\b", fragmento[:ini], re.I))


def _evidencia_pedido_explicito(evidencia: Evidencia) -> bool:
    posicion = _buscar_posicion_nombre(evidencia)
    if posicion[0] is None:
        return False
    ini, fin = posicion
    assert ini is not None and fin is not None
    antes = evidencia.fragmento[max(0, ini - 155):ini]
    despues = evidencia.fragmento[fin:min(len(evidencia.fragmento), fin + 85)]
    # Evitar nombres administrativos con el identificador de otra persona.
    if re.search(r"\b(?:domicilio|sito en|autorizad[oa]|firmado por|letrado patrocinante)\b", antes[-75:], re.I):
        return False
    es_solicitud = bool(re.search(r"\b(?:inform|solicit|verific|identific|acreditacion|compras|cuentas?|transferencias|movimientos|(?:co)?demandad[oa]|actor[ao]|empleado|alimentante)\w*\b", antes, re.I))
    es_objeto = bool(re.search(r"\b(?:dni|cuit|cuil|cuenta|cvu|movimiento|transferencia|documento\s+nacional\s+de\s+identidad)\b|C\.?U\.?I\.?T\.?", despues, re.I))
    # Algunas frases llegan recortadas: 'por NOMBRE, CVU..., CUIT/CUIL...'.
    # La combinación 'por' + identificador bancario explícito constituye
    # una relación local suficiente, aunque el verbo esté fuera del recorte.
    detalle_bancario = bool(re.search(r"\bpor\s+$", antes[-25:], re.I)
                            and re.search(r"\bCVU\b", despues, re.I)
                            and re.search(r"\b(?:CUIT|CUIL)\b", despues, re.I))
    return (es_solicitud and es_objeto) or detalle_bancario


def _pedido_comercial_fiscal_explicito(e: Evidencia) -> bool:
    """Comprobar la relación local NOMBRE + ID dentro de pedido comercial/fiscal.

    No usar el rol del modelo como única señal.
    """
    if not _identificador_cerca_nombre(e) or _nombre_parcial_en_lista(e):
        return False
    pos = _buscar_posicion_nombre(e)
    if pos[0] is None:
        return False
    previo = e.fragmento[max(0, pos[0]-115):pos[0]]
    posterior = e.fragmento[pos[1]:pos[1]+135]
    comercial = bool(re.search(r"(?:\bimportes?\s+facturados?\s+a\s*$|\bfacturaci[oó]n\b|\boperaciones\s+(?:concertadas|realizadas)\s+con\s*$)", previo, re.I))
    fiscal = bool(re.search(r"(?:\b(?:referente|respecto)\s+a\s+la\s+contribuyente\s*$|\bfiscalizaci[oó]n\b.{0,85}\bcontribuyente\s*$)", previo, re.I))
    # Rol fiscal no basta si el texto no lo menciona en relación directa.
    return bool((comercial or fiscal) and re.search(r"\b(?:CUIT|CUIL)\b", posterior, re.I))


def _grupo_evidencia_vinculante(grupo: GrupoPersona) -> bool:
    return any((_evidencia_pedido_explicito(e) or _evidencia_lista_explicita(e) or _pedido_comercial_fiscal_explicito(e))
               and _identificador_cerca_nombre(e) and not _nombre_parcial_en_lista(e)
               and not e.tercero_fuerte for e in grupo.evidencias)


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
        # Algunos spans del predictor están desplazados. Solo confiar
        # en ellos si el texto en ese rango coincide realmente.
        if (evidencia.fragmento[
            evidencia.nombre_span_inicio:evidencia.nombre_span_fin
        ].casefold() == evidencia.nombre.casefold()):
            return (evidencia.nombre_span_inicio, evidencia.nombre_span_fin)

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

    # Las personas de una lista siguen siendo objeto del oficio aunque
    # el encabezado quede fuera de la ventana local de 120 caracteres.
    # Solo usar la señal si el fragmento contiene un encabezado explícito
    # y el candidato figura en el fragmento de esa enumeración.
    if _evidencia_lista_explicita(evidencia):
        score += 3.0

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

def _registrar_candidatos_incompletos(documento: dict[str, Any]) -> list[dict[str, Any]]:
    """Auditoria de predicciones sin nombre util; NO modifica la aceptacion."""
    incompletos: list[dict[str, Any]] = []
    for resultado in documento.get("resultados", []) or []:
        for indice, candidate in enumerate(resultado.get("candidates", []) or [], start=1):
            nombre = _texto_seguro(candidate.get("nombre_persona") or candidate.get("nombre"))
            if _nombre_es_util(nombre):
                continue
            dni = _texto_seguro(candidate.get("dni_persona") or candidate.get("dni"))
            cuit = _texto_seguro(candidate.get("cuit_cuil_persona") or candidate.get("cuil_cuit"))
            # Solo registrar predicciones con identificador; evitar ruido vacio.
            if not (dni or cuit):
                continue
            incompletos.append({
                "numero_archivo": documento.get("numero_archivo"),
                "contador_interno": resultado.get("contador_interno"),
                "indice_candidato": indice,
                "nombre_persona": nombre or None,
                "dni_persona": dni or None,
                "cuit_cuil_persona": cuit or None,
                "motivo": "sin_nombre_persona" if not nombre else "nombre_no_util",
                "origen": "gliner2",
                "palabra_clave": resultado.get("palabra_clave"),
                "categoria": resultado.get("categoria"),
                "fragmento": resultado.get("fragmento") or resultado.get("texto_entrada_modelo") or "",
                "nombre_confidence": candidate.get("nombre_persona_confidence"),
                "dni_confidence": candidate.get("dni_persona_confidence"),
                "cuit_cuil_confidence": candidate.get("cuit_cuil_persona_confidence"),
            })
    return incompletos


def _recuperar_apellido_antes_nombre(fragmento: str, nombre: str, dni: str) -> str | None:
    """Recupera un apellido literal omitido solo en 'APELLIDO, Nombres, DNI'.

    No infiere apellidos desde caratulas ni otros fragmentos. Exige una
    coincidencia unica y un DNI etiquetado inmediatamente despues del nombre.
    """
    if not (fragmento and nombre and dni):
        return None
    dni_normalizado = _normalizar_identificador(dni)
    if not (7 <= len(dni_normalizado) <= 8):
        return None
    patron = re.compile(
        r"(?<![\w])([A-ZÁÉÍÓÚÜÑ]{2,})\s*,\s*(" + re.escape(nombre) +
        r")\s*,?\s*D\.?\s*N\.?\s*I\.?\s*[:Nº°o.\s-]*\s*"
        r"([0-9][0-9.\s-]{5,14}[0-9])(?!\d)",
        re.IGNORECASE,
    )
    coincidencias = [m for m in patron.finditer(fragmento)
                     if _normalizar_identificador(m.group(3)) == dni_normalizado]
    if len(coincidencias) != 1:
        return None
    m = coincidencias[0]
    # Evitar 'Sr.' y otras palabras de tratamiento como supuesto apellido.
    if not m.group(1).isupper():
        return None
    if _normalizar_texto(m.group(1)) in {"SR", "SRA", "DNI", "DR", "DRA", "ACTOR", "ACTORA"}:
        return None
    return fragmento[m.start(1):m.end(2)]


# Recuperacion estricta en listados multilinea: NOMBRE DNI VALOR.
# No corrige nombres o DNI por cercania dentro de parrafos.
def _parejas_lista_estructurada(fragmento: str) -> dict[str, tuple[str, str]]:
    patron = re.compile(
        r"^\s*([A-ZÁÉÍÓÚÜÑ]+(?:[ \t]+[A-ZÁÉÍÓÚÜÑ]+){1,6})"
        r"[ \t]+D\.?[ \t]*N\.?[ \t]*I\.?\s*[:#º°Nnro.\-]*\s*"
        r"(\d{1,2}(?:[.]?\d{3}){2})\s*$",
        re.IGNORECASE,
    )
    lineas = fragmento.splitlines()
    encontrados = []
    for linea in lineas:
        m = patron.fullmatch(linea.strip())
        if m and m.group(1) == m.group(1).upper():
            encontrados.append((m.group(1).strip(), m.group(2).strip()))
    # Evitar aplicar reglas de lista a una unica mencion aislada.
    if len(encontrados) < 3:
        return {}
    pares: dict[str, tuple[str, str]] = {}
    ambiguos: set[str] = set()
    for nombre, dni in encontrados:
        clave = _normalizar_texto(nombre)
        if clave in pares and _normalizar_identificador(pares[clave][1]) != _normalizar_identificador(dni):
            ambiguos.add(clave)
        else:
            pares[clave] = (nombre, dni)
    return {k: v for k, v in pares.items() if k not in ambiguos}


# Lista numerada: recuperacion literal de filas omitidas o nombres parciales.
def _filas_numeradas_verificadas(fragmento: str) -> list[dict[str, str]]:
    patron = re.compile(
        r"^\s*(\d{1,3})[.)]\s+"
        r"([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ' -]{1,70}),\s*"
        r"([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ' -]{2,75})"
        r"\s+-\s*(?:(?:CUIT|CUIL)\s+([0-9.\- ]{10,18})\s*)?"
        r"(?:\(\s*)?DNI\s*[:#º°Nnro.\- ]*"
        r"(\d{1,2}(?:\.\d{3}){2}|\d{7,8})\s*\)?\s*$",
        re.IGNORECASE,
    )
    filas = []
    for linea in fragmento.splitlines():
        m = patron.fullmatch(linea.strip())
        if not m:
            continue
        apellido, nombres = m.group(2).strip(), m.group(3).strip()
        if apellido != apellido.upper() or nombres != nombres.upper():
            continue
        filas.append({"numero": int(m.group(1)), "nombre": f"{apellido}, {nombres}",
                      "dni": m.group(5), "cuit_cuil": (m.group(4) or "").strip(),
                      "linea": linea.strip()})
    # Exigir una lista real y numeraciones consecutivas; evitar lecturas aisladas.
    if len(filas) < 3 or len({f['numero'] for f in filas}) != len(filas):
        return []
    if any(b['numero'] != a['numero'] + 1 for a, b in zip(filas, filas[1:])):
        return []
    nombres = [_normalizar_texto(f['nombre']) for f in filas]
    dnis = [_normalizar_identificador(f['dni']) for f in filas]
    if len(nombres) != len(set(nombres)) or len(dnis) != len(set(dnis)):
        return []
    return filas


def _parejas_lista_extensa_en_linea(fragmento: str) -> list[dict[str, str]]:
    """Parejas literales en listas de 8+ entradas: NOMBRE DNI, aun sin saltos.

    No busca en texto_completo ni interpreta proximidad libre. Exige que cada
    segmento entre DNIs sea exactamente un nombre en mayusculas y que haya
    correspondencias univocas en toda la secuencia.
    """
    if not fragmento or "DNI" not in fragmento.upper():
        return []
    patron_dni = re.compile(
        r"(?<![\w])D\.?\s*N\.?\s*I\.?\s*[:#Nº°o.\s-]*"
        r"(\d{1,2}(?:\.\d{3}){2}|\d{7,8})(?!\d)", re.I,
    )
    hallazgos = list(patron_dni.finditer(fragmento))
    if len(hallazgos) < 8:
        return []
    inicio = fragmento.upper().find("PERSONAL POLICIAL A VERIFICAR:")
    if inicio >= 0:
        inicio += len("PERSONAL POLICIAL A VERIFICAR:")
    else:
        # No activar sobre parrafos o listados sin encabezado verificable.
        return []
    if hallazgos[0].start() <= inicio:
        return []
    filas = []
    pos = inicio
    patron_nombre = re.compile(r"[A-ZÁÉÍÓÚÜÑ]+(?:[ \t\n]+[A-ZÁÉÍÓÚÜÑ]+){1,6}")
    for match in hallazgos:
        tramo = fragmento[pos:match.start()].strip(" \t\n.:-;,")
        if not patron_nombre.fullmatch(tramo):
            return []
        filas.append({"nombre": tramo, "dni": match.group(1),
                      "origen": "lista_extensa_pareja_literal"})
        pos = match.end()
    claves = [_normalizar_texto(f["nombre"]) for f in filas]
    dnis = [_normalizar_identificador(f["dni"]) for f in filas]
    if len(set(claves)) != len(filas) or len(set(dnis)) != len(filas):
        return []
    return filas


def _v12_recuperar_campos_locales(candidatos: list[dict[str, Any]], fragmento: str) -> list[dict[str, Any]]:
    """Recuperar solo parejas inequívocas y literalmente presentes en fragmento.

    Nunca inventar nombres a partir de CUIT ni cruzar listas de personas.
    """
    recuperados = []
    patron_sociedad = re.compile(
        r"(?:\b(?:informe\s+si|contribuyente|firma|empresa|(?:la\s+|el\s+)?codemandad[oa])\s+)"
        r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ. ]{3,75}?\s+"
        r"(?:S\.?\s*A\.?|S\.?\s*R\.?\s*L\.?|S\.?\s*A\.?\s*S\.?))"
        r"(?:\s*\([A-Z]{2,8}\))?\s*,?\s*"
        r"C\.?\s*U\.?\s*I\.?\s*T\.?\s*(?:N[°ºo]\.?\s*)?[:.]?\s*"
        r"([0-9][0-9. -]{9,17}[0-9])", re.I)
    for c in candidatos:
        c = dict(c)
        nombre = _texto_seguro(c.get('nombre_persona'))
        dni = _texto_seguro(c.get('dni_persona'))
        cuit = _texto_seguro(c.get('cuit_cuil_persona'))
        if not nombre and cuit:
            coincidencias = [m for m in patron_sociedad.finditer(fragmento) if _normalizar_identificador(m.group(2)) == _normalizar_identificador(cuit)]
            if len(coincidencias)==1:
                m=coincidencias[0]
                candidato_nombre=m.group(1).strip()
                candidato_nombre=re.sub(r"^(?:la\s+)?(?:contribuyente|empresa|firma)\s+", '', candidato_nombre, flags=re.I)
                # No extrapolar el nombre desde oraciones largas/antecedentes.
                if 2 <= len(candidato_nombre.split()) <= 8 and _nombre_tiene_estructura_valida(candidato_nombre):
                    c['nombre_persona']=candidato_nombre
                    c['nombre_persona_confidence']=None
                    c['origen_recuperacion_v12']='razon_social_cuit_local'
        if nombre and not dni:
            # Sólo DNI inmediatamente posterior al nombre, no otro sujeto.
            p=_posicion_nombre_texto(fragmento,nombre)
            if p:
                tramo=fragmento[p[1]:p[1]+55]
                m=re.match(r"\s*[,;:]?\s*\(?\s*D\.?\s*N\.?\s*I\.?\s*[-: ]\s*(\d{1,2}(?:[. -]?\d{3}){2})\b", tramo, re.I)
                if m and len(re.sub(r'\D','',m.group(1))) in (7,8):
                    c['dni_persona']=m.group(1)
                    c['origen_recuperacion_v12']='dni_local_adyacente'
        recuperados.append(c)
    return recuperados


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
            ) or resultado.get("texto_entrada_modelo")
        )

        candidatos_originales = resultado.get("candidates", []) or []
        candidatos_procesados = _v12_recuperar_campos_locales([dict(c) for c in candidatos_originales], fragmento)
        filas_numeradas = _filas_numeradas_verificadas(fragmento)
        filas_extensas = _parejas_lista_extensa_en_linea(fragmento)
        # Exigir al menos cinco nombres originales coincidentes con la lista,
        # para no fabricar identidades desde un solo candidato aislado.
        nombres_originales = {
            _normalizar_texto(_texto_seguro(c.get("nombre_persona") or c.get("nombre")))
            for c in candidatos_originales
        }
        nombres_lista = {_normalizar_texto(f["nombre"]) for f in filas_extensas}
        if filas_extensas and len(nombres_originales & nombres_lista) >= 5:
            por_nombre = {_normalizar_texto(f["nombre"]): f for f in filas_extensas}
            # Reusar los candidatos validos, corrigiendo solo identidades
            # cuyos nombres aparecen univocamente en la lista literal.
            nombres_vistos = set()
            candidatos_lista = []
            for c in candidatos_procesados:
                nombre_c = _texto_seguro(c.get("nombre_persona") or c.get("nombre"))
                clave = _normalizar_texto(nombre_c)
                if clave not in por_nombre:
                    # Los candidatos sin nombre se conservan en el reporte
                    # de incompletos, pero no forman una identidad.
                    if nombre_c:
                        candidatos_lista.append(c)
                    continue
                fila = por_nombre[clave]
                if clave in nombres_vistos:
                    # Duplicado espurio del mismo nombre con DNI desplazado.
                    continue
                nombres_vistos.add(clave)
                c2 = dict(c)
                dni_viejo = _texto_seguro(c.get("dni_persona") or c.get("dni"))
                if _normalizar_identificador(dni_viejo) != _normalizar_identificador(fila["dni"]):
                    c2["dni_original_gliner_recuperacion"] = dni_viejo
                    c2["dni_persona"] = fila["dni"]
                    c2["motivo_correccion_lista_extensa"] = "dni_reasociado_lista_extensa"
                candidatos_lista.append(c2)
            for fila in filas_extensas:
                clave = _normalizar_texto(fila["nombre"])
                if clave not in nombres_vistos:
                    candidatos_lista.append({
                        "nombre_persona": fila["nombre"], "dni_persona": fila["dni"],
                        "cuit_cuil_persona": None, "rol_persona": None,
                        "origen_recuperacion_lista": "lista_extensa_pareja_literal",
                        "nombre_persona_confidence": None,
                    })
            candidatos_procesados = candidatos_lista
        # Solo ampliar una lista si hay algun candidato de GLiNER vinculado
        # a la misma lista; no ejecutar una extraccion regex independiente.
        if filas_numeradas and candidatos_originales:
            for fila in filas_numeradas:
                clave = _normalizar_texto(fila["nombre"])
                coincidencias = []
                for i, c in enumerate(candidatos_procesados):
                    nom = _texto_seguro(c.get("nombre_persona") or c.get("nombre"))
                    dni_c = _normalizar_identificador(_texto_seguro(c.get("dni_persona") or c.get("dni")))
                    if not nom or dni_c != _normalizar_identificador(fila["dni"]):
                        continue
                    # Nombre completo o sufijo exacto de nombres, no proximidad.
                    if _normalizar_texto(nom) in {clave, _normalizar_texto(fila["nombre"].split(",", 1)[1])}:
                        coincidencias.append(i)
                if len(coincidencias) == 1:
                    c = candidatos_procesados[coincidencias[0]]
                    if _normalizar_texto(_texto_seguro(c.get("nombre_persona"))) != clave:
                        c["nombre_original_gliner_recuperacion"] = c.get("nombre_persona")
                        c["nombre_persona"] = fila["nombre"]
                    continue
                if coincidencias:
                    continue
                # No fabricar parejas si hay un candidato existente para
                # ese mismo nombre con otro DNI: requiere investigacion.
                if any(_normalizar_texto(_texto_seguro(c.get("nombre_persona"))) == clave
                       for c in candidatos_procesados):
                    continue
                candidatos_procesados.append({
                    "nombre_persona": fila["nombre"], "dni_persona": fila["dni"],
                    "cuit_cuil_persona": fila["cuit_cuil"], "rol_persona": None,
                    "nombre_persona_confidence": None,
                    "origen_recuperacion_lista": "fila_numerada_literal_verificada",
                })

        for candidate in candidatos_procesados:

            nombre = _texto_seguro(
                candidate.get(
                    "nombre_persona"
                )
                or candidate.get(
                    "nombre"
                )
            )

            if not _nombre_es_util(
                nombre
            ):
                continue

            nombre_original_gliner = _texto_seguro(candidate.get("nombre_original_gliner_recuperacion"))
            origen_recuperacion_lista = _texto_seguro(candidate.get("origen_recuperacion_lista"))
            dni_candidato = _texto_seguro(candidate.get("dni_persona") or candidate.get("dni"))
            recuperado = _recuperar_apellido_antes_nombre(fragmento, nombre, dni_candidato)
            if recuperado and _normalizar_texto(recuperado) != _normalizar_texto(nombre):
                nombre_original_gliner = nombre
                nombre = recuperado

            dni_original_gliner_lista = _texto_seguro(candidate.get("dni_original_gliner_recuperacion"))
            motivo_correccion_lista = _texto_seguro(candidate.get("motivo_correccion_lista_extensa"))
            parejas_lista = _parejas_lista_estructurada(fragmento)
            pareja = parejas_lista.get(_normalizar_texto(nombre))
            if pareja and dni_candidato:
                nombre_lista, dni_lista = pareja
                if _normalizar_identificador(dni_candidato) != _normalizar_identificador(dni_lista):
                    # Solo corregir si el DNI original tambien aparece en el
                    # fragmento: documenta el desplazamiento entre filas.
                    digitos_originales = _normalizar_identificador(dni_candidato)
                    dnis_en_lista = {_normalizar_identificador(d) for _, d in parejas_lista.values()}
                    if digitos_originales in dnis_en_lista:
                        dni_original_gliner_lista = dni_original_gliner_lista or dni_candidato
                        dni_candidato = dni_lista
                        motivo_correccion_lista = "dni_reasociado_por_linea_de_lista"

            start = candidate.get(
                "nombre_persona_span_inicio"
            )

            if start is None:
                start = candidate.get(
                    "nombre_span_inicio"
                )

            end = candidate.get(
                "nombre_persona_span_fin"
            )

            if end is None:
                end = candidate.get(
                    "nombre_span_fin"
                )

            if nombre_original_gliner:
                start, end = None, None

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
                nombre_original_gliner=nombre_original_gliner,
                origen_recuperacion_lista=origen_recuperacion_lista,
                origen_recuperacion_v12=_texto_seguro(candidate.get("origen_recuperacion_v12")),

                dni=dni_candidato,
                dni_original_gliner_lista=dni_original_gliner_lista,
                motivo_correccion_lista=motivo_correccion_lista,

                cuit_cuil=_texto_seguro(
                    candidate.get(
                        "cuit_cuil_persona"
                    )
                    or candidate.get(
                        "cuil_cuit"
                    )
                ),

                rol=_texto_seguro(
                    candidate.get("rol_persona")
                    or (candidate.get("fields", {}).get("rol_persona") or {}).get("text")
                ),

                nombre_confidence=(
                    candidate.get(
                        "nombre_persona_confidence"
                    )
                    or candidate.get(
                        "nombre_persona_confidence"
                    )
                ),

                dni_confidence=(
                    candidate.get(
                        "dni_persona_confidence"
                    )
                    or candidate.get(
                        "dni_persona_confidence"
                    )
                ),

                cuit_cuil_confidence=(
                    candidate.get(
                        "cuit_cuil_persona_confidence"
                    )
                    or candidate.get(
                        "cuit_cuil_persona_confidence"
                    )
                ),

                rol_confidence=(
                    candidate.get(
                        "rol_persona_confidence"
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
# EXCEPCION OCR: DNI con un unico digito inicial omitido
# Solo para el consolidador de OFICIOS; se conserva el DNI original.
# ============================================================

def _corregir_dni_ocr_inicial(evidencias: list[Evidencia]) -> None:
    """Corrige una variante OCR únicamente si hay corroboración local inequívoca.

    Exige mismo nombre completo normalizado, un DNI de ocho cifras y
    otro de siete cuyo sufijo coincida exactamente; ambas parejas deben
    estar localmente verificadas en sus respectivos fragmentos. Si hay
    otros DNI o CUIT contradictorios para ese nombre, no modifica nada.
    Nunca completa DNIs de siete cifras sin un homólogo explícito.
    """
    por_nombre: dict[str, list[Evidencia]] = defaultdict(list)
    for evidencia in evidencias:
        nombre = _normalizar_texto(evidencia.nombre)
        dni = _normalizar_identificador(evidencia.dni)
        if nombre and len(nombre.split()) >= 2 and dni:
            por_nombre[nombre].append(evidencia)

    for grupo in por_nombre.values():
        dnis = {_normalizar_identificador(e.dni) for e in grupo}
        if len(dnis) != 2:
            continue
        largos = [dni for dni in dnis if len(dni) == 8]
        cortos = [dni for dni in dnis if len(dni) == 7]
        if len(largos) != 1 or len(cortos) != 1:
            continue
        largo, corto = largos[0], cortos[0]
        if largo[1:] != corto:
            continue
        if any(e.cuit_cuil for e in grupo):
            # Una identidad con CUIT/CUIL adicionales necesita revisión aparte.
            continue
        if not all(_identificador_cerca_nombre(e) for e in grupo):
            continue
        if not all(_evidencia_pedido_explicito(e) or _evidencia_lista_explicita(e)
                   for e in grupo):
            continue
        if any(e.tercero_fuerte for e in grupo):
            continue
        fuente = next(e.dni for e in grupo if _normalizar_identificador(e.dni) == largo)
        for evidencia in grupo:
            if _normalizar_identificador(evidencia.dni) == corto:
                evidencia.dni_original_ocr = evidencia.dni
                evidencia.dni = fuente


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


def _prioridad_pedido_principal(grupo: GrupoPersona) -> dict[str, Any]:
    """Prioriza evidencias expresas, solo para diagnóstico, sin resolver conflictos.

    No premia la repetición en autos transcritos: un requerimiento explícito
    vinculado a un identificador prevalece en el orden de revisión.
    """
    vinculantes = [e for e in grupo.evidencias if
                   _evidencia_pedido_explicito(e)
                   and _identificador_cerca_nombre(e)
                   and not e.tercero_fuerte]
    return {
        "nivel": "pedido_explicito_identificado" if vinculantes else "evidencia_complementaria",
        "prioridad": 2 if vinculantes else 1,
        "fragmentos_explicitos": sorted({str(e.contador_interno) for e in vinculantes}),
        "justificacion": ("Nombre e identificador vinculados en solicitud explicita"
                          if vinculantes else "No se verifico solicitud explicita local; revisar fuentes"),
    }


def _homonimos_enumerados_explicitamente(
    grupo_a: GrupoPersona,
    grupo_b: GrupoPersona,
    tipo: str,
) -> bool:
    """Dos identidades distintas si el MISMO fragmento enumera nombre+DNI
    independientemente para ambos, dentro de un pedido directo.

    No basta con que coincidan nombres y difieran DNI en secciones distintas.
    Tampoco presupone parentesco entre las personas.
    """
    if tipo != "dni":
        return False
    nombre_a = _normalizar_texto(_nombre_canonico(grupo_a))
    nombre_b = _normalizar_texto(_nombre_canonico(grupo_b))
    if not nombre_a or nombre_a != nombre_b:
        return False
    ids_a = _identificadores_grupo(grupo_a)["dni"]
    ids_b = _identificadores_grupo(grupo_b)["dni"]
    if len(ids_a) != 1 or len(ids_b) != 1 or ids_a == ids_b:
        return False
    dni_a, dni_b = next(iter(ids_a)), next(iter(ids_b))
    # Evitar resolver aqui una omision del primer digito: lo trata la
    # correccion OCR existente, que exige evidencia independiente.
    if dni_a.endswith(dni_b) or dni_b.endswith(dni_a):
        return False

    fragmentos_a = {e.fragmento for e in grupo_a.evidencias if e.fragmento}
    fragmentos_b = {e.fragmento for e in grupo_b.evidencias if e.fragmento}
    for fragmento in fragmentos_a & fragmentos_b:
        texto = _normalizar_texto(fragmento)
        # Requisito de contexto: consulta plural con sujetos enumerados.
        if not re.search(r"\b(?:INFORMAR|INFORME|INFORMEN|CONSULTAR|VERIFICAR)\b", texto):
            continue
        if not re.search(r"\b(?:SRES|SEN ORES|PERSONAS|TITULARES)\b", texto):
            continue
        nombre_patron = r"\b" + r"\s+".join(map(re.escape, nombre_a.split())) + r"\b"
        # Las puntuaciones del DNI desaparecen al normalizar el texto.
        expresion = re.compile(
            nombre_patron +
            r"\s+TITULAR\s+DEL?\s+DNI\s+(?:NRO?\s+)?(?:N\s+)?"
            r"(\d{1,2})\s+(\d{3})\s+(\d{3})\b"
        )
        encontrados = {"".join(m.groups()) for m in expresion.finditer(texto)}
        if dni_a in encontrados and dni_b in encontrados:
            return True
    return False


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

            # Reportar también mismo nombre con DNI/CUIT diferentes.
            # Estos grupos no se fusionan porque sus ID contradicen,
            # pero la contradicción debe quedar visible en el diagnóstico.
            if _nombres_equivalentes(nombre_a, nombre_b):
                ids_b = _identificadores_grupo(grupo_b)
                for tipo in ("dni", "cuit_cuil"):
                    if ids_a[tipo] and ids_b[tipo] and ids_a[tipo].isdisjoint(ids_b[tipo]):
                        key_conflicto = (tipo, "identificadores_distintos", nombre_a, nombre_b)
                        if key_conflicto not in vistos:
                            vistos.add(key_conflicto)
                            prioridad_a = _prioridad_pedido_principal(grupo_a)
                            prioridad_b = _prioridad_pedido_principal(grupo_b)
                            # Es solo una sugerencia para revisar; nunca elimina
                            # conflictos ni cambia el estado/suficiencia.
                            preferida = ("a" if prioridad_a["prioridad"] > prioridad_b["prioridad"]
                                         else "b" if prioridad_b["prioridad"] > prioridad_a["prioridad"]
                                         else None)
                            homonimos_confirmados = _homonimos_enumerados_explicitamente(
                                grupo_a, grupo_b, tipo,
                            )
                            conflictos.append({
                                "conflicto_bloqueante": not homonimos_confirmados,
                                "resolucion_conflicto": (
                                    "homonimos_enumerados_explicitamente"
                                    if homonimos_confirmados else "pendiente"
                                ),
                                "priorizacion_evidencia": {
                                    "grupo_preferente_para_revision": preferida,
                                    "criterio": "pedido_explicito_con_identificador_local",
                                    "grupo_a": prioridad_a,
                                    "grupo_b": prioridad_b,
                                    "conflicto_pendiente": not homonimos_confirmados,
                                    "resolucion_automatica": homonimos_confirmados,
                                },
                                "tipo_identificador": tipo,
                                "tipo_conflicto": "mismo_nombre_identificadores_distintos",
                                "valores_a": sorted(ids_a[tipo]),
                                "valores_b": sorted(ids_b[tipo]),
                                "nombre_a": nombre_a,
                                "nombre_b": nombre_b,
                                "variantes_a": sorted(grupo_a.variantes_nombre),
                                "variantes_b": sorted(grupo_b.variantes_nombre),
                            })
                continue
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


def _evaluar_grupo_oficio(
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

    if any(_nombre_parcial_en_lista(e) for e in grupo.evidencias):
        return False, ["nombre_parcial_en_lista"], detalle

    if tercero_fuerte:
        return (
            False,
            [
                "tercero_fuerte"
            ],
            detalle,
        )

    # Una identidad puede tener DNI válido pero estar enlazada al nombre
    # equivocado. No la aceptamos sin al menos una pareja local verificable.
    pareja_local_verificada = any(
        _identificador_cerca_nombre(e) for e in grupo.evidencias
    )
    evidencia_vinculante = _grupo_evidencia_vinculante(grupo)
    senales["identificador_local_verificado"] = pareja_local_verificada
    senales["requerimiento_explicito"] = evidencia_vinculante
    # Solo descartar si el texto prueba que el nombre identificado es
    # un tercero y existe otra persona expresamente consultada con su DNI.
    contradiccion_nombre_id = any(
        not _identificador_cerca_nombre(e)
        and re.search(r"\b(?:a\s+los\s+fines\s+que|para\s+que|a\s+fin\s+de\s+que)\b", e.fragmento, re.I)
        and re.search(r"\b(?:informe|informar)\s+si\s+(?:el\s+)?(?:alimentante|demandado|demandada|sr\.?)\b", e.fragmento, re.I)
        and (_buscar_posicion_nombre(e)[0] or 0) <
            (re.search(r"\b(?:informe|informar)\s+si\s+(?:el\s+)?(?:alimentante|demandado|demandada|sr\.?)\b",e.fragmento,re.I).start())
        for e in grupo.evidencias if e.dni or e.cuit_cuil
    )
    # Evitar tomar el DNI del sujeto explícito del pedido cuando el
    # nombre candidato se encuentra ANTES de la cláusula "informe si".
    # Documento 48: "Tatiana Gulián, sito en ... informe si el
    # alimentante PAVOLNI ... DNI ...".
    if tiene_id and any(
        (lambda pos: pos[0] is not None and
         bool(re.search(r"\binforme\s+si\b", e.fragmento[pos[1]:], re.I)) and
         bool(re.search(r"\b(?:alimentante|demandad[oa]|sr\.?)\b", e.fragmento[pos[1]:], re.I)))
        (_buscar_posicion_nombre(e))
        for e in grupo.evidencias
    ):
        return False, ["identificador_corresponde_a_otro_sujeto_del_pedido"], detalle
    if contradiccion_nombre_id:
        return False, ["identificador_asociado_a_otra_persona_en_requerimiento"], detalle

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

    # V12: nombre sin DNI/CUIT no satisface una identidad individualizada.
    if not tiene_id:
        return False, ["sin_identificador_verificable"], detalle

    # ========================================================
    # REGLAS POSITIVAS
    # ========================================================

    # Evidencia directa del requerimiento + nombre e ID localmente ligados.
    # No depende de repeticion ni de un rol jurídico predicho.
    if evidencia_vinculante:
        return True, ["requerimiento_explicito", "identificador_local_verificado"], detalle

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


def _grupo_es_objeto_oficio(
    grupo: GrupoPersona,
    total_grupos: int,
) -> bool:
    """
    Mantiene la interfaz anterior.

    La decision real se realiza en
    _evaluar_grupo_oficio(), que ahora tambien
    genera informacion de diagnostico.
    """

    aceptado, _, _ = (
        _evaluar_grupo_oficio(
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
        **({
            "nombre_original_gliner": evidencia.nombre_original_gliner,
            "motivo_recuperacion_nombre": "apellido_literal_recuperado_del_fragmento",
        } if evidencia.nombre_original_gliner else {}),

        **({"origen_recuperacion_lista": evidencia.origen_recuperacion_lista}
           if evidencia.origen_recuperacion_lista else {}),
        "origen_recuperacion_v12": evidencia.origen_recuperacion_v12 or None,
        "dni_detectado":
            evidencia.dni_original_ocr or evidencia.dni,
        **({
            "dni_original_gliner": evidencia.dni_original_gliner_lista,
            "dni_corregido_lista": evidencia.dni,
            "motivo_correccion_lista": evidencia.motivo_correccion_lista,
        } if evidencia.dni_original_gliner_lista else {}),

        "dni_corregido_ocr":
            evidencia.dni if evidencia.dni_original_ocr else None,

        "motivo_correccion_ocr":
            "omision_digito_inicial_verificada" if evidencia.dni_original_ocr else None,

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
        "nombre_persona":
            _nombre_canonico(
                grupo
            ),

        "dni_persona":
            _valor_mas_frecuente(
                [
                    evidencia.dni
                    for evidencia
                    in grupo.evidencias
                ]
            ),

        "cuit_cuil_persona":
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
    personas_objeto_oficio: list[
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
                "nombre_persona",
                "",
            )
        )
        for persona
        in personas_objeto_oficio
        if persona.get(
            "nombre_persona"
        )
    }

    if not nombres_aceptados:
        return False

    for conflicto in conflictos_identificador:

        if conflicto.get("conflicto_bloqueante") is False:
            continue

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

def _evidencia_pedido_explicito_obj_serializada(data: dict[str, Any]) -> bool:
    evidencia = Evidencia(
        numero_archivo="", id_documento="", contador_interno="",
        palabra_clave="", categoria="", fragmento=data.get("fragmento", ""),
        nombre=data.get("nombre_detectado", ""),
        dni=data.get("dni_detectado", ""),
        cuit_cuil=data.get("cuit_cuil_detectado", ""),
    )
    return _grupo_evidencia_vinculante(GrupoPersona(evidencias=[evidencia]))


def evaluar_suficiencia(
    estado: str,
    personas_objeto_oficio: list[
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

    if not personas_objeto_oficio:
        motivos.append(
            "sin_persona_objeto_oficio"
        )

    # --------------------------------------------------------
    # 3. SOLO HUBO DESCARTADOS
    # --------------------------------------------------------

    if (
        not personas_objeto_oficio
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
        personas_objeto_oficio,
    ):
        motivos.append(
        "conflicto_identificador"
    )

    # --------------------------------------------------------
    # 5. DEMASIADOS EMBARGADOS
    # --------------------------------------------------------

    if (
        len(
            personas_objeto_oficio
        )
        > MAX_PERSONAS_SIN_REVISION
    ):
        motivos.append(
            "cantidad_personas_objeto_oficio_anormal"
        )

    # Si un candidato plausible con identificador quedó descartado,
    # las personas aceptadas NO prueban que el oficio esté completamente
    # resuelto (caso 7: dos destinatarias distintas).
    pendientes_relevantes = [
        grupo for grupo in grupos_descartados
        if (_texto_seguro(grupo.get("dni_persona")) or
            _texto_seguro(grupo.get("cuit_cuil_persona")))
        and _nombre_tiene_estructura_valida(grupo.get("nombre_persona"))
        and not _normalizar_texto(grupo.get("nombre_persona", "")).startswith("ALIAS")
        and any(_evidencia_pedido_explicito_obj_serializada(e)
                for e in (grupo.get("evidencias") or []))
    ]
    if personas_objeto_oficio and pendientes_relevantes:
        motivos.append("candidatos_con_identificador_descartados")

    # Una lista extensa (p. ej. 37 policias) requiere auditoria de cobertura.
    # Evaluamos cantidad de DNI en fragmentos vs. candidatos aceptados,
    # sin utilizar texto_completo ni inventar personas faltantes.
    fragmentos_unicos = {
        (e.get("contador_interno"), e.get("fragmento"))
        for p in personas_objeto_oficio + grupos_descartados
        for e in (p.get("evidencias") or [])
        if e.get("fragmento")
    }
    texto_fragmentos = "\n".join(f for _, f in fragmentos_unicos)
    hay_lista_enumerada = bool(re.search(r"(?m)^\s*1[.)]\s+.+?(?:DNI|CUIT)", texto_fragmentos, re.I)
                               and re.search(r"(?m)^\s*3[.)]\s+", texto_fragmentos))
    if re.search(r"\b(?:PERSONAL POLICIAL A VERIFICAR|PERSONAL SUJETO A RELEVAMIENTO|PERSONAS A VERIFICAR)\b", texto_fragmentos, re.I) or hay_lista_enumerada:
        dnis_en_lista = set(re.findall(r"\bDNI\s*(?:N[°ºo.]*)?\s*([0-9]{1,2}(?:\.[0-9]{3}){2})", texto_fragmentos, re.I))
        filas_enumeradas = len(re.findall(r"(?m)^\s*\d+[.)]\s+[A-ZÁÉÍÓÚÑ]", texto_fragmentos)) if hay_lista_enumerada else 0
        if max(len(dnis_en_lista), filas_enumeradas) > len(personas_objeto_oficio):
            motivos.append("lista_personas_cobertura_incompleta")

    # --------------------------------------------------------
    # 6. ANALISIS INDIVIDUAL DE PERSONAS
    # --------------------------------------------------------

    for index, persona in enumerate(
        personas_objeto_oficio,
        start=1,
    ):

        nombre = _texto_seguro(
            persona.get(
                "nombre_persona"
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
            and score_total < MIN_SCORE_EVIDENCIA_UNICA
            and not any(_evidencia_pedido_explicito_obj_serializada(e) for e in evidencias)
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

            if not tiene_contexto_positivo and not any(
                _evidencia_pedido_explicito_obj_serializada(e) for e in evidencias
            ):

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

    candidatos_incompletos = _registrar_candidatos_incompletos(documento)

    evidencias = _extraer_evidencias_documento(
        documento
    )

    _corregir_dni_ocr_inicial(evidencias)

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
        ) = _evaluar_grupo_oficio(
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

    # V12: conflicto del mismo nombre entre pedido explícito y evidencia
    # complementaria. No aplica a homónimos explícitos: esos conflictos
    # ya están marcados como no bloqueantes.
    for conflicto in conflictos:
        if (conflicto.get("tipo_conflicto") != "mismo_nombre_identificadores_distintos"
                or conflicto.get("conflicto_bloqueante") is False):
            continue
        prioridad = conflicto.get("priorizacion_evidencia", {})
        preferido = prioridad.get("grupo_preferente_para_revision")
        if preferido not in ("a", "b"):
            continue
        preferente = prioridad.get("grupo_" + preferido, {})
        otro = prioridad.get("grupo_" + ("b" if preferido == "a" else "a"), {})
        if not (preferente.get("prioridad", 0) >= 2 and otro.get("prioridad", 0) < 2):
            continue
        # No resolver si hay otras evidencias explícitas para el ID secundario.
        tipo = conflicto["tipo_identificador"]
        ids_descartar = set(conflicto["valores_b" if preferido == "a" else "valores_a"])
        posibles = [ev for ev in evaluaciones_grupos if
                    _identificadores_grupo(ev["grupo"])[tipo] == ids_descartar and
                    _nombres_equivalentes(_nombre_canonico(ev["grupo"]), conflicto["nombre_a"])]
        if len(posibles) != 1:
            continue
        posibles[0]["aceptado"] = False
        posibles[0]["motivos"] = ["identificador_contradictorio_evidencia_complementaria"]
        conflicto["conflicto_bloqueante"] = False
        conflicto["resolucion_conflicto"] = "prioridad_pedido_principal_con_alerta"
        prioridad["conflicto_pendiente"] = False
        prioridad["resolucion_automatica"] = True

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

    personas_objeto_oficio: list[
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

        personas_objeto_oficio.append(
            persona
        )

    if not personas_objeto_oficio:
        estado = ESTADO_NO_RESUELTO

    elif len(
        personas_objeto_oficio
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
            personas_objeto_oficio=(
                personas_objeto_oficio
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
        # SUFICIENCIA
        # ----------------------------------------------------

        "suficiente":
            suficiente,

        "requiere_fallback_documento_completo":
            not suficiente,

        "motivos_insuficiencia":
            motivos,

        # ----------------------------------------------------

        "cantidad_personas_objeto_oficio":
            len(
                personas_objeto_oficio
            ),

        "personas_objeto_oficio":
            personas_objeto_oficio,

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

        # Predicciones con identificador que no llegaron a agruparse
        # por no contar con un nombre util. Solo auditoria.
        "cantidad_candidatos_incompletos": len(candidatos_incompletos),
        "candidatos_incompletos": candidatos_incompletos,

        "requiere_revision":
            any(c.get("conflicto_bloqueante", True) or
                c.get("resolucion_conflicto") == "prioridad_pedido_principal_con_alerta"
                for c in conflictos),

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

        "total_personas_objeto_oficio":
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
            "total_personas_objeto_oficio"
        ] += int(
            resultado.get(
                "cantidad_personas_objeto_oficio",
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