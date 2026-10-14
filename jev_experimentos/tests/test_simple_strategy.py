from copy import deepcopy
import hashlib
import json

import pytest

from jev_experimentos.config import Config, DEFAULT_EXPERIMENT, PROJECT_ROOT, predictions_path
from jev_experimentos.run_experiment import parse_args, run_experiment
from jev_experimentos.src.decision_engine import build_questions, interpret_responses, prepare_plan
from jev_experimentos.src.loader import prepare_document
from jev_experimentos.src.result_builder import build_result
from .conftest import FakeSDK, candidate, document, fake_response
from .test_integration import factory, source


def test_strategy_defaults_and_cli_choices():
    assert Config().strategy == parse_args([]).estrategia == "completa"
    assert parse_args(["--estrategia", "simple"]).estrategia == "simple"
    with pytest.raises(ValueError, match="estrategia"):
        Config(strategy="otra")
    with pytest.raises(SystemExit):
        parse_args(["--estrategia", "otra"])


def test_simple_preserves_state_and_asks_exactly_one_noul_per_candidate():
    raw = document(candidate("PEREZ", confidence=0.00001), candidate(None, None),
                   candidate(role="abogado"), separate=True)
    before = deepcopy(raw)
    doc = prepare_document(raw)
    simple = prepare_plan(doc, Config(strategy="simple"))
    complete = prepare_plan(doc, Config())
    assert simple["state"] == complete["state"]
    assert simple["state"]["documento"]["resultados"] == raw["resultados"]
    assert raw == before
    assert len(simple["preguntas"]) == len(doc.candidates) == 3
    assert all(qid.startswith("acepta:") and question["type"] == "noul"
               for qid, question in simple["preguntas"].items())
    assert [q["instructions"]["candidatos"] for q in simple["preguntas"].values()] == [[cid] for cid in doc.candidates]
    assert all(q["instructions"]["pregunta"] ==
               "Considerando todas las extracciones y fragmentos originales de este documento, "
               "¿este candidato representa a una persona o entidad cuyos fondos, cuentas o bienes "
               "son objeto de la medida de embargo?" for q in simple["preguntas"].values())
    assert build_questions(doc) == build_questions(doc, "completa")


def test_simple_keeps_duplicate_accepted_extractions_independent():
    doc = prepare_document(document(candidate(), candidate(), separate=True))
    config = Config(strategy="simple")
    plan = prepare_plan(doc, config)
    response = fake_response(plan["preguntas"], accepted=tuple(doc.candidates))
    result = build_result(doc, interpret_responses(plan, [response]), config)
    assert result["estado"] == "RESUELTO_MULTIPLE" and result["cantidad_embargados"] == 2
    assert [p["candidatos_ids"] for p in result["personas_embargadas"]] == [[cid] for cid in doc.candidates]
    assert result["deduplicacion"] == "NO_EVALUADA" and result["requiere_revision"]
    assert not result["incertidumbre"] and not result["errores_respuesta"]
    assert not result["conflictos"]
    assert {"rol", "nombre_completo", "conflictos_identificador"} <= set(result["evaluaciones_no_realizadas"])
    assert not any(o["tipo"] in ("rol_incierto", "conflicto_incierto", "equivalencia_incierta") for o in result["observaciones"])
    for person in result["personas_embargadas"]:
        cid = person["candidatos_ids"][0]
        assert person["evidencias"][0]["extraccion_original"] == doc.candidates[cid]
        assert person["referencias_evidencia"] == [doc.references[cid]["candidato"]]


@pytest.mark.parametrize("p,status,count", [(0.1, "DESCARTADO", 0), (0.6, "INCIERTO", 0),
                                          (0.799, "INCIERTO", 0), (0.8, "ACEPTADO", 1),
                                          (0.99, "ACEPTADO", 1)])
def test_simple_respects_acceptance_threshold_and_uncertainty(p, status, count):
    doc = prepare_document(document(candidate(None, "11", role="abogado")))
    config = Config(strategy="simple")
    plan = prepare_plan(doc, config)
    response = {"answers": {"acepta:f0001.c0001": {"type": "noul", "noul": p}}}
    result = build_result(doc, interpret_responses(plan, [response]), config)
    assert result["cantidad_embargados"] == count
    assert result["decisiones_candidatos"][0]["decision"] == status
    assert result["incertidumbre"] == (status == "INCIERTO")
    if count:
        assert result["estado"] == "RESUELTO"
        assert result["personas_embargadas"][0]["nombre_embargado"] is None
        assert result["personas_embargadas"][0]["dni_embargado"] == "11"
    else:
        assert result["estado"] == "NO_RESUELTO"


def test_simple_configurable_threshold_and_missing_answers():
    doc = prepare_document(document(candidate()))
    config = Config(strategy="simple", threshold=0.9)
    plan = prepare_plan(doc, config)
    raw = {"answers": {"acepta:f0001.c0001": {"type": "noul", "noul": 0.85}}}
    assert build_result(doc, interpret_responses(plan, [raw]), config)["cantidad_embargados"] == 0
    incomplete = build_result(doc, interpret_responses(plan, [{"answers": {}}]), config)
    assert incomplete["cantidad_embargados"] == 0 and incomplete["incertidumbre"]
    assert incomplete["procesamiento"] == "RESPUESTA_INCOMPLETA"
    missing = next(e["preguntas"] for e in incomplete["errores_respuesta"] if e["tipo"] == "respuestas_incompletas")
    assert missing == ["acepta:f0001.c0001"]


def test_simple_simulated_integration_records_strategy_and_preserves_evidence(tmp_path):
    raw = document(candidate("PEREZ", "11"), candidate("PEREZ", "11"), candidate(None, "22"))
    path = source(tmp_path, [raw])
    before = path.read_bytes()
    sdk = FakeSDK(accepted=("f0001.c0001", "f0001.c0002", "f0001.c0003"))
    directory, summary = run_experiment(input_path=path, output_dir=tmp_path / "simple", authorized=True,
                                        config=Config(strategy="simple"), client_factory=factory(sdk))
    assert summary["estrategia"] == "simple" and summary["deduplicacion"] == "NO_EVALUADA"
    assert summary["total_preguntas"] == 3 and summary["total_personas_embargadas"] == 3
    assert len(sdk.calls) == 1 and sdk.closed
    assert sdk.calls[0]["state"]["documento"]["resultados"] == raw["resultados"]
    assert all(q["type"] == "noul" for q in sdk.calls[0]["questions"].values())
    metadata = json.loads((directory / "metadata.json").read_text())
    records = json.loads((directory / "decisiones_jev.json").read_text())
    consolidated = json.loads((directory / "consolidacion_jev.json").read_text())
    assert metadata["estrategia"] == metadata["contrato"]["estrategia"] == "simple"
    assert records[0]["estrategia"] == records[0]["plan"]["estrategia"] == "simple"
    assert consolidated[0]["deduplicacion"] == "NO_EVALUADA"
    assert path.read_bytes() == before


@pytest.mark.parametrize("original_strategy,new_strategy", [("simple", "completa"), ("completa", "simple")])
def test_cannot_resume_with_a_different_strategy(tmp_path, original_strategy, new_strategy):
    path = source(tmp_path)
    directory, _ = run_experiment(input_path=path, output_dir=tmp_path / "run", dry_run=True,
                                  config=Config(strategy=original_strategy))
    previous = (directory / "metadata.json").read_bytes()
    with pytest.raises(ValueError, match="estrategia diferente"):
        run_experiment(input_path=path, resume=directory, dry_run=True, config=Config(strategy=new_strategy))
    assert (directory / "metadata.json").read_bytes() == previous


def test_simple_resume_reuses_saved_answers(tmp_path):
    path = source(tmp_path, [document(candidate(), candidate(), candidate())])
    options = {"accepted": ("f0001.c0001", "f0001.c0002", "f0001.c0003")}
    first_sdk, second_sdk = FakeSDK(**options), FakeSDK(**options)
    directory, pending = run_experiment(input_path=path, output_dir=tmp_path / "resume", authorized=True,
                                        config=Config(strategy="simple", questions_per_request=1, max_requests=1),
                                        client_factory=factory(first_sdk))
    assert pending["documentos_pendientes"] == 1 and len(first_sdk.calls) == 1
    _, complete = run_experiment(input_path=path, resume=directory, authorized=True,
                                  config=Config(strategy="simple", questions_per_request=1, max_requests=3),
                                  client_factory=factory(second_sdk))
    assert complete["solicitudes_realizadas"] == 3 and complete["total_personas_embargadas"] == 3
    assert len(second_sdk.calls) == 2
    assert all(set(c["questions"]).isdisjoint(first_sdk.calls[0]["questions"]) for c in second_sdk.calls)


def test_default_output_directories_are_independent_and_name_the_strategy(tmp_path, monkeypatch):
    import jev_experimentos.run_experiment as runner
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    path = source(tmp_path)
    simple_dir, _ = run_experiment(input_path=path, dry_run=True, config=Config(strategy="simple"))
    complete_dir, _ = run_experiment(input_path=path, dry_run=True)
    assert simple_dir != complete_dir
    assert simple_dir.name.endswith("_simple_dry_run") and complete_dir.name.endswith("_completa_dry_run")
    with pytest.raises(FileExistsError):
        run_experiment(input_path=path, dry_run=True, output_dir=simple_dir, config=Config(strategy="completa"))


def test_legacy_complete_checkpoint_is_still_resumable(tmp_path):
    path = source(tmp_path)
    directory, _ = run_experiment(input_path=path, output_dir=tmp_path / "legacy", dry_run=True)
    metadata_path = directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata.pop("estrategia")
    metadata["config"].pop("strategy")
    metadata["contrato"].pop("estrategia")
    metadata["contrato"]["config"].pop("strategy")
    metadata_path.write_text(json.dumps(metadata))
    for cache in (directory / "documentos").glob("*.json"):
        record = json.loads(cache.read_text())
        record.pop("estrategia")
        record["plan"].pop("estrategia")
        cache.write_text(json.dumps(record))
    _, summary = run_experiment(input_path=path, resume=directory, dry_run=True)
    assert summary["estrategia"] == "completa" and summary["total_preguntas"] == 4


def test_real_four_document_dry_runs_share_state_and_preserve_all_candidates(tmp_path, monkeypatch):
    path = predictions_path(DEFAULT_EXPERIMENT)
    if not path.exists():
        pytest.skip("Las predicciones reales no están en este checkout.")
    before = path.read_bytes()
    raw_docs = [d for d in json.loads(before) if d["numero_archivo"] in ("9", "11", "30", "79")]
    monkeypatch.setenv("TYPESAFE_API_KEY", "presence-does-not-authorize")
    def forbidden(config):
        raise AssertionError("dry-run no puede construir un cliente")
    records_by_strategy = {}
    for strategy, expected in (("simple", 15), ("completa", 144)):
        directory, summary = run_experiment(numbers=["9", "11", "30", "79"], dry_run=True,
                                            config=Config(strategy=strategy), output_dir=tmp_path / strategy,
                                            client_factory=forbidden)
        assert summary["total_documentos"] == 4 and summary["total_candidatos"] == 15
        assert summary["total_preguntas"] == expected and summary["solicitudes_realizadas"] == 0
        assert summary["estrategia"] == strategy
        records = json.loads((directory / "decisiones_jev.json").read_text())
        assert [r["numero_archivo"] for r in records] == [d["numero_archivo"] for d in raw_docs]
        records_by_strategy[strategy] = records
        for raw, record in zip(raw_docs, records):
            assert record["plan"]["state"]["documento"]["resultados"] == raw["resultados"]
        if strategy == "simple":
            assert all(qid.startswith("acepta:") and q["type"] == "noul"
                       for r in records for qid, q in r["plan"]["preguntas"].items())
    assert [r["plan"]["state"] for r in records_by_strategy["simple"]] == [r["plan"]["state"] for r in records_by_strategy["completa"]]
    historical = PROJECT_ROOT / "jev_experimentos/outputs/validacion_jev_v1_cuatro_archivos/decisiones_jev.json"
    if historical.exists():
        old_records = json.loads(historical.read_text())
        assert [r["plan"]["preguntas"] for r in old_records] == [r["plan"]["preguntas"] for r in records_by_strategy["completa"]]
    assert path.read_bytes() == before
    assert hashlib.sha256(before).hexdigest() == "420d8e2f2cedfffe4591de2876af8bdbdd46d7daf3c8671354900af4c6e9322d"
