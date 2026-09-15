import pytest

from src.run_experiment import (
    _apply_field_thresholds,
)


def test_apply_field_thresholds_structured():
    schema_config = {
        "type":
            "structured",

        "name":
            "persona_embargada",

        "fields": {
            "nombre_embargado": {
                "dtype":
                    "str",

                "threshold":
                    None,
            },

            "dni_embargado": {
                "dtype":
                    "str",

                "threshold":
                    None,
            },
        },
    }

    experiment = {
        "field_thresholds": {
            "nombre_embargado":
                0.60,

            "dni_embargado":
                0.50,
        }
    }

    result = _apply_field_thresholds(
        schema_config,
        experiment,
    )

    assert (
        result[
            "fields"
        ][
            "nombre_embargado"
        ][
            "threshold"
        ]
        == 0.60
    )

    assert (
        result[
            "fields"
        ][
            "dni_embargado"
        ][
            "threshold"
        ]
        == 0.50
    )


def test_apply_field_thresholds_does_not_modify_original():
    schema_config = {
        "type":
            "structured",

        "fields": {
            "nombre_embargado": {
                "dtype":
                    "str",

                "threshold":
                    None,
            },
        },
    }

    experiment = {
        "field_thresholds": {
            "nombre_embargado":
                0.60,
        }
    }

    result = _apply_field_thresholds(
        schema_config,
        experiment,
    )

    assert (
        schema_config[
            "fields"
        ][
            "nombre_embargado"
        ][
            "threshold"
        ]
        is None
    )

    assert (
        result[
            "fields"
        ][
            "nombre_embargado"
        ][
            "threshold"
        ]
        == 0.60
    )


def test_unknown_field_threshold_raises_error():
    schema_config = {
        "type":
            "structured",

        "fields": {
            "nombre_embargado": {
                "dtype":
                    "str",
            },
        },
    }

    experiment = {
        "field_thresholds": {
            "campo_inexistente":
                0.50,
        }
    }

    with pytest.raises(
        ValueError,
        match=(
            "field_thresholds contiene campos"
        ),
    ):
        _apply_field_thresholds(
            schema_config,
            experiment,
        )


def test_without_field_thresholds_returns_equivalent_schema():
    schema_config = {
        "type":
            "structured",

        "fields": {
            "nombre_embargado": {
                "dtype":
                    "str",
            },
        },
    }

    result = _apply_field_thresholds(
        schema_config,
        {},
    )

    assert (
        result
        == schema_config
    )

    assert (
        result
        is not schema_config
    )