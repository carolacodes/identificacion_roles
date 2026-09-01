from pathlib import Path

import pytest

from src.config_loader import ConfigError, get_named_config, load_yaml


def test_load_yaml_reads_mapping(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("root:\n  value: 1\n", encoding="utf-8")

    assert load_yaml(path) == {"root": {"value": 1}}


def test_get_named_config_reports_missing_name():
    with pytest.raises(ConfigError, match="No existe"):
        get_named_config({"items": {"a": {}}}, "items", "b")
