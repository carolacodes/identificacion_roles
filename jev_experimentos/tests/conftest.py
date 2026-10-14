from copy import deepcopy
import socket

import pytest

from jev_experimentos.src.decision_engine import ROLES


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Los tests no pueden realizar conexiones de red.")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)


def candidate(name="ANA PEREZ", dni="12.345.678", role="embargado", confidence=0.01):
    return {"nombre_embargado": name, "dni_embargado": dni,
            "cuit_cuil_embargado": None, "rol_embargado": role,
            "confidence": confidence, "fields": {"nombre_embargado": {"text": name, "confidence": confidence},
                                                    "dni_embargado": {"text": dni, "start": None}}}


def document(*candidates, separate=False):
    groups = [[c] for c in candidates] if separate else [list(candidates)]
    return {"id": "sintetico", "numero_archivo": "9", "nombre": "sintetico.pdf",
            "texto_completo": "OCR EXTRA QUE NO DEBE TRANSMITIRSE",
            "metadata": {"original": True},
            "resultados": [{"contador_interno": str(i), "fragmento": f"Evidencia sintética {i}",
                            "texto_entrada_modelo": f"Evidencia sintética {i}",
                            "contexto_embargado": "Contexto ya presente en el JSON", "status": None,
                            "candidates": deepcopy(group)} for i, group in enumerate(groups)]}


def fake_response(questions, *, accepted=(), equivalent=(), conflicts=(), incomplete=(), roles=None):
    roles = roles or {}
    answers = {}
    for qid, question in questions.items():
        kind = qid.split(":")[0]
        ids = question["instructions"]["candidatos"]
        cid = ids[0]
        if kind == "rol":
            choice = roles.get(cid, "embargado" if cid in accepted else "tercero")
            answers[qid] = {"type": "choice", "choice": choice, "confidence": 0.99,
                            "probabilities": {k: float(k == choice) for k in ROLES}}
        else:
            yes = ((kind == "acepta" and cid in accepted) or
                   (kind == "completo" and cid not in incomplete) or
                   (kind == "equiv" and tuple(ids) in equivalent) or
                   (kind in ("conflicto", "conflicto_par") and tuple(ids) in conflicts))
            answers[qid] = {"type": "noul", "noul": 0.99 if yes else 0.01}
    return {"model": "jev-1.13.0", "usage": {"input_tokens": 20, "output_tokens": 10}, "answers": answers}


class FakeSDK:
    def __init__(self, **options):
        self.options, self.calls, self.closed = options, [], False

    def system_one(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        return fake_response(kwargs["questions"], **self.options)

    def close(self):
        self.closed = True
