import json
from types import SimpleNamespace

import pytest

from jev_experimentos.config import Config
from jev_experimentos.src.jev_client import ClientError, JevClient, RequestLimitError, serialize_response
from .conftest import FakeSDK


def test_requires_authorization_and_key(monkeypatch):
    with pytest.raises(ClientError, match="no autorizado"):
        JevClient(Config())
    with pytest.raises(ClientError, match="Falta TYPESAFE_API_KEY"):
        JevClient(Config(), authorized=True)


def test_timeout_retry_and_request_limit():
    calls, delays, errors = [], [], []
    def request(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise TimeoutError("mensaje que nunca se registra")
        return {"answers": {}, "model": "jev-1.13.0", "usage": {}}
    client = JevClient(Config(timeout=7, max_requests=2), authorized=True,
                       sdk_client=SimpleNamespace(system_one=request), sleep=delays.append)
    result = client.evaluate({"original": None}, {"q": {"type": "noul", "instructions": "?"}}, on_error=errors.append)
    assert result["answers"] == {} and client.attempts == 2
    assert calls[0]["timeout"] == 7 and calls[0]["state"] == {"original": None}
    assert delays == [0.5] and errors[0]["tipo"] == "TimeoutError"
    with pytest.raises(RequestLimitError):
        client.evaluate({}, {})


def test_non_transient_error_never_retried_or_leaks_key(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "private-test-key")
    class AuthError(Exception):
        status = 401
    def fail(**kwargs):
        raise AuthError("private-test-key")
    client = JevClient(Config(), authorized=True, sdk_client=SimpleNamespace(system_one=fail))
    with pytest.raises(ClientError) as error:
        client.evaluate({}, {"q": {}})
    assert client.attempts == 1
    assert "private-test-key" not in str(error.value) + json.dumps(error.value.errors)
    assert serialize_response({"echo": "private-test-key"}) == {"echo": "[REDACTED]"}


def test_transient_http_error_and_retry_after():
    class RateError(Exception):
        status, retry_after_ms = 429, 2000
    sdk, delays = FakeSDK(), []
    original = sdk.system_one
    count = 0
    def request(**kwargs):
        nonlocal count
        count += 1
        if count == 1:
            raise RateError()
        return original(**kwargs)
    sdk.system_one = request
    client = JevClient(Config(), authorized=True, sdk_client=sdk, sleep=delays.append)
    client.evaluate({}, {})
    assert count == 2 and delays == [2.0]


def test_installed_sdk_wire_contract_without_network(monkeypatch):
    sdk = pytest.importorskip("typesafe_sdk")
    httpx = pytest.importorskip("httpx2")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-token")
    requests = []
    def handle(request):
        requests.append(request)
        payload = json.loads(request.content)
        assert payload == {"state": {"null": None}, "model": "jev-1.13.0",
                           "questions": {"q": {"type": "noul", "instructions": "¿Sí?"}}}
        return httpx.Response(200, json={"answers": {"q": {"type": "noul", "noul": 0.95}},
                                         "model": "jev-1.13.0", "usage": {"input_tokens": 10, "output_tokens": 3}})
    official = sdk.TypeSafeClient(api_key="test-token", base_url="https://api.typesafe.ai",
                                 transport=httpx.MockTransport(handle), retry=sdk.RetryPolicy(max_retries=0))
    client = JevClient(Config(), authorized=True, sdk_client=official)
    raw = client.evaluate({"null": None}, {"q": {"type": "noul", "instructions": "¿Sí?"}})
    client.close()
    assert raw["answers"]["q"]["noul"] == 0.95
    assert str(requests[0].url) == "https://api.typesafe.ai/v1/systemone"
    assert "test-token" not in json.dumps(raw)


def test_official_initialization_pins_host_and_disables_hidden_retries(monkeypatch):
    sdk = pytest.importorskip("typesafe_sdk")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-token")
    monkeypatch.setenv("TYPESAFE_BASE_URL", "https://unapproved.invalid")
    captured = {}
    def constructor(**kwargs):
        captured.update(kwargs)
        return FakeSDK()
    monkeypatch.setattr(sdk, "TypeSafeClient", constructor)
    client = JevClient(Config(), authorized=True)
    assert captured["base_url"] == "https://api.typesafe.ai"
    assert captured["retry"].max_retries == 0
    client.close()


def test_real_sdk_structured_questions_and_typed_choice_response():
    sdk = pytest.importorskip("typesafe_sdk")
    httpx = pytest.importorskip("httpx2")
    from jev_experimentos.src.loader import prepare_document
    from jev_experimentos.src.decision_engine import prepare_plan, interpret_responses
    from jev_experimentos.src.result_builder import build_result
    from .conftest import candidate, document, fake_response
    doc = prepare_document(document(candidate()))
    plan = prepare_plan(doc, Config())
    for question in plan["preguntas"].values():
        cls = sdk.Noul if question["type"] == "noul" else sdk.Choice
        assert cls(**question).instructions == question["instructions"]
    def handle(request):
        payload = json.loads(request.content)
        assert payload["state"] == doc.state and payload["questions"] == plan["preguntas"]
        return httpx.Response(200, json=fake_response(payload["questions"], accepted=("f0001.c0001",)))
    official = sdk.TypeSafeClient(api_key="synthetic-token", base_url="https://api.typesafe.ai",
                                 transport=httpx.MockTransport(handle), retry=sdk.RetryPolicy(max_retries=0))
    client = JevClient(Config(), authorized=True, sdk_client=official)
    response = client.evaluate(doc.state, plan["preguntas"])
    client.close()
    assert response["answers"]["rol:f0001.c0001"]["choice"] == "embargado"
    assert build_result(doc, interpret_responses(plan, [response]), Config())["estado"] == "RESUELTO"
