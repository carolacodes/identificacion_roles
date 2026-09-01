"""Normalización conservadora de candidatos sin reglas jurídicas complejas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .inference import PredictionResult


@dataclass(slots=True)
class PostprocessedResult:
    """Resultado normalizado para exportación y futura revisión humana."""

    prediction: PredictionResult
    status: str
    candidates: list[dict[str, Any]] = field(default_factory=list)


def postprocess_results(
    predictions: list[PredictionResult],
) -> list[PostprocessedResult]:
    """Produce candidatos conservadores a partir de predicciones crudas."""
    return [
        postprocess_prediction(prediction)
        for prediction in predictions
    ]


def postprocess_prediction(
    prediction: PredictionResult,
) -> PostprocessedResult:
    """Normaliza un resultado individual."""

    candidates = _extract_candidates(prediction)

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
) -> list[dict[str, Any]]:
    """
    Selecciona el normalizador apropiado según el tipo de schema.
    """

    if prediction.schema_type == "structured":
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
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Normaliza entidades simples como:

    persona_embargada
    demandado
    embargado
    ejecutado
    deudor
    """

    candidates: list[dict[str, Any]] = []

    for item in items:
        value = _first_present(
            item,
            (
                "text",
                "value",
                "span",
            ),
        )

        if value in (None, ""):
            continue

        candidates.append(
            {
                "tipo": (
                    item.get("entity_type")
                    or item.get("label")
                ),
                "valor": value,
                "confidence": _first_present(
                    item,
                    (
                        "score",
                        "confidence",
                        "probability",
                    ),
                ),
                "span_inicio": _first_present(
                    item,
                    (
                        "start",
                        "start_char",
                        "span_inicio",
                    ),
                ),
                "span_fin": _first_present(
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
# STRUCTURED SCHEMAS
# ============================================================

def _structured_candidates(
    raw_response: Any,
) -> list[dict[str, Any]]:
    """
    Normaliza la salida structured real de GLiNER2.

    Forma real observada:

    {
        "persona_embargada": [
            {
                "nombre": {
                    "text": "NAHUEL OSCAR MARQUEZ",
                    "confidence": 0.93,
                    "start": 125,
                    "end": 145
                },
                "dni": {
                    "text": "33.470.065",
                    "confidence": 0.98,
                    "start": 151,
                    "end": 161
                },
                "cuil_cuit": null
            }
        ]
    }

    También funciona para otras estructuras:
    - datos_embargo
    - cuenta_deposito
    """

    if not isinstance(raw_response, dict):
        return []

    candidates: list[dict[str, Any]] = []

    for structure_name, structures in raw_response.items():

        if structures is None:
            continue

        if not isinstance(structures, list):
            structures = [structures]

        for structure in structures:

            if not isinstance(structure, dict):
                continue

            candidate = _normalize_structure(
                structure_name,
                structure,
            )

            if candidate is not None:
                candidates.append(candidate)

    return candidates


def _normalize_structure(
    structure_name: str,
    structure: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Convierte cualquier structure de GLiNER2
    a una representación homogénea.
    """

    candidate: dict[str, Any] = {
        "tipo": structure_name,
        "valor": None,
        "fields": {},
    }

    found_any_value = False

    confidences: list[float] = []

    for field_name, field_value in structure.items():

        normalized_field = _normalize_field(
            field_value
        )

        candidate["fields"][field_name] = normalized_field

        if normalized_field["text"] not in (None, ""):
            found_any_value = True

        confidence = normalized_field.get(
            "confidence"
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

    # ========================================================
    # Campos comunes de persona_embargada
    # ========================================================

    if structure_name == "persona_embargada":

        nombre = candidate["fields"].get(
            "nombre",
            {},
        )

        dni = candidate["fields"].get(
            "dni",
            {},
        )

        cuil_cuit = candidate["fields"].get(
            "cuil_cuit",
            {},
        )

        candidate.update(
            {
                "valor": nombre.get("text"),
                "nombre": nombre.get("text"),
                "dni": dni.get("text"),
                "cuil_cuit": cuil_cuit.get("text"),

                "nombre_confidence": nombre.get(
                    "confidence"
                ),
                "dni_confidence": dni.get(
                    "confidence"
                ),
                "cuil_cuit_confidence": (
                    cuil_cuit.get("confidence")
                ),

                "nombre_span_inicio": nombre.get(
                    "start"
                ),
                "nombre_span_fin": nombre.get(
                    "end"
                ),

                "dni_span_inicio": dni.get(
                    "start"
                ),
                "dni_span_fin": dni.get(
                    "end"
                ),

                "cuil_cuit_span_inicio": (
                    cuil_cuit.get("start")
                ),
                "cuil_cuit_span_fin": (
                    cuil_cuit.get("end")
                ),
            }
        )

        # Para compatibilidad con exporter actual.
        candidate["confidence"] = (
            nombre.get("confidence")
        )

        candidate["span_inicio"] = (
            nombre.get("start")
        )

        candidate["span_fin"] = (
            nombre.get("end")
        )

    # ========================================================
    # Otros structured schemas
    # ========================================================

    else:
        candidate["valor"] = _first_text_field(
            candidate["fields"]
        )

        candidate["confidence"] = (
            min(confidences)
            if confidences
            else None
        )

        candidate["span_inicio"] = None
        candidate["span_fin"] = None

        # También exponemos cada field en primer nivel.
        for field_name, normalized_field in (
            candidate["fields"].items()
        ):
            candidate[field_name] = (
                normalized_field.get("text")
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

    return candidate


def _normalize_field(
    value: Any,
) -> dict[str, Any]:
    """
    Normaliza un field structured.

    GLiNER2 puede devolver:

    {
        "text": "...",
        "confidence": 0.9,
        "start": 10,
        "end": 20
    }

    o null.
    """

    if value is None:
        return {
            "text": None,
            "confidence": None,
            "start": None,
            "end": None,
        }

    if isinstance(value, dict):
        return {
            "text": _first_present(
                value,
                (
                    "text",
                    "value",
                ),
            ),
            "confidence": _first_present(
                value,
                (
                    "confidence",
                    "score",
                    "probability",
                ),
            ),
            "start": _first_present(
                value,
                (
                    "start",
                    "start_char",
                    "span_inicio",
                ),
            ),
            "end": _first_present(
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
    fields: dict[str, dict[str, Any]],
) -> Any:
    """Devuelve el primer field no vacío."""

    for field in fields.values():
        value = field.get("text")

        if value not in (None, ""):
            return value

    return None


def _first_present(
    mapping: dict[str, Any],
    keys: tuple[str, ...],
) -> Any:
    """Devuelve el primer valor existente y no vacío."""

    for key in keys:

        if (
            key in mapping
            and mapping[key] not in (None, "")
        ):
            return mapping[key]

    return None