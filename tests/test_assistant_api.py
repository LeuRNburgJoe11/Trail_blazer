"""Local prototype boundary checks and real SDK request construction (no network)."""
import importlib.util
import json
from pathlib import Path

import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from railpulse.assistant.catalog import MODELS, validate_model
from railpulse.assistant.llm import make_selector

SPEC = importlib.util.spec_from_file_location("railpulse_assistant_api_test", Path(__file__).resolve().parents[1] / "app/assistant_api.py")
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


@pytest.fixture
def client():
    return TestClient(api.app, base_url="http://localhost")


def test_catalog_and_real_reference_replay(client):
    response = client.get("/api/assistant/context")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["record_count"] == 123
    assert response.json()["api_schema_version"] == 4
    assert response.json()["knowledge"]["documents"] >= 5
    assert len(response.json()["models"]) == 8
    assert {m["provider"] for m in response.json()["models"]} == {"openai", "anthropic"}


def test_scoped_offline_answer(client):
    response = client.post("/api/assistant/ask", json={"question": "Summarise this batch", "subsystem": "shm", "file_ids": ["test01.csv"]})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "evidence_template"
    assert data["scope"]["file_ids"] == ["test01.csv"]
    assert "not live" in data["dataset_label"]


def test_clarification_roundtrip(client):
    first = client.post("/api/assistant/ask", json={"question": "How does this model work?"}).json()
    assert first["status"] == "needs_clarification"
    second = client.post("/api/assistant/ask", json={"question": "SHM", "previous_question": first["clarification"]["question"]}).json()
    assert second["status"] == "answered"
    assert second["scope"]["subsystems"] == ["shm"]
    assert "rainflow" in second["answer"]


def test_read_only_knowledge_tool(client):
    response = client.post("/api/assistant/knowledge/search", json={"question": "DCSR", "subsystem": "door"})
    assert response.status_code == 200
    assert response.json()["local_only"]
    assert response.json()["results"][0]["source"].endswith("Door Data Headers.md")
    assert client.post("/api/assistant/knowledge/search", json={"question": "DCSR", "path": "/etc/hosts"}).status_code == 400
    assert client.post("/api/assistant/knowledge/search", content=b"x" * 8193).status_code == 413


@pytest.mark.parametrize("provider,model", [("openai", "gpt-6-astra"), ("anthropic", "claude-opus-5")])
def test_verified_definition_identical_with_provider_configured(client, monkeypatch, provider, model):
    def factory(**kwargs):
        def forbidden(*args):
            pytest.fail("Verified definitions must not invoke a model")
        return forbidden
    monkeypatch.setattr(api, "make_selector", factory)
    local = client.post("/api/assistant/ask", json={"question": "what does shm mean"}).json()
    configured = client.post("/api/assistant/ask", json={"question": "what does shm mean", "provider": provider, "model": model, "api_key": "TEST-SECRET", "consent": True}).json()
    assert local["answer"] == configured["answer"] == "SHM means Structural Health Monitoring."
    assert local["facts"] == configured["facts"]
    assert configured["presentation"] == "verified_definition"
    assert "TEST-SECRET" not in json.dumps(configured)


@pytest.mark.parametrize("provider,model", [("openai", "gpt-6-astra"), ("anthropic", "claude-opus-5")])
def test_cited_generation_and_no_call_for_ambiguity(client, monkeypatch, provider, model):
    calls = []
    def factory(**kwargs):
        def generate(question, cards):
            calls.append(question)
            return {"paragraphs": [{"text": "A Normal classification may still require review.", "citation_ids": [cards[0]["id"]]}]}
        return generate
    monkeypatch.setattr(api, "make_selector", factory)
    connection = {"provider": provider, "model": model, "api_key": "TEST-SECRET", "consent": True}
    first = client.post("/api/assistant/ask", json={**connection, "question": "Explain it"}).json()
    assert first["status"] == "needs_clarification"
    assert calls == []
    second = client.post("/api/assistant/ask", json={**connection, "question": "Explain review policy"}).json()
    assert second["mode"] == "grounded_llm"
    assert len(calls) == 1
    assert "TEST-SECRET" not in json.dumps(second)


@pytest.mark.parametrize("body", [{"question": "Hi", "unexpected": "SECRET"}, {"question": "Hi", "provider": "evil", "api_key": "SECRET"}, {"question": " "}, {"question": "x" * 2001}])
def test_invalid_input_is_sanitised(client, body):
    response = client.post("/api/assistant/ask", json=body)
    assert response.status_code == 400
    assert "SECRET" not in response.text


def test_unknown_file_and_origin_and_oversize(client):
    assert client.post("/api/assistant/ask", json={"question": "Show evidence", "file_ids": ["private.csv"]}).status_code == 400
    assert client.get("/api/assistant/context", headers={"origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/assistant/context", headers={"host": "evil.example"}).status_code == 400
    assert client.post("/api/assistant/ask", content=b"x" * 16385).status_code == 413


def test_no_consent_no_external_call(client, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("No consent: must not instantiate a provider")
    monkeypatch.setattr(api, "make_selector", forbidden)
    response = client.post("/api/assistant/ask", json={"question": "Summarise", "provider": "openai", "model": "gpt-6-astra", "api_key": "SECRET"})
    assert response.json()["mode"] == "evidence_template"
    assert "SECRET" not in response.text


@pytest.mark.parametrize("provider,model", [("openai", "gpt-6-astra"), ("anthropic", "claude-opus-5")])
def test_both_providers_flow_and_key_redaction(client, monkeypatch, provider, model):
    calls = []
    def factory(**kwargs):
        calls.append(kwargs)
        return lambda question, cards: [cards[0]["id"]]
    monkeypatch.setattr(api, "make_selector", factory)
    response = client.post("/api/assistant/ask", json={"question": "Summarise", "provider": provider, "model": model, "api_key": "SECRET", "consent": True})
    assert response.json()["mode"] == "grounded_llm"
    assert calls == [{"provider": provider, "model": model, "api_key": "SECRET"}]
    assert "SECRET" not in response.text


def test_provider_failure_does_not_echo_secrets(client, monkeypatch):
    def failing(**kwargs):
        raise RuntimeError("SECRET payload")
    monkeypatch.setattr(api, "make_selector", failing)
    response = client.post("/api/assistant/ask", json={"question": "Summarise", "provider": "openai", "model": "gpt-6-astra", "api_key": "SECRET", "consent": True})
    assert response.json()["mode"] == "evidence_template"
    assert response.json()["warnings"]
    assert "SECRET" not in response.text


@pytest.mark.parametrize("entry", MODELS, ids=lambda m: m["id"])
def test_installed_sdk_serializes_all_models_without_network(entry, monkeypatch):
    pytest.importorskip("langchain")
    for key in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        monkeypatch.delenv(key, raising=False)
    selector = make_selector(provider=entry["provider"], model=entry["id"], api_key="test-placeholder")
    llm = next(cell.cell_contents for cell in selector.__closure__ if hasattr(cell.cell_contents, "_get_request_payload"))
    payload = llm._get_request_payload([("system", "Choose evidence IDs"), ("human", "Question")])
    assert payload["model"] == entry["id"]
    assert "test-placeholder" not in json.dumps(payload)
    if entry["provider"] == "openai":
        assert payload["store"] is False
        assert payload["max_output_tokens"] == 8192
        assert payload["reasoning"]["effort"] == "low"
        assert "input" in payload
    else:
        assert payload["max_tokens"] == 8192
        assert payload["messages"]


def test_cross_provider_model_rejected():
    with pytest.raises(ValueError):
        validate_model("openai", "claude-opus-5")


def test_engineer_instructions_api(client):
    response = client.post("/api/assistant/ask", json={"question": "Prepare a handover", "subsystem": "shm", "engineer_instructions": "Explain for a technician, detailed", "engineer_context": "Sensor status awaiting confirmation", "engineer_author": "Duty engineer"})
    assert response.status_code == 200
    answer = response.json()
    assert answer["schema_version"] == 2
    assert answer["engineer_input"]["context"]["status"] == "user_provided_unverified"
    assert answer["explanation"]["audience"] == "technician"
    assert answer["explanation"]["detail"] == "detailed"


def test_engineer_instruction_limits_api(client):
    response = client.post("/api/assistant/ask", json={"question": "Explain", "engineer_context": "NOTE-SECRET" * 300})
    assert response.status_code == 400
    assert "NOTE-SECRET" not in response.text


def test_typed_response_blocks_discard_reasoning(monkeypatch):
    from types import SimpleNamespace
    pytest.importorskip("langchain")
    import langchain.chat_models
    monkeypatch.setattr(langchain.chat_models, "init_chat_model", lambda *args, **kwargs: SimpleNamespace(invoke=lambda *args: SimpleNamespace(content=[{"type": "thinking", "thinking": "Never display"}, {"type": "text", "text": '["fact:0"]'}])))
    selector = make_selector(provider="anthropic", model="claude-fable-5-1", api_key="fake")
    assert selector("question", [{"id": "fact:0", "text": "fact"}]) == ["fact:0"]
