"""Inferencia común para GLiNER2 y GLiNER clásico."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .data_loader import InputRecord
from .model_loader import LoadedModel
from .schema_builder import BuiltSchema


@dataclass(slots=True)
class PredictionResult:
    """Resultado completo por registro."""

    record: InputRecord
    model_id: str
    schema_id: str
    threshold: float | None
    schema_type: str
    architecture: str
    raw_response: Any
    normalized_items: list[dict[str, Any]] = field(
        default_factory=list
    )


def run_inference(
    loaded_model: LoadedModel,
    schema: BuiltSchema,
    records: list[InputRecord],
    experiment_config: dict[str, Any],
    model_config: dict[str, Any],
) -> list[PredictionResult]:
    """
    Ejecuta inferencia sin escribir archivos.
    """
    threshold = _resolve_threshold(
        experiment_config,
        model_config,
    )

    results: list[PredictionResult] = []

    for record in records:
        raw_response = _extract(
            loaded_model=loaded_model,
            text=record.texto,
            schema=schema,
            threshold=threshold,
        )

        normalized_items = _flatten_raw_response(
            raw_response=raw_response,
            schema=schema,
        )

        results.append(
            PredictionResult(
                record=record,
                model_id=loaded_model.model_id,
                schema_id=schema.schema_id,
                threshold=threshold,
                schema_type=schema.schema_type,
                architecture=loaded_model.architecture,
                raw_response=raw_response,
                normalized_items=normalized_items,
            )
        )

    return results


def _resolve_threshold(
    experiment_config: dict[str, Any],
    model_config: dict[str, Any],
) -> float | None:
    experiment_threshold = experiment_config.get(
        "threshold"
    )

    if experiment_threshold is not None:
        return float(experiment_threshold)

    model_threshold = model_config.get(
        "default_threshold"
    )

    if model_threshold is not None:
        return float(model_threshold)

    return None


def _extract(
    loaded_model: LoadedModel,
    text: str,
    schema: BuiltSchema,
    threshold: float | None,
) -> Any:
    """
    Ejecuta el método correcto según la arquitectura.
    """
    if loaded_model.architecture == "gliner2":
        return _extract_gliner2(
            model=loaded_model.model,
            text=text,
            schema=schema,
            threshold=threshold,
        )

    if loaded_model.architecture == "gliner":
        return _extract_gliner(
            model=loaded_model.model,
            text=text,
            schema=schema,
            threshold=threshold,
        )

    raise ValueError(
        f"Arquitectura no soportada: {loaded_model.architecture}"
    )


def _extract_gliner2(
    model: Any,
    text: str,
    schema: BuiltSchema,
    threshold: float | None,
) -> Any:
    """
    Inferencia con schemas nativos GLiNER2.
    """
    kwargs: dict[str, Any] = {
        "include_confidence": True,
        "include_spans": True,
    }

    if threshold is not None:
        kwargs["threshold"] = threshold

    return model.extract(
        text,
        schema.gliner_schema,
        **kwargs,
    )


def _extract_gliner(
    model: Any,
    text: str,
    schema: BuiltSchema,
    threshold: float | None,
) -> Any:
    """
    Inferencia con GLiNER clásico.

    Devuelve normalmente una lista de:
    {
        text,
        label,
        score,
        start,
        end
    }
    """
    kwargs: dict[str, Any] = {}

    if threshold is not None:
        kwargs["threshold"] = threshold

    return model.predict_entities(
        text,
        schema.gliner_schema,
        **kwargs,
    )


def _flatten_raw_response(
    raw_response: Any,
    schema: BuiltSchema,
) -> list[dict[str, Any]]:
    if raw_response is None:
        return []

    if schema.architecture == "gliner":
        return _flatten_gliner(
            raw_response
        )

    if schema.schema_type == "entities":
        return _flatten_gliner2_entities(
            raw_response
        )

    if schema.schema_type == "structured":
        return _flatten_gliner2_structured(
            raw_response,
            schema,
        )

    return []


def _flatten_gliner(
    raw_response: Any,
) -> list[dict[str, Any]]:
    """
    Normaliza la lista devuelta por GLiNER clásico.
    """
    if not isinstance(raw_response, list):
        return []

    items: list[dict[str, Any]] = []

    for entity in raw_response:
        if not isinstance(entity, dict):
            continue

        items.append(
            {
                "entity_type": entity.get("label"),
                "text": entity.get("text"),
                "confidence": entity.get("score"),
                "start": entity.get("start"),
                "end": entity.get("end"),
            }
        )

    return items


def _flatten_gliner2_entities(
    raw_response: Any,
) -> list[dict[str, Any]]:
    if not isinstance(raw_response, dict):
        return []

    entities = raw_response.get("entities")

    if not isinstance(entities, dict):
        return []

    items: list[dict[str, Any]] = []

    for entity_type, values in entities.items():
        if not isinstance(values, list):
            values = [values]

        for value in values:
            if isinstance(value, dict):
                item = {
                    "entity_type": entity_type,
                }

                item.update(value)

            else:
                item = {
                    "entity_type": entity_type,
                    "value": value,
                }

            items.append(item)

    return items


def _flatten_gliner2_structured(
    raw_response: Any,
    schema: BuiltSchema,
) -> list[dict[str, Any]]:
    if not isinstance(raw_response, dict):
        return []

    structure_name = str(
        schema.raw_config.get(
            "name",
            schema.schema_id,
        )
    )

    structures = raw_response.get(
        structure_name
    )

    if structures is None:
        return []

    if not isinstance(structures, list):
        structures = [structures]

    items: list[dict[str, Any]] = []

    for index, structure in enumerate(structures):
        if not isinstance(structure, dict):
            continue

        item: dict[str, Any] = {
            "entity_type": structure_name,
            "structure_index": index,
        }

        item.update(structure)

        items.append(item)

    return items