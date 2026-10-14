from copy import deepcopy
from itertools import combinations

import pytest

from jev_experimentos.config import Config
from jev_experimentos.src.decision_engine import interpret_responses, prepare_plan
from jev_experimentos.src.loader import prepare_document
from jev_experimentos.src.result_builder import build_result
from .conftest import candidate, document, fake_response


@pytest.mark.parametrize("candidates,options,count", [
    ([candidate()], {"accepted": ("f0001.c0001",)}, 1),
    ([candidate(), candidate("BETO LOPEZ", "99")], {"accepted": ("f0001.c0001", "f0001.c0002")}, 2),
    ([candidate(), candidate()], {"accepted": ("f0001.c0001", "f0001.c0002"), "equivalent": (("f0001.c0001", "f0001.c0002"),)}, 1),
    ([candidate(role="embargado")], {"roles": {"f0001.c0001": "profesional"}}, 0),
    ([candidate(role="embargado")], {"roles": {"f0001.c0001": "funcionario"}}, 0),
    ([candidate(role="embargado")], {"roles": {"f0001.c0001": "autorizado"}}, 0),
    ([candidate("PEREZ")], {"accepted": ("f0001.c0001",), "incomplete": ("f0001.c0001",)}, 1),
    ([candidate("ANA PEREZ"), candidate("PEREZ")], {"accepted": ("f0001.c0001", "f0001.c0002"), "equivalent": (("f0001.c0001", "f0001.c0002"),), "incomplete": ("f0001.c0002",)}, 1),
    ([candidate(dni="11"), candidate("BETO LOPEZ", "22")], {"accepted": ("f0001.c0001", "f0001.c0002")}, 2),
    ([candidate(dni="11"), candidate("BETO LOPEZ", "11")], {"accepted": ("f0001.c0001", "f0001.c0002"), "conflicts": (("f0001.c0001", "f0001.c0002"),)}, 2),
    ([], {}, 0),
    ([candidate(None, "11")], {"accepted": ("f0001.c0001",), "incomplete": ("f0001.c0001",)}, 1),
])
def test_twelve_synthetic_scenarios_depend_only_on_jev(candidates, options, count):
    doc = prepare_document(document(*candidates))
    before = deepcopy(doc.state)
    plan = prepare_plan(doc, Config())
    response = fake_response(plan["preguntas"], **options)
    result = build_result(doc, interpret_responses(plan, [response]), Config())
    assert result["cantidad_embargados"] == count
    assert doc.state == before and plan["state"] == before
    assert len(plan["preguntas"]) == 4 * len(candidates) + len(candidates) * (len(candidates) - 1)
    if options.get("conflicts") or (options.get("incomplete") and count == 1 and len(candidates) == 1):
        assert result["requiere_revision"]


def test_batches_preserve_context_and_every_pair_without_filtering():
    doc = prepare_document(document(*(candidate(f"PERSONA {i}", str(i)) for i in range(5)), separate=True))
    config = Config(questions_per_request=3)
    plan = prepare_plan(doc, config)
    assert all(len(batch) <= 3 for batch in plan["lotes"])
    assert sum(map(len, plan["lotes"])) == len(plan["preguntas"])
    assert {k for batch in plan["lotes"] for k in batch} == set(plan["preguntas"])
    assert sum(q.startswith("equiv:") for q in plan["preguntas"]) == len(list(combinations(doc.candidates, 2)))
    assert plan["state"]["documento"]["resultados"] == doc.original["resultados"]


def test_oversized_context_is_reported_without_truncation():
    raw = document(candidate())
    raw["resultados"][0]["fragmento"] = "x" * 35000
    doc = prepare_document(raw)
    plan = prepare_plan(doc, Config())
    assert plan["dimension"]["bloqueado_por_estimacion"]
    assert plan["state"]["documento"]["resultados"] == raw["resultados"]


def test_unknown_reference_invalid_probability_and_incomplete_response():
    plan = prepare_plan(prepare_document(document(candidate())), Config())
    raw = {"answers": {"no_existe": {"type": "noul", "noul": 1},
                       "acepta:f0001.c0001": {"type": "noul", "noul": True},
                       "conflicto:f0001.c0001": {"type": "noul", "noul": float("nan")}}}
    result = interpret_responses(plan, [raw])
    assert not result["answers"]
    assert len(result["errores"]) == 4


def test_answers_cannot_reference_questions_from_another_batch():
    plan = prepare_plan(prepare_document(document(candidate())), Config(questions_per_request=2))
    raw = fake_response(plan["preguntas"], accepted=("f0001.c0001",))
    interpreted = interpret_responses(plan, [raw], expected_batches=plan["lotes"])
    assert set(interpreted["answers"]) == set(plan["lotes"][0])
    assert any(e["tipo"] == "respuestas_incompletas" for e in interpreted["errores"])
