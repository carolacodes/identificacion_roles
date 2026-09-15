"""Consolidacion de candidatos a persona embargada por documento.

Este modulo recibe predicciones realizadas sobre fragmentos y consolida
los candidatos encontrados para cada numero_archivo.

Objetivo principal:
    resolver un unico nombre_embargado por documento a partir de la
    evidencia obtenida en multiples fragmentos.

Principios:
- un fragmento individual puede no contener el nombre;
- el resultado final se obtiene utilizando todos los fragmentos del documento;
- se prioriza evidencia repetida y contextual;
- no se inventan nombres cuando no existe evidencia;
- si no puede resolverse el nombre, el documento queda como NO_RESUELTO;
- se conserva trazabilidad de que fragmentos respaldaron la decision.

Este modulo NO realiza inferencia con GLiNER.
Solo consolida resultados que ya fueron extraidos previamente.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any


# ---------------------------------------------------------------------------
# Estados finales
# ---------------------------------------------------------------------------

ESTADO_RESUELTO = "RESUELTO"
ESTADO_NO_RESUELTO = "NO_RESUELTO"
ESTADO_AMBIGUO = "AMBIGUO"


# ---------------------------------------------------------------------------
# Categoria prioritaria
# ---------------------------------------------------------------------------

CATEGORIA_DATOS_EMBARGADO = "Datos_Embargado"


# ---------------------------------------------------------------------------
# Palabras clave
#
# No se usan para extraer nombres.
# Solamente aportan peso adicional cuando el modelo YA encontro un candidato.
# ---------------------------------------------------------------------------

PALABRAS_CLAVE_FUERTES = {
    "a nombre del demandado",
    "cuentas de titularidad",
    "proceder a embargar",
    "decretado el embargo",
}

PALABRAS_CLAVE_MEDIAS = {
    "decrétase embargo",
    "decretase embargo",
    "trabese embargo",
    "trábese embargo",
    "trabar embargo",
    "decretase embargo sobre",
    "decrétase embargo sobre",
    "embargo sobre la cuenta",
}

PALABRAS_CLAVE_DEBILES = {
    "sobre los fondos",
    "cuentas que",
    "traba del embargo",
}


# ---------------------------------------------------------------------------
# Valores que nunca deben considerarse nombres validos
# ---------------------------------------------------------------------------

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
    "desconocido",
    "unknown",
}


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------

def _texto_seguro(value: Any) -> str:
    """Convierte un valor a texto sin generar 'None' artificialmente."""

    if value is None:
        return ""

    return str(value).strip()


def _normalizar_para_comparar(value: Any) -> str:
    """Normaliza texto para comparar candidatos sin alterar el valor original.

    La normalizacion se utiliza solamente internamente para agrupar nombres
    equivalentes.

    Ejemplo:
        'José Pérez'
        'JOSE PEREZ'

    producen una clave comparable similar.

    El valor original extraido por el modelo se conserva para la salida.
    """

    text = _texto_seguro(value)

    if not text:
        return ""

    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = text.upper()

    text = re.sub(r"\s+", " ", text)

    # Se eliminan solamente signos exteriores.
    text = text.strip(" \t\n\r,.;:-")

    return text


def _es_nombre_valido(value: Any) -> bool:
    """Valida de forma minima que exista un candidato util.

    No intenta decidir si el texto realmente es una persona.
    Esa responsabilidad corresponde al modelo de extraccion.

    Esta funcion solo evita valores vacios o marcadores tecnicos.
    """

    text = _texto_seguro(value)

    if not text:
        return False

    if text.lower() in VALORES_VACIOS:
        return False

    # Evita cadenas formadas solamente por numeros o puntuacion.
    if not any(char.isalpha() for char in text):
        return False

    return True


# ---------------------------------------------------------------------------
# Extraccion de campos desde la prediccion estructurada
# ---------------------------------------------------------------------------

def _buscar_clave_recursiva(
    data: Any,
    clave_buscada: str,
) -> Any:
    """Busca una clave dentro de estructuras anidadas de diccionarios/listas."""

    if isinstance(data, dict):
        if clave_buscada in data:
            return data[clave_buscada]

        for value in data.values():
            encontrado = _buscar_clave_recursiva(
                value,
                clave_buscada,
            )

            if encontrado is not None:
                return encontrado

    elif isinstance(data, list):
        for item in data:
            encontrado = _buscar_clave_recursiva(
                item,
                clave_buscada,
            )

            if encontrado is not None:
                return encontrado

    return None


def extraer_campos_embargado(
    registro: dict[str, Any],
) -> dict[str, str]:
    """Extrae campos del nuevo esquema desde una prediccion.

    Se buscan EXCLUSIVAMENTE los nombres de campos definidos para el nuevo
    esquema.

    Deliberadamente NO se busca una clave generica llamada 'nombre',
    porque el CSV de fragmentos ya contiene una columna 'nombre' con otro
    significado ('Embargo - usuario').

    Campos esperados:
        nombre_embargado
        dni_embargado
        cuit_cuil_embargado
        rol_embargado
    """

    nombre = _buscar_clave_recursiva(
        registro,
        "nombre_embargado",
    )

    dni = _buscar_clave_recursiva(
        registro,
        "dni_embargado",
    )

    cuit_cuil = _buscar_clave_recursiva(
        registro,
        "cuit_cuil_embargado",
    )

    rol = _buscar_clave_recursiva(
        registro,
        "rol_embargado",
    )

    return {
        "nombre_embargado": _texto_seguro(nombre),
        "dni_embargado": _texto_seguro(dni),
        "cuit_cuil_embargado": _texto_seguro(cuit_cuil),
        "rol_embargado": _texto_seguro(rol),
    }


# ---------------------------------------------------------------------------
# Peso contextual
# ---------------------------------------------------------------------------

def _peso_palabra_clave(palabra_clave: Any) -> float:
    """Asigna peso contextual segun la palabra clave del fragmento."""

    clave = _normalizar_para_comparar(palabra_clave).lower()

    fuertes = {
        _normalizar_para_comparar(x).lower()
        for x in PALABRAS_CLAVE_FUERTES
    }

    medias = {
        _normalizar_para_comparar(x).lower()
        for x in PALABRAS_CLAVE_MEDIAS
    }

    debiles = {
        _normalizar_para_comparar(x).lower()
        for x in PALABRAS_CLAVE_DEBILES
    }

    if clave in fuertes:
        return 3.0

    if clave in medias:
        return 2.0

    if clave in debiles:
        return 1.0

    return 0.5


def _peso_categoria(categoria: Any) -> float:
    """Da mayor peso a fragmentos especificamente clasificados como embargado."""

    categoria_texto = _texto_seguro(categoria)

    if categoria_texto == CATEGORIA_DATOS_EMBARGADO:
        return 3.0

    return 1.0


def _peso_identificadores(
    dni: str,
    cuit_cuil: str,
) -> float:
    """Agrega evidencia cuando nombre e identificadores aparecen juntos."""

    peso = 0.0

    if dni:
        peso += 2.0

    if cuit_cuil:
        peso += 2.0

    return peso


def _peso_rol(rol: str) -> float:
    """Da una pequeña bonificacion cuando el modelo encontro tambien un rol."""

    if not rol:
        return 0.0

    rol_normalizado = _normalizar_para_comparar(rol).lower()

    señales = (
        "demandado",
        "demandada",
        "embargado",
        "embargada",
        "ejecutado",
        "ejecutada",
        "deudor",
        "deudora",
        "titular",
    )

    if any(señal in rol_normalizado for señal in señales):
        return 2.0

    return 0.5


# ---------------------------------------------------------------------------
# Deduplicacion de fragmentos
# ---------------------------------------------------------------------------

def _clave_fragmento(registro: dict[str, Any]) -> tuple[str, str]:
    """Genera una clave estable para detectar fragmentos duplicados.

    Se utiliza:
        numero_archivo + fragmento

    Dos palabras clave distintas pueden haber generado exactamente la misma
    ventana de texto. Ese texto no debe contar dos veces como evidencia
    independiente.
    """

    numero_archivo = _texto_seguro(
        registro.get("numero_archivo")
    )

    fragmento = _texto_seguro(
        registro.get("fragmento")
    )

    return (
        numero_archivo,
        fragmento,
    )


def deduplicar_fragmentos(
    registros: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Elimina ventanas exactamente duplicadas dentro del mismo documento."""

    vistos: set[tuple[str, str]] = set()
    resultado: list[dict[str, Any]] = []

    for registro in registros:
        clave = _clave_fragmento(registro)

        if clave in vistos:
            continue

        vistos.add(clave)
        resultado.append(registro)

    return resultado


# ---------------------------------------------------------------------------
# Construccion de candidatos
# ---------------------------------------------------------------------------

def _crear_candidato(
    nombre_original: str,
) -> dict[str, Any]:
    """Inicializa la estructura interna de un candidato."""

    return {
        "nombre_embargado": nombre_original,
        "clave_normalizada": _normalizar_para_comparar(
            nombre_original
        ),
        "score": 0.0,
        "cantidad_fragmentos": 0,
        "dni_encontrados": set(),
        "cuit_cuil_encontrados": set(),
        "roles_encontrados": set(),
        "fragmentos_soporte": [],
        "palabras_clave_soporte": set(),
        "categorias_soporte": set(),
    }


def _agregar_evidencia(
    candidato: dict[str, Any],
    registro: dict[str, Any],
    campos: dict[str, str],
) -> None:
    """Agrega al candidato la evidencia de un fragmento."""

    categoria = _texto_seguro(
        registro.get("categoria")
    )

    palabra_clave = _texto_seguro(
        registro.get("palabra_clave")
    )

    dni = campos["dni_embargado"]
    cuit_cuil = campos["cuit_cuil_embargado"]
    rol = campos["rol_embargado"]

    score_fragmento = 1.0

    score_fragmento += _peso_categoria(
        categoria
    )

    score_fragmento += _peso_palabra_clave(
        palabra_clave
    )

    score_fragmento += _peso_identificadores(
        dni,
        cuit_cuil,
    )

    score_fragmento += _peso_rol(
        rol
    )

    candidato["score"] += score_fragmento
    candidato["cantidad_fragmentos"] += 1

    if dni:
        candidato["dni_encontrados"].add(dni)

    if cuit_cuil:
        candidato["cuit_cuil_encontrados"].add(
            cuit_cuil
        )

    if rol:
        candidato["roles_encontrados"].add(rol)

    if palabra_clave:
        candidato["palabras_clave_soporte"].add(
            palabra_clave
        )

    if categoria:
        candidato["categorias_soporte"].add(
            categoria
        )

    candidato["fragmentos_soporte"].append(
        {
            "contador_interno": registro.get(
                "contador_interno"
            ),
            "palabra_clave": palabra_clave,
            "categoria": categoria,
            "posicion_inicio": registro.get(
                "posicion_inicio"
            ),
            "posicion_fin": registro.get(
                "posicion_fin"
            ),
        }
    )


# ---------------------------------------------------------------------------
# Serializacion de candidatos
# ---------------------------------------------------------------------------

def _serializar_candidato(
    candidato: dict[str, Any],
) -> dict[str, Any]:
    """Convierte sets y estructuras internas a formatos serializables JSON."""

    return {
        "nombre_embargado": candidato[
            "nombre_embargado"
        ],
        "score": round(
            candidato["score"],
            3,
        ),
        "cantidad_fragmentos": candidato[
            "cantidad_fragmentos"
        ],
        "dni_encontrados": sorted(
            candidato["dni_encontrados"]
        ),
        "cuit_cuil_encontrados": sorted(
            candidato["cuit_cuil_encontrados"]
        ),
        "roles_encontrados": sorted(
            candidato["roles_encontrados"]
        ),
        "palabras_clave_soporte": sorted(
            candidato["palabras_clave_soporte"]
        ),
        "categorias_soporte": sorted(
            candidato["categorias_soporte"]
        ),
        "fragmentos_soporte": candidato[
            "fragmentos_soporte"
        ],
    }


# ---------------------------------------------------------------------------
# Resolucion del ganador
# ---------------------------------------------------------------------------

def _resolver_estado(
    candidatos_ordenados: list[dict[str, Any]],
    margen_ambiguedad: float = 1.0,
) -> str:
    """Determina si el documento queda resuelto o ambiguo.

    Si no existen candidatos:
        NO_RESUELTO

    Si existe uno:
        RESUELTO

    Si existen varios y los dos mejores tienen scores demasiado cercanos:
        AMBIGUO

    El margen se mantiene configurable para poder ajustarlo posteriormente
    con datos reales.
    """

    if not candidatos_ordenados:
        return ESTADO_NO_RESUELTO

    if len(candidatos_ordenados) == 1:
        return ESTADO_RESUELTO

    primero = candidatos_ordenados[0]["score"]
    segundo = candidatos_ordenados[1]["score"]

    diferencia = primero - segundo

    if diferencia <= margen_ambiguedad:
        return ESTADO_AMBIGUO

    return ESTADO_RESUELTO


# ---------------------------------------------------------------------------
# Consolidacion de un documento
# ---------------------------------------------------------------------------

def consolidar_documento(
    registros: list[dict[str, Any]],
    margen_ambiguedad: float = 1.0,
) -> dict[str, Any]:
    """Consolida todos los fragmentos correspondientes a un documento."""

    if not registros:
        raise ValueError(
            "consolidar_documento requiere al menos un registro"
        )

    registros_unicos = deduplicar_fragmentos(
        registros
    )

    primer_registro = registros_unicos[0]

    numero_archivo = primer_registro.get(
        "numero_archivo"
    )

    id_documento = primer_registro.get("id")

    candidatos: dict[str, dict[str, Any]] = {}

    for registro in registros_unicos:
        campos = extraer_campos_embargado(
            registro
        )

        nombre = campos["nombre_embargado"]

        if not _es_nombre_valido(nombre):
            continue

        clave = _normalizar_para_comparar(
            nombre
        )

        if not clave:
            continue

        if clave not in candidatos:
            candidatos[clave] = _crear_candidato(
                nombre
            )

        _agregar_evidencia(
            candidatos[clave],
            registro,
            campos,
        )

    candidatos_serializados = [
        _serializar_candidato(candidato)
        for candidato in candidatos.values()
    ]

    candidatos_serializados.sort(
        key=lambda candidato: (
            candidato["score"],
            candidato["cantidad_fragmentos"],
            len(candidato["dni_encontrados"]),
            len(candidato["cuit_cuil_encontrados"]),
        ),
        reverse=True,
    )

    estado = _resolver_estado(
        candidatos_serializados,
        margen_ambiguedad=margen_ambiguedad,
    )

    if candidatos_serializados:
        mejor = candidatos_serializados[0]

        nombre_final = mejor[
            "nombre_embargado"
        ]

        dni_final = (
            mejor["dni_encontrados"][0]
            if mejor["dni_encontrados"]
            else ""
        )

        cuit_cuil_final = (
            mejor["cuit_cuil_encontrados"][0]
            if mejor["cuit_cuil_encontrados"]
            else ""
        )

        rol_final = (
            mejor["roles_encontrados"][0]
            if mejor["roles_encontrados"]
            else ""
        )

        score_final = mejor["score"]

    else:
        nombre_final = ""
        dni_final = ""
        cuit_cuil_final = ""
        rol_final = ""
        score_final = 0.0

    return {
        "numero_archivo": numero_archivo,
        "id": id_documento,

        "estado_nombre_embargado": estado,

        "nombre_embargado": nombre_final,
        "dni_embargado": dni_final,
        "cuit_cuil_embargado": cuit_cuil_final,
        "rol_embargado": rol_final,

        "score_nombre_embargado": score_final,

        "cantidad_fragmentos_originales": len(
            registros
        ),

        "cantidad_fragmentos_unicos": len(
            registros_unicos
        ),

        "cantidad_candidatos_nombre": len(
            candidatos_serializados
        ),

        "candidatos_nombre_embargado": (
            candidatos_serializados
        ),
    }


# ---------------------------------------------------------------------------
# Consolidacion completa
# ---------------------------------------------------------------------------

def consolidar_por_documento(
    predicciones_fragmentos: list[dict[str, Any]],
    margen_ambiguedad: float = 1.0,
) -> list[dict[str, Any]]:
    """Agrupa predicciones por numero_archivo y consolida cada documento."""

    documentos: dict[str, list[dict[str, Any]]] = (
        defaultdict(list)
    )

    for registro in predicciones_fragmentos:
        numero_archivo = _texto_seguro(
            registro.get("numero_archivo")
        )

        if not numero_archivo:
            raise ValueError(
                "Se encontro una prediccion sin numero_archivo"
            )

        documentos[numero_archivo].append(
            registro
        )

    resultados: list[dict[str, Any]] = []

    for numero_archivo in sorted(
        documentos,
        key=_orden_numero_archivo,
    ):
        resultado = consolidar_documento(
            documentos[numero_archivo],
            margen_ambiguedad=margen_ambiguedad,
        )

        resultados.append(resultado)

    return resultados


def _orden_numero_archivo(value: str) -> tuple[int, Any]:
    """Permite ordenar numero_archivo numericamente cuando sea posible."""

    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

def resumir_consolidacion(
    resultados: list[dict[str, Any]],
) -> dict[str, int]:
    """Genera un resumen sencillo de estados finales."""

    resumen = {
        "total_documentos": len(resultados),
        ESTADO_RESUELTO: 0,
        ESTADO_AMBIGUO: 0,
        ESTADO_NO_RESUELTO: 0,
    }

    for resultado in resultados:
        estado = resultado.get(
            "estado_nombre_embargado"
        )

        if estado in resumen:
            resumen[estado] += 1

    return resumen