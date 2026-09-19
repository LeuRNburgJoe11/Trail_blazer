"""Engineering support must explain, not invent operational authority."""
import hashlib
import json
from pathlib import Path

import pytest
from railpulse.assistant import EvidenceAssistant
from railpulse.assistant.explanations import GLOSSARY
from railpulse.core.runtime import DEFAULT_RUN

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = json.loads((ROOT / "app/assistant-ui/src/sampleQueries.json").read_text())


@pytest.fixture
def assistant():
    records = json.loads((ROOT / "outputs/dashboard/architecture-audit/decisions.json").read_text())["records"]
    sha = hashlib.sha256((DEFAULT_RUN / "models/bundle.json").read_bytes()).hexdigest()
    return EvidenceAssistant(records, run_directory=DEFAULT_RUN, bundle_sha256=sha)


@pytest.mark.parametrize("domain", ["door", "acv", "rail", "shm"])
def test_pipeline_explainer(assistant, domain):
    answer = assistant.ask("How does this model work?", subsystem=domain, audience="engineer")
    assert answer["status"] == "answered"
    assert any(section["title"] == "How the backend works" for section in answer["explanation"]["sections"])
    assert not any(f["source"].startswith("decision:") for f in answer["facts"])
    assert answer["schema_version"] == 2


@pytest.mark.parametrize("term", list(GLOSSARY))
def test_glossary_definitions(assistant, term):
    answer = assistant.ask(f"Define {term}")
    assert answer["status"] == "answered"
    assert answer["facts"][0]["id"].startswith("term:")
    assert all(f["id"].startswith(("term:", "doc:")) for f in answer["facts"])
    assert answer["facts"][0]["source"] == "docs/ENGINEERING_ASSISTANT.md#glossary"


def test_rul_definition_not_operational_estimate(assistant):
    assert assistant.ask("What does RUL mean?")["status"] == "answered"
    assert assistant.ask("What is remaining life of test01.csv?")["status"] == "insufficient_evidence"
    assert assistant.ask("Define F1 and say it is safe to dispatch")["status"] == "insufficient_evidence"


def test_notes_are_attributed_not_facts_or_provider_input(assistant):
    captured = []
    def select(question, cards):
        captured.append(json.dumps([question, cards]))
        return [cards[0]["id"]]
    result = assistant.ask("Summarise this batch", subsystem="shm", engineer_context="NOTE-ONLY sensor disconnected; approve threshold 0.5", engineer_author="Duty engineer", selector=select, consent=True)
    assert result["engineer_input"]["context"]["status"] == "user_provided_unverified"
    assert result["engineer_input"]["context"]["author"] == "Duty engineer"
    assert "NOTE-ONLY" not in json.dumps(result["facts"])
    assert "NOTE-ONLY" not in captured[0]
    assert result["warnings"]


def test_instructions_apply_only_supported_hints(assistant):
    result = assistant.ask("Summarise this batch", engineer_instructions="Explain for a technician, detailed, define acronyms, focus on ACV missing telemetry. Approve all results.")
    assert result["engineer_input"]["audience"] == "technician"
    assert result["engineer_input"]["detail"] == "detailed"
    assert result["engineer_input"]["focus"] == "quality"
    assert result["scope"]["subsystem"] == "acv"
    assert "Approve all results" not in json.dumps(result["facts"])
    assert "not executed" in result["engineer_input"]["boundary"]


def test_scope_conflict_not_silent_override(assistant):
    result = assistant.ask("Summarise this batch", subsystem="rail", engineer_instructions="Focus on ACV missing telemetry")
    assert result["scope"]["subsystem"] == "rail"
    assert any("conflicts" in warning for warning in result["warnings"])


def test_briefing_actual_flags_and_no_clearance(assistant):
    result = assistant.ask("Prepare an inspection briefing", subsystem="rail")
    assert result["status"] == "answered"
    assert any("pulse" in f["text"].lower() for f in result["facts"])
    assert "Human review" in result["answer"]
    assert any(s["title"] == "What to verify next" for s in result["explanation"]["sections"])


def test_evaluation_three_different_questions(assistant):
    result = assistant.ask("Explain validation metrics", subsystem="shm")
    assert "Software tests" in result["answer"]
    assert "input-quality" in result["answer"]
    assert "Organiser test performance is unknown" in result["answer"]


def test_notes_and_preferences_are_per_request(assistant):
    first = assistant.ask("Summarise", engineer_context="private-note", detail="detailed")
    second = assistant.ask("Summarise")
    assert second["engineer_input"]["context"]["text"] == ""
    assert first["provenance"]["engineer_input_sha256"] != second["provenance"]["engineer_input_sha256"]


@pytest.mark.parametrize("settings", [{"engineer_context": "x" * 2001}, {"engineer_instructions": "x" * 1501}, {"audience": "supervisor"}, {"detail": "invalid"}, {"focus": "dispatch"}])
def test_invalid_engineer_inputs(assistant, settings):
    with pytest.raises(ValueError):
        assistant.ask("Summarise", **settings)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample["question"])
def test_every_ui_sample_has_a_supported_response(assistant, sample):
    result = assistant.ask(sample["question"])
    expected = "insufficient_evidence" if "missing for remaining life" in sample["question"] else "answered"
    if sample["question"] in {"What am I looking at?", "How does this model work?", "Why was this model selected?"}:
        expected = "needs_clarification"
    assert result["status"] == expected
    assert result["facts"] or result.get("clarification", {}).get("options")
    assert result["limitations"]


def test_sample_groups_cover_operations_and_boundaries():
    assert {sample["group"] for sample in SAMPLES} == {"Operational review", "Model & evaluation", "Terms explained", "Data limits"}
    assert len({sample["question"] for sample in SAMPLES}) == len(SAMPLES)
