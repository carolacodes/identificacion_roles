"""Agregacion de documentos, fragmentos y comparacion por documento."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Callable

from .normalize import (
    is_present,
    normalize_cuil_cuit,
    normalize_dni,
    normalize_name,
    to_float,
)


Normalizer = Callable[[Any], str]


# ============================================================
# HELPERS GENERALES
# ============================================================


def first_present(
    row: dict[str, Any],
    *fields: str,
) -> Any:
    """Devuelve el primer valor presente entre varios campos posibles."""

    for field in fields:
        value = row.get(field)

        if is_present(value):
            return value

    return None


def first_float(
    row: dict[str, Any],
    *fields: str,
) -> float | None:
    """Devuelve el primer valor convertible a float."""

    for field in fields:
        value = to_float(
            row.get(field)
        )

        if value is not None:
            return value

    return None


def schema_name(
    row: dict[str, Any],
) -> str:
    """Devuelve el nombre del schema en minusculas."""

    return str(
        row.get(
            "schema",
            "",
        )
    ).strip().lower()


def is_simple_person_schema(
    row: dict[str, Any],
) -> bool:
    """
    Detecta si la fila pertenece al schema simple de persona embargada.
    """

    schema = schema_name(row)

    return (
        "persona_simple" in schema
        or schema == "schema_v1"
    )


def get_person_name(
    row: dict[str, Any],
) -> Any:
    """
    Obtiene el nombre de la persona embargada independientemente
    del formato del schema.

    Structured:
        nombre_detectado

    Simple:
        entidad_tipo == persona_embargada
        entidad_valor
    """

    structured_name = row.get(
        "nombre_detectado"
    )

    if is_present(
        structured_name
    ):
        return structured_name

    if (
        str(
            row.get(
                "entidad_tipo",
                "",
            )
        ).strip().lower()
        == "persona_embargada"
    ):
        return row.get(
            "entidad_valor"
        )

    return None


def get_person_confidence(
    row: dict[str, Any],
) -> float | None:
    """
    Obtiene confidence de nombre.

    Structured:
        nombre_confidence

    Simple:
        confidence
    """

    value = to_float(
        row.get(
            "nombre_confidence"
        )
    )

    if value is not None:
        return value

    if (
        str(
            row.get(
                "entidad_tipo",
                "",
            )
        ).strip().lower()
        == "persona_embargada"
    ):
        return to_float(
            row.get(
                "confidence"
            )
        )

    return None


def get_dni(
    row: dict[str, Any],
) -> Any:
    """Obtiene DNI solo si existe en la salida estructurada."""

    return row.get(
        "dni_detectado"
    )


def get_dni_confidence(
    row: dict[str, Any],
) -> float | None:
    """Obtiene confidence del DNI."""

    return to_float(
        row.get(
            "dni_confidence"
        )
    )


def get_cuil_cuit(
    row: dict[str, Any],
) -> Any:
    """Obtiene CUIL/CUIT solo si existe en la salida estructurada."""

    return row.get(
        "cuil_cuit_detectado"
    )


def get_cuil_cuit_confidence(
    row: dict[str, Any],
) -> float | None:
    """Obtiene confidence del CUIL/CUIT."""

    return to_float(
        row.get(
            "cuil_cuit_confidence"
        )
    )


def has_candidate(
    row: dict[str, Any],
) -> bool:
    """Indica si la fila contiene al menos una deteccion relevante."""

    return any(
        (
            is_present(
                get_person_name(row)
            ),
            is_present(
                get_dni(row)
            ),
            is_present(
                get_cuil_cuit(row)
            ),
        )
    )


def unique_preserving_order(
    values: list[Any],
    normalizer: Normalizer,
) -> tuple[list[str], list[str]]:
    """
    Devuelve valores originales y normalizados unicos,
    preservando el orden.
    """

    originals: list[str] = []
    normalized: list[str] = []

    seen: set[str] = set()

    for value in values:

        norm = normalizer(
            value
        )

        if not norm:
            continue

        if norm in seen:
            continue

        seen.add(
            norm
        )

        originals.append(
            str(
                value
            ).strip()
        )

        normalized.append(
            norm
        )

    return (
        originals,
        normalized,
    )


def _confidence_stats(
    values: list[float | None],
) -> tuple[
    float | None,
    float | None,
]:
    """Devuelve confidence maxima y media."""

    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return (
            None,
            None,
        )

    return (
        max(clean),
        mean(clean),
    )


# ============================================================
# FRAGMENTOS
# ============================================================


def aggregate_fragments_by_document(
    fragment_rows: list[
        dict[str, Any]
    ],
) -> dict[
    str,
    dict[str, Any],
]:
    """
    Agrupa predicciones de fragmentos por id.
    """

    grouped: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = defaultdict(list)

    for row in fragment_rows:

        doc_id = str(
            row.get(
                "id"
            )
        )

        grouped[
            doc_id
        ].append(
            row
        )

    aggregated: dict[
        str,
        dict[str, Any],
    ] = {}

    for (
        doc_id,
        rows,
    ) in grouped.items():

        names = [
            get_person_name(
                row
            )
            for row in rows
        ]

        dnis = [
            get_dni(
                row
            )
            for row in rows
        ]

        cuils = [
            get_cuil_cuit(
                row
            )
            for row in rows
        ]

        (
            name_originals,
            name_norms,
        ) = unique_preserving_order(
            names,
            normalize_name,
        )

        (
            dni_originals,
            dni_norms,
        ) = unique_preserving_order(
            dnis,
            normalize_dni,
        )

        (
            cuil_originals,
            cuil_norms,
        ) = unique_preserving_order(
            cuils,
            normalize_cuil_cuit,
        )

        name_confidences = [
            get_person_confidence(
                row
            )
            for row in rows
            if is_present(
                get_person_name(
                    row
                )
            )
        ]

        dni_confidences = [
            get_dni_confidence(
                row
            )
            for row in rows
            if is_present(
                get_dni(
                    row
                )
            )
        ]

        cuil_confidences = [
            get_cuil_cuit_confidence(
                row
            )
            for row in rows
            if is_present(
                get_cuil_cuit(
                    row
                )
            )
        ]

        (
            name_max,
            name_mean,
        ) = _confidence_stats(
            name_confidences
        )

        (
            dni_max,
            dni_mean,
        ) = _confidence_stats(
            dni_confidences
        )

        (
            cuil_max,
            cuil_mean,
        ) = _confidence_stats(
            cuil_confidences
        )

        aggregated[
            doc_id
        ] = {

            "id":
                doc_id,

            "numero_archivo":
                first_present(
                    rows[0],
                    "numero_archivo",
                ),

            "nombre_documento":
                first_present(
                    rows[0],
                    "nombre",
                ),

            "schema":
                first_present(
                    rows[0],
                    "schema",
                ),

            "cantidad_fragmentos":
                len(rows),

            "fragmentos_con_candidato":
                sum(
                    1
                    for row in rows
                    if has_candidate(
                        row
                    )
                ),

            "cantidad_nombres_distintos":
                len(
                    name_norms
                ),

            "cantidad_dni_distintos":
                len(
                    dni_norms
                ),

            "cantidad_cuil_cuit_distintos":
                len(
                    cuil_norms
                ),

            "nombres_detectados":
                name_originals,

            "dni_detectados":
                dni_originals,

            "cuil_cuit_detectados":
                cuil_originals,

            "nombres_normalizados":
                name_norms,

            "dni_normalizados":
                dni_norms,

            "cuil_cuit_normalizados":
                cuil_norms,

            "nombre_confidence_max":
                name_max,

            "nombre_confidence_media":
                name_mean,

            "dni_confidence_max":
                dni_max,

            "dni_confidence_media":
                dni_mean,

            "cuil_cuit_confidence_max":
                cuil_max,

            "cuil_cuit_confidence_media":
                cuil_mean,
        }

    return aggregated


# ============================================================
# DOCUMENTOS COMPLETOS
# ============================================================


def aggregate_documents_by_id(
    document_rows: list[
        dict[str, Any]
    ],
) -> dict[
    str,
    dict[str, Any],
]:
    """
    Agrupa resultados de documentos completos por id.

    Soporta:
    - schema simple
    - schema structured
    """

    grouped: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = defaultdict(list)

    for row in document_rows:

        doc_id = str(
            row.get(
                "id"
            )
        )

        grouped[
            doc_id
        ].append(
            row
        )

    aggregated: dict[
        str,
        dict[str, Any],
    ] = {}

    for (
        doc_id,
        rows,
    ) in grouped.items():

        names = [
            get_person_name(
                row
            )
            for row in rows
        ]

        dnis = [
            get_dni(
                row
            )
            for row in rows
        ]

        cuils = [
            get_cuil_cuit(
                row
            )
            for row in rows
        ]

        (
            name_originals,
            name_norms,
        ) = unique_preserving_order(
            names,
            normalize_name,
        )

        (
            dni_originals,
            dni_norms,
        ) = unique_preserving_order(
            dnis,
            normalize_dni,
        )

        (
            cuil_originals,
            cuil_norms,
        ) = unique_preserving_order(
            cuils,
            normalize_cuil_cuit,
        )

        name_confidences = [
            get_person_confidence(
                row
            )
            for row in rows
            if is_present(
                get_person_name(
                    row
                )
            )
        ]

        dni_confidences = [
            get_dni_confidence(
                row
            )
            for row in rows
            if is_present(
                get_dni(
                    row
                )
            )
        ]

        cuil_confidences = [
            get_cuil_cuit_confidence(
                row
            )
            for row in rows
            if is_present(
                get_cuil_cuit(
                    row
                )
            )
        ]

        (
            name_max,
            name_mean,
        ) = _confidence_stats(
            name_confidences
        )

        (
            dni_max,
            dni_mean,
        ) = _confidence_stats(
            dni_confidences
        )

        (
            cuil_max,
            cuil_mean,
        ) = _confidence_stats(
            cuil_confidences
        )

        postprocess_states = {
            str(
                row.get(
                    "estado_postprocess",
                    "",
                )
            )
            for row in rows
            if row.get(
                "estado_postprocess"
            )
        }

        explicit_multiple = (
            "multiples_candidatos"
            in postprocess_states
        )

        inferred_multiple = (
            len(
                name_norms
            ) > 1
            or len(
                dni_norms
            ) > 1
            or len(
                cuil_norms
            ) > 1
        )

        multiple_candidates = (
            explicit_multiple
            or inferred_multiple
        )

        aggregated[
            doc_id
        ] = {

            "id":
                doc_id,

            "numero_archivo":
                first_present(
                    rows[0],
                    "numero_archivo",
                ),

            "nombre_documento":
                first_present(
                    rows[0],
                    "nombre",
                ),

            "schema":
                first_present(
                    rows[0],
                    "schema",
                ),

            "cantidad_filas":
                len(
                    rows
                ),

            "filas_con_candidato":
                sum(
                    1
                    for row in rows
                    if has_candidate(
                        row
                    )
                ),

            "nombres_detectados":
                name_originals,

            "nombres_normalizados":
                name_norms,

            "dni_detectados":
                dni_originals,

            "dni_normalizados":
                dni_norms,

            "cuil_cuit_detectados":
                cuil_originals,

            "cuil_cuit_normalizados":
                cuil_norms,

            "cantidad_nombres_distintos":
                len(
                    name_norms
                ),

            "cantidad_dni_distintos":
                len(
                    dni_norms
                ),

            "cantidad_cuil_cuit_distintos":
                len(
                    cuil_norms
                ),

            "nombre_confidence_max":
                name_max,

            "nombre_confidence_media":
                name_mean,

            "dni_confidence_max":
                dni_max,

            "dni_confidence_media":
                dni_mean,

            "cuil_cuit_confidence_max":
                cuil_max,

            "cuil_cuit_confidence_media":
                cuil_mean,

            "estados_postprocess":
                sorted(
                    postprocess_states
                ),

            "multiples_candidatos":
                multiple_candidates,
        }

    return aggregated


def document_row_summary(
    document: dict[
        str,
        Any,
    ],
) -> dict[
    str,
    Any,
]:
    """
    Convierte un documento agregado en representacion comparable.
    """

    names = document.get(
        "nombres_detectados",
        [],
    )

    name_norms = document.get(
        "nombres_normalizados",
        [],
    )

    dnis = document.get(
        "dni_detectados",
        [],
    )

    dni_norms = document.get(
        "dni_normalizados",
        [],
    )

    cuils = document.get(
        "cuil_cuit_detectados",
        [],
    )

    cuil_norms = document.get(
        "cuil_cuit_normalizados",
        [],
    )

    primary_name = (
        names[0]
        if len(
            names
        ) == 1
        else None
    )

    primary_name_norm = (
        name_norms[0]
        if len(
            name_norms
        ) == 1
        else ""
    )

    primary_dni = (
        dnis[0]
        if len(
            dnis
        ) == 1
        else None
    )

    primary_dni_norm = (
        dni_norms[0]
        if len(
            dni_norms
        ) == 1
        else ""
    )

    primary_cuil = (
        cuils[0]
        if len(
            cuils
        ) == 1
        else None
    )

    primary_cuil_norm = (
        cuil_norms[0]
        if len(
            cuil_norms
        ) == 1
        else ""
    )

    return {

        "id":
            document.get(
                "id"
            ),

        "numero_archivo":
            document.get(
                "numero_archivo"
            ),

        "nombre_documento":
            document.get(
                "nombre_documento"
            ),

        "schema":
            document.get(
                "schema"
            ),

        "docs_detecto_nombre":
            bool(
                name_norms
            ),

        "docs_nombre":
            primary_name,

        "docs_nombre_normalizado":
            primary_name_norm,

        "docs_nombres_unicos":
            names,

        "docs_nombres_normalizados":
            name_norms,

        "docs_nombre_confidence":
            document.get(
                "nombre_confidence_max"
            ),

        "docs_detecto_dni":
            bool(
                dni_norms
            ),

        "docs_dni":
            primary_dni,

        "docs_dni_normalizado":
            primary_dni_norm,

        "docs_dni_unicos":
            dnis,

        "docs_dni_normalizados":
            dni_norms,

        "docs_dni_confidence":
            document.get(
                "dni_confidence_max"
            ),

        "docs_detecto_cuil_cuit":
            bool(
                cuil_norms
            ),

        "docs_cuil_cuit":
            primary_cuil,

        "docs_cuil_cuit_normalizado":
            primary_cuil_norm,

        "docs_cuil_cuit_unicos":
            cuils,

        "docs_cuil_cuit_normalizados":
            cuil_norms,

        "docs_cuil_cuit_confidence":
            document.get(
                "cuil_cuit_confidence_max"
            ),

        "docs_estado_postprocess":
            document.get(
                "estados_postprocess"
            ),

        "docs_multiples_candidatos":
            bool(
                document.get(
                    "multiples_candidatos"
                )
            ),
    }


# ============================================================
# COMPARACION
# ============================================================


def _field_flags(
    doc_detects: bool,
    frag_detects: bool,
    agreement: bool,
    field: str,
) -> dict[
    str,
    bool,
]:
    """Genera flags de comparacion."""

    return {

        f"acuerdo_{field}":
            agreement,

        f"ambos_detectan_{field}":
            (
                doc_detects
                and frag_detects
            ),

        f"solo_documento_detecta_{field}":
            (
                doc_detects
                and not frag_detects
            ),

        f"solo_fragmentos_detectan_{field}":
            (
                frag_detects
                and not doc_detects
            ),

        f"ninguno_detecta_{field}":
            (
                not doc_detects
                and not frag_detects
            ),
    }


def _has_overlap(
    left: list[str],
    right: list[str],
) -> bool:
    """True si ambas listas comparten algun valor."""

    if not left:
        return False

    if not right:
        return False

    return bool(
        set(left)
        & set(right)
    )


def compare_by_document(
    document_rows: list[
        dict[str, Any]
    ],
    fragment_rows: list[
        dict[str, Any]
    ],
    ids: list[str] | None = None,
) -> list[
    dict[str, Any]
]:
    """
    Crea comparacion por documento.
    """

    documents_by_id = (
        aggregate_documents_by_id(
            document_rows
        )
    )

    fragments_by_id = (
        aggregate_fragments_by_document(
            fragment_rows
        )
    )

    common_ids = (
        ids
        if ids is not None
        else sorted(
            set(
                documents_by_id
            )
            & set(
                fragments_by_id
            )
        )
    )

    comparisons: list[
        dict[str, Any]
    ] = []

    for doc_id in common_ids:

        if doc_id not in documents_by_id:
            continue

        if doc_id not in fragments_by_id:
            continue

        doc = document_row_summary(
            documents_by_id[
                doc_id
            ]
        )

        frag = fragments_by_id[
            doc_id
        ]

        row: dict[
            str,
            Any,
        ] = {

            "id":
                doc_id,

            "numero_archivo":
                (
                    doc.get(
                        "numero_archivo"
                    )
                    or frag.get(
                        "numero_archivo"
                    )
                ),

            "nombre_documento":
                (
                    doc.get(
                        "nombre_documento"
                    )
                    or frag.get(
                        "nombre_documento"
                    )
                ),

            "schema":
                (
                    doc.get(
                        "schema"
                    )
                    or frag.get(
                        "schema"
                    )
                ),

            **doc,

            "docs_detecto_algo":
                (
                    doc[
                        "docs_detecto_nombre"
                    ]
                    or doc[
                        "docs_detecto_dni"
                    ]
                    or doc[
                        "docs_detecto_cuil_cuit"
                    ]
                ),

            "frag_cantidad_fragmentos":
                frag[
                    "cantidad_fragmentos"
                ],

            "frag_fragmentos_con_candidato":
                frag[
                    "fragmentos_con_candidato"
                ],

            "frag_detecto_nombre":
                bool(
                    frag[
                        "nombres_normalizados"
                    ]
                ),

            "frag_nombres_unicos":
                frag[
                    "nombres_detectados"
                ],

            "frag_nombres_normalizados":
                frag[
                    "nombres_normalizados"
                ],

            "frag_detecto_dni":
                bool(
                    frag[
                        "dni_normalizados"
                    ]
                ),

            "frag_dni_unicos":
                frag[
                    "dni_detectados"
                ],

            "frag_dni_normalizados":
                frag[
                    "dni_normalizados"
                ],

            "frag_detecto_cuil_cuit":
                bool(
                    frag[
                        "cuil_cuit_normalizados"
                    ]
                ),

            "frag_cuil_cuit_unicos":
                frag[
                    "cuil_cuit_detectados"
                ],

            "frag_cuil_cuit_normalizados":
                frag[
                    "cuil_cuit_normalizados"
                ],

            "frag_nombre_confidence_max":
                frag[
                    "nombre_confidence_max"
                ],

            "frag_nombre_confidence_media":
                frag[
                    "nombre_confidence_media"
                ],

            "frag_dni_confidence_max":
                frag[
                    "dni_confidence_max"
                ],

            "frag_dni_confidence_media":
                frag[
                    "dni_confidence_media"
                ],

            "frag_cuil_cuit_confidence_max":
                frag[
                    "cuil_cuit_confidence_max"
                ],

            "frag_cuil_cuit_confidence_media":
                frag[
                    "cuil_cuit_confidence_media"
                ],
        }

        row[
            "frag_detecto_algo"
        ] = (
            row[
                "frag_detecto_nombre"
            ]
            or row[
                "frag_detecto_dni"
            ]
            or row[
                "frag_detecto_cuil_cuit"
            ]
        )

        row.update(
            _field_flags(
                doc_detects=row[
                    "docs_detecto_nombre"
                ],
                frag_detects=row[
                    "frag_detecto_nombre"
                ],
                agreement=_has_overlap(
                    row[
                        "docs_nombres_normalizados"
                    ],
                    row[
                        "frag_nombres_normalizados"
                    ],
                ),
                field="nombre",
            )
        )

        row.update(
            _field_flags(
                doc_detects=row[
                    "docs_detecto_dni"
                ],
                frag_detects=row[
                    "frag_detecto_dni"
                ],
                agreement=_has_overlap(
                    row[
                        "docs_dni_normalizados"
                    ],
                    row[
                        "frag_dni_normalizados"
                    ],
                ),
                field="dni",
            )
        )

        row.update(
            _field_flags(
                doc_detects=row[
                    "docs_detecto_cuil_cuit"
                ],
                frag_detects=row[
                    "frag_detecto_cuil_cuit"
                ],
                agreement=_has_overlap(
                    row[
                        "docs_cuil_cuit_normalizados"
                    ],
                    row[
                        "frag_cuil_cuit_normalizados"
                    ],
                ),
                field="cuil_cuit",
            )
        )

        comparisons.append(
            row
        )

    return comparisons