"""Funciones de exportacion de resultados."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import csv
import json
import re

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

OUTPUTS_DIR = (
    PROJECT_ROOT
    / "outputs"
)

RAW_DIR = (
    OUTPUTS_DIR
    / "raw"
)

DOCUMENT_DIR = (
    OUTPUTS_DIR
    / "por_documento"
)

CONSOLIDATION_DIR = (
    OUTPUTS_DIR
    / "consolidacion"
)


# ============================================================
# HELPERS
# ============================================================

def _safe_name(
    value: str,
) -> str:

    value = str(
        value
    ).strip()

    value = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        value,
    )

    return (
        value.strip(
            "_"
        )
        or "run"
    )


def _write_json(
    path: Path,
    data: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as fh:

        json.dump(
            data,
            fh,
            ensure_ascii=False,
            indent=2,
        )


def _write_yaml(
    path: Path,
    data: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as fh:

        yaml.safe_dump(
            data,
            fh,
            allow_unicode=True,
            sort_keys=False,
        )


def _write_csv(
    path: Path,
    rows: list[
        dict[str, Any]
    ],
    columns: list[str],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as fh:

        writer = csv.DictWriter(
            fh,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:

            writer.writerow(
                {
                    column:
                        row.get(
                            column,
                            "",
                        )
                    for column
                    in columns
                }
            )


# ============================================================
# CONVERSION GENERICA
# ============================================================

def _to_dict(
    value: Any,
) -> dict[str, Any]:
    """
    Convierte distintos tipos de resultados internos
    del pipeline a diccionarios.

    Soporta:

    - dict
    - dataclasses
    - objetos con to_dict()
    - objetos con __dict__
    """

    # --------------------------------------------------------
    # Ya es dict
    # --------------------------------------------------------

    if isinstance(
        value,
        dict,
    ):
        return value

    # --------------------------------------------------------
    # Dataclass
    #
    # Ejemplo:
    # PostprocessedResult
    # --------------------------------------------------------

    if is_dataclass(
        value
    ):
        result = asdict(
            value
        )

        if isinstance(
            result,
            dict,
        ):
            return result

    # --------------------------------------------------------
    # Objetos con to_dict()
    # --------------------------------------------------------

    if hasattr(
        value,
        "to_dict",
    ):
        result = value.to_dict()

        if isinstance(
            result,
            dict,
        ):
            return result

    # --------------------------------------------------------
    # Objetos normales
    # --------------------------------------------------------

    if hasattr(
        value,
        "__dict__",
    ):
        return dict(
            vars(
                value
            )
        )

    raise TypeError(
        "No se puede convertir el resultado "
        f"a dict: {type(value)!r}"
    )


# ============================================================
# AGRUPACION POR DOCUMENTO
# ============================================================

def _get_value(
    source: dict[str, Any],
    metadata: dict[str, Any],
    key: str,
    default: Any = "",
) -> Any:
    """Obtiene un valor primero desde el record y luego desde metadata."""

    value = source.get(key)

    if value not in (None, ""):
        return value

    value = metadata.get(key)

    if value not in (None, ""):
        return value

    return default


def _infer_text_column(
    source: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    """
    Intenta inferir qué columna fue enviada al modelo.

    Esto se usa solamente como fallback cuando
    build_document_rows() es llamado directamente
    sin recibir text_column.

    En las ejecuciones normales, export_results()
    recibe text_column desde experimentos.yaml y
    lo pasa explicitamente.
    """

    texto = str(
        source.get("texto")
        or source.get("text")
        or ""
    )

    # ========================================================
    # 1. Intentar detectar coincidencia exacta
    # ========================================================

    if texto:

        for column in (
            "fragmento",
            "contexto_embargado",
            "texto_completo",
        ):

            candidate = _get_value(
                source,
                metadata,
                column,
                "",
            )

            if (
                candidate
                and str(candidate) == texto
            ):
                return column

    # ========================================================
    # 2. Compatibilidad histórica
    #
    # Antes todos los registros con modo_entrada=fragmentos
    # utilizaban fragmento como entrada del modelo.
    #
    # Esto permite que tests y resultados antiguos sigan
    # funcionando aunque fragmento no estuviera duplicado
    # dentro de metadata.
    # ========================================================

    modo_entrada = str(
        source.get("modo_entrada")
        or metadata.get("modo_entrada")
        or ""
    )

    if modo_entrada == "fragmentos":
        return "fragmento"

    # ========================================================
    # 3. Documentos completos históricos
    # ========================================================

    if modo_entrada == "documentos_completos":
        return "texto_completo"

    # ========================================================
    # 4. No fue posible inferirlo
    # ========================================================

    return "texto"

def build_document_rows(
    rows: list[Any],
    text_column: str | None = None,
) -> list[
    dict[str, Any]
]:
    """Agrupa resultados de inferencia por documento.

    La función ya no asume que ``InputRecord.texto`` es siempre el
    fragmento. ``InputRecord.texto`` representa exactamente el texto
    enviado al modelo y puede provenir de ``fragmento``,
    ``contexto_embargado`` u otra columna configurada en
    ``experimentos.yaml``.

    Además conserva por separado:

    - ``texto_entrada_modelo``: texto realmente enviado a GLiNER;
    - ``tipo_entrada_modelo``: columna de origen de ese texto;
    - ``fragmento``: fragmento original, si existe;
    - ``contexto_embargado``: contexto ampliado, si existe;
    - ``texto_completo``: documento completo, si existe.

    Soporta tanto el formato actual ``PostprocessedResult`` como el
    formato legacy/plano usado por algunos tests y scripts antiguos.
    """

    grouped: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for raw_row in rows:

        row = _to_dict(raw_row)

        prediction = (
            row.get("prediction", {})
            or {}
        )

        if not isinstance(prediction, dict):
            prediction = {}

        record = (
            prediction.get("record", {})
            or {}
        )

        if not isinstance(record, dict):
            record = {}

        legacy_metadata = (
            row.get("metadata", {})
            or {}
        )

        if not isinstance(legacy_metadata, dict):
            legacy_metadata = {}

        record_metadata = (
            record.get("metadata", {})
            or {}
        )

        if not isinstance(record_metadata, dict):
            record_metadata = {}

        tiene_record_real = bool(record)

        if tiene_record_real:
            source = record
            metadata = record_metadata
        else:
            source = row
            metadata = legacy_metadata

        document_id = str(
            _get_value(
                source,
                metadata,
                "id",
                "",
            )
        )

        numero_archivo = str(
            _get_value(
                source,
                metadata,
                "numero_archivo",
                "",
            )
        )

        key = (
            numero_archivo,
            document_id,
        )

        if key not in grouped:
            grouped[key] = {
                "id": document_id,
                "numero_archivo": numero_archivo,
                "nombre": _get_value(
                    source,
                    metadata,
                    "nombre",
                    "",
                ),
                "texto_completo": _get_value(
                    source,
                    metadata,
                    "texto_completo",
                    "",
                ),
                "resultados": [],
            }

        documento = grouped[key]

        # Recuperar texto_completo desde otra fila del mismo documento
        # si la primera no lo contenía.
        if not documento.get("texto_completo"):
            texto_completo = _get_value(
                source,
                metadata,
                "texto_completo",
                "",
            )

            if texto_completo:
                documento["texto_completo"] = texto_completo

        # ----------------------------------------------------
        # Texto realmente enviado al modelo
        # ----------------------------------------------------

        if tiene_record_real:
            texto_entrada_modelo = str(
                source.get("texto")
                or ""
            )
        else:
            texto_entrada_modelo = str(
                source.get("texto_entrada_modelo")
                or source.get("text")
                or source.get("fragmento")
                or ""
            )

        tipo_entrada_modelo = (
            str(text_column)
            if text_column
            else _infer_text_column(
                source,
                metadata,
            )
        )

        # ----------------------------------------------------
        # Mantener las fuentes originales separadas
        # ----------------------------------------------------

        fragmento = _get_value(
            source,
            metadata,
            "fragmento",
            "",
        )

        contexto_embargado = _get_value(
            source,
            metadata,
            "contexto_embargado",
            "",
        )

        # Compatibilidad con experimentos históricos donde fragmento era
        # la columna enviada al modelo y por eso no estaba en metadata.
        if (
            not fragmento
            and tipo_entrada_modelo == "fragmento"
        ):
            fragmento = texto_entrada_modelo

        # Misma idea para contexto_embargado cuando se usa como entrada y
        # no quedó duplicado en metadata.
        if (
            not contexto_embargado
            and tipo_entrada_modelo == "contexto_embargado"
        ):
            contexto_embargado = texto_entrada_modelo

        resultado = {
            "contador_interno": _get_value(
                source,
                metadata,
                "contador_interno",
                "",
            ),
            "palabra_clave": _get_value(
                source,
                metadata,
                "palabra_clave",
                "",
            ),
            "categoria": _get_value(
                source,
                metadata,
                "categoria",
                "",
            ),

            # Entrada real usada por GLiNER.
            "tipo_entrada_modelo":
                tipo_entrada_modelo,
            "texto_entrada_modelo":
                texto_entrada_modelo,

            # Fuentes originales conservadas de forma independiente.
            "fragmento": fragmento,
            "contexto_embargado": contexto_embargado,
            "palabra_clave_contexto": _get_value(
                source,
                metadata,
                "palabra_clave_contexto",
                "",
            ),

            "posicion_inicio": _get_value(
                source,
                metadata,
                "posicion_inicio",
                None,
            ),
            "posicion_fin": _get_value(
                source,
                metadata,
                "posicion_fin",
                None,
            ),
            "inicio_fragmento": _get_value(
                source,
                metadata,
                "inicio_fragmento",
                None,
            ),
            "fin_fragmento": _get_value(
                source,
                metadata,
                "fin_fragmento",
                None,
            ),
            "status": row.get("status") or "",
            "candidates": row.get("candidates", []) or [],
        }

        documento["resultados"].append(resultado)

    return list(grouped.values())


# ============================================================
# CSV DE PREDICCIONES
# ============================================================

def _json_cell(value: Any) -> str:
    """Serializa estructuras anidadas para guardarlas en una celda CSV."""

    if value in (None, ""):
        return ""

    if isinstance(value, (str, int, float, bool)):
        return str(value)

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
    )


def _prediction_source(
    row: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """Devuelve prediction, record/source y metadata normalizados."""

    prediction = row.get("prediction", {}) or {}

    if not isinstance(prediction, dict):
        prediction = {}

    record = prediction.get("record", {}) or {}

    if not isinstance(record, dict):
        record = {}

    if record:
        metadata = record.get("metadata", {}) or {}

        if not isinstance(metadata, dict):
            metadata = {}

        return prediction, record, metadata

    metadata = row.get("metadata", {}) or {}

    if not isinstance(metadata, dict):
        metadata = {}

    return prediction, row, metadata


def _build_prediction_csv_rows(
    rows: list[Any],
    text_column: str | None = None,
) -> list[dict[str, Any]]:
    """Construye un CSV legible de las predicciones.

    Genera una fila por candidato. Cuando un registro no tiene candidatos,
    genera igualmente una fila para poder auditar los ``no_detectado``.
    """

    csv_rows: list[dict[str, Any]] = []

    for raw_row in rows:
        row = _to_dict(raw_row)
        prediction, source, metadata = _prediction_source(row)

        texto_entrada = str(
            source.get("texto")
            or source.get("texto_entrada_modelo")
            or source.get("text")
            or ""
        )

        tipo_entrada = (
            str(text_column)
            if text_column
            else _infer_text_column(
                source,
                metadata,
            )
        )

        fragmento = _get_value(
            source,
            metadata,
            "fragmento",
            "",
        )

        contexto = _get_value(
            source,
            metadata,
            "contexto_embargado",
            "",
        )

        if not fragmento and tipo_entrada == "fragmento":
            fragmento = texto_entrada

        if (
            not contexto
            and tipo_entrada == "contexto_embargado"
        ):
            contexto = texto_entrada

        base = {
            "numero_archivo": _get_value(
                source,
                metadata,
                "numero_archivo",
                "",
            ),
            "id": _get_value(
                source,
                metadata,
                "id",
                "",
            ),
            "nombre": _get_value(
                source,
                metadata,
                "nombre",
                "",
            ),
            "contador_interno": _get_value(
                source,
                metadata,
                "contador_interno",
                "",
            ),
            "palabra_clave": _get_value(
                source,
                metadata,
                "palabra_clave",
                "",
            ),
            "categoria": _get_value(
                source,
                metadata,
                "categoria",
                "",
            ),
            "tipo_entrada_modelo": tipo_entrada,
            "texto_entrada_modelo": texto_entrada,
            "fragmento": fragmento,
            "contexto_embargado": contexto,
            "palabra_clave_contexto": _get_value(
                source,
                metadata,
                "palabra_clave_contexto",
                "",
            ),
            "texto_completo": _get_value(
                source,
                metadata,
                "texto_completo",
                "",
            ),
            "status": row.get("status") or "",
            "model_id": prediction.get("model_id", ""),
            "schema_id": prediction.get("schema_id", ""),
            "threshold": prediction.get("threshold", ""),
            "schema_type": prediction.get("schema_type", ""),
            "architecture": prediction.get("architecture", ""),
        }

        candidates = row.get("candidates", []) or []

        if not candidates:
            csv_rows.append(
                {
                    **base,
                    "candidate_index": "",
                    "tipo": "",
                    "valor": "",
                    "nombre_embargado": "",
                    "dni_embargado": "",
                    "cuit_cuil_embargado": "",
                    "rol_embargado": "",
                    "confidence": "",
                    "span_inicio": "",
                    "span_fin": "",
                    "candidate_json": "",
                    "raw_response_json": _json_cell(
                        prediction.get("raw_response")
                    ),
                }
            )
            continue

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            if not isinstance(candidate, dict):
                candidate = {
                    "valor": candidate,
                }

            csv_rows.append(
                {
                    **base,
                    "candidate_index": index,
                    "tipo": candidate.get("tipo", ""),
                    "valor": candidate.get("valor", ""),
                    "nombre_embargado": candidate.get(
                        "nombre_embargado",
                        candidate.get("nombre", ""),
                    ),
                    "dni_embargado": candidate.get(
                        "dni_embargado",
                        candidate.get("dni", ""),
                    ),
                    "cuit_cuil_embargado": candidate.get(
                        "cuit_cuil_embargado",
                        candidate.get("cuil_cuit", ""),
                    ),
                    "rol_embargado": candidate.get(
                        "rol_embargado",
                        "",
                    ),
                    "confidence": candidate.get(
                        "confidence",
                        "",
                    ),
                    "span_inicio": candidate.get(
                        "span_inicio",
                        "",
                    ),
                    "span_fin": candidate.get(
                        "span_fin",
                        "",
                    ),
                    "candidate_json": _json_cell(candidate),
                    "raw_response_json": _json_cell(
                        prediction.get("raw_response")
                    ),
                }
            )

    return csv_rows


def _build_document_prediction_csv_rows(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aplana ``predicciones_por_documento.json`` para CSV."""

    csv_rows: list[dict[str, Any]] = []

    for document in documents:
        document_base = {
            "numero_archivo": document.get(
                "numero_archivo",
                "",
            ),
            "id": document.get("id", ""),
            "nombre": document.get("nombre", ""),
            "texto_completo": document.get(
                "texto_completo",
                "",
            ),
        }

        resultados = document.get("resultados", []) or []

        for resultado_index, resultado in enumerate(
            resultados,
            start=1,
        ):
            if not isinstance(resultado, dict):
                continue

            result_base = {
                **document_base,
                "resultado_index": resultado_index,
                "contador_interno": resultado.get(
                    "contador_interno",
                    "",
                ),
                "palabra_clave": resultado.get(
                    "palabra_clave",
                    "",
                ),
                "categoria": resultado.get(
                    "categoria",
                    "",
                ),
                "tipo_entrada_modelo": resultado.get(
                    "tipo_entrada_modelo",
                    "",
                ),
                "texto_entrada_modelo": resultado.get(
                    "texto_entrada_modelo",
                    "",
                ),
                "fragmento": resultado.get(
                    "fragmento",
                    "",
                ),
                "contexto_embargado": resultado.get(
                    "contexto_embargado",
                    "",
                ),
                "palabra_clave_contexto": resultado.get(
                    "palabra_clave_contexto",
                    "",
                ),
                "status": resultado.get("status", ""),
            }

            candidates = resultado.get("candidates", []) or []

            if not candidates:
                csv_rows.append(
                    {
                        **result_base,
                        "candidate_index": "",
                        "tipo": "",
                        "valor": "",
                        "nombre_embargado": "",
                        "dni_embargado": "",
                        "cuit_cuil_embargado": "",
                        "rol_embargado": "",
                        "confidence": "",
                        "candidate_json": "",
                    }
                )
                continue

            for candidate_index, candidate in enumerate(
                candidates,
                start=1,
            ):
                if not isinstance(candidate, dict):
                    candidate = {
                        "valor": candidate,
                    }

                csv_rows.append(
                    {
                        **result_base,
                        "candidate_index": candidate_index,
                        "tipo": candidate.get("tipo", ""),
                        "valor": candidate.get("valor", ""),
                        "nombre_embargado": candidate.get(
                            "nombre_embargado",
                            candidate.get("nombre", ""),
                        ),
                        "dni_embargado": candidate.get(
                            "dni_embargado",
                            candidate.get("dni", ""),
                        ),
                        "cuit_cuil_embargado": candidate.get(
                            "cuit_cuil_embargado",
                            candidate.get("cuil_cuit", ""),
                        ),
                        "rol_embargado": candidate.get(
                            "rol_embargado",
                            "",
                        ),
                        "confidence": candidate.get(
                            "confidence",
                            "",
                        ),
                        "candidate_json": _json_cell(candidate),
                    }
                )

    return csv_rows


# ============================================================
# EXPORT RESULTADOS GLINER
# ============================================================

def export_results(
    rows: list[Any],
    experiment_name: str,
    used_config: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Path]:

    timestamp = (
        now
        or datetime.now()
    ).strftime("%Y%m%d_%H%M%S")

    safe_name = _safe_name(experiment_name)

    raw_run_dir = (
        RAW_DIR
        / f"{timestamp}_{safe_name}"
    )

    document_run_dir = (
        DOCUMENT_DIR
        / f"{timestamp}_{safe_name}"
    )

    raw_run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    document_run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    dict_rows = [
        _to_dict(row)
        for row in rows
    ]

    experiment_config = (
        used_config.get("experiment", {})
        if isinstance(used_config, dict)
        else {}
    )

    if not isinstance(experiment_config, dict):
        experiment_config = {}

    text_column_value = experiment_config.get(
        "text_column"
    )

    text_column = (
        str(text_column_value)
        if text_column_value not in (None, "")
        else None
    )

    # --------------------------------------------------------
    # RAW JSON + CSV
    # --------------------------------------------------------

    raw_json = (
        raw_run_dir
        / "predicciones.json"
    )

    raw_csv = (
        raw_run_dir
        / "predicciones.csv"
    )

    _write_json(
        raw_json,
        dict_rows,
    )

    raw_csv_rows = _build_prediction_csv_rows(
        rows,
        text_column=text_column,
    )

    raw_csv_columns = [
        "numero_archivo",
        "id",
        "nombre",
        "contador_interno",
        "palabra_clave",
        "categoria",
        "tipo_entrada_modelo",
        "texto_entrada_modelo",
        "fragmento",
        "contexto_embargado",
        "palabra_clave_contexto",
        "texto_completo",
        "status",
        "model_id",
        "schema_id",
        "threshold",
        "schema_type",
        "architecture",
        "candidate_index",
        "tipo",
        "valor",
        "nombre_embargado",
        "dni_embargado",
        "cuit_cuil_embargado",
        "rol_embargado",
        "confidence",
        "span_inicio",
        "span_fin",
        "candidate_json",
        "raw_response_json",
    ]

    _write_csv(
        raw_csv,
        raw_csv_rows,
        raw_csv_columns,
    )

    # --------------------------------------------------------
    # POR DOCUMENTO JSON + CSV
    # --------------------------------------------------------

    documents = build_document_rows(
        rows,
        text_column=text_column,
    )

    document_json = (
        document_run_dir
        / "predicciones_por_documento.json"
    )

    document_csv = (
        document_run_dir
        / "predicciones_por_documento.csv"
    )

    _write_json(
        document_json,
        documents,
    )

    document_csv_rows = (
        _build_document_prediction_csv_rows(
            documents
        )
    )

    document_csv_columns = [
        "numero_archivo",
        "id",
        "nombre",
        "resultado_index",
        "contador_interno",
        "palabra_clave",
        "categoria",
        "tipo_entrada_modelo",
        "texto_entrada_modelo",
        "fragmento",
        "contexto_embargado",
        "palabra_clave_contexto",
        "texto_completo",
        "status",
        "candidate_index",
        "tipo",
        "valor",
        "nombre_embargado",
        "dni_embargado",
        "cuit_cuil_embargado",
        "rol_embargado",
        "confidence",
        "candidate_json",
    ]

    _write_csv(
        document_csv,
        document_csv_rows,
        document_csv_columns,
    )

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    _write_yaml(
        raw_run_dir
        / "config_usada.yaml",
        used_config,
    )

    _write_yaml(
        document_run_dir
        / "config_usada.yaml",
        used_config,
    )

    return {
        "raw_dir": raw_run_dir,
        "document_dir": document_run_dir,
        "raw_json": raw_json,
        "raw_csv": raw_csv,
        "document_json": document_json,
        "document_csv": document_csv,
    }


# ============================================================
# CONSOLIDACION CSV
# ============================================================

def _build_consolidation_csv_rows(
    resultados: list[
        dict[str, Any]
    ],
) -> list[
    dict[str, Any]
]:

    rows: list[
        dict[str, Any]
    ] = []

    for resultado in resultados:

        personas = (
            resultado.get(
                "personas_embargadas",
                [],
            )
            or []
        )

        base = {
            "numero_archivo":
                resultado.get(
                    "numero_archivo"
                ),

            "id":
                resultado.get(
                    "id"
                ),

            "nombre_documento":
                resultado.get(
                    "nombre_documento"
                ),

            "estado":
                resultado.get(
                    "estado"
                ),

            "suficiente":
                resultado.get(
                    "suficiente",
                    False,
                ),

            "requiere_fallback_documento_completo":
                resultado.get(
                    "requiere_fallback_documento_completo",
                    False,
                ),

            "motivos_insuficiencia":
                " | ".join(
                    resultado.get(
                        "motivos_insuficiencia",
                        [],
                    )
                    or []
                ),

            "cantidad_embargados":
                resultado.get(
                    "cantidad_embargados",
                    0,
                ),

            "requiere_revision":
                resultado.get(
                    "requiere_revision",
                    False,
                ),

            "cantidad_conflictos_identificador":
                resultado.get(
                    "cantidad_conflictos_identificador",
                    0,
                ),
        }

        # ----------------------------------------------------
        # DOCUMENTO SIN PERSONAS ACEPTADAS
        # ----------------------------------------------------

        if not personas:

            rows.append(
                {
                    **base,

                    "indice_embargado":
                        "",

                    "nombre_embargado":
                        "",

                    "dni_embargado":
                        "",

                    "cuit_cuil_embargado":
                        "",

                    "roles_detectados":
                        "",

                    "variantes_nombre":
                        "",

                    "cantidad_fragmentos_soporte":
                        0,

                    "cantidad_evidencias":
                        0,

                    "score_total":
                        0,

                    "identidad_inconsistente":
                        False,
                }
            )

            continue

        # ----------------------------------------------------
        # UNA FILA POR PERSONA CONSOLIDADA
        # ----------------------------------------------------

        for index, persona in enumerate(
            personas,
            start=1,
        ):

            rows.append(
                {
                    **base,

                    "indice_embargado":
                        index,

                    "nombre_embargado":
                        persona.get(
                            "nombre_embargado",
                            "",
                        ),

                    "dni_embargado":
                        persona.get(
                            "dni_embargado",
                            "",
                        ),

                    "cuit_cuil_embargado":
                        persona.get(
                            "cuit_cuil_embargado",
                            "",
                        ),

                    "roles_detectados":
                        " | ".join(
                            persona.get(
                                "roles_detectados",
                                [],
                            )
                            or []
                        ),

                    "variantes_nombre":
                        " | ".join(
                            persona.get(
                                "variantes_nombre",
                                [],
                            )
                            or []
                        ),

                    "cantidad_fragmentos_soporte":
                        persona.get(
                            "cantidad_fragmentos_soporte",
                            0,
                        ),

                    "cantidad_evidencias":
                        persona.get(
                            "cantidad_evidencias",
                            0,
                        ),

                    "score_total":
                        persona.get(
                            "score_total",
                            0,
                        ),

                    "identidad_inconsistente":
                        persona.get(
                            "identidad_inconsistente",
                            False,
                        ),
                }
            )

    return rows


# ============================================================
# EXPORT CONSOLIDACION
# ============================================================

def export_consolidation(
    resultados: list[
        dict[str, Any]
    ],
    resumen: dict[str, Any],
    experiment_name: str,
    used_config: dict[str, Any],
    outputs_dir: str | Path = CONSOLIDATION_DIR,
    now: datetime | None = None,
) -> dict[str, Path]:

    timestamp = (
        now
        or datetime.now()
    ).strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_name = _safe_name(
        experiment_name
    )

    run_dir = (
        Path(
            outputs_dir
        )
        / f"{timestamp}_{safe_name}"
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # SEPARACION SUFICIENTES / INSUFICIENTES
    # ========================================================

    suficientes = [
        resultado
        for resultado
        in resultados
        if resultado.get(
            "suficiente",
            False,
        )
    ]

    insuficientes = [
        resultado
        for resultado
        in resultados
        if not resultado.get(
            "suficiente",
            False,
        )
    ]

    # ========================================================
    # JSON GENERAL
    # ========================================================

    consolidacion_json = (
        run_dir
        / "consolidacion.json"
    )

    _write_json(
        consolidacion_json,
        resultados,
    )

    # ========================================================
    # JSON SUFICIENTES
    # ========================================================

    suficientes_json = (
        run_dir
        / "suficientes.json"
    )

    _write_json(
        suficientes_json,
        suficientes,
    )

    # ========================================================
    # JSON INSUFICIENTES
    #
    # Entrada futura para extracción sobre texto_completo.
    # ========================================================

    insuficientes_json = (
        run_dir
        / "insuficientes.json"
    )

    _write_json(
        insuficientes_json,
        insuficientes,
    )

    # ========================================================
    # COLUMNAS CSV
    # ========================================================

    columns = [
        "numero_archivo",
        "id",
        "nombre_documento",

        "estado",

        "suficiente",
        "requiere_fallback_documento_completo",
        "motivos_insuficiencia",

        "cantidad_embargados",

        "indice_embargado",

        "nombre_embargado",
        "dni_embargado",
        "cuit_cuil_embargado",

        "roles_detectados",
        "variantes_nombre",

        "cantidad_fragmentos_soporte",
        "cantidad_evidencias",

        "score_total",

        "identidad_inconsistente",

        "requiere_revision",
        "cantidad_conflictos_identificador",
    ]

    # ========================================================
    # CSV GENERAL
    # ========================================================

    consolidacion_csv = (
        run_dir
        / "consolidacion.csv"
    )

    _write_csv(
        consolidacion_csv,
        _build_consolidation_csv_rows(
            resultados
        ),
        columns,
    )

    # ========================================================
    # CSV SUFICIENTES
    # ========================================================

    suficientes_csv = (
        run_dir
        / "suficientes.csv"
    )

    _write_csv(
        suficientes_csv,
        _build_consolidation_csv_rows(
            suficientes
        ),
        columns,
    )

    # ========================================================
    # CSV INSUFICIENTES
    # ========================================================

    insuficientes_csv = (
        run_dir
        / "insuficientes.csv"
    )

    _write_csv(
        insuficientes_csv,
        _build_consolidation_csv_rows(
            insuficientes
        ),
        columns,
    )

    # ========================================================
    # RESUMEN
    # ========================================================

    resumen_json = (
        run_dir
        / "resumen.json"
    )

    _write_json(
        resumen_json,
        resumen,
    )

    # ========================================================
    # CONFIG
    # ========================================================

    _write_yaml(
        run_dir
        / "config_usada.yaml",
        used_config,
    )

    return {
        "consolidacion_dir":
            run_dir,

        "consolidacion_json":
            consolidacion_json,

        "consolidacion_csv":
            consolidacion_csv,

        "suficientes_json":
            suficientes_json,

        "suficientes_csv":
            suficientes_csv,

        "insuficientes_json":
            insuficientes_json,

        "insuficientes_csv":
            insuficientes_csv,

        "resumen_json":
            resumen_json,
    }