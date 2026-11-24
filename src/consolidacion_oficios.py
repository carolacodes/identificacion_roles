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
    evidencias_independientes: int = 0



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
              r"n[uú]mero)?\s*(?:argentino|argentina)?\s*[:°º.]?\s*([0-9][0-9.\- ]{5,18}[0-9])")
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
    # Solicitudes policiales donde el verbo queda fuera del fragmento:
    # "información ... acerca del ciudadano NOMBRE, DNI ..."
    pedido_datos_ciudadano = bool(
        re.search(r"\b(?:informaci[oó]n|datos)\b.{0,110}\b(?:acerca\s+del\s+ciudadano|sobre\s+el\s+ciudadano)\s*$", antes, re.I)
        and re.search(r"^\s*[,;]?\s*D\.?\s*N\.?\s*I\.?\b", despues, re.I)
    )
    # Petición con sintaxis truncada: "a la mayor brevedad posible, NOMBRE DNI ..."
    # Exigir ventana específica y DNI literal, no solo una mención incidental.
    pedido_plataforma = bool(
        re.search(r"\ba\s+la\s+mayor\s+brevedad\s+posible\s*,?\s*$", antes, re.I)
        and re.search(r"^\s*DNI\s+nro\.?\s*\d", despues, re.I)
    )
    pedido_plataforma_persona = bool(
        re.search(r"\b(?:Mercado\s+Pago|Mercado\s+Libre)\s*:\s*$", antes, re.I)
        and re.search(r"^\s*[,;]?\s*D\.?\s*N\.?\s*I\.?\s*argentino\s+\d", despues, re.I)
        and re.search(r"\busuarios?\b", evidencia.fragmento[:ini], re.I)
    )
    return ((es_solicitud and es_objeto) or detalle_bancario or pedido_datos_ciudadano
            or pedido_plataforma or pedido_plataforma_persona)


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


def _evidencia_relacion_directa(e: Evidencia) -> bool:
    """V17.2: vínculo semántico LOCAL con la persona, no palabras sueltas.

    Se exige nombre y documento asociados en el fragmento; se reconocen
    estructuras generales que describen al sujeto de una operación/pedido.
    """
    if not _identificador_cerca_nombre(e) or _nombre_parcial_en_lista(e):
        return False
    pos = _buscar_posicion_nombre(e)
    if pos[0] is None:
        return False
    ini, fin = pos
    antes = _normalizar_texto(e.fragmento[max(0, ini-180):ini])
    despues = _normalizar_texto(e.fragmento[fin:fin+115])
    # Filtros contra menciones administrativas, incluso si tienen DNI.
    if re.search(r"\b(?:FIRMADO POR|AUTORIZAD[OA]S? (?:PARA|AL)|LETRADO PATROCINANTE)\b", antes[-100:]):
        return False
    relaciones = (
        # Operaciones realizadas POR la persona identificada; sujeto, no receptor.
        bool(re.search(r"\bPOR (?:EL |LA )?CIUDADAN[OA]\s*$", antes) and re.search(r"\bCVU\b", despues) and re.search(r"\bD N I\b|\bDNI\b", despues)),
        # Encabezado del requerimiento identificando al sujeto y sus datos.
        bool(re.search(r"\bRESPECTO (?:DE|DEL|A) (?:LA |EL )?(?:SENORA|SENOR|SRA|SR|PERSONA|CIUDADANO|CIUDADANA)\s*$", antes)
             and re.search(r"\b(?:DNI|D N I|CUIT|C U I T|CUIL|C U I L)\b", despues)
             and re.search(r"\b(?:LO SIGUIENTE|SE SOLICITA|INFORME|CUENTA|CUENTAS)\b", despues)),
        # Individualización del responsable de intereses/costas del proceso.
        bool(re.search(r"\b(?:INTERESES Y COSTAS|COSTAS E INTERESES) DEL JUICIO (?:AL|A LA) (?:SR|SRA|SENOR|SENORA)\s*$", antes)
             and re.search(r"\b(?:CUIT|CUIL|DNI)\b", despues)),
    )
    return any(relaciones) and not e.tercero_fuerte


def _grupo_evidencia_vinculante(grupo: GrupoPersona) -> bool:
    return any((_evidencia_pedido_explicito(e) or _evidencia_lista_explicita(e) or _pedido_comercial_fiscal_explicito(e) or _evidencia_relacion_directa(e))
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

    # Abogados individualizados como comparecientes en un acta; el CUIT
    # profesional NO convierte a esa persona en sujeto del requerimiento.
    posicion = _buscar_posicion_nombre(evidencia)
    if posicion[0] is not None:
        ini, fin = posicion
        previo = evidencia.fragmento[max(0, ini - 85):ini]
        posterior = evidencia.fragmento[fin:fin + 100]
        if (re.search(r"\b(?:las?\s+dras?\.?|los?\s+dres?\.?|abogad[oa]s?\s+|letrad[oa]s?\s+)", previo, re.I)
                and (re.search(r"\bM\.?\s*P\.?\s*\d+", posterior, re.I)
                     or re.search(r"\bM\.?\s*P\.?\s*\d+", evidencia.nombre, re.I))):
            return True, "profesional_interviniente_no_objeto_oficio"

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

# ============================================================
# V17.7 - CONTEXTO POSITIVO COMPLEMENTARIO (SOLO FRAGMENTOS)
# Detecta relaciones cercanas entre requerimiento, objeto e identidad.
# No reemplaza ni restringe la lógica anterior. La señal se añade
# únicamente si la puntuación contextual original no era positiva,
# hay un identificador local verificable y no se detectó un tercero.
# ============================================================

_V17_7_PATRONES={
 'posesion_registro': re.compile(r'\b(?:REGISTRA|REGISTRO|REGISTRADO|REGISTRADA|REGISTRAN|MANTIENE|MANTUVO|POSEE|POSEYO|DISPONE|DISPUSO|ES|FUE|RESULTA)\b.{0,52}\b(?:CUENTAS?|USUARIOS?|CLIENTES?|BILLETERAS?|PRODUCTOS?|TARJETAS?|PRESTAMOS?|CREDITOS?)\b.{0,45}\b(?:DE|DEL|A\s+NOMBRE\s+DE)\s*$',re.I),
 'cuentas_pertinencia':re.compile(r'\b(?:CUENTAS?|BILLETERAS?|SALDOS?|FONDOS?|PRODUCTOS?|TARJETAS?)\b.{0,65}\b(?:PERTENECIENTES?\s+A|DE\s+TITULARIDAD\s+DE|CORRESPONDIENTES?\s+A|A\s+NOMBRE\s+DE)\s*$',re.I),
 'operacion_autor':re.compile(r'\b(?:OPERACIONES?|TRANSFERENCIAS?|COMPRAS?|MOVIMIENTOS?|EXTRACCIONES?|DEPOSITOS?|ACREDITACIONES?)\b.{0,95}\b(?:REALIZAD[AO]S?|EFECTUAD[AO]S?|ORDENAD[AO]S?|PERCIBID[AO]S?)\s+POR\b\s*(?:EL|LA|LOS|LAS)?\s*(?:SR\.?|SRA\.?|CIUDADAN[OA]|SENOR|SENORA)?\s*$',re.I),
 'relacion_persona_pedido': re.compile(r'\b(?:REQUIERE|REQUIERA|REQUIRIO|SOLICITA|SOLICITO|INFORME|INFORMAR|DETALLE|IDENTIFIQUE|VERIFIQUE|REMlTA|PROPORCIONE)\b.{0,125}\b(?:RESPECTO\s+DE(?:L)?|ACERCA\s+DE(?:L)?|EN\s+RELACION\s+CON|SOBRE)\s+(?:LA|EL)?\s*(?:SRA\.?|SR\.?|SENOR[A]?|CIUDADAN[OA]|PERSONA|CONTRIBUYENTE)?\s*$',re.I),
 'consultado_enunciado':re.compile(r'\b(?:RESPECTO\s+DE(?:L)?|ACERCA\s+DE(?:L)?|EN\s+RELACION\s+CON)\s+(?:LA|EL)?\s*(?:SRA\.?|SR\.?|SENOR[A]?|CIUDADAN[OA]|IMPUTAD[OA]|CONTRIBUYENTE|ACCIONAD[OA])\s*$',re.I),
 'laboral_fiscal':re.compile(r'\b(?:HABERES|REMUNERACIONES|IMPORTE[S]?\s+FACTURADOS|FACTURACION|OPERACIONES\s+CONCERTADAS)\b.{0,85}\b(?:PERCIBID[AO]S?\s+POR|A\s+NOMBRE\s+DE|CON|A)\s*$',re.I),
}
_V17_7_PEDIDO=re.compile(r'\b(?:INFORME|INFORMAR|INFORMEN|SOLICITA|SOLICITO|SOLICITAR|REQUIERE|REQUIERA|REQUERIR|VERIFICAR|VERIFIQUE|IDENTIFICAR|IDENTIFIQUE|DETALLAR|DETALLE|REMITIR|REMITA|PROPORCIONAR|PROPORCIONE|DATOS|INFORMACION|OFICIO|LO\s+SIGUIENTE|EN\s+CUANTO\s+A)\b',re.I)
_V17_7_OBJETO=re.compile(r'\b(?:CUENTAS?|BILLETERAS?|SALDOS?|FONDOS?|MOVIMIENTOS?|OPERACIONES?|TRANSFERENCIAS?|COMPRAS?|DATOS|INFORMACION|FACTURACION|FACTURADOS?|HABERES?|REMUNERACIONES?|IDENTIDAD|TITULARIDAD|CREDITOS?|PRESTAMOS?|PRODUCTOS?)\b',re.I)
_V17_7_NEG=re.compile(r'\b(?:AUTORIZADOS?\s+(?:PARA|AL)|FIRMADO\s+POR|SECRETARI[OA]|JUEZ(?:A)?|LETRADO\s+PATROCINANTE|PERITO|PERITA|DILIGENCIAR)\b',re.I)

def _v17_7_relacion_contextual(e: Evidencia) -> str | None:
    pos=_buscar_posicion_nombre(e)
    if pos[0] is None or pos[1] is None:return None
    if _nombre_parcial_en_lista(e) or not _identificador_cerca_nombre(e):return None
    ini,fin=pos
    previo=_normalizar_texto(e.fragmento[max(0,ini-185):ini]); despues=_normalizar_texto(e.fragmento[fin:fin+115]); frag=_normalizar_texto(e.fragmento)
    if _V17_7_NEG.search(previo[-90:]):return None
    if not _V17_7_PEDIDO.search(frag) or not _V17_7_OBJETO.search(frag):return None
    # No atribuir la misma solicitud a cada participante de un pago con varias contrapartes
    if re.search(r'\b(?:TRANSFERENCIAS?|OPERACIONES?)\b',frag) and re.search(r'\b(?:CUENTA DE DESTINO|DESTINATARIO|TRABAJADORA)\b',frag):return None
    if any(_V17_7_PATRONES[k].search(previo) for k in _V17_7_PATRONES):
        return next(k for k in _V17_7_PATRONES if _V17_7_PATRONES[k].search(previo))
    return None



# V17.8: familias de contexto positivo para requerimientos, objetos e identidades.
# EXCLUSIVAMENTE fragmentos: requiere nombre+ID en la misma clausula.
# Una familia detectada no equivale a aceptar un candidato.
_V17_8_FAMILIAS = {
 'pedido_persona': [
  r'\b(?:SIRVASE|SIRVANSE|SOLICITA|SOLICITO|SE REQUIERE|SE REQUIERA|REMITA|REMITAN|DETALLE|HAGA SABER|INFORME|INFORMAR|IDENTIFIQUE|VERIFIQUE)\b.{0,105}\b(?:RESPECTO DE|RESPECTO DEL|ACERCA DE|ACERCA DEL|SOBRE|EN RELACION CON|CON RELACION A)\s+(?:(?:LA|EL|LAS|LOS)\s+)?(?:(?:SENORA?|SR|SRA|CIUDADAN[OA]|PERSONA|CONTRIBUYENTE|IMPUTAD[OA])\s*)?$',
  r'\b(?:RESPECTO|REFERENTE)\s+(?:DE|DEL|A)\s+(?:LA|EL)\s+(?:SENORA?|SR|SRA|CIUDADAN[OA]|CONTRIBUYENTE|IMPUTAD[OA])\s*$',
 ],
 'titularidad_productos': [
  r'\b(?:CUENTAS?|BILLETERAS?|SALDOS?|FONDOS?|PRODUCTOS?|TARJETAS?|PRESTAMOS?|CREDITOS?)\b.{0,72}\b(?:PERTENECIENTES? A|DE TITULARIDAD DE|CORRESPONDIENTES? A|A NOMBRE DE|REGISTRAD[AO]S? A NOMBRE DE)\s*$',
  r'\b(?:CLIENTE|USUARIO|TITULAR|COTITULAR)\s+(?:DE|DEL|DE LA|DE LAS)\s+(?:CUENTAS?|BILLETERAS?|PRODUCTOS?|SERVICIOS?)\s+(?:A NOMBRE DE|DE)\s*$',
 ],
 'registro_historico': [
  r'\b(?:REGISTRA|REGISTRO|REGISTRAN|REGISTRO O REGISTRA|MANTIENE|MANTUVO|POSEE|POSEYO|ES O FUE TITULAR)\b.{0,70}\b(?:CUENTAS?|BILLETERAS?|TARJETAS?|PRESTAMOS?|CREDITOS?|PRODUCTOS?)\b.{0,45}\b(?:A NOMBRE DE|DE TITULARIDAD DE|PERTENECIENTES? A|DE)\s*$',
 ],
 'operacion_sujeto': [
  r'\b(?:OPERACIONES?|COMPRAS?|MOVIMIENTOS?|EXTRACCIONES?|DEPOSITOS?|ACREDITACIONES?|TRANSFERENCIAS?)\b.{0,92}\b(?:REALIZAD[AO]S?|EFECTUAD[AO]S?|ORDENAD[AO]S?|PERCIBID[AO]S?|RECIBID[AO]S?)\s+POR\s+(?:(?:EL|LA)\s+)?(?:(?:CIUDADAN[OA]|SENOR[A]?|SR|SRA)\s*)?$',
 ],
 'comercial_fiscal_laboral': [
  r'\b(?:IMPORTES? FACTURADOS?|FACTURACION|OPERACIONES? CONCERTADAS|CONTRATOS? CELEBRADOS|HABERES|REMUNERACIONES)\b.{0,75}\b(?:A|CON|PERCIBID[AO]S? POR|A NOMBRE DE)\s*$',
  r'\b(?:FISCALIZACION|SITUACION FISCAL|INFORMACION TRIBUTARIA|REGISTROS? TRIBUTARIOS?)\b.{0,85}\b(?:RESPECTO DE|DE LA CONTRIBUYENTE|CORRESPONDIENTES? A)\s*$',
 ],
 'datos_identificacion': [
  r'\b(?:DATOS PERSONALES|DOMICILIO REGISTRADO|IDENTIFICACION|DATOS REGISTRADOS|INFORMACION)\b.{0,60}\b(?:CORRESPONDIENTES? A|RESPECTO DE|ACERCA DE|DE LA PERSONA|DEL CIUDADANO)\s*$',
 ],
}
_V17_8_FAMILIAS={k:tuple(re.compile(s,re.I) for s in v) for k,v in _V17_8_FAMILIAS.items()}
_V17_8_REQ=re.compile(r'\b(?:SOLICIT\w*|REQUER\w*|INFORM\w*|REMIT\w*|DETALL\w*|VERIFIC\w*|IDENTIFIC\w*|OFICIO|DATOS|INFORMACION|FACTURACION|FISCALIZACION)\b',re.I)
_V17_8_OBJ=re.compile(r'\b(?:CUENTAS?|BILLETERAS?|FONDOS?|SALDOS?|MOVIMIENTOS?|OPERACIONES?|TRANSFERENCIAS?|COMPRAS?|PRODUCTOS?|CREDITOS?|PRESTAMOS?|FACTURACION|FACTURADOS?|CONTRATOS?|HABERES?|REMUNERACIONES?|DATOS|INFORMACION|IDENTIFICACION|DOMICILIO|CONTRIBUYENTE|TRIBUTARI[AO]S?)\b',re.I)
_V17_8_NEG=re.compile(r'\b(?:FIRMADO POR|AUTORIZAD[OA]S? PARA|DILIGENCIAR|LETRAD[OA] PATROCINANTE|SECRETARI[OA]|JUEZ(?:A)?|PERIT[OA]|ABOGAD[OA]S? AUTORIZAD[OA]S?|APODERAD[OA]|EN REPRESENTACION DE|SUSCRIPTO POR)\b',re.I)
_V17_8_CONTRAPARTE=re.compile(r'\b(?:CUENTA DE DESTINO|DESTINATARIO|TRABAJADORA|RECEPTOR|BENEFICIARIO DE TRANSFERENCIA)\b',re.I)

def _v17_8_relacion_refuerzo(e: Evidencia) -> str | None:
    """Señal positiva contextual verificable, sin inferir desde texto_completo.

    Evita premiar firmas, autorizados, DNI de terceros y contrapartes
    ambiguas. Se mantiene el mismo detector ensayado sobre 120 documentos.
    """
    pos = _buscar_posicion_nombre(e)
    if pos[0] is None or pos[1] is None:
        return None
    ini, fin = pos
    antes = _normalizar_texto(e.fragmento[max(0, ini-200):ini])
    completo = _normalizar_texto(e.fragmento)
    tipos = [k for k, patrones in _V17_8_FAMILIAS.items()
             if any(p.search(antes) for p in patrones)]
    if not tipos:
        return None
    if not _identificador_cerca_nombre(e) or _nombre_parcial_en_lista(e):
        return None
    if _V17_8_NEG.search(antes[-95:]):
        return None
    posterior = _normalizar_texto(e.fragmento[fin:fin+115])
    # Un nombre repetido como firmante requiere revisión, no refuerzo.
    if re.search(r'\b(?:FIRMADO POR|SUSCRIPTO POR)\s+'
                 + re.escape(_normalizar_texto(e.nombre)) + r'\b', posterior):
        return None
    if not _V17_8_REQ.search(completo) or not _V17_8_OBJ.search(completo):
        return None
    # No premiar automáticamente a ambos participantes de una transferencia.
    if (re.search(r'\b(?:TRANSFERENCIAS?|OPERACIONES?)\b', completo)
            and _V17_8_CONTRAPARTE.search(completo)):
        return None
    return tipos[0]


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

    # V17.7: mantener la señal complementaria existente sin alterar sus reglas.
    v17_7_activada = False
    if score <= 0 and not evidencia.tercero_fuerte:
        if _v17_7_relacion_contextual(evidencia) is not None:
            score += 1.5
            v17_7_activada = True

    # V17.8: refuerzo contextual independiente (+1.5 por fragmento), incluso
    # si el candidato ya tenía contexto positivo. Nunca sumar dos veces por
    # la misma activación de V17.7 ni premiar terceros.
    if not evidencia.tercero_fuerte and not v17_7_activada:
        if _v17_8_relacion_refuerzo(evidencia) is not None:
            score += 1.5

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


def _recuperar_apellido_antes_nombre(fragmento: str, nombre: str, dni: str, cuit: str = "") -> str | None:
    """Recuperación literal de APELLIDO, NOMBRE ligada a DNI/CUIT/CUIL.

    Dos tokens son un nombre perfectamente válido: SOLO se amplía ante un
    apellido anterior explícito y un identificador inequívoco. No infiere.
    """
    if not fragmento or not nombre or not (dni or cuit):
        return None
    tokens = _tokens_nombre(nombre)
    if len(tokens) < 1:
        return None
    # El nombre debe corresponder exactamente a la porción posterior a la coma.
    patron = re.compile(
        r"(?<![\w])([A-ZÁÉÍÓÚÜÑ]{2,})\s*,\s*(" + re.escape(nombre) +
        r")\s*[,;:]?\s*\(?\s*(D\.?\s*N\.?\s*I\.?|C\.?\s*U\.?\s*I\.?\s*T\.?|C\.?\s*U\.?\s*I\.?\s*L\.?)"
        r"\s*(?:N[°ºo.]*(?:ro\.?)?|número)?\s*[:°º.\-]*\s*"
        r"([0-9][0-9.\- ]{5,18}[0-9])(?!\d)", re.I)
    coincidencias = []
    for m in patron.finditer(fragmento):
        tipo = _normalizar_texto(m.group(3))
        esperado = dni if tipo == 'D N I' or tipo == 'DNI' else cuit
        if not esperado or _normalizar_identificador(m.group(4)) != _normalizar_identificador(esperado):
            continue
        apellido = m.group(1)
        if not apellido.isupper() or _normalizar_texto(apellido) in {"SR", "SRA", "DNI", "DR", "DRA", "ACTOR", "ACTORA"}:
            continue
        coincidencias.append(m)
    if len(coincidencias) != 1:
        return None
    m = coincidencias[0]
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


def _v17_razon_social_local(fragmento: str, cuit: str) -> str | None:
    """Recupera razón social solo de una cláusula de pedido explícito.

    No confunde enumeraciones de destinatarios ('líbrense oficios a...')
    con personas jurídicas objeto de la consulta.
    """
    if not fragmento or not cuit:
        return None
    patron = re.compile(
        r"\b(?:CON|RESPECTO\s+DE|SOBRE|DE\s+LA\s+EMPRESA|DE\s+LA\s+FIRMA)\s+"
        r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ0-9. &'\-]{3,90}?\s+"
        r"(?:S\.?\s*A\.?\s*S\.?|S\.?\s*R\.?\s*L\.?|S\.?\s*A\.?))"
        r"\s*[,;:]?\s*\(?\s*C\.?\s*U\.?\s*I\.?\s*T\.?"
        r"\s*[:N°ºo.\- ]*\s*([0-9][0-9.\- ]{9,17}[0-9])", re.I)
    hallazgos = []
    for m in patron.finditer(fragmento):
        if _normalizar_identificador(m.group(2)) != _normalizar_identificador(cuit):
            continue
        prev = _normalizar_texto(fragmento[max(0,m.start()-140):m.start()])
        if not re.search(r"\b(?:INFORME|INFORMAR|SOLICITA|SOLICITAR|REQUIERE)\b", prev):
            continue
        nom = m.group(1).strip()
        if _nombre_tiene_estructura_valida(nom):
            hallazgos.append(nom)
    return hallazgos[0] if len(hallazgos) == 1 else None


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
            recuperacion_general = _v17_razon_social_local(fragmento, cuit)
            if recuperacion_general:
                c['nombre_persona'] = recuperacion_general
                c['nombre_persona_confidence'] = None
                c['origen_recuperacion_v12'] = 'razon_social_cuit_pedido_local_v17'
                nombre = recuperacion_general
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
                m=re.match(r"\s*[,;:]?\s*\(?\s*D\.?\s*N\.?\s*I\.?\s*(?:argentino|argentina)?\s*[-: ]\s*(\d{1,2}(?:[. -]?\d{3}){2})\b", tramo, re.I)
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
            recuperado = _recuperar_apellido_antes_nombre(fragmento, nombre, dni_candidato, _texto_seguro(candidate.get("cuit_cuil_persona") or candidate.get("cuil_cuit")))
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

        # Se puntuan todas las predicciones para conservar diagnostico,
        # pero el score se agrega por fragmento/identidad SOLO una vez.
        _score_evidencia(evidencia)

    for grupo in grupos:
        por_fragmento: dict[tuple[str, str], list[Evidencia]] = defaultdict(list)
        for e in grupo.evidencias:
            por_fragmento[(str(e.contador_interno), e.fragmento)].append(e)
        grupo.evidencias_independientes = len(por_fragmento)
        grupo.score_total = sum(max(_score_evidencia(e) for e in items)
                                for items in por_fragmento.values())
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


def _dni_ocr_malformado_en_grupo(grupo: GrupoPersona) -> str | None:
    """Detecta DNI literal de 9 dígitos local al nombre, sin transformarlo."""
    for e in grupo.evidencias:
        pos = _buscar_posicion_nombre(e)
        if not pos:
            continue
        tramo = e.fragmento[pos[1]:pos[1] + 65]
        m = re.match(r"\s*[,;:]?\s*D\.?N\.?I\.?\s*:?\s*([0-9][0-9. ]{6,14})", tramo, re.I)
        if m:
            raw = m.group(1).strip().rstrip('.')
            if len(re.sub(r"\D", "", raw)) == 9:
                return raw
    return None


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
        dni_malformado = _dni_ocr_malformado_en_grupo(grupo)
        if dni_malformado and not tercero_fuerte and (
            tiene_contexto or any(re.search(r"\b(?:solicito|informar|informe)\b", e.fragmento, re.I)
                                  for e in grupo.evidencias)
        ):
            detalle["dni_ocr_original_no_validado"] = dni_malformado
            detalle["requiere_revision_manual"] = True
            return True, ["aceptacion_provisional_dni_ocr_malformado"], detalle
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


def _auditar_roles_contextuales(grupo: GrupoPersona) -> dict[str, Any]:
    """V17.4: conserva el rol de GLiNER y evidencia discrepancias textuales.

    No sobreescribe el rol original ni inventa uno en ausencia de frase
    inequívoca junto al nombre. Auditoría separada de la decisión de sujeto.
    """
    roles = set()
    for e in grupo.evidencias:
        pos = _buscar_posicion_nombre(e)
        if pos[0] is None:
            continue
        previo = _normalizar_texto(e.fragmento[max(0, pos[0]-65):pos[0]])
        m = re.search(r"\b(?:EL|LA|LOS|LAS|SR|SRA|SENOR|SENORA)?\s*"
                      r"(ACCIONAD[OA]|DEMANDAD[OA]|ACTOR|ACTORA|EMBARGAD[OA]|"
                      r"CAUSANTE|EJECUTAD[OA]|IMPUTAD[OA])\s*(?:SR|SRA|SENOR|SENORA)?\s*$", previo)
        if m:
            r = m.group(1).lower()
            if r in ('accionado','accionada'):
                r = 'demandado' if r == 'accionado' else 'demandada'
            roles.add(r)
    modelo = _roles_normalizados_grupo(grupo)
    pares_opuestos = ({'actor','actora'}, {'demandado','demandada'})
    contradiccion = bool(roles and any(
        ((r in pares_opuestos[0] and modelo & pares_opuestos[1]) or
         (r in pares_opuestos[1] and modelo & pares_opuestos[0]))
        for r in roles))
    return {'roles_validados_fragmento': sorted(roles),
            'roles_originales_gliner': sorted(modelo),
            'contradiccion_rol_gliner': contradiccion}


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
        **_auditar_roles_contextuales(grupo),

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
        "cantidad_evidencias_independientes": grupo.evidencias_independientes,

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
        # Un profesional descartado con evidencia contextual firme no es
        # una identidad pendiente. Otros descartes sí siguen bloqueando.
        and not ("tercero_fuerte" in (grupo.get("decision_consolidacion", {}).get("motivos") or [])
                 and any(e.get("motivo_tercero") == "profesional_interviniente_no_objeto_oficio"
                         for e in (grupo.get("evidencias") or [])))
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
            persona.get("cantidad_evidencias_independientes",
                        persona.get("cantidad_evidencias", 0))
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
# V17.6: recuperación provisional de campos de identidad estructurados
# Solo se buscan campos literales en fragmentos que GLiNER procesó.
# No confundir datos útiles con sujeto del oficio confirmado.
# ============================================================

def _recuperar_identidades_estructuradas_revision(documento: dict[str, Any]) -> list[dict[str, Any]]:
    """Recupera Nombre/Apellido/ID del mismo registro, sin inferencias externas.

    Solo acepta registros delimitados y con campos explícitos en orden;
    no convierte estas identidades en personas aceptadas automáticamente.
    """
    patron = re.compile(
        r"\bNombre\s*:\s*(?P<nombre>[^\r\n]{1,100}?)"
        r"\s+-\s+Apellido\s*:\s*(?P<apellido>[^\r\n]{1,100}?)"
        r"\s+-\s+Tipo\s+de\s+Documento\s*:\s*(?P<tipo>DNI|CUIT|CUIL)"
        r"\s+-\s+(?:N[uú]mero\s+de\s+documento|Nro\.?\s+de\s+documento)\s*:\s*(?P<id>[0-9.\- ]{7,18})(?=\s+-\s+|\s*$)",
        re.I,
    )
    encontrados = {}
    for resultado in documento.get('resultados', []) or []:
        fragmento = _texto_seguro(resultado.get('fragmento') or resultado.get('texto_entrada_modelo'))
        if not fragmento:
            continue
        for m in patron.finditer(fragmento):
            nombre, apellido = m.group('nombre').strip(), m.group('apellido').strip()
            tipo, identificador = m.group('tipo').upper(), m.group('id').strip()
            if not nombre or not apellido or not re.fullmatch(r"[\wÁÉÍÓÚÜÑáéíóúüñ .'-]{2,100}", nombre + ' ' + apellido):
                continue
            digits = _normalizar_identificador(identificador)
            if (tipo == 'DNI' and len(digits) not in (7, 8)) or (tipo in ('CUIT','CUIL') and len(digits) != 11):
                continue
            denominacion = f'{nombre} {apellido}'
            if not _nombre_tiene_estructura_valida(denominacion):
                continue
            clave = (_normalizar_texto(denominacion), tipo, digits)
            if clave not in encontrados:
                encontrados[clave] = {
                    'nombre_persona': denominacion,
                    'dni_persona': identificador if tipo == 'DNI' else '',
                    'cuit_cuil_persona': identificador if tipo in ('CUIT','CUIL') else '',
                    'tipo_identificador': tipo,
                    'tipo_identidad': 'NO_DETERMINADO',
                    'estado_validacion_identidad': 'REQUIERE_REVISION_MANUAL',
                    'origen_recuperacion': 'campos_estructurados_en_fragmento',
                    'motivo_revision': 'Registro de identidad recuperado; falta verificar el alcance del pedido y la naturaleza de la identidad',
                    'fragmentos_soporte': [{'contador_interno': resultado.get('contador_interno'), 'fragmento': fragmento}],
                }
            else:
                encontrados[clave]['fragmentos_soporte'].append({'contador_interno': resultado.get('contador_interno'), 'fragmento': fragmento})
    return list(encontrados.values())


# ============================================================
# CONSOLIDAR DOCUMENTO
# ============================================================

def consolidar_documento(
    documento: dict[str, Any],
) -> dict[str, Any]:

    candidatos_incompletos = _registrar_candidatos_incompletos(documento)
    identidades_estructuradas = _recuperar_identidades_estructuradas_revision(documento)

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

    # Diagnóstico legible separado de la clasificación histórica de suficiencia.
    fragmentos_utiles = [r for r in (documento.get("resultados") or [])
                        if _texto_seguro(r.get("fragmento") or r.get("texto_entrada_modelo"))]
    revision_motivos = []
    if not fragmentos_utiles:
        revision_motivos.append(("sin_fragmentos_para_gliner",
           "No se generaron fragmentos de entrada para GLiNER2. La ausencia de predicciones no demuestra que el oficio carezca de personas; revisar el texto completo y el proceso de fragmentación."))
    for persona in personas_objeto_oficio:
        d = persona.get("decision_consolidacion", {}).get("detalle", {})
        if d.get("requiere_revision_manual"):
            persona["identificador_pendiente_validacion"] = d.get("dni_ocr_original_no_validado")
            persona["estado_validacion_identidad"] = "PROVISIONAL_REQUIERE_REVISION_MANUAL"
            revision_motivos.append(("dni_ocr_malformado",
               "Se detectó la persona objeto del oficio, pero el DNI textual tiene 9 dígitos. Identidad provisional: comprobar el DNI contra el documento original; no enviar el identificador a producción sin validación."))
    if not personas_objeto_oficio and fragmentos_utiles and not grupos_descartados:
        revision_motivos.append(("sin_candidatos_en_fragmentos",
          "GLiNER2 no produjo identidades útiles en los fragmentos disponibles; revisar el texto completo y el alcance del pedido."))
    if not personas_objeto_oficio and grupos_descartados and fragmentos_utiles:
        revision_motivos.append(("candidatos_descartados",
           "GLiNER2 detectó candidatos, pero la consolidación no aceptó ninguno. Revisar el pedido principal, los identificadores y los motivos individuales de descarte."))
    if not personas_objeto_oficio and not fragmentos_utiles:
        revision_motivos.append(("verificar_objeto_del_pedido",
           "Determinar manualmente si el oficio requiere datos de personas identificadas o si solicita otra información, como autenticidad de comprobantes."))
    if any(p.get("estado_validacion_identidad") == "PROVISIONAL_REQUIERE_REVISION_MANUAL" for p in personas_objeto_oficio):
        suficiente = False
        motivos = list(dict.fromkeys(motivos + ["dni_ocr_malformado_revision_manual"]))
    # Los registros estructurados pueden aportar información útil sin demostrar
    # que sus titulares sean los sujetos consultados por el oficio.
    if identidades_estructuradas:
        revision_motivos.append(("identidades_estructuradas_pendientes",
          "Se recuperaron campos identificatorios desde fragmentos estructurados; comprobar identidad y alcance del requerimiento."))
        suficiente = False
        motivos = list(dict.fromkeys(motivos + ["identidades_estructuradas_requieren_revision_manual"]))
    # Una aceptación provisional no equivale a identidad verificada.
    revision_manual = bool(revision_motivos) or any(
        c.get("conflicto_bloqueante", True) or c.get("resolucion_conflicto") == "prioridad_pedido_principal_con_alerta"
        for c in conflictos)
    return {
        "revision_manual_motivos": [{"codigo": k, "descripcion": v} for k,v in revision_motivos],
        "revision_manual_descripcion": " ".join(v for _,v in revision_motivos),
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
        "identidades_recuperadas_revision_manual": identidades_estructuradas,
        "cantidad_identidades_recuperadas_revision_manual": len(identidades_estructuradas),

        "requiere_revision": revision_manual,

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

# ============================================================
# EXTENSION INTERNACIONAL V15 (CHILE Y URUGUAY)
# Métodos nuevos; las reglas anteriores permanecen intactas.
# La fuente complementaria es opcional; también acepta un único JSON.
# ============================================================

import copy

# Guardar la consolidacion historica SIN MODIFICAR su implementacion.
_consolidar_documentos_argentinos = consolidar_documentos

_int_RUT = re.compile(r'\b(?:RUT|RUN)\s*[:Nº°\.]*\s*(\d{1,2}[. ]?\d{3}[. ]?\d{3}\s*[-–]\s*[\dKk])\b', re.I)
# C.I., C.I:, CI:, C.I .; exige marcador explícito seguido de número.
_int_CI = re.compile(r'(?<![A-Za-z])C\s*\.?\s*I\s*\.?\s*[:.]?\s*(\d[. ]?\d{3}[. ]?\d{3}\s*[-–]\s*\d)\b', re.I)


def _int_normalizar(s: str) -> str:
    s = ''.join(c for c in unicodedata.normalize('NFD', str(s or '')) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s).strip().upper()


def _int_nombre(s: str) -> str:
    return re.sub(r'^(?:DON|DOÑA|DONA|SR\.?|SRA\.?)\s+', '', _int_normalizar(s))


def _int_nombre_visible(s: str) -> str:
    return re.sub(r'^(?:don|doña|sr\.?|sra\.?)\s+', '', str(s).strip(), flags=re.I)


def _int_rut_valido(s: str) -> bool:
    s = re.sub(r'[^0-9K]', '', s.upper())
    if not re.fullmatch(r'\d{7,8}[0-9K]', s):
        return False
    total = sum(int(d) * [2, 3, 4, 5, 6, 7][i % 6] for i, d in enumerate(s[-2::-1]))
    resto = 11 - total % 11
    esperado = '0' if resto == 11 else 'K' if resto == 10 else str(resto)
    return s[-1] == esperado


def _int_ci_uy_valida(s: str) -> bool:
    s = re.sub(r'\D', '', s)
    if len(s) not in (7, 8):
        return False
    s = s.zfill(8)
    total = sum(int(d) * w for d, w in zip(s[:7], [2, 9, 8, 7, 6, 3, 4]))
    return (10 - total % 10) % 10 == int(s[-1])


def _int_candidatos_gliner(documento: dict[str, Any]) -> list[dict[str, Any]]:
    candidatos = []
    for res in documento.get('resultados', []):
        frag = res.get('fragmento') or res.get('texto_entrada_modelo') or ''
        for can in res.get('candidates', []):
            nombre = can.get('nombre_persona') or (can.get('fields', {}).get('nombre_persona') or {}).get('text')
            if nombre and len(_int_nombre(nombre).split()) >= 2:
                candidatos.append({'nombre': nombre, 'fragmento': frag,
                    'palabra_clave': res.get('palabra_clave', ''),
                    'contador_interno': res.get('contador_interno', ''),
                    'confianza': can.get('nombre_persona_confidence')})
    return candidatos


def _int_buscar_identificador_local(nombre: str, fragmento: str, patron: re.Pattern) -> str | None:
    """Solo asociar un ID explícitamente junto a ese nombre, nunca al siguiente."""
    # Nombres detectados están literalmente en fragmento (quitamos DON/SR para matching).
    n = _int_nombre(nombre)
    frag_norm = _int_normalizar(fragmento)
    inicio = frag_norm.find(n)
    if inicio < 0:
        return None
    # Ignora ID antecedente de otra persona, sólo próximos 35 caracteres.
    siguiente = frag_norm[inicio + len(n):inicio + len(n) + 65]
    m = patron.search(siguiente)
    if not m or m.start() > 30:
        return None
    return m.group(1).replace(' ', '').replace('–', '-')


def _int_pedido_general_fragmento(fragmento: str, nombre: str) -> bool:
    """Pedido internacional genérico; no infiere país, banco ni identidad.

    Evita nombres administrativos y solo reconoce cláusulas próximas que
    introducen solicitud relacionada directamente con el sujeto nombrado.
    """
    t = _int_normalizar(fragmento)
    n = _int_nombre(nombre)
    pos = t.find(n)
    if pos < 0:
        return False
    antes = t[max(0,pos-135):pos]
    despues = t[pos+len(n):pos+len(n)+110]
    if re.search(r"(?:FIRMADO POR|AUTORIZADO PARA|AUTORIZADA PARA|PERITO|PERITA)\s*$", antes):
        return False
    # Solicitud dirigida a la persona consultada (no a una marca específica).
    return bool(re.search(r"(?:INFORME|INFORMAR|INFORMEN|SOLICITAR|REQUIERE)\b.{0,110}(?:RESPECTO DE|SOBRE|ACERCA DE|DE LAS CUENTAS DE)\s*$", antes)
                and re.search(r"\b(?:RUT|RUN|C\.?I\.?)\b", despues))


def _int_contexto_chile_fragmento(fragmento: str, nombre: str) -> tuple[bool, bool, str]:
    """Analiza EXCLUSIVAMENTE el fragmento del candidato.

    Retorna (objeto_potencial, pedido_mercadopago_confirmado, motivo).
    Una parte demandada no demuestra por sí sola el destinatario del oficio.
    """
    t = _int_normalizar(fragmento)
    n = _int_nombre(nombre)
    pos = t.find(n)
    if pos < 0:
        return False, False, 'nombre_fuera_del_fragmento'
    previo = t[max(0, pos - 180):pos]
    # Confirmación acotada al fragmento y a la cláusula pertinente.
    mp = bool(re.search(r'MERCADO\s*PAGO', previo))
    pedido = bool(re.search(r'\b(?:INFORME|INFORMAR|INFORMEN|SOLICIT|OFICIO)\w*\b', previo))
    if mp and pedido:
        return True, True, 'requerimiento_mercadopago_en_fragmento'
    # Información inequívoca de la parte investigada, pero no del destinatario.
    if re.search(r'PARTE\s+DEMANDADA\s+COMPARECIENTE\s*$', previo):
        return True, False, 'parte_demandada_sin_destinatario_verificado'
    return False, False, 'sin_requerimiento_mercadopago_en_fragmento'


def _int_pedidos_uruguay(fragmento: str) -> bool:
    n = _int_normalizar(fragmento)
    return 'DE LAS PERSONAS:' in n and any(w in n for w in ('CREDITOS', 'CUENTAS', 'TRANSFERENCIAS'))


def _int_es_perito(fragmento: str, nombre: str) -> bool:
    n = _int_nombre(nombre)
    t = _int_normalizar(fragmento)
    ix = t.find(n)
    return ix >= 0 and bool(re.search(r'\bPERITA?\b|TRABAJADORA SOCIAL', t[max(0, ix-90):ix]))


def _int_nueva_persona(nombre: str, identificador: str, pais: str, tipo: str,
                   soportes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'nombre_persona': nombre, 'dni_persona': '', 'cuit_cuil_persona': '',
        'pais_identificador': pais, 'tipo_identificador': tipo,
        'identificador_extranjero': identificador,
        'identificador_validado': True, 'roles_detectados': [],
        'variantes_nombre': [nombre],
        'cantidad_fragmentos_soporte': len(set(s['contador_interno'] for s in soportes)),
        'cantidad_evidencias': len(soportes), 'score_total': None,
        'identidad_inconsistente': False,
        'evidencias': [{
            'tipo_entrada': 'fragmento_internacional',
            'contador_interno': s['contador_interno'], 'palabra_clave': s['palabra_clave'],
            'nombre_detectado': nombre, 'nombre_confidence': s['confianza'],
            'identificador_extranjero_detectado': identificador,
            'fragmento': s['fragmento'], 'origen_recuperacion': 'identificador_extranjero_local',
        } for s in soportes],
        'decision_consolidacion': {
            'aceptado': True,
            'motivos': ['identificador_extranjero_validado', 'requerimiento_explicito_verificado'],
            'detalle': {'metodo': 'recuperacion_internacional_aislada', 'pais': pais}
        }
    }


def _int_recuperar_personas_internacionales(documento: dict[str, Any]) -> dict[str, Any]:
    """Solo fragmentos y candidatos GLiNER; nunca consulta texto_completo."""
    resultados = documento.get('resultados') or []
    cands = _int_candidatos_gliner(documento)
    # País sustentado por los fragmentos, nunca por el documento completo.
    hay_rut = any((str(r.get('palabra_clave') or '').upper() in ('RUT', 'RUN'))
                  and _int_RUT.search(str(r.get('fragmento') or r.get('texto_entrada_modelo') or ''))
                  for r in resultados)
    hay_ci_lista = any((str(r.get('palabra_clave') or '').upper() == 'CI')
                       and _int_CI.search(str(r.get('fragmento') or r.get('texto_entrada_modelo') or ''))
                       and _int_pedidos_uruguay(str(r.get('fragmento') or r.get('texto_entrada_modelo') or ''))
                       for r in resultados)
    # No inferir Uruguay solo de una aparición de CI; no mezclar con RUT.
    chile = bool(hay_rut)
    uruguay = bool(hay_ci_lista) and not chile
    agrupados: dict[tuple[str, str, str], list] = defaultdict(list)
    motivos_por_clave: dict[tuple[str, str, str], dict[str, Any]] = {}
    rechazados: dict[tuple[str, str, str], dict] = {}
    observaciones: list[str] = []

    for c in cands:
        clave = (c['palabra_clave'] or '').upper()
        frag = c['fragmento']
        nombre = _int_nombre(c['nombre'])
        if chile and clave in {'RUT', 'RUN'}:
            ident = _int_buscar_identificador_local(c['nombre'], frag, _int_RUT)
            if not ident:
                continue
            pais, tipo = 'CL', 'RUT'
            valido = _int_rut_valido(ident)
            objeto, pedido_confirmado, motivo = _int_contexto_chile_fragmento(frag, c['nombre'])
            if not objeto and _int_pedido_general_fragmento(frag, c['nombre']):
                objeto, pedido_confirmado, motivo = True, True, 'requerimiento_general_en_fragmento'
            if _int_es_perito(frag, c['nombre']):
                objeto, pedido_confirmado, motivo = False, False, 'perito_no_objeto_oficio'
        elif uruguay and clave == 'CI':
            ident = _int_buscar_identificador_local(c['nombre'], frag, _int_CI)
            if not ident:
                continue
            pais, tipo = 'UY', 'CI'
            valido = _int_ci_uy_valida(ident)
            pedido_confirmado = _int_pedidos_uruguay(frag)
            objeto = pedido_confirmado
            motivo = 'requerimiento_lista_personas_en_fragmento' if objeto else 'sin_contexto_pedido_explicito'
        else:
            continue

        key = (nombre, ident, pais)
        if not valido:
            objeto = False
            motivo = 'identificador_extranjero_digito_verificador_invalido'
            observaciones.append(f'{nombre}: identificador {tipo} {ident} no supera validación')
        if not objeto:
            rechazados[key] = {
                'nombre_persona': nombre, 'tipo_identificador': tipo,
                'pais_identificador': pais, 'identificador_extranjero': ident,
                'decision_consolidacion': {'aceptado': False, 'motivos': [motivo]},
            }
            continue
        agrupados[key].append(c)
        motivos_por_clave[key] = {'pedido_confirmado': pedido_confirmado, 'motivo': motivo}

    aceptadas = []
    for (nombre, ident, pais), soportes in agrupados.items():
        p = _int_nueva_persona(_int_nombre_visible(soportes[0]['nombre']).upper(), ident,
                              pais, 'RUT' if pais == 'CL' else 'CI', soportes)
        info = motivos_por_clave[(nombre, ident, pais)]
        if info['pedido_confirmado']:
            p['decision_consolidacion']['motivos'] = [
                'identificador_extranjero_validado', 'requerimiento_explicito_en_fragmento']
        else:
            p['decision_consolidacion']['motivos'] = [
                'identificador_extranjero_validado', 'objeto_potencial_sin_destinatario_confirmado']
            p['estado_validacion_identidad'] = 'PENDIENTE_VERIFICACION_PEDIDO'
            p['requiere_revision'] = True
        aceptadas.append(p)

    por_nombre: dict[str, set] = defaultdict(set)
    for p in aceptadas:
        por_nombre[_int_nombre(p['nombre_persona'])].add(p['identificador_extranjero'])
    conflictos = {n for n, ids in por_nombre.items() if len(ids) > 1}
    if conflictos:
        aceptadas = [p for p in aceptadas if _int_nombre(p['nombre_persona']) not in conflictos]
        observaciones.extend(f'{n}: identificadores extranjeros contradictorios' for n in sorted(conflictos))
    return {'personas': aceptadas, 'descartados': list(rechazados.values()),
            'alertas': observaciones, 'pais': 'CL' if chile else 'UY' if uruguay else None}


def _int_unificar_resultado(resultado: dict[str, Any], recuperacion: dict[str, Any]) -> dict[str, Any]:
    """Unifica una sola vez cada identidad, sin alterar las reglas V14."""
    nuevo = copy.deepcopy(resultado)
    personas = list(nuevo['personas_objeto_oficio'])
    descartados = list(nuevo['grupos_descartados'])
    extranjeras = recuperacion['personas']
    rechazadas = recuperacion['descartados']
    claves_int = {_int_nombre(p['nombre_persona']) for p in extranjeras + rechazadas}

    # Remover el diagnóstico argentino anterior SOLAMENTE para identidades
    # que el módulo internacional volvió a evaluar con identificador propio.
    descartados = [p for p in descartados if _int_nombre(p.get('nombre_persona', '')) not in claves_int]
    aceptados_norm = {_int_nombre(p.get('nombre_persona', '')) for p in personas}
    for p in extranjeras:
        clave = _int_nombre(p['nombre_persona'])
        if clave not in aceptados_norm:
            personas.append(p)
            aceptados_norm.add(clave)
    descartados.extend(p for p in rechazadas
                       if _int_nombre(p['nombre_persona']) not in aceptados_norm)

    nuevo['personas_objeto_oficio'] = personas
    nuevo['grupos_descartados'] = descartados
    nuevo['cantidad_personas_objeto_oficio'] = len(personas)
    nuevo['cantidad_grupos_descartados'] = len(descartados)
    nuevo['cantidad_grupos_candidatos'] = len(personas) + len(descartados)
    nuevo['estado'] = (ESTADO_NO_RESUELTO if not personas else
                      ESTADO_RESUELTO if len(personas) == 1 else ESTADO_RESUELTO_MULTIPLE)
    pendientes = [p for p in extranjeras if p.get('requiere_revision')]
    alertas = recuperacion['alertas']
    nuevo['recuperacion_internacional'] = {
        'pais': recuperacion['pais'],
        'origen': 'exclusivamente_fragmentos_gliner2',
        'uso_texto_completo': False,
        'cantidad_recuperadas': len(extranjeras),
        'cantidad_terceros_o_no_solicitados': len(rechazadas),
        'alertas': alertas,
    }
    if pendientes or alertas:
        # Si el fragmento no incluye el pedido a Mercado Pago, no afirmar
        # suficiencia. El proceso posterior podrá decidir la revisión.
        nuevo['suficiente'] = False
        nuevo['requiere_fallback_documento_completo'] = True
        motivo = ('destinatario_no_verificado_en_fragmentos' if pendientes else
                  'identificador_extranjero_requiere_revision')
        nuevo['motivos_insuficiencia'] = list(dict.fromkeys(nuevo['motivos_insuficiencia'] + [motivo]))
        nuevo['requiere_revision'] = True
        descripcion = ('Se recuperó nombre y RUT desde un fragmento, pero el fragmento no contiene el pedido específico a Mercado Pago. Revisar el destinatario antes de dar por suficiente el resultado.'
                       if pendientes else 'Se detectaron identificadores extranjeros inválidos o contradictorios; revisar.')
        anteriores = [m for m in nuevo.get('revision_manual_motivos', [])
                      if m.get('codigo') not in {'sin_fragmentos_para_gliner', 'verificar_objeto_del_pedido', 'candidatos_descartados', 'sin_candidatos_en_fragmentos'}]
        nuevo['revision_manual_motivos'] = anteriores + [{'codigo': motivo, 'descripcion': descripcion}]
        nuevo['revision_manual_descripcion'] = ' '.join(m['descripcion'] for m in nuevo['revision_manual_motivos'])
    elif personas and not nuevo.get('conflictos_identificador'):
        nuevo['suficiente'] = True
        nuevo['requiere_fallback_documento_completo'] = False
        nuevo['motivos_insuficiencia'] = []
        nuevo['requiere_revision'] = False
        nuevo['revision_manual_motivos'] = []
        nuevo['revision_manual_descripcion'] = ''
    return nuevo


def _consolidar_documentos_con_fuente_internacional(documentos_originales: list[dict[str, Any]],
                            documentos_internacionales: list[dict[str, Any]] | None = None
                           ) -> list[dict[str, Any]]:
    """V14 intacta en los documentos sin evidencia internacional."""
    resultados = _consolidar_documentos_argentinos(documentos_originales)
    if not documentos_internacionales:
        return resultados
    extra_por_id = {str(d.get('id')): d for d in documentos_internacionales}
    for i, resultado in enumerate(resultados):
        internacional = extra_por_id.get(str(resultado.get('id')))
        if internacional is None:
            continue
        recuperacion = _int_recuperar_personas_internacionales(internacional)
        if not recuperacion['personas'] and not recuperacion['descartados'] and not recuperacion['alertas']:
            continue
        resultados[i] = _int_unificar_resultado(resultado, recuperacion)
    return resultados



def consolidar_documentos(
    documentos: list[dict[str, Any]],
    documentos_internacionales: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Consolida oficios; detección internacional solo desde fragmentos.

    Se puede pasar un JSON internacional único o la fuente complementaria.
    Nunca inspecciona texto_completo para decisiones internacionales.
    """
    if documentos_internacionales is not None:
        # Modalidad complementaria existente: JSON original + JSON internacional.
        return _consolidar_documentos_con_fuente_internacional(
            documentos, documentos_internacionales
        )

    # Modalidad de prueba con UN SOLO JSON de predicciones internacionales.
    # El despachador solo reconoce fragmentos realmente etiquetados con
    # identificadores internacionales. Una coincidencia de 'CI' dentro de
    # palabras comunes NO activa la rama internacional.
    hay_fragmentos_internacionales = any(
        (
            (str(r.get('palabra_clave') or '').upper() in {'RUT', 'RUN'}
             and _int_RUT.search(str(r.get('fragmento') or r.get('texto_entrada_modelo') or '')))
            or
            (str(r.get('palabra_clave') or '').upper() == 'CI'
             and _int_CI.search(str(r.get('fragmento') or r.get('texto_entrada_modelo') or '')))
        )
        for doc in documentos
        for r in (doc.get('resultados') or [])
    )
    if hay_fragmentos_internacionales:
        # El mismo JSON alimenta las reglas existentes y la recuperación
        # especializada: no requiere cambiar el ejecutor de consola.
        return _consolidar_documentos_con_fuente_internacional(documentos, documentos)
    return _consolidar_documentos_argentinos(documentos)
