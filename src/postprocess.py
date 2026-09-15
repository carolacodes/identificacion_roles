"""Normalizacion conservadora de candidatos."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .inference import PredictionResult


@dataclass(slots=True)
class PostprocessedResult:
    """Resultado normalizado para exportacion."""

    prediction: PredictionResult
    status: str

    candidates: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )


def postprocess_results(
    predictions: list[
        PredictionResult
    ],
) -> list[
    PostprocessedResult
]:

    return [
        postprocess_prediction(
            prediction
        )
        for prediction
        in predictions
    ]


def postprocess_prediction(
    prediction: PredictionResult,
) -> PostprocessedResult:

    candidates = _extract_candidates(
        prediction
    )

    if not candidates:

        status = "no_detectado"

    elif len(candidates) == 1:

        status = "candidato_unico"

    else:

        status = "multiples_candidatos"

    return PostprocessedResult(
        prediction=prediction,
        status=status,
        candidates=candidates,
    )


def _extract_candidates(
    prediction: PredictionResult,
) -> list[
    dict[str, Any]
]:

    if (
        prediction.schema_type
        == "structured"
    ):
        return _structured_candidates(
            prediction.raw_response
        )

    return _entity_candidates(
        prediction.normalized_items
    )


# ============================================================
# ENTITY SCHEMAS
# ============================================================

def _entity_candidates(
    items: list[
        dict[str, Any]
    ],
) -> list[
    dict[str, Any]
]:

    candidates: list[
        dict[str, Any]
    ] = []

    for item in items:

        value = _first_present(
            item,
            (
                "text",
                "value",
                "span",
            ),
        )

        if value in (
            None,
            "",
        ):
            continue

        candidates.append(
            {
                "tipo": (
                    item.get(
                        "entity_type"
                    )
                    or item.get(
                        "label"
                    )
                ),

                "valor": value,

                "confidence":
                    _first_present(
                        item,
                        (
                            "score",
                            "confidence",
                            "probability",
                        ),
                    ),

                "span_inicio":
                    _first_present(
                        item,
                        (
                            "start",
                            "start_char",
                            "span_inicio",
                        ),
                    ),

                "span_fin":
                    _first_present(
                        item,
                        (
                            "end",
                            "end_char",
                            "span_fin",
                        ),
                    ),
            }
        )

    return candidates


# ============================================================
# STRUCTURED
# ============================================================

def _structured_candidates(
    raw_response: Any,
) -> list[
    dict[str, Any]
]:

    if not isinstance(
        raw_response,
        dict,
    ):
        return []

    candidates: list[
        dict[str, Any]
    ] = []

    for (
        structure_name,
        structures,
    ) in raw_response.items():

        if structures is None:
            continue

        if not isinstance(
            structures,
            list,
        ):
            structures = [
                structures
            ]

        for structure in structures:

            if not isinstance(
                structure,
                dict,
            ):
                continue

            candidate = (
                _normalize_structure(
                    structure_name,
                    structure,
                )
            )

            if candidate is not None:

                candidates.append(
                    candidate
                )

    return candidates


def _normalize_structure(
    structure_name: str,
    structure: dict[str, Any],
) -> dict[str, Any] | None:

    candidate: dict[
        str,
        Any,
    ] = {
        "tipo":
            structure_name,

        "valor":
            None,

        "fields":
            {},
    }

    found_any_value = False

    confidences: list[
        float
    ] = []

    for (
        field_name,
        field_value,
    ) in structure.items():

        normalized_field = (
            _normalize_field(
                field_value
            )
        )

        candidate[
            "fields"
        ][
            field_name
        ] = normalized_field

        if normalized_field[
            "text"
        ] not in (
            None,
            "",
        ):
            found_any_value = True

        confidence = (
            normalized_field.get(
                "confidence"
            )
        )

        if isinstance(
            confidence,
            (int, float),
        ):
            confidences.append(
                float(confidence)
            )

    if not found_any_value:
        return None

    # --------------------------------------------------------
    # Exponer siempre todos los campos structured
    # --------------------------------------------------------

    for (
        field_name,
        normalized_field,
    ) in candidate[
        "fields"
    ].items():

        candidate[
            field_name
        ] = normalized_field.get(
            "text"
        )

        candidate[
            f"{field_name}_confidence"
        ] = normalized_field.get(
            "confidence"
        )

        candidate[
            f"{field_name}_span_inicio"
        ] = normalized_field.get(
            "start"
        )

        candidate[
            f"{field_name}_span_fin"
        ] = normalized_field.get(
            "end"
        )

    # --------------------------------------------------------
    # Persona embargada
    #
    # Compatibilidad:
    #
    # V3/V6:
    #   nombre
    #   dni
    #   cuil_cuit
    #
    # V7:
    #   nombre_embargado
    #   dni_embargado
    #   cuit_cuil_embargado
    #   rol_embargado
    # --------------------------------------------------------

    if structure_name == (
        "persona_embargada"
    ):

        nombre = _get_field_alias(
            candidate["fields"],
            (
                "nombre_embargado",
                "nombre",
            ),
        )

        dni = _get_field_alias(
            candidate["fields"],
            (
                "dni_embargado",
                "dni",
            ),
        )

        cuit_cuil = (
            _get_field_alias(
                candidate["fields"],
                (
                    "cuit_cuil_embargado",
                    "cuil_cuit",
                    "cuit_cuil",
                ),
            )
        )

        rol = _get_field_alias(
            candidate["fields"],
            (
                "rol_embargado",
                "rol_mencionado",
            ),
        )

        # Nombres canonicos nuevos.
        candidate[
            "nombre_embargado"
        ] = nombre.get(
            "text"
        )

        candidate[
            "dni_embargado"
        ] = dni.get(
            "text"
        )

        candidate[
            "cuit_cuil_embargado"
        ] = cuit_cuil.get(
            "text"
        )

        candidate[
            "rol_embargado"
        ] = rol.get(
            "text"
        )

        # Compatibilidad historica.
        candidate[
            "nombre"
        ] = nombre.get(
            "text"
        )

        candidate[
            "dni"
        ] = dni.get(
            "text"
        )

        candidate[
            "cuil_cuit"
        ] = cuit_cuil.get(
            "text"
        )

        # ----------------------------------------------------
        # Confidences
        # ----------------------------------------------------

        candidate[
            "nombre_embargado_confidence"
        ] = nombre.get(
            "confidence"
        )

        candidate[
            "dni_embargado_confidence"
        ] = dni.get(
            "confidence"
        )

        candidate[
            "cuit_cuil_embargado_confidence"
        ] = cuit_cuil.get(
            "confidence"
        )

        candidate[
            "rol_embargado_confidence"
        ] = rol.get(
            "confidence"
        )

        # Compatibilidad.
        candidate[
            "nombre_confidence"
        ] = nombre.get(
            "confidence"
        )

        candidate[
            "dni_confidence"
        ] = dni.get(
            "confidence"
        )

        candidate[
            "cuil_cuit_confidence"
        ] = cuit_cuil.get(
            "confidence"
        )

        # ----------------------------------------------------
        # Spans
        # ----------------------------------------------------

        candidate[
            "nombre_embargado_span_inicio"
        ] = nombre.get(
            "start"
        )

        candidate[
            "nombre_embargado_span_fin"
        ] = nombre.get(
            "end"
        )

        candidate[
            "dni_embargado_span_inicio"
        ] = dni.get(
            "start"
        )

        candidate[
            "dni_embargado_span_fin"
        ] = dni.get(
            "end"
        )

        candidate[
            "cuit_cuil_embargado_span_inicio"
        ] = cuit_cuil.get(
            "start"
        )

        candidate[
            "cuit_cuil_embargado_span_fin"
        ] = cuit_cuil.get(
            "end"
        )

        # Compatibilidad spans antiguos.
        candidate[
            "nombre_span_inicio"
        ] = nombre.get(
            "start"
        )

        candidate[
            "nombre_span_fin"
        ] = nombre.get(
            "end"
        )

        candidate[
            "dni_span_inicio"
        ] = dni.get(
            "start"
        )

        candidate[
            "dni_span_fin"
        ] = dni.get(
            "end"
        )

        candidate[
            "cuil_cuit_span_inicio"
        ] = cuit_cuil.get(
            "start"
        )

        candidate[
            "cuil_cuit_span_fin"
        ] = cuit_cuil.get(
            "end"
        )

        # Campo principal del candidato.
        candidate[
            "valor"
        ] = nombre.get(
            "text"
        )

        candidate[
            "confidence"
        ] = nombre.get(
            "confidence"
        )

        candidate[
            "span_inicio"
        ] = nombre.get(
            "start"
        )

        candidate[
            "span_fin"
        ] = nombre.get(
            "end"
        )

    # --------------------------------------------------------
    # Otros schemas structured
    # --------------------------------------------------------

    else:

        candidate[
            "valor"
        ] = _first_text_field(
            candidate[
                "fields"
            ]
        )

        candidate[
            "confidence"
        ] = (
            min(confidences)
            if confidences
            else None
        )

        candidate[
            "span_inicio"
        ] = None

        candidate[
            "span_fin"
        ] = None

    return candidate


def _get_field_alias(
    fields: dict[
        str,
        dict[str, Any],
    ],
    aliases: tuple[str, ...],
) -> dict[str, Any]:
    """Devuelve el primer campo existente entre varios aliases."""

    for alias in aliases:

        field = fields.get(
            alias
        )

        if field is not None:
            return field

    return {
        "text": None,
        "confidence": None,
        "start": None,
        "end": None,
    }


def _normalize_field(
    value: Any,
) -> dict[str, Any]:

    if value is None:

        return {
            "text": None,
            "confidence": None,
            "start": None,
            "end": None,
        }

    if isinstance(
        value,
        dict,
    ):

        return {
            "text":
                _first_present(
                    value,
                    (
                        "text",
                        "value",
                    ),
                ),

            "confidence":
                _first_present(
                    value,
                    (
                        "confidence",
                        "score",
                        "probability",
                    ),
                ),

            "start":
                _first_present(
                    value,
                    (
                        "start",
                        "start_char",
                        "span_inicio",
                    ),
                ),

            "end":
                _first_present(
                    value,
                    (
                        "end",
                        "end_char",
                        "span_fin",
                    ),
                ),
        }

    return {
        "text": value,
        "confidence": None,
        "start": None,
        "end": None,
    }


def _first_text_field(
    fields: dict[
        str,
        dict[str, Any],
    ],
) -> Any:

    for field in fields.values():

        value = field.get(
            "text"
        )

        if value not in (
            None,
            "",
        ):
            return value

    return None


def _first_present(
    mapping: dict[str, Any],
    keys: tuple[str, ...],
) -> Any:

    for key in keys:

        if (
            key in mapping
            and mapping[key]
            not in (
                None,
                "",
            )
        ):
            return mapping[
                key
            ]

    return None