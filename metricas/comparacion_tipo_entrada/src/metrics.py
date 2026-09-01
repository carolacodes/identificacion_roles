"""Calculo de metricas globales sin gold manual."""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from .compare_by_document import (
    aggregate_documents_by_id,
    aggregate_fragments_by_document,
    document_row_summary,
)


# ============================================================
# HELPERS
# ============================================================


def pct(
    count: int,
    total: int,
) -> float:
    """Porcentaje seguro."""

    if not total:
        return 0.0

    return round(
        count
        / total
        * 100,
        4,
    )


def count_pct(
    count: int,
    total: int,
) -> dict[
    str,
    float | int,
]:
    """Cantidad + porcentaje."""

    return {

        "cantidad":
            count,

        "porcentaje":
            pct(
                count,
                total,
            ),
    }


def numeric_stats(
    values: list[Any],
) -> dict[
    str,
    float | None,
]:
    """Estadisticas ignorando nulos."""

    clean = [
        float(
            value
        )
        for value in values
        if value is not None
    ]

    if not clean:

        return {

            "media":
                None,

            "mediana":
                None,

            "minimo":
                None,

            "maximo":
                None,
        }

    return {

        "media":
            mean(
                clean
            ),

        "mediana":
            median(
                clean
            ),

        "minimo":
            min(
                clean
            ),

        "maximo":
            max(
                clean
            ),
    }


def is_simple_schema(
    rows: list[
        dict[str, Any]
    ],
) -> bool:
    """
    Detecta si el dataset usa schema_v1_persona_simple.
    """

    if not rows:
        return False

    schema = str(
        rows[0].get(
            "schema",
            "",
        )
    ).lower()

    return (
        "persona_simple"
        in schema
        or schema
        == "schema_v1"
    )


# ============================================================
# COBERTURA DOCUMENTOS
# ============================================================


def coverage_document_rows(
    document_rows: list[
        dict[str, Any]
    ],
) -> dict[
    str,
    Any,
]:
    """Cobertura por documento unico."""

    aggregated = (
        aggregate_documents_by_id(
            document_rows
        )
    )

    summaries = [
        document_row_summary(
            document
        )
        for document
        in aggregated.values()
    ]

    total = len(
        summaries
    )

    con_nombre = sum(
        summary[
            "docs_detecto_nombre"
        ]
        for summary
        in summaries
    )

    con_dni = sum(
        summary[
            "docs_detecto_dni"
        ]
        for summary
        in summaries
    )

    con_cuil = sum(
        summary[
            "docs_detecto_cuil_cuit"
        ]
        for summary
        in summaries
    )

    con_algo = sum(
        (
            summary[
                "docs_detecto_nombre"
            ]
            or summary[
                "docs_detecto_dni"
            ]
            or summary[
                "docs_detecto_cuil_cuit"
            ]
        )
        for summary
        in summaries
    )

    sin_deteccion = (
        total
        - con_algo
    )

    multiples = sum(
        summary[
            "docs_multiples_candidatos"
        ]
        for summary
        in summaries
    )

    candidatos_unicos = sum(
        (
            summary[
                "docs_detecto_nombre"
            ]
            and not summary[
                "docs_multiples_candidatos"
            ]
        )
        for summary
        in summaries
    )

    result = {

        "total_documentos":
            total,

        "documentos_con_alguna_deteccion":
            count_pct(
                con_algo,
                total,
            ),

        "documentos_con_nombre":
            count_pct(
                con_nombre,
                total,
            ),

        "documentos_no_detectados":
            count_pct(
                sin_deteccion,
                total,
            ),

        "documentos_multiples_candidatos":
            count_pct(
                multiples,
                total,
            ),

        "documentos_candidato_unico":
            count_pct(
                candidatos_unicos,
                total,
            ),
    }

    if not is_simple_schema(
        document_rows
    ):

        result[
            "documentos_con_dni"
        ] = count_pct(
            con_dni,
            total,
        )

        result[
            "documentos_con_cuil_cuit"
        ] = count_pct(
            con_cuil,
            total,
        )

    return result


# ============================================================
# COBERTURA FRAGMENTOS
# ============================================================


def coverage_fragment_rows(
    fragment_rows: list[
        dict[str, Any]
    ],
) -> dict[
    str,
    Any,
]:
    """Cobertura de fragmentos agrupados por documento."""

    aggregated = (
        aggregate_fragments_by_document(
            fragment_rows
        )
    )

    total = len(
        aggregated
    )

    values = list(
        aggregated.values()
    )

    con_nombre = sum(
        bool(
            value[
                "nombres_normalizados"
            ]
        )
        for value
        in values
    )

    con_dni = sum(
        bool(
            value[
                "dni_normalizados"
            ]
        )
        for value
        in values
    )

    con_cuil = sum(
        bool(
            value[
                "cuil_cuit_normalizados"
            ]
        )
        for value
        in values
    )

    con_algo = sum(
        bool(
            value[
                "nombres_normalizados"
            ]
            or value[
                "dni_normalizados"
            ]
            or value[
                "cuil_cuit_normalizados"
            ]
        )
        for value
        in values
    )

    multiples_nombre = sum(
        value[
            "cantidad_nombres_distintos"
        ] > 1
        for value
        in values
    )

    candidato_unico = sum(
        value[
            "cantidad_nombres_distintos"
        ] == 1
        for value
        in values
    )

    result = {

        "total_documentos":
            total,

        "total_fragmentos":
            len(
                fragment_rows
            ),

        "documentos_con_alguna_deteccion":
            count_pct(
                con_algo,
                total,
            ),

        "documentos_con_nombre":
            count_pct(
                con_nombre,
                total,
            ),

        "documentos_sin_deteccion_en_ningun_fragmento":
            count_pct(
                (
                    total
                    - con_algo
                ),
                total,
            ),

        "documentos_con_multiples_nombres_distintos":
            count_pct(
                multiples_nombre,
                total,
            ),

        "documentos_con_un_nombre_unico":
            count_pct(
                candidato_unico,
                total,
            ),
    }

    if not is_simple_schema(
        fragment_rows
    ):

        result[
            "documentos_con_dni"
        ] = count_pct(
            con_dni,
            total,
        )

        result[
            "documentos_con_cuil_cuit"
        ] = count_pct(
            con_cuil,
            total,
        )

        result[
            "documentos_con_multiples_dni_distintos"
        ] = count_pct(
            sum(
                value[
                    "cantidad_dni_distintos"
                ] > 1
                for value
                in values
            ),
            total,
        )

        result[
            "documentos_con_multiples_cuil_cuit_distintos"
        ] = count_pct(
            sum(
                value[
                    "cantidad_cuil_cuit_distintos"
                ] > 1
                for value
                in values
            ),
            total,
        )

    return result


# ============================================================
# AGREEMENT
# ============================================================


def agreement_metrics(
    comparisons: list[
        dict[str, Any]
    ],
    simple_schema: bool,
) -> dict[
    str,
    Any,
]:
    """Agreement entre modos."""

    fields = [
        "nombre"
    ]

    if not simple_schema:

        fields.extend(
            [
                "dni",
                "cuil_cuit",
            ]
        )

    result: dict[
        str,
        Any,
    ] = {}

    for field in fields:

        denominator = sum(
            bool(
                row[
                    f"ambos_detectan_{field}"
                ]
            )
            for row
            in comparisons
        )

        count = sum(
            bool(
                row[
                    f"acuerdo_{field}"
                ]
            )
            for row
            in comparisons
        )

        result[
            f"acuerdo_{field}_count"
        ] = count

        result[
            f"acuerdo_{field}_denominador"
        ] = denominator

        result[
            f"acuerdo_{field}_pct"
        ] = pct(
            count,
            denominator,
        )

    return result


# ============================================================
# DETECCION EXCLUSIVA
# ============================================================


def exclusive_detection_metrics(
    comparisons: list[
        dict[str, Any]
    ],
    simple_schema: bool,
) -> dict[
    str,
    Any,
]:
    """Casos detectados por un modo y no por el otro."""

    total = len(
        comparisons
    )

    fields = [
        "nombre"
    ]

    if not simple_schema:

        fields.extend(
            [
                "dni",
                "cuil_cuit",
            ]
        )

    result: dict[
        str,
        Any,
    ] = {

        "total_documentos_comparados":
            total
    }

    for field in fields:

        result[
            field
        ] = {

            "solo_documento":
                count_pct(
                    sum(
                        bool(
                            row[
                                f"solo_documento_detecta_{field}"
                            ]
                        )
                        for row
                        in comparisons
                    ),
                    total,
                ),

            "solo_fragmentos":
                count_pct(
                    sum(
                        bool(
                            row[
                                f"solo_fragmentos_detectan_{field}"
                            ]
                        )
                        for row
                        in comparisons
                    ),
                    total,
                ),

            "ambos":
                count_pct(
                    sum(
                        bool(
                            row[
                                f"ambos_detectan_{field}"
                            ]
                        )
                        for row
                        in comparisons
                    ),
                    total,
                ),

            "ninguno":
                count_pct(
                    sum(
                        bool(
                            row[
                                f"ninguno_detecta_{field}"
                            ]
                        )
                        for row
                        in comparisons
                    ),
                    total,
                ),
        }

    return result


# ============================================================
# AMBIGUEDAD
# ============================================================


def ambiguity_metrics(
    comparisons: list[
        dict[str, Any]
    ],
    simple_schema: bool,
) -> dict[
    str,
    Any,
]:
    """Cantidad de valores distintos detectados."""

    total = len(
        comparisons
    )

    fields = {

        "nombre":
            "frag_nombres_normalizados",
    }

    if not simple_schema:

        fields.update(
            {

                "dni":
                    "frag_dni_normalizados",

                "cuil_cuit":
                    "frag_cuil_cuit_normalizados",
            }
        )

    result: dict[
        str,
        Any,
    ] = {}

    for (
        field,
        key,
    ) in fields.items():

        result[
            field
        ] = {

            "0_unicos":
                count_pct(
                    sum(
                        len(
                            row[
                                key
                            ]
                        ) == 0
                        for row
                        in comparisons
                    ),
                    total,
                ),

            "1_unico":
                count_pct(
                    sum(
                        len(
                            row[
                                key
                            ]
                        ) == 1
                        for row
                        in comparisons
                    ),
                    total,
                ),

            "mas_de_1_unico":
                count_pct(
                    sum(
                        len(
                            row[
                                key
                            ]
                        ) > 1
                        for row
                        in comparisons
                    ),
                    total,
                ),
        }

    return result


# ============================================================
# CONFIDENCE
# ============================================================


def confidence_metrics(
    comparisons: list[
        dict[str, Any]
    ],
    simple_schema: bool,
) -> dict[
    str,
    Any,
]:
    """Estadisticas de confidence."""

    documentos = {

        "nombre_confidence":
            numeric_stats(
                [
                    row[
                        "docs_nombre_confidence"
                    ]
                    for row
                    in comparisons
                ]
            )
    }

    fragmentos = {

        "nombre_confidence_max_por_documento":
            numeric_stats(
                [
                    row[
                        "frag_nombre_confidence_max"
                    ]
                    for row
                    in comparisons
                ]
            ),

        "nombre_confidence_media_por_documento":
            numeric_stats(
                [
                    row[
                        "frag_nombre_confidence_media"
                    ]
                    for row
                    in comparisons
                ]
            ),
    }

    if not simple_schema:

        documentos.update(
            {

                "dni_confidence":
                    numeric_stats(
                        [
                            row[
                                "docs_dni_confidence"
                            ]
                            for row
                            in comparisons
                        ]
                    ),

                "cuil_cuit_confidence":
                    numeric_stats(
                        [
                            row[
                                "docs_cuil_cuit_confidence"
                            ]
                            for row
                            in comparisons
                        ]
                    ),
            }
        )

        fragmentos.update(
            {

                "dni_confidence_max_por_documento":
                    numeric_stats(
                        [
                            row[
                                "frag_dni_confidence_max"
                            ]
                            for row
                            in comparisons
                        ]
                    ),

                "dni_confidence_media_por_documento":
                    numeric_stats(
                        [
                            row[
                                "frag_dni_confidence_media"
                            ]
                            for row
                            in comparisons
                        ]
                    ),

                "cuil_cuit_confidence_max_por_documento":
                    numeric_stats(
                        [
                            row[
                                "frag_cuil_cuit_confidence_max"
                            ]
                            for row
                            in comparisons
                        ]
                    ),

                "cuil_cuit_confidence_media_por_documento":
                    numeric_stats(
                        [
                            row[
                                "frag_cuil_cuit_confidence_media"
                            ]
                            for row
                            in comparisons
                        ]
                    ),
            }
        )

    return {

        "documentos":
            documentos,

        "fragmentos":
            fragmentos,
    }


# ============================================================
# TIEMPOS
# ============================================================


def timing_metrics(
    docs_seconds: float | None,
    fragments_seconds: float | None,
    total_docs: int,
    total_fragments: int,
) -> dict[
    str,
    Any,
]:
    """Metricas de rendimiento."""

    return {

        "tiempo_total_documentos":
            docs_seconds,

        "tiempo_total_fragmentos":
            fragments_seconds,

        "segundos_por_documento_documentos":
            (
                docs_seconds
                / total_docs
                if (
                    docs_seconds
                    is not None
                    and total_docs
                )
                else None
            ),

        "segundos_por_documento_fragmentos":
            (
                fragments_seconds
                / total_docs
                if (
                    fragments_seconds
                    is not None
                    and total_docs
                )
                else None
            ),

        "segundos_por_fragmento":
            (
                fragments_seconds
                / total_fragments
                if (
                    fragments_seconds
                    is not None
                    and total_fragments
                )
                else None
            ),

        "speedup_fragmentos_vs_documentos":
            (
                docs_seconds
                / fragments_seconds
                if (
                    docs_seconds
                    is not None
                    and fragments_seconds
                    not in (
                        None,
                        0,
                    )
                )
                else None
            ),
    }


# ============================================================
# GLOBAL
# ============================================================


def compute_global_metrics(
    document_rows: list[
        dict[str, Any]
    ],
    fragment_rows: list[
        dict[str, Any]
    ],
    comparisons: list[
        dict[str, Any]
    ],
    metadata: dict[
        str,
        Any
    ],
    docs_seconds: float | None = None,
    fragments_seconds: float | None = None,
) -> dict[
    str,
    Any,
]:
    """Compone todas las metricas."""

    simple_schema = (
        is_simple_schema(
            document_rows
        )
        or is_simple_schema(
            fragment_rows
        )
    )

    unique_docs_dataset_docs = {
        str(
            row.get(
                "id"
            )
        )
        for row
        in document_rows
    }

    unique_docs_dataset_fragments = {
        str(
            row.get(
                "id"
            )
        )
        for row
        in fragment_rows
    }

    return {

        "configuracion": {

            "modelo":
                metadata.get(
                    "modelo"
                ),

            "schema":
                metadata.get(
                    "schema"
                ),

            "schema_simple":
                simple_schema,

            "threshold":
                metadata.get(
                    "threshold"
                ),

            "cantidad_documentos_dataset_documentos":
                len(
                    unique_docs_dataset_docs
                ),

            "cantidad_documentos_dataset_fragmentos":
                len(
                    unique_docs_dataset_fragments
                ),

            "cantidad_documentos_comparados":
                len(
                    comparisons
                ),

            "cantidad_fragmentos":
                len(
                    fragment_rows
                ),

            "ids_solo_documentos":
                metadata.get(
                    "ids_solo_documentos",
                    [],
                ),

            "ids_solo_fragmentos":
                metadata.get(
                    "ids_solo_fragmentos",
                    [],
                ),

            "ids_comunes":
                metadata.get(
                    "ids_comunes",
                    [],
                ),
        },

        "cobertura_documentos_completos":
            coverage_document_rows(
                document_rows
            ),

        "cobertura_fragmentos_por_documento":
            coverage_fragment_rows(
                fragment_rows
            ),

        "agreement_entre_modos":
            agreement_metrics(
                comparisons,
                simple_schema,
            ),

        "deteccion_exclusiva":
            exclusive_detection_metrics(
                comparisons,
                simple_schema,
            ),

        "ambiguedad_fragmentos":
            ambiguity_metrics(
                comparisons,
                simple_schema,
            ),

        "confidence":
            confidence_metrics(
                comparisons,
                simple_schema,
            ),

        "rendimiento":
            timing_metrics(
                docs_seconds=docs_seconds,
                fragments_seconds=fragments_seconds,
                total_docs=len(
                    comparisons
                ),
                total_fragments=len(
                    fragment_rows
                ),
            ),
    }