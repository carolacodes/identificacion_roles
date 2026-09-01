"""Entry point CLI para ejecutar experimentos declarados en YAML."""

from __future__ import annotations

import argparse
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


LOG_DIR = PROJECT_ROOT / "outputs" / "logs"


def main() -> None:
    args = parse_args()
    setup_logging()
    run_experiment(args.experiment)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ejecuta un experimento de identificacion de roles.")
    parser.add_argument("--experiment", required=True, help="Nombre del experimento declarado en config/experimentos.yaml")
    return parser.parse_args()


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "experimentos.log", encoding="utf-8"),
        ],
    )


def run_experiment(experiment_name: str) -> dict[str, Path]:
    """Ejecuta el flujo completo para un experimento configurado."""
    logger = logging.getLogger(__name__)
    logger.info("Inicio de experimento: %s", experiment_name)

    experiments_config = load_experiments_config()
    models_config = load_models_config()
    schemas_config = load_schemas_config()

    experiment = get_named_config(experiments_config, "experiments", experiment_name)
    model_key = str(experiment["model"])
    schema_key = str(experiment["schema"])
    model_config = get_named_config(models_config, "models", model_key)
    schema_config = get_named_config(schemas_config, "schemas", schema_key)

    input_file = PROJECT_ROOT / str(experiment["input_file"])
    input_mode = str(experiment["input_mode"])
    text_column = str(experiment["text_column"])

    records = load_records(input_file, input_mode=input_mode, text_column=text_column)
    logger.info(
        "Dataset cargado: experimento=%s modelo=%s schema=%s modo=%s registros=%s",
        experiment_name,
        model_key,
        schema_key,
        input_mode,
        len(records),
    )

    loaded_model = load_model(model_config)

    schema = build_schema(
        schema_key,
        schema_config,
        loaded_model,
    )

    predictions = run_inference(
        loaded_model,
        schema,
        records,
        experiment,
        model_config,
    )
    postprocessed = postprocess_results(predictions)
    used_config: dict[str, Any] = {
        "experiment_name": experiment_name,
        "experiment": experiment,
        "model": model_config,
        "schema": schema_config,
    }
    paths = export_results(postprocessed, experiment.get("run_name", experiment_name), used_config)

    logger.info("Finalizacion de experimento: %s", experiment_name)
    return paths


if __name__ == "__main__":
    main()
