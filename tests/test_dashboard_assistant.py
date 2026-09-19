"""Dashboard integration: live evidence, scope, isolation and transport."""
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from railpulse.assistant.dashboard import DashboardAssistant

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("assistant_bridge_test", ROOT / "app/railpulse/backend/assistant_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def test_current_results_not_saved_replay():
    assistant = DashboardAssistant("shm", {"rows": [{"file_id": "private.csv", "prediction": 0.123, "evidence": {"cycle_count": 72}}]})
    answer = assistant.answer("Summarise this batch")
    assert "private.csv" in answer["answer"] and "0.123" in answer["answer"]
    assert "test03.csv" not in answer["answer"]
    assert "Current dashboard" in answer["dataset_label"]
    assert assistant.answer("What does SHM mean?")["answer"] == "SHM means Structural Health Monitoring."


def test_empty_never_invents_results():
    answer = DashboardAssistant("door").answer("Summarise this batch")
    assert "No analysed dashboard results" in answer["answer"]
    assert "123" not in answer["answer"]


@pytest.mark.parametrize("domain,question,expected", [
    ("door", "Explain the Normal envelope", "90th percentile"),
    ("acv", "Explain the suspicion index", "not a failure probability"),
    ("acv", "Explain near ties in the consist", "0.02"),
    ("rail", "Explain the validation fold scores", "UI reference literals"),
    ("shm", "Explain the Miner reference", "not percentage of lifetime"),
])
def test_panel_explanations(domain, question, expected):
    answer = DashboardAssistant(domain).answer(question)
    assert expected in answer["answer"]


def test_ambiguous_rows_and_scope():
    assistant = DashboardAssistant("rail", {"rows": [{"file_id": "one.csv", "prediction": "Normal"}, {"file_id": "two.csv", "prediction": "Side I"}]})
    first = assistant.answer("Explain this result")
    assert first["status"] == "needs_clarification"
    answer = assistant.answer(first["clarification"]["options"][1]["question"])
    assert "two.csv" in answer["answer"] and "one.csv" not in answer["answer"]
    with pytest.raises(ValueError):
        assistant.answer("Explain this result", file_id="foreign.csv")


def test_car_scope_and_chart_values():
    assistant = DashboardAssistant("acv", {"rows": [{"file_id": "case.xlsx", "ranked_cars": ["03", "01"], "display_scores": {"03": 100, "01": 0}, "series": {"by_car": {"03": [24, 25], "01": [20, 22]}}}]})
    answer = assistant.answer("Show temperature chart maximum", row_index=0, car_id="03")
    assert "25" in answer["answer"]
    assert "car 01" not in answer["answer"]
    with pytest.raises(ValueError):
        assistant.answer("Explain this result", row_index=0, car_id="99")


def test_no_external_without_consent_and_no_unsafe_authority():
    def forbidden(*args):
        pytest.fail("Must not call external provider")
    assistant = DashboardAssistant("shm")
    assert assistant.answer("Summarise this batch", selector=forbidden)["mode"] == "evidence_template"
    assert assistant.answer("Is it safe to dispatch?", selector=forbidden, consent=True)["status"] == "insufficient_evidence"


def test_snapshot_capability_is_scoped_copied_and_expiring(monkeypatch):
    bridge.SNAPSHOTS.clear()
    payload = {"rows": [{"file_id": "one.csv", "prediction": 0.2}], "submission_csv": "private csv"}
    saved = bridge.remember("shm", payload)
    token = saved["assistant_snapshot"]
    assert "submission_csv" not in bridge.snapshot_for(token, "shm")
    with pytest.raises(ValueError):
        bridge.snapshot_for(token, "rail")
    copy = bridge.snapshot_for(token, "shm")
    copy["rows"].clear()
    assert bridge.snapshot_for(token, "shm")["rows"]
    monkeypatch.setattr(bridge.time, "monotonic", lambda: 10**15)
    with pytest.raises(ValueError):
        bridge.snapshot_for(token, "shm")


def test_bridge_rejects_client_evidence_and_external_origins(monkeypatch):
    app = FastAPI()
    app.include_router(bridge.router)
    client = TestClient(app, base_url="http://localhost")
    monkeypatch.setattr(bridge, "invoke", lambda payload: {"answer": "test", "snapshot": payload.get("dashboard_snapshot")})
    assert client.post("/api/assistant/ask", json={"question": "Hi", "subsystem": "shm", "dashboard_snapshot": {}}).status_code == 400
    assert client.post("/api/assistant/ask", json={"question": "Hi", "subsystem": "shm"}, headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/assistant/ask", content=b"x" * 17000).status_code == 413
    result = client.post("/api/assistant/ask", json={"question": "Hi", "subsystem": "shm"})
    assert result.status_code == 200 and result.json()["snapshot"] is None


def test_subprocess_bridge_real_definition():
    result = bridge.invoke({"question": "what does shm mean", "subsystem": "shm"})
    assert result["answer"] == "SHM means Structural Health Monitoring."
