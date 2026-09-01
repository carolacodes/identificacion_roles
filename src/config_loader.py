"""Carga y validacion liviana de configuraciones YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigError(ValueError):
    """Error de configuracion con mensaje apto para CLI."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Carga un archivo YAML y devuelve un diccionario."""
    yaml_path = Path(path)
    if not yaml_path.is_absolute():
        yaml_path = PROJECT_ROOT / yaml_path
    if not yaml_path.exists():
        raise ConfigError(f"No existe el archivo de configuracion: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"El archivo YAML debe contener un objeto en la raiz: {yaml_path}")
    return data


def load_models_config(config_dir: str | Path = CONFIG_DIR) -> dict[str, Any]:
    """Carga config/modelos.yaml."""
    data = load_yaml(Path(config_dir) / "modelos.yaml")
    models = data.get("models")
    if not isinstance(models, dict) or not models:
        raise ConfigError("config/modelos.yaml debe definir 'models' con al menos un modelo.")
    return data


def load_schemas_config(config_dir: str | Path = CONFIG_DIR) -> dict[str, Any]:
    """Carga config/schemas.yaml."""
    data = load_yaml(Path(config_dir) / "schemas.yaml")
    schemas = data.get("schemas")
    if not isinstance(schemas, dict) or not schemas:
        raise ConfigError("config/schemas.yaml debe definir 'schemas' con al menos un schema.")
    return data


def load_experiments_config(config_dir: str | Path = CONFIG_DIR) -> dict[str, Any]:
    """Carga config/experimentos.yaml."""
    data = load_yaml(Path(config_dir) / "experimentos.yaml")
    experiments = data.get("experiments")
    if not isinstance(experiments, dict) or not experiments:
        raise ConfigError("config/experimentos.yaml debe definir 'experiments' con al menos un experimento.")
    return data


def get_named_config(section: dict[str, Any], collection_key: str, name: str) -> dict[str, Any]:
    """Obtiene una entrada nombrada dentro de una coleccion de configuracion."""
    collection = section.get(collection_key)
    if not isinstance(collection, dict):
        raise ConfigError(f"La configuracion no contiene la seccion esperada '{collection_key}'.")
    item = collection.get(name)
    if not isinstance(item, dict):
        available = ", ".join(sorted(collection)) or "(ninguno)"
        raise ConfigError(f"No existe '{name}' en '{collection_key}'. Disponibles: {available}")
    return item
