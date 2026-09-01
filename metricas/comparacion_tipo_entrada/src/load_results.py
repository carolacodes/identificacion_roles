"""Carga y validacion basica de predicciones exportadas."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


Rows = list[dict[str, Any]]


def load_results(path: str | Path) -> Rows:
    """Carga resultados desde JSON o CSV."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {file_path}")
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        return _load_json(file_path)
    if suffix == ".csv":
        return _load_csv(file_path)
    raise ValueError(f"Formato no soportado: {file_path.suffix}")


def _load_json(path: Path) -> Rows:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        for key in ("predicciones", "results", "rows", "data"):
            if isinstance(data.get(key), list):
                rows = data[key]
                break
        else:
            rows = [data]
    else:
        raise ValueError("El JSON debe contener una lista, objeto o clave con lista.")
    return [dict(row) for row in rows if isinstance(row, dict)]


def _load_csv(path: Path) -> Rows:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def validate_required_id(rows: Rows, label: str) -> None:
    """Valida que el dataset tenga columna id."""
    if not rows:
        raise ValueError(f"{label}: no contiene filas.")
    if any("id" not in row for row in rows):
        raise ValueError(f"{label}: todas las filas deben contener 'id'.")


def unique_values(rows: Rows, field: str) -> set[Any]:
    """Devuelve valores no vacios de un campo."""
    return {row.get(field) for row in rows if row.get(field) not in (None, "")}


def validate_single_value(rows: Rows, field: str, label: str) -> Any:
    """Valida que un campo tenga un unico valor global, si existe."""
    values = unique_values(rows, field)
    if len(values) > 1:
        raise ValueError(f"{label}: multiples valores para {field}: {sorted(values)}")
    return next(iter(values), None)


def validate_compatible_inputs(document_rows: Rows, fragment_rows: Rows) -> dict[str, Any]:
    """Valida consistencia de ambos datasets y devuelve metadatos comparables."""
    validate_required_id(document_rows, "documentos")
    validate_required_id(fragment_rows, "fragmentos")

    docs_mode = validate_single_value(document_rows, "modo_entrada", "documentos")
    frag_mode = validate_single_value(fragment_rows, "modo_entrada", "fragmentos")
    if docs_mode and "fragment" in str(docs_mode).lower():
        raise ValueError("documentos: modo_entrada parece corresponder a fragmentos.")
    if frag_mode and "document" in str(frag_mode).lower():
        raise ValueError("fragmentos: modo_entrada parece corresponder a documentos.")

    metadata: dict[str, Any] = {"modo_documentos": docs_mode, "modo_fragmentos": frag_mode}
    for field in ("modelo", "schema", "threshold"):
        docs_value = validate_single_value(document_rows, field, "documentos")
        frag_value = validate_single_value(fragment_rows, field, "fragmentos")
        if docs_value != frag_value:
            raise ValueError(
                f"Los datasets no coinciden en {field}: documentos={docs_value!r}, "
                f"fragmentos={frag_value!r}"
            )
        metadata[field] = docs_value

    docs_ids = {str(row.get("id")) for row in document_rows}
    frag_ids = {str(row.get("id")) for row in fragment_rows}
    metadata["ids_solo_documentos"] = sorted(docs_ids - frag_ids)
    metadata["ids_solo_fragmentos"] = sorted(frag_ids - docs_ids)
    metadata["ids_comunes"] = sorted(docs_ids & frag_ids)
    return metadata

