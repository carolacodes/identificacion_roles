import csv
import json
from pathlib import Path

import pytest

from jev_experimentos.config import Config, DEFAULT_EXPERIMENT, predictions_path
from jev_experimentos.run_experiment import execution_lock, main, run_experiment
from jev_experimentos.src.jev_client import ClientError, JevClient
from jev_experimentos.src.loader import load_predictions
from .conftest import FakeSDK, candidate, document


def source(tmp_path, raw=None):
    path = tmp_path / "predicciones_por_documento.json"
    path.write_text(json.dumps(raw or [document(candidate())]), encoding="utf-8")
    return path


def factory(sdk):
    return lambda config: JevClient(config, authorized=True, sdk_client=sdk, sleep=lambda _: None)


def test_entire_simulated_flow_outputs_and_comparison(tmp_path):
    path = source(tmp_path)
    baseline = tmp_path / "consolidacion.json"
    baseline.write_text(json.dumps([{"id": "sintetico", "numero_archivo": "9", "estado": "NO_RESUELTO", "personas_embargadas": []}]))
    sdk = FakeSDK(accepted=("f0001.c0001",))
    directory, summary = run_experiment(input_path=path, baseline_path=baseline, authorized=True,
                                        output_dir=tmp_path / "run", client_factory=factory(sdk))
    assert summary["RESUELTO"] == 1 and summary["solicitudes_realizadas"] == 1
    assert sdk.closed
    for name in ("decisiones_jev.json", "consolidacion_jev.json", "resumen_jev.json", "metadata.json"):
        assert json.loads((directory / name).read_text()) is not None
    decisions = json.loads((directory / "decisiones_jev.json").read_text())
    assert decisions[0]["lotes"][0]["respuesta_original"]["usage"]["input_tokens"] == 20
    assert sdk.calls[0]["state"]["documento"]["resultados"] == json.loads(path.read_text())[0]["resultados"]
    rows = list(csv.DictReader((directory / "comparacion.csv").open()))
    assert rows[0]["estado_jev"] == "RESUELTO" and rows[0]["nombres_solo_jev"] == '["ANA PEREZ"]'
    assert json.loads((directory / "metadata.json").read_text())["input_no_modificado"]


def test_dry_run_never_constructs_a_client_even_with_key_and_authorization(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "present-does-not-authorize")
    def forbidden(config):
        raise AssertionError("dry-run construyó un cliente")
    directory, summary = run_experiment(input_path=source(tmp_path), output_dir=tmp_path / "dry",
                                        dry_run=True, authorized=True, client_factory=forbidden)
    assert summary["solicitudes_realizadas"] == 0 and summary["documentos_procesados"] == 0
    assert json.loads((directory / "consolidacion_jev.json").read_text()) == []
    assert len((directory / "comparacion.csv").read_text().splitlines()) == 1
    assert "present-does-not-authorize" not in (directory / "metadata.json").read_text()


def test_resume_reuses_saved_batches_and_global_budget(tmp_path):
    path = source(tmp_path)
    sdk = FakeSDK(accepted=("f0001.c0001",))
    directory, summary = run_experiment(input_path=path, output_dir=tmp_path / "resume",
                                        authorized=True, config=Config(questions_per_request=2, max_requests=1),
                                        client_factory=factory(sdk))
    assert summary["documentos_pendientes"] == 1 and len(sdk.calls) == 1
    resumed_sdk = FakeSDK(accepted=("f0001.c0001",))
    _, summary = run_experiment(input_path=path, resume=directory, authorized=True,
                                config=Config(questions_per_request=2, max_requests=3), client_factory=factory(resumed_sdk))
    assert summary["RESUELTO"] == 1 and summary["solicitudes_realizadas"] == 2
    assert len(resumed_sdk.calls) == 1
    assert set(resumed_sdk.calls[0]["questions"]).isdisjoint(sdk.calls[0]["questions"])
    def forbidden(config):
        raise AssertionError("Repite llamadas de una ejecución completada")
    _, again = run_experiment(input_path=path, resume=directory, authorized=True,
                              config=Config(questions_per_request=2, max_requests=3), client_factory=forbidden)
    assert again["solicitudes_realizadas"] == 2


def test_resume_rejects_changed_input_config_and_mode(tmp_path):
    path = source(tmp_path)
    directory, _ = run_experiment(input_path=path, dry_run=True, output_dir=tmp_path / "dry")
    with pytest.raises(ValueError, match="incompatible"):
        run_experiment(input_path=path, resume=directory, authorized=True)
    with pytest.raises(ValueError, match="incompatible"):
        run_experiment(input_path=path, resume=directory, dry_run=True, config=Config(threshold=0.9))
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="incompatible"):
        run_experiment(input_path=path, resume=directory, dry_run=True)


def test_interrupted_call_requires_explicit_retry_and_preserves_attempt_count(tmp_path):
    path = source(tmp_path)
    class InterruptedSDK(FakeSDK):
        def system_one(self, **kwargs):
            raise KeyboardInterrupt()
    directory = tmp_path / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        run_experiment(input_path=path, output_dir=directory, authorized=True,
                       client_factory=factory(InterruptedSDK()))
    assert json.loads((directory / "metadata.json").read_text())["solicitudes_realizadas"] == 1
    with pytest.raises(ValueError, match="EN_CURSO"):
        run_experiment(input_path=path, resume=directory, authorized=True, client_factory=factory(FakeSDK()))
    _, summary = run_experiment(input_path=path, resume=directory, authorized=True,
                                retry_errors=True, client_factory=factory(FakeSDK(accepted=("f0001.c0001",))))
    assert summary["RESUELTO"] == 1 and summary["solicitudes_realizadas"] == 2


def test_errors_persist_and_dont_repeat_automatically(tmp_path):
    class Failure(FakeSDK):
        def system_one(self, **kwargs):
            raise TimeoutError()
    path = source(tmp_path)
    directory, summary = run_experiment(input_path=path, output_dir=tmp_path / "errors", authorized=True,
                                        config=Config(retries=0), client_factory=factory(Failure()))
    assert summary["errores_procesamiento"] and summary["solicitudes_realizadas"] == 1
    _, resumed = run_experiment(input_path=path, resume=directory, authorized=True,
                                config=Config(retries=0), client_factory=factory(FakeSDK()))
    assert resumed["solicitudes_realizadas"] == 1 and resumed["documentos_procesados"] == 0


def test_global_max_requests_includes_retries(tmp_path):
    class TimeoutSDK(FakeSDK):
        def system_one(self, **kwargs):
            raise TimeoutError()
    directory, summary = run_experiment(input_path=source(tmp_path), output_dir=tmp_path / "budget",
                                        authorized=True, config=Config(max_requests=1, retries=2),
                                        client_factory=factory(TimeoutSDK()))
    assert summary["solicitudes_realizadas"] == 1 and summary["documentos_procesados"] == 0


def test_no_calls_without_authorization_and_cli_errors(tmp_path):
    with pytest.raises(ClientError, match="no autorizado"):
        run_experiment(input_path=source(tmp_path), output_dir=tmp_path / "blocked")
    assert main(["--solo-archivos", "9"]) == 2
    assert main(["--autorizar-envio-datos", "--solo-archivos", "9", "--output-dir", str(tmp_path / "missing-key")]) == 2


def test_real_predictions_dry_run_is_lossless(tmp_path):
    path = predictions_path(DEFAULT_EXPERIMENT)
    if not path.exists():
        pytest.skip("Las predicciones reales no están en este checkout.")
    before = path.read_bytes()
    docs, sha = load_predictions(path)
    directory, summary = run_experiment(dry_run=True, output_dir=tmp_path / "real-dry")
    assert len(docs) == summary["total_documentos"] == 79
    assert summary["total_fragmentos"] == 163 and summary["total_candidatos"] == 239
    assert summary["solicitudes_realizadas"] == 0
    records = json.loads((directory / "decisiones_jev.json").read_text())
    for doc, rec in zip(docs, records):
        assert rec["plan"]["state"]["documento"]["resultados"] == doc.original["resultados"]
        assert len(rec["plan"]["candidatos"]) == sum(len(r["candidates"]) for r in doc.original["resultados"])
    assert path.read_bytes() == before
    assert json.loads((directory / "metadata.json").read_text())["input_sha256"] == sha


def test_oversized_document_never_constructs_client(tmp_path):
    raw = document(candidate())
    raw["resultados"][0]["fragmento"] = "x" * 40000
    def forbidden(config):
        raise AssertionError("Documento bloqueado llegó a la API")
    _, summary = run_experiment(input_path=source(tmp_path, [raw]), output_dir=tmp_path / "oversized",
                                authorized=True, client_factory=forbidden)
    assert summary["documentos_bloqueados_por_estimacion"] == ["9"]
    assert summary["solicitudes_realizadas"] == 0


def test_estimated_oversize_can_be_attempted_without_removing_evidence(tmp_path):
    raw = document(candidate())
    raw["resultados"][0]["fragmento"] = "x" * 40000
    sdk = FakeSDK(accepted=("f0001.c0001",))
    _, summary = run_experiment(input_path=source(tmp_path, [raw]), output_dir=tmp_path / "allowed-estimate",
                                authorized=True, config=Config(allow_estimated_oversize=True), client_factory=factory(sdk))
    assert summary["documentos_exceden_estimacion"] == ["9"]
    assert not summary["documentos_bloqueados_por_estimacion"]
    assert sdk.calls[0]["state"]["documento"]["resultados"] == raw["resultados"]


def test_execution_lock_prevents_two_writers_and_is_released(tmp_path):
    with execution_lock(tmp_path):
        with pytest.raises(ValueError, match="otro proceso"):
            with execution_lock(tmp_path):
                raise AssertionError("Dos escritores simultáneos")
    with execution_lock(tmp_path):
        pass


def test_comparison_detects_swapped_identifiers_between_shared_names(tmp_path):
    path = source(tmp_path, [document(candidate("ANA PEREZ", "11"), candidate("BETO LOPEZ", "22"))])
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps([{"id": "sintetico", "numero_archivo": "9", "estado": "RESUELTO_MULTIPLE",
                                     "personas_embargadas": [{"nombre_embargado": "ANA PEREZ", "dni_embargado": "22"},
                                                            {"nombre_embargado": "BETO LOPEZ", "dni_embargado": "11"}]}]))
    directory, _ = run_experiment(input_path=path, baseline_path=baseline, output_dir=tmp_path / "swapped",
                                  authorized=True, client_factory=factory(FakeSDK(accepted=("f0001.c0001", "f0001.c0002"))))
    row = list(csv.DictReader((directory / "comparacion.csv").open()))[0]
    differences = json.loads(row["diferencias_identificadores"])
    assert differences["solo_actual"] == differences["solo_jev"] == []
    assert set(differences["por_nombre_compartido"]) == {"ANA PEREZ", "BETO LOPEZ"}
