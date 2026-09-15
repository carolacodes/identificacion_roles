"""Entry point CLI para ejecutar experimentos declarados en YAML."""

from __future__ import annotations

import argparse
import copy
import logging

from pathlib import Path
from typing import Any

from .config_loader import (
    PROJECT_ROOT,
    get_named_config,
    load_experiments_config,
    load_models_config,
    load_schemas_config,
)

from .data_loader import load_records
from .exporter import export_results
from .inference import run_inference
from .model_loader import load_model
from .postprocess import postprocess_results
from .schema_builder import build_schema


LOG_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "logs"
)


def main() -> None:

    args = parse_args()

    setup_logging()

    run_experiment(
        args.experiment
    )


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta un experimento "
            "de identificacion de roles."
        )
    )

    parser.add_argument(
        "--experiment",
        required=True,
        help=(
            "Nombre del experimento declarado "
            "en config/experimentos.yaml"
        ),
    )

    return parser.parse_args()


def setup_logging() -> None:

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    logging.basicConfig(
        level=logging.INFO,

        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s - "
            "%(message)s"
        ),

        handlers=[
            logging.StreamHandler(),

            logging.FileHandler(
                LOG_DIR / "experimentos.log",
                encoding="utf-8",
            ),
        ],
    )


def _apply_field_thresholds(
    schema_config: dict[str, Any],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    """Aplica thresholds por campo definidos en el experimento.

    No modifica el schema original cargado desde YAML.

    Ejemplo:

        field_thresholds:
          nombre_embargado: 0.60
          dni_embargado: 0.50

    sobreescribe temporalmente:

        fields:
          nombre_embargado:
            threshold: ...
    """

    effective_schema = copy.deepcopy(
        schema_config
    )

    field_thresholds = experiment.get(
        "field_thresholds"
    )

    if not field_thresholds:
        return effective_schema

    if not isinstance(
        field_thresholds,
        dict,
    ):
        raise ValueError(
            "field_thresholds debe ser un objeto."
        )

    schema_type = effective_schema.get(
        "type"
    )

    if schema_type == "structured":

        fields = effective_schema.get(
            "fields"
        )

        if not isinstance(fields, dict):
            raise ValueError(
                "El schema structured no contiene fields."
            )

        unknown_fields = sorted(
            set(field_thresholds)
            - set(fields)
        )

        if unknown_fields:
            raise ValueError(
                "field_thresholds contiene campos "
                "que no existen en el schema: "
                + ", ".join(unknown_fields)
            )

        for field_name, threshold in (
            field_thresholds.items()
        ):

            if threshold is None:
                continue

            fields[field_name][
                "threshold"
            ] = float(threshold)

    elif schema_type == "entities":

        entities = effective_schema.get(
            "entities"
        )

        if not isinstance(
            entities,
            dict,
        ):
            raise ValueError(
                "El schema entities no contiene entities."
            )

        unknown_entities = sorted(
            set(field_thresholds)
            - set(entities)
        )

        if unknown_entities:
            raise ValueError(
                "field_thresholds contiene entidades "
                "que no existen en el schema: "
                + ", ".join(unknown_entities)
            )

        for entity_name, threshold in (
            field_thresholds.items()
        ):

            if threshold is None:
                continue

            entities[entity_name][
                "threshold"
            ] = float(threshold)

    else:

        raise ValueError(
            "Tipo de schema no soportado para "
            f"field_thresholds: {schema_type}"
        )

    return effective_schema


def run_experiment(
    experiment_name: str,
) -> dict[str, Path]:
    """Ejecuta el flujo completo de un experimento."""

    logger = logging.getLogger(
        __name__
    )

    logger.info(
        "Inicio de experimento: %s",
        experiment_name,
    )

    experiments_config = (
        load_experiments_config()
    )

    models_config = (
        load_models_config()
    )

    schemas_config = (
        load_schemas_config()
    )

    experiment = get_named_config(
        experiments_config,
        "experiments",
        experiment_name,
    )

    model_key = str(
        experiment["model"]
    )

    schema_key = str(
        experiment["schema"]
    )

    model_config = get_named_config(
        models_config,
        "models",
        model_key,
    )

    schema_config_original = (
        get_named_config(
            schemas_config,
            "schemas",
            schema_key,
        )
    )

    # ---------------------------------------------------------
    # Thresholds por campo
    # ---------------------------------------------------------

    schema_config = (
        _apply_field_thresholds(
            schema_config_original,
            experiment,
        )
    )

    # ---------------------------------------------------------
    # Configuracion de entrada
    # ---------------------------------------------------------

    input_file = (
        PROJECT_ROOT
        / str(
            experiment[
                "input_file"
            ]
        )
    )

    input_mode = str(
        experiment[
            "input_mode"
        ]
    )

    text_column = str(
        experiment[
            "text_column"
        ]
    )

    filters = experiment.get(
        "filters"
    )

    metadata_columns = (
        experiment.get(
            "metadata_columns"
        )
    )

    if metadata_columns is not None:

        if not isinstance(
            metadata_columns,
            list,
        ):
            raise ValueError(
                "metadata_columns debe ser una lista."
            )

        metadata_columns = [
            str(column)
            for column in metadata_columns
        ]

    # ---------------------------------------------------------
    # Dataset
    # ---------------------------------------------------------

    records = load_records(
        input_file=input_file,
        input_mode=input_mode,
        text_column=text_column,
        filters=filters,
        metadata_columns=metadata_columns,
    )

    logger.info(
        (
            "Dataset cargado: "
            "experimento=%s "
            "modelo=%s "
            "schema=%s "
            "modo=%s "
            "registros=%s "
            "filtros=%s"
        ),
        experiment_name,
        model_key,
        schema_key,
        input_mode,
        len(records),
        filters,
    )

    if not records:
        raise ValueError(
            "El experimento no contiene registros "
            "despues de aplicar los filtros."
        )

    # ---------------------------------------------------------
    # Modelo
    # ---------------------------------------------------------

    loaded_model = load_model(
        model_config
    )

    # ---------------------------------------------------------
    # Schema
    # ---------------------------------------------------------

    schema = build_schema(
        schema_key,
        schema_config,
        loaded_model,
    )

    # ---------------------------------------------------------
    # Inferencia
    # ---------------------------------------------------------

    predictions = run_inference(
        loaded_model,
        schema,
        records,
        experiment,
        model_config,
    )

    # ---------------------------------------------------------
    # Postprocess
    # ---------------------------------------------------------

    postprocessed = (
        postprocess_results(
            predictions
        )
    )

    # ---------------------------------------------------------
    # Config usada
    # ---------------------------------------------------------

    used_config: dict[
        str,
        Any,
    ] = {
        "experiment_name":
            experiment_name,

        "experiment":
            experiment,

        "model":
            model_config,

        # Guardamos el schema efectivo.
        # Esto incluye field_thresholds.
        "schema":
            schema_config,
    }

    # ---------------------------------------------------------
    # Exportacion
    # ---------------------------------------------------------

    paths = export_results(
        postprocessed,
        experiment.get(
            "run_name",
            experiment_name,
        ),
        used_config,
    )

    logger.info(
        (
            "Finalizacion de experimento: "
            "%s registros=%s"
        ),
        experiment_name,
        len(records),
    )

    return paths


if __name__ == "__main__":
    main()