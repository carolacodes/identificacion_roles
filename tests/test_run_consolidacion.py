import json

from pathlib import Path

import pytest

from src.run_consolidacion import (
    _derive_run_name,
    load_predictions,
)


def test_load_predictions_valid_json(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "predicciones_por_documento.json"
    )

    data = [
        {
            "id": "doc-1",
            "numero_archivo": "1",
            "resultados": [],
        }
    ]

    path.write_text(
        json.dumps(
            data
        ),
        encoding="utf-8",
    )

    resultado = load_predictions(
        path
    )

    assert (
        len(resultado)
        == 1
    )

    assert (
        resultado[0]["id"]
        == "doc-1"
    )


def test_load_predictions_missing_file():
    with pytest.raises(
        FileNotFoundError,
    ):
        load_predictions(
            "archivo_que_no_existe.json"
        )


def test_load_predictions_invalid_json(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "bad.json"
    )

    path.write_text(
        "{esto no es json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="JSON valido",
    ):
        load_predictions(
            path
        )


def test_load_predictions_requires_list(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "bad_structure.json"
    )

    path.write_text(
        json.dumps(
            {
                "id":
                    "doc-1"
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="lista de documentos",
    ):
        load_predictions(
            path
        )


def test_load_predictions_requires_id(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "sin_id.json"
    )

    path.write_text(
        json.dumps(
            [
                {
                    "resultados": []
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="campo 'id'",
    ):
        load_predictions(
            path
        )


def test_load_predictions_requires_resultados(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "sin_resultados.json"
    )

    path.write_text(
        json.dumps(
            [
                {
                    "id":
                        "doc-1"
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="campo 'resultados'",
    ):
        load_predictions(
            path
        )


def test_derive_run_name_from_parent(
    tmp_path: Path,
):
    run_dir = (
        tmp_path
        / "20260915_multi_v7_thr50"
    )

    run_dir.mkdir()

    path = (
        run_dir
        / "predicciones_por_documento.json"
    )

    result = _derive_run_name(
        path,
        None,
    )

    assert (
        result
        == "20260915_multi_v7_thr50"
    )


def test_explicit_run_name_has_priority(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "predicciones_por_documento.json"
    )

    result = _derive_run_name(
        path,
        "mi_prueba",
    )

    assert (
        result
        == "mi_prueba"
    )