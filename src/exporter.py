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

def build_document_rows(
    rows: list[Any],
) -> list[
    dict[str, Any]
]:
    """
    Agrupa resultados por documento.

    Soporta dos formatos:

    1. Formato actual:
       PostprocessedResult
         -> prediction
            -> record

    2. Formato legacy/plano:
       {
           "id": ...,
           "metadata": {...},
           "candidates": [...]
       }

    Conserva texto_completo para el fallback posterior.
    """

    grouped: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for raw_row in rows:

        row = _to_dict(
            raw_row
        )

        # ====================================================
        # FORMATO ACTUAL
        # ====================================================

        prediction = (
            row.get(
                "prediction",
                {},
            )
            or {}
        )

        if not isinstance(
            prediction,
            dict,
        ):
            prediction = {}

        record = (
            prediction.get(
                "record",
                {},
            )
            or {}
        )

        if not isinstance(
            record,
            dict,
        ):
            record = {}

        # ====================================================
        # FORMATO LEGACY
        # ====================================================

        legacy_metadata = (
            row.get(
                "metadata",
                {},
            )
            or {}
        )

        if not isinstance(
            legacy_metadata,
            dict,
        ):
            legacy_metadata = {}

        # ====================================================
        # METADATA DEL INPUT RECORD
        # ====================================================

        record_metadata = (
            record.get(
                "metadata",
                {},
            )
            or {}
        )

        if not isinstance(
            record_metadata,
            dict,
        ):
            record_metadata = {}

        # ====================================================
        # SELECCIONAR FUENTE
        # ====================================================

        tiene_record_real = bool(
            record
        )

        if tiene_record_real:

            source = record
            metadata = record_metadata

        else:

            source = row
            metadata = legacy_metadata

        # ====================================================
        # IDENTIFICACION DEL DOCUMENTO
        # ====================================================

        document_id = str(
            source.get(
                "id"
            )
            or metadata.get(
                "id"
            )
            or ""
        )

        numero_archivo = str(
            source.get(
                "numero_archivo"
            )
            or metadata.get(
                "numero_archivo"
            )
            or ""
        )

        key = (
            numero_archivo,
            document_id,
        )

        # ====================================================
        # DOCUMENTO NUEVO
        # ====================================================

        if key not in grouped:

            grouped[
                key
            ] = {
                "id":
                    document_id,

                "numero_archivo":
                    numero_archivo,

                "nombre":
                    source.get(
                        "nombre"
                    )
                    or metadata.get(
                        "nombre"
                    )
                    or "",

                # --------------------------------------------
                # TEXTO COMPLETO
                #
                # Normalmente llega como metadata adicional.
                # --------------------------------------------

                "texto_completo":
                    source.get(
                        "texto_completo"
                    )
                    or metadata.get(
                        "texto_completo"
                    )
                    or "",

                "resultados":
                    [],
            }

        documento = grouped[
            key
        ]

        # ----------------------------------------------------
        # Si la primera fila no traia texto_completo,
        # recuperarlo desde otra fila del mismo documento.
        # ----------------------------------------------------

        if not documento.get(
            "texto_completo"
        ):

            texto_completo = (
                source.get(
                    "texto_completo"
                )
                or metadata.get(
                    "texto_completo"
                )
                or ""
            )

            if texto_completo:

                documento[
                    "texto_completo"
                ] = texto_completo

        # ====================================================
        # FRAGMENTO
        # ====================================================

        if tiene_record_real:

            # InputRecord.texto contiene exactamente
            # el texto enviado al modelo.
            #
            # En modo fragmentos:
            #
            # record["texto"] == fragmento
            fragmento = (
                source.get(
                    "texto"
                )
                or ""
            )

        else:

            fragmento = (
                source.get(
                    "fragmento"
                )
                or source.get(
                    "text"
                )
                or metadata.get(
                    "fragmento"
                )
                or ""
            )

        # ====================================================
        # RESULTADO DEL FRAGMENTO
        # ====================================================

        resultado = {
            "contador_interno":
                source.get(
                    "contador_interno"
                )
                or metadata.get(
                    "contador_interno"
                )
                or "",

            "palabra_clave":
                source.get(
                    "palabra_clave"
                )
                or metadata.get(
                    "palabra_clave"
                )
                or "",

            "categoria":
                source.get(
                    "categoria"
                )
                or metadata.get(
                    "categoria"
                )
                or "",

            "fragmento":
                fragmento,

            "posicion_inicio":
                source.get(
                    "posicion_inicio"
                )
                or metadata.get(
                    "posicion_inicio"
                ),

            "posicion_fin":
                source.get(
                    "posicion_fin"
                )
                or metadata.get(
                    "posicion_fin"
                ),

            "inicio_fragmento":
                source.get(
                    "inicio_fragmento"
                )
                or metadata.get(
                    "inicio_fragmento"
                ),

            "fin_fragmento":
                source.get(
                    "fin_fragmento"
                )
                or metadata.get(
                    "fin_fragmento"
                ),

            "status":
                row.get(
                    "status"
                )
                or "",

            "candidates":
                row.get(
                    "candidates",
                    [],
                )
                or [],
        }

        documento[
            "resultados"
        ].append(
            resultado
        )

    return list(
        grouped.values()
    )


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
    ).strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_name = _safe_name(
        experiment_name
    )

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
        _to_dict(
            row
        )
        for row
        in rows
    ]

    # --------------------------------------------------------
    # RAW JSON
    # --------------------------------------------------------

    _write_json(
        raw_run_dir
        / "predicciones.json",
        dict_rows,
    )

    # --------------------------------------------------------
    # POR DOCUMENTO
    # --------------------------------------------------------

    documents = (
        build_document_rows(
            rows
        )
    )

    document_json = (
        document_run_dir
        / "predicciones_por_documento.json"
    )

    _write_json(
        document_json,
        documents,
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
        "raw_dir":
            raw_run_dir,

        "document_dir":
            document_run_dir,

        "raw_json":
            raw_run_dir
            / "predicciones.json",

        "document_json":
            document_json,
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