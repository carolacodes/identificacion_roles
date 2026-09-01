"""Construcción de schemas para GLiNER2 y labels para GLiNER clásico."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .model_loader import LoadedModel


class SchemaBuilderError(ValueError):
    """Error en la definición o construcción de un schema."""


@dataclass(frozen=True, slots=True)
class BuiltSchema:
    """
    Representación común de un schema.

    Para GLiNER2:
        gliner_schema contiene un schema nativo.

    Para GLiNER clásico:
        gliner_schema contiene una lista de labels.
    """

    schema_id: str
    schema_type: str
    architecture: str
    gliner_schema: Any
    descriptions: dict[str, str]
    thresholds: dict[str, float | None]
    raw_config: dict[str, Any]


def build_schema(
    schema_id: str,
    schema_config: dict[str, Any],
    loaded_model: LoadedModel,
) -> BuiltSchema:
    """
    Construye el schema según la arquitectura del modelo.
    """
    if loaded_model.architecture == "gliner2":
        return _build_gliner2_schema(
            schema_id=schema_id,
            schema_config=schema_config,
            model=loaded_model.model,
        )

    if loaded_model.architecture == "gliner":
        return _build_gliner_schema(
            schema_id=schema_id,
            schema_config=schema_config,
        )

    raise SchemaBuilderError(
        f"Arquitectura no soportada: {loaded_model.architecture}"
    )


# ============================================================
# GLINER2
# ============================================================


def _build_gliner2_schema(
    schema_id: str,
    schema_config: dict[str, Any],
    model: Any,
) -> BuiltSchema:
    """
    Construye schemas nativos de GLiNER2 usando create_schema().
    """
    if not hasattr(model, "create_schema"):
        raise SchemaBuilderError(
            "El modelo GLiNER2 cargado no expone create_schema()."
        )

    schema_type = schema_config.get("type")

    if schema_type == "entities":
        return _build_gliner2_entities(
            schema_id,
            schema_config,
            model,
        )

    if schema_type == "structured":
        return _build_gliner2_structured(
            schema_id,
            schema_config,
            model,
        )

    raise SchemaBuilderError(
        f"Tipo de schema no soportado: {schema_type}"
    )


def _build_gliner2_entities(
    schema_id: str,
    schema_config: dict[str, Any],
    model: Any,
) -> BuiltSchema:
    entities = schema_config.get("entities")

    if not isinstance(entities, dict) or not entities:
        raise SchemaBuilderError(
            f"El schema '{schema_id}' debe definir entities."
        )

    entity_definitions: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    thresholds: dict[str, float | None] = {}

    for label, config in entities.items():
        if not isinstance(config, dict):
            raise SchemaBuilderError(
                f"La entidad '{label}' debe ser un objeto."
            )

        description = str(
            config.get("description", "")
        ).strip()

        entity_definitions[label] = description
        descriptions[label] = description

        threshold = config.get("threshold")
        thresholds[label] = (
            float(threshold)
            if threshold is not None
            else None
        )

    native_schema = (
        model.create_schema()
        .entities(entity_definitions)
    )

    return BuiltSchema(
        schema_id=schema_id,
        schema_type="entities",
        architecture="gliner2",
        gliner_schema=native_schema,
        descriptions=descriptions,
        thresholds=thresholds,
        raw_config=schema_config,
    )


def _build_gliner2_structured(
    schema_id: str,
    schema_config: dict[str, Any],
    model: Any,
) -> BuiltSchema:
    fields = schema_config.get("fields")

    if not isinstance(fields, dict) or not fields:
        raise SchemaBuilderError(
            f"El schema '{schema_id}' debe definir fields."
        )

    structure_name = str(
        schema_config.get("name", schema_id)
    )

    descriptions: dict[str, str] = {}
    thresholds: dict[str, float | None] = {}

    schema = model.create_schema()
    structure = schema.structure(structure_name)

    for field_name, config in fields.items():
        if not isinstance(config, dict):
            raise SchemaBuilderError(
                f"El campo '{field_name}' debe ser un objeto."
            )

        description = str(
            config.get("description", "")
        ).strip()

        dtype = str(
            config.get("dtype", "str")
        )

        threshold_value = config.get("threshold")

        threshold = (
            float(threshold_value)
            if threshold_value is not None
            else None
        )

        descriptions[field_name] = description
        thresholds[field_name] = threshold

        kwargs: dict[str, Any] = {
            "dtype": dtype,
        }

        if description:
            kwargs["description"] = description

        if threshold is not None:
            kwargs["threshold"] = threshold

        choices = config.get("choices")

        if choices is not None:
            if not isinstance(choices, list):
                raise SchemaBuilderError(
                    f"choices de '{field_name}' debe ser una lista."
                )

            kwargs["choices"] = [
                str(choice)
                for choice in choices
            ]

        validators = _build_validators(
            schema_id=schema_id,
            field_name=field_name,
            field_config=config,
        )

        if validators:
            kwargs["validators"] = validators

        structure = structure.field(
            field_name,
            **kwargs,
        )

    return BuiltSchema(
        schema_id=schema_id,
        schema_type="structured",
        architecture="gliner2",
        gliner_schema=structure,
        descriptions=descriptions,
        thresholds=thresholds,
        raw_config=schema_config,
    )


# ============================================================
# GLINER CLÁSICO
# ============================================================


def _build_gliner_schema(
    schema_id: str,
    schema_config: dict[str, Any],
) -> BuiltSchema:
    """
    Convierte schemas del proyecto a labels compatibles con GLiNER clásico.

    GLiNER clásico no usa create_schema()/structure().
    """
    schema_type = schema_config.get("type")

    labels: list[str] = []
    descriptions: dict[str, str] = {}
    thresholds: dict[str, float | None] = {}

    if schema_type == "entities":
        entities = schema_config.get("entities")

        if not isinstance(entities, dict):
            raise SchemaBuilderError(
                f"El schema '{schema_id}' debe definir entities."
            )

        for label, config in entities.items():
            labels.append(str(label))

            if isinstance(config, dict):
                descriptions[label] = str(
                    config.get("description", "")
                )

                threshold_value = config.get("threshold")

                thresholds[label] = (
                    float(threshold_value)
                    if threshold_value is not None
                    else None
                )

    elif schema_type == "structured":
        structure_name = str(
            schema_config.get("name", schema_id)
        )

        fields = schema_config.get("fields")

        if not isinstance(fields, dict):
            raise SchemaBuilderError(
                f"El schema '{schema_id}' debe definir fields."
            )

        for field_name, config in fields.items():
            # Labels más descriptivos para GLiNER clásico.
            label = f"{structure_name}_{field_name}"

            labels.append(label)

            if isinstance(config, dict):
                descriptions[label] = str(
                    config.get("description", "")
                )

                threshold_value = config.get("threshold")

                thresholds[label] = (
                    float(threshold_value)
                    if threshold_value is not None
                    else None
                )

    else:
        raise SchemaBuilderError(
            f"Tipo de schema no soportado: {schema_type}"
        )

    return BuiltSchema(
        schema_id=schema_id,
        schema_type=schema_type,
        architecture="gliner",
        gliner_schema=labels,
        descriptions=descriptions,
        thresholds=thresholds,
        raw_config=schema_config,
    )


# ============================================================
# VALIDATORS GLINER2
# ============================================================


def _build_validators(
    schema_id: str,
    field_name: str,
    field_config: dict[str, Any],
) -> list[Any]:
    validator_configs: list[dict[str, Any]] = []

    single = field_config.get("validator")
    multiple = field_config.get("validators")

    if single is not None:
        if not isinstance(single, dict):
            raise SchemaBuilderError(
                f"validator de '{field_name}' debe ser un objeto."
            )

        validator_configs.append(single)

    if multiple is not None:
        if not isinstance(multiple, list):
            raise SchemaBuilderError(
                f"validators de '{field_name}' debe ser una lista."
            )

        validator_configs.extend(multiple)

    if not validator_configs:
        return []

    try:
        from gliner2 import RegexValidator
    except ImportError as exc:
        raise SchemaBuilderError(
            "No se pudo importar RegexValidator."
        ) from exc

    validators: list[Any] = []

    for validator_config in validator_configs:
        if not isinstance(validator_config, dict):
            raise SchemaBuilderError(
                f"Validator inválido en {schema_id}.{field_name}"
            )

        validator_type = str(
            validator_config.get("type", "")
        ).lower()

        if validator_type != "regex":
            raise SchemaBuilderError(
                f"Solo se soporta validator type=regex. "
                f"Recibido: {validator_type}"
            )

        pattern = validator_config.get("pattern")

        if not isinstance(pattern, str) or not pattern:
            raise SchemaBuilderError(
                f"Falta pattern en {schema_id}.{field_name}"
            )

        mode = str(
            validator_config.get("mode", "full")
        )

        exclude = bool(
            validator_config.get("exclude", False)
        )

        flags = _parse_regex_flags(
            validator_config.get("flags")
        )

        validators.append(
            RegexValidator(
                pattern,
                mode=mode,
                exclude=exclude,
                flags=flags,
            )
        )

    return validators


def _parse_regex_flags(
    flags_config: Any,
) -> int:
    if flags_config is None:
        return 0

    if isinstance(flags_config, str):
        flags_config = [flags_config]

    supported = {
        "IGNORECASE": re.IGNORECASE,
        "I": re.IGNORECASE,
        "MULTILINE": re.MULTILINE,
        "M": re.MULTILINE,
        "DOTALL": re.DOTALL,
        "S": re.DOTALL,
    }

    value = 0

    for flag in flags_config:
        normalized = str(flag).upper()

        if normalized not in supported:
            raise SchemaBuilderError(
                f"Flag regex no soportado: {flag}"
            )

        value |= supported[normalized]

    return value