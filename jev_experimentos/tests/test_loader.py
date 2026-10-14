from copy import deepcopy
import json

import pytest

from jev_experimentos.src.loader import load_predictions, prepare_document, select_documents
from .conftest import candidate, document


def test_preserves_every_original_value_and_null(tmp_path):
    original = document(candidate("GONZALEZ", "39.872.112", confidence=0.00001),
                        candidate(None, None, role=None), separate=True)
    original["resultados"].append({"fragmento": "Sin candidatos", "candidates": None, "metadata": None})
    before = deepcopy(original)
    source = tmp_path / "predicciones_por_documento.json"
    source.write_text(json.dumps([original], ensure_ascii=False), encoding="utf-8")
    content = source.read_bytes()
    docs, sha = load_predictions(source)
    doc = docs[0]
    assert len(doc.candidates) == 2
    expected = deepcopy(original)
    del expected["texto_completo"]
    assert doc.state["documento"] == expected
    assert doc.candidates["f0001.c0001"] == original["resultados"][0]["candidates"][0]
    assert doc.candidates["f0002.c0001"]["nombre_embargado"] is None
    assert original == before
    assert source.read_bytes() == content and len(sha) == 64
    assert "OCR EXTRA" not in json.dumps(doc.state)
    assert prepare_document(original).key == doc.key


@pytest.mark.parametrize("value", [{}, {"id": "1", "numero_archivo": "1", "resultados": None},
                                     {"id": "1", "numero_archivo": "1", "resultados": [None]},
                                     {"id": "1", "numero_archivo": "1", "resultados": [{"candidates": "bad"}]}])
def test_rejects_only_structurally_invalid_documents(value):
    with pytest.raises(ValueError):
        prepare_document(value)


def test_selection_unknown_and_duplicate_documents(tmp_path):
    first = prepare_document(document(candidate()))
    second_raw = document(candidate()); second_raw["numero_archivo"] = "11"
    second = prepare_document(second_raw)
    assert select_documents([first, second], ["11"]) == [second]
    with pytest.raises(ValueError, match="inexistentes"):
        select_documents([first], ["79"])
    with pytest.raises(ValueError, match="positivo"):
        select_documents([first], limit=0)
    source = tmp_path / "duplicate.json"
    source.write_text(json.dumps([first.original, first.original]))
    with pytest.raises(ValueError, match="duplicados"):
        load_predictions(source)


def test_rejects_nested_full_ocr_instead_of_silently_trimming():
    raw = document(candidate())
    raw["resultados"][0]["texto_completo"] = "texto adicional"
    with pytest.raises(ValueError, match="texto_completo"):
        prepare_document(raw)
