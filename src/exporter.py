"""Exportacion CSV/JSON de resultados crudos y por documento."""

from __future__ import annotations

import csv
import json

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .postprocess import (
    PostprocessedResult,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

OUTPUTS_DIR = (
    PROJECT_ROOT
    / "outputs"
)


RAW_COLUMNS = [
    # --------------------------------------------------------
    # Metadata documento / fragmento
    # --------------------------------------------------------
    "numero_archivo",
    "id",
    "nombre",
    "modo_entrada",

    "contador_interno",
    "palabra_clave",
    "categoria",

    "posicion_inicio",
    "posicion_fin",
    "inicio_fragmento",
    "fin_fragmento",

    # --------------------------------------------------------
    # Configuracion
    # --------------------------------------------------------
    "modelo",
    "schema",
    "threshold",

    "texto_usado",
    "estado_postprocess",

    # --------------------------------------------------------
    # Entidad generica
    # --------------------------------------------------------
    "entidad_tipo",
    "entidad_valor",
    "confidence",
    "span_inicio",
    "span_fin",

    # --------------------------------------------------------
    # Persona embargada V7
    # --------------------------------------------------------
    "nombre_embargado",
    "nombre_embargado_confidence",
    "nombre_embargado_span_inicio",
    "nombre_embargado_span_fin",

    "dni_embargado",
    "dni_embargado_confidence",
    "dni_embargado_span_inicio",
    "dni_embargado_span_fin",

    "cuit_cuil_embargado",
    "cuit_cuil_embargado_confidence",
    "cuit_cuil_embargado_span_inicio",
    "cuit_cuil_embargado_span_fin",

    "rol_embargado",
    "rol_embargado_confidence",

    # --------------------------------------------------------
    # Compatibilidad con V3/V6
    # --------------------------------------------------------
    "nombre_detectado",
    "nombre_confidence",
    "nombre_span_inicio",
    "nombre_span_fin",

    "dni_detectado",
    "dni_confidence",
    "dni_span_inicio",
    "dni_span_fin",

    "cuil_cuit_detectado",
    "cuil_cuit_confidence",
    "cuil_cuit_span_inicio",
    "cuil_cuit_span_fin",

    # --------------------------------------------------------
    # Structured completo
    # --------------------------------------------------------
    "fields_json",

    # --------------------------------------------------------
    # Respuesta original
    # --------------------------------------------------------
    "raw_json",
]


def export_results(
    postprocessed: list[
        PostprocessedResult
    ],
    experiment_name: str,
    used_config: dict[str, Any],
    outputs_dir: str | Path = OUTPUTS_DIR,
    now: datetime | None = None,
) -> dict[str, Path]:

    timestamp = (
        now or datetime.now()
    ).strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_name = _safe_name(
        experiment_name
    )

    run_dir_name = (
        f"{timestamp}_{safe_name}"
    )

    base_outputs = Path(
        outputs_dir
    )

    raw_dir = (
        base_outputs
        / "raw"
        / run_dir_name
    )

    document_dir = (
        base_outputs
        / "por_documento"
        / run_dir_name
    )

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    document_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_rows = build_raw_rows(
        postprocessed
    )

    grouped = build_document_rows(
        postprocessed
    )

    # --------------------------------------------------------
    # RAW
    # --------------------------------------------------------

    _write_csv(
        raw_dir
        / "predicciones.csv",
        raw_rows,
        RAW_COLUMNS,
    )

    _write_json(
        raw_dir
        / "predicciones.json",
        raw_rows,
    )

    _write_yaml(
        raw_dir
        / "config_usada.yaml",
        used_config,
    )

    # --------------------------------------------------------
    # POR DOCUMENTO
    # --------------------------------------------------------

    _write_json(
        document_dir
        / "predicciones_por_documento.json",
        grouped,
    )

    _write_csv(
        document_dir
        / "predicciones_por_documento.csv",

        _flatten_grouped_rows(
            grouped
        ),

        [
            "id",
            "numero_archivo",
            "nombre",
            "cantidad_resultados",
            "cantidad_candidatos",
            "modo_entrada",
        ],
    )

    _write_yaml(
        document_dir
        / "config_usada.yaml",
        used_config,
    )

    return {
        "raw_dir":
            raw_dir,

        "por_documento_dir":
            document_dir,
    }


def build_raw_rows(
    postprocessed: list[
        PostprocessedResult
    ],
) -> list[
    dict[str, Any]
]:

    rows: list[
        dict[str, Any]
    ] = []

    for item in postprocessed:

        prediction = (
            item.prediction
        )

        record = (
            prediction.record
        )

        candidates = (
            item.candidates
            if item.candidates
            else [{}]
        )

        for candidate in candidates:

            rows.append(
                {
                    # ----------------------------------------
                    # Metadata
                    # ----------------------------------------

                    "numero_archivo":
                        record.numero_archivo,

                    "id":
                        record.id,

                    "nombre":
                        record.nombre,

                    "modo_entrada":
                        record.modo_entrada,

                    "contador_interno":
                        record.contador_interno,

                    "palabra_clave":
                        record.palabra_clave,

                    "categoria":
                        record.categoria,

                    "posicion_inicio":
                        record.posicion_inicio,

                    "posicion_fin":
                        record.posicion_fin,

                    "inicio_fragmento":
                        record.inicio_fragmento,

                    "fin_fragmento":
                        record.fin_fragmento,

                    # ----------------------------------------
                    # Config
                    # ----------------------------------------

                    "modelo":
                        prediction.model_id,

                    "schema":
                        prediction.schema_id,

                    "threshold":
                        prediction.threshold,

                    "texto_usado":
                        record.texto,

                    "estado_postprocess":
                        item.status,

                    # ----------------------------------------
                    # Generico
                    # ----------------------------------------

                    "entidad_tipo":
                        candidate.get(
                            "tipo"
                        ),

                    "entidad_valor":
                        candidate.get(
                            "valor"
                        ),

                    "confidence":
                        candidate.get(
                            "confidence"
                        ),

                    "span_inicio":
                        candidate.get(
                            "span_inicio"
                        ),

                    "span_fin":
                        candidate.get(
                            "span_fin"
                        ),

                    # ----------------------------------------
                    # V7 nombre_embargado
                    # ----------------------------------------

                    "nombre_embargado":
                        candidate.get(
                            "nombre_embargado"
                        ),

                    "nombre_embargado_confidence":
                        candidate.get(
                            "nombre_embargado_confidence"
                        ),

                    "nombre_embargado_span_inicio":
                        candidate.get(
                            "nombre_embargado_span_inicio"
                        ),

                    "nombre_embargado_span_fin":
                        candidate.get(
                            "nombre_embargado_span_fin"
                        ),

                    # ----------------------------------------
                    # V7 DNI
                    # ----------------------------------------

                    "dni_embargado":
                        candidate.get(
                            "dni_embargado"
                        ),

                    "dni_embargado_confidence":
                        candidate.get(
                            "dni_embargado_confidence"
                        ),

                    "dni_embargado_span_inicio":
                        candidate.get(
                            "dni_embargado_span_inicio"
                        ),

                    "dni_embargado_span_fin":
                        candidate.get(
                            "dni_embargado_span_fin"
                        ),

                    # ----------------------------------------
                    # V7 CUIT/CUIL
                    # ----------------------------------------

                    "cuit_cuil_embargado":
                        candidate.get(
                            "cuit_cuil_embargado"
                        ),

                    "cuit_cuil_embargado_confidence":
                        candidate.get(
                            "cuit_cuil_embargado_confidence"
                        ),

                    "cuit_cuil_embargado_span_inicio":
                        candidate.get(
                            "cuit_cuil_embargado_span_inicio"
                        ),

                    "cuit_cuil_embargado_span_fin":
                        candidate.get(
                            "cuit_cuil_embargado_span_fin"
                        ),

                    # ----------------------------------------
                    # Rol
                    # ----------------------------------------

                    "rol_embargado":
                        candidate.get(
                            "rol_embargado"
                        ),

                    "rol_embargado_confidence":
                        candidate.get(
                            "rol_embargado_confidence"
                        ),

                    # ----------------------------------------
                    # Compatibilidad nombre
                    # ----------------------------------------

                    "nombre_detectado":
                        candidate.get(
                            "nombre"
                        ),

                    "nombre_confidence":
                        candidate.get(
                            "nombre_confidence"
                        ),

                    "nombre_span_inicio":
                        candidate.get(
                            "nombre_span_inicio"
                        ),

                    "nombre_span_fin":
                        candidate.get(
                            "nombre_span_fin"
                        ),

                    # ----------------------------------------
                    # Compatibilidad DNI
                    # ----------------------------------------

                    "dni_detectado":
                        candidate.get(
                            "dni"
                        ),

                    "dni_confidence":
                        candidate.get(
                            "dni_confidence"
                        ),

                    "dni_span_inicio":
                        candidate.get(
                            "dni_span_inicio"
                        ),

                    "dni_span_fin":
                        candidate.get(
                            "dni_span_fin"
                        ),

                    # ----------------------------------------
                    # Compatibilidad CUIT/CUIL
                    # ----------------------------------------

                    "cuil_cuit_detectado":
                        candidate.get(
                            "cuil_cuit"
                        ),

                    "cuil_cuit_confidence":
                        candidate.get(
                            "cuil_cuit_confidence"
                        ),

                    "cuil_cuit_span_inicio":
                        candidate.get(
                            "cuil_cuit_span_inicio"
                        ),

                    "cuil_cuit_span_fin":
                        candidate.get(
                            "cuil_cuit_span_fin"
                        ),

                    # ----------------------------------------
                    # Structured completo
                    # ----------------------------------------

                    "fields_json":
                        json.dumps(
                            candidate.get(
                                "fields",
                                {},
                            ),
                            ensure_ascii=False,
                            default=str,
                        ),

                    # ----------------------------------------
                    # Raw
                    # ----------------------------------------

                    "raw_json":
                        json.dumps(
                            prediction.raw_response,
                            ensure_ascii=False,
                            default=str,
                        ),
                }
            )

    return rows


def build_document_rows(
    postprocessed: list[
        PostprocessedResult
    ],
) -> list[
    dict[str, Any]
]:

    grouped: dict[
        str,
        dict[str, Any],
    ] = {}

    for item in postprocessed:

        prediction = (
            item.prediction
        )

        record = (
            prediction.record
        )

        bucket = grouped.setdefault(
            record.id,
            {
                "id":
                    record.id,

                "numero_archivo":
                    record.numero_archivo,

                "nombre":
                    record.nombre,

                "modo_entrada":
                    record.modo_entrada,

                "resultados":
                    [],
            },
        )

        bucket[
            "resultados"
        ].append(
            {
                "contador_interno":
                    record.contador_interno,

                "palabra_clave":
                    record.palabra_clave,

                "categoria":
                    record.categoria,

                "fragmento":
                    record.texto,

                "posicion_inicio":
                    record.posicion_inicio,

                "posicion_fin":
                    record.posicion_fin,

                "inicio_fragmento":
                    record.inicio_fragmento,

                "fin_fragmento":
                    record.fin_fragmento,

                "status":
                    item.status,

                "candidates":
                    item.candidates,

                "modelo":
                    prediction.model_id,

                "schema":
                    prediction.schema_id,

                "threshold":
                    prediction.threshold,

                "raw_response":
                    prediction.raw_response,
            }
        )

    return list(
        grouped.values()
    )


def _flatten_grouped_rows(
    grouped: list[
        dict[str, Any]
    ],
) -> list[
    dict[str, Any]
]:

    rows: list[
        dict[str, Any]
    ] = []

    for item in grouped:

        results = item.get(
            "resultados",
            [],
        )

        rows.append(
            {
                "id":
                    item.get(
                        "id"
                    ),

                "numero_archivo":
                    item.get(
                        "numero_archivo"
                    ),

                "nombre":
                    item.get(
                        "nombre"
                    ),

                "cantidad_resultados":
                    len(
                        results
                    ),

                "cantidad_candidatos":
                    sum(
                        len(
                            result.get(
                                "candidates",
                                [],
                            )
                        )
                        for result
                        in results
                    ),

                "modo_entrada":
                    item.get(
                        "modo_entrada"
                    ),
            }
        )

    return rows


def _write_csv(
    path: Path,
    rows: list[
        dict[str, Any]
    ],
    fieldnames: list[str],
) -> None:

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as fh:

        writer = csv.DictWriter(
            fh,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


def _write_json(
    path: Path,
    data: Any,
) -> None:

    with path.open(
        "w",
        encoding="utf-8",
    ) as fh:

        json.dump(
            data,
            fh,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


def _write_yaml(
    path: Path,
    data: dict[str, Any],
) -> None:

    with path.open(
        "w",
        encoding="utf-8",
    ) as fh:

        yaml.safe_dump(
            data,
            fh,
            sort_keys=False,
            allow_unicode=True,
        )


def _safe_name(
    value: str,
) -> str:

    allowed: list[
        str
    ] = []

    for char in (
        value
        .lower()
        .strip()
    ):

        if (
            char.isalnum()
            or char in {
                "_",
                "-",
            }
        ):
            allowed.append(
                char
            )

        elif char.isspace():

            allowed.append(
                "_"
            )

    return (
        "".join(
            allowed
        )
        or "experimento"
    )