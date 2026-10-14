from jev_experimentos.config import Config
from jev_experimentos.src.decision_engine import interpret_responses, prepare_plan
from jev_experimentos.src.loader import prepare_document
from jev_experimentos.src.result_builder import build_result
from .conftest import candidate, document, fake_response


def evaluate(raw, options=None, modify=None):
    doc = prepare_document(raw)
    plan = prepare_plan(doc, Config())
    response = fake_response(plan["preguntas"], **(options or {}))
    if modify:
        modify(response)
    return build_result(doc, interpret_responses(plan, [response]), Config())


def test_exact_original_values_and_original_evidence_after_model_equivalence():
    raw = document(candidate("PEREZ", "12.345.678"), candidate("ANA PEREZ", "12.345.678"), separate=True)
    result = evaluate(raw, {"accepted": ("f0001.c0001", "f0002.c0001"),
                            "equivalent": (("f0001.c0001", "f0002.c0001"),), "incomplete": ("f0001.c0001",)})
    person = result["personas_embargadas"][0]
    assert result["estado"] == "RESUELTO"
    assert person["nombre_embargado"] == "ANA PEREZ"
    assert person["dni_embargado"] == "12.345.678"
    assert person["cuit_cuil_embargado"] is None
    assert len(person["referencias_evidencia"]) == 2
    assert person["evidencias"][0]["resultado_original"] == raw["resultados"][0]
    assert person["valores_originales"]["nombre_embargado"] == ["PEREZ", "ANA PEREZ"]
    assert not result["requiere_revision"]


def test_no_automatic_merge_even_when_same_name_and_identifier():
    result = evaluate(document(candidate(), candidate()), {"accepted": ("f0001.c0001", "f0001.c0002")})
    assert result["estado"] == "RESUELTO_MULTIPLE"


def test_conflicting_ids_are_retained_without_choosing_or_normalizing():
    result = evaluate(document(candidate(dni="12.345.678"), candidate(dni="12345678")),
                      {"accepted": ("f0001.c0001", "f0001.c0002"), "equivalent": (("f0001.c0001", "f0001.c0002"),)})
    person = result["personas_embargadas"][0]
    assert person["dni_embargado"] is None
    assert person["valores_originales"]["dni_embargado"] == ["12.345.678", "12345678"]
    assert result["requiere_revision"]


def test_acceptance_does_not_require_a_name_or_gliner_role():
    result = evaluate(document(candidate(None, "123", role="abogado")),
                      {"accepted": ("f0001.c0001",), "incomplete": ("f0001.c0001",)})
    assert result["estado"] == "RESUELTO"
    assert result["personas_embargadas"][0]["nombre_embargado"] is None
    assert result["requiere_revision"]
    assert result["evaluacion_suficiencia"] == "NO_EVALUADA_EN_JEV_V1"


def test_uncertainty_and_incomplete_responses_are_not_sufficiency():
    def modify(response):
        response["answers"]["acepta:f0001.c0001"]["noul"] = 0.6
        del response["answers"]["rol:f0001.c0001"]
    result = evaluate(document(candidate()), modify=modify)
    assert result["estado"] == "NO_RESUELTO"
    assert result["requiere_revision"] and result["errores_respuesta"]


def test_non_transitive_equivalence_does_not_invent_merges():
    result = evaluate(document(candidate("ANA"), candidate("ANA PEREZ"), candidate("PEREZ")),
                      {"accepted": ("f0001.c0001", "f0001.c0002", "f0001.c0003"),
                       "equivalent": (("f0001.c0001", "f0001.c0002"), ("f0001.c0002", "f0001.c0003"))})
    assert result["cantidad_embargados"] == 3
    assert any(c["tipo"] == "equivalencia_no_transitiva" for c in result["conflictos"])


def test_role_disagreement_is_audited_but_does_not_override_jev_acceptance():
    result = evaluate(document(candidate()), {"accepted": ("f0001.c0001",), "roles": {"f0001.c0001": "profesional"}})
    assert result["cantidad_embargados"] == 1
    assert any(c["tipo"] == "rol_aceptacion_contradictorios" for c in result["conflictos"])
