"""General workspace remains documentation-only, never a replay fallback."""
import pytest

from railpulse.assistant.dashboard import DashboardAssistant


def test_general_definition_and_navigation():
    assistant = DashboardAssistant("general")
    assert assistant.answer("What does SHM mean?")["answer"] == "SHM means Structural Health Monitoring."
    guide = assistant.answer("What can this assistant help me with?")
    assert "RailPulser" in guide["answer"]
    assert "documentation only" in guide["answer"]


def test_general_result_request_requires_subsystem():
    answer = DashboardAssistant("general").answer("Summarise my uploaded results")
    assert answer["status"] == "needs_clarification"
    assert "Select Door, ACV, Rail or SHM" in answer["answer"]
    assert not answer["facts"]


def test_general_rejects_snapshot_and_row_selectors():
    with pytest.raises(ValueError):
        DashboardAssistant("general", {"rows": []})
    with pytest.raises(ValueError):
        DashboardAssistant("general").answer("Explain this result", row_index=0)


def test_general_preserves_safety_refusal():
    answer = DashboardAssistant("general").answer("Can you confirm it is safe to dispatch?")
    assert answer["status"] == "insufficient_evidence"
