"""Validación estructural: ninguna selección o normalización semántica."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

from .storage import digest


@dataclass
class Document:
    key: str
    original: dict
    state: dict
    candidates: dict
    references: dict


def prepare_document(original: dict) -> Document:
    if not isinstance(original, dict) or any(k not in original for k in ("id", "numero_archivo", "resultados")):
        raise ValueError("Documento debe tener id, numero_archivo y resultados.")
    for field in ("id", "numero_archivo"):
        if not isinstance(original[field], (str, int)) or isinstance(original[field], bool):
            raise ValueError(f"Identificador estructural inválido: {field}.")
    if not isinstance(original["resultados"], list):
        raise ValueError("resultados debe ser una lista.")
    raw = deepcopy(original)
    # Única exclusión explícita de JEV-V1: OCR completo del documento.
    raw.pop("texto_completo", None)
    candidates, references = {}, {}
    for i, result in enumerate(raw["resultados"]):
        if not isinstance(result, dict):
            raise ValueError("Cada resultado debe ser un objeto.")
        if "texto_completo" in result:
            raise ValueError("JEV-V1 no admite texto_completo dentro de resultados.")
        values = result.get("candidates")
        if values is None:
            continue  # Se conserva null/ausencia en state; no crea candidatos ficticios.
        if not isinstance(values, list):
            raise ValueError("candidates debe ser una lista o null.")
        for j, candidate in enumerate(values):
            if not isinstance(candidate, dict):
                raise ValueError("Cada candidato debe ser un objeto (sus campos pueden ser null).")
            cid = f"f{i + 1:04d}.c{j + 1:04d}"
            candidates[cid] = candidate
            references[cid] = {
                "candidato": f"/documento/resultados/{i}/candidates/{j}",
                "resultado": f"/documento/resultados/{i}",
            }
    state = {"documento": raw, "referencias_candidatos": references}
    key = digest([original["id"], original["numero_archivo"]])
    return Document(key, deepcopy(original), state, candidates, references)


def load_predictions(path: Path):
    content = Path(path).read_bytes()
    def invalid_constant(value):
        raise ValueError(f"Constante JSON inválida: {value}")
    raw = json.loads(content, parse_constant=invalid_constant)
    if not isinstance(raw, list):
        raise ValueError("La entrada debe ser una lista de documentos.")
    documents = [prepare_document(value) for value in raw]
    if len({doc.key for doc in documents}) != len(documents):
        raise ValueError("Hay documentos con id/numero_archivo duplicados.")
    return documents, hashlib.sha256(content).hexdigest()


def select_documents(documents, numbers=None, limit=None):
    if limit is not None and limit <= 0:
        raise ValueError("El límite de documentos debe ser positivo.")
    if numbers:
        wanted = set(map(str, numbers))
        missing = wanted - {str(d.original["numero_archivo"]) for d in documents}
        if missing:
            raise ValueError(f"Archivos inexistentes: {', '.join(sorted(missing))}")
        documents = [d for d in documents if str(d.original["numero_archivo"]) in wanted]
    return documents[:limit] if limit else documents
