"""Keyless explanations must not dump retrieved tables or adjacent passages."""
import pytest
from test_engineering_assistant import assistant
from railpulse.assistant.excerpts import local_excerpt


@pytest.mark.parametrize("term,meaning", [("DCSR", "Door Close Switch Right"), ("DCSL", "Door Close Switch Left"), ("DLSR", "Door Locked Switch Right"), ("DLSL", "Door Locked Switch Left")])
def test_specific_switch_definition(assistant, term, meaning):
    result = assistant.ask(f"What does {term} mean?")
    assert meaning in result["answer"]
    assert "released" in result["answer"] and "actuated" in result["answer"]
    assert len(result["answer"]) < 350
    assert "|" not in result["answer"] and "Datetime" not in result["answer"]
    assert "Reference:" not in result["answer"]
    assert len(result["answer_citation_ids"]) == 1
    assert result["facts"][0]["source_quote"]  # Exact source retained.


def test_two_requested_terms(assistant):
    answer = assistant.ask("What do DCSR and DCSL mean?")["answer"]
    assert "DCSR:" in answer and "DCSL:" in answer
    assert "DLSL" not in answer


def test_prose_top_passage_only(assistant):
    result = assistant.ask("How does refrigerant transport heat?", subsystem="acv")
    assert "heat transport" in result["answer"]
    assert len(result["answer"]) <= 1200
    assert len(result["answer_citation_ids"]) == 1
    assert "Reference:" not in result["answer"]


def test_glossary_no_appended_passages(assistant):
    result = assistant.ask("Define MAPE")
    assert "Mean Absolute Percentage Error" in result["answer"]
    assert "Reference:" not in result["answer"]
    assert result["answer_citation_ids"] == ["term:mape"]


def test_provider_failure_uses_focused_answer(assistant):
    def failing(*args):
        pytest.fail("Exact definitions must not call a provider")
    result = assistant.ask("What does DCSR mean?", selector=failing, consent=True)
    assert len(result["answer"]) < 350
    assert result["mode"] == "evidence_template"
    assert result["presentation"] == "verified_definition"


def test_no_truncated_negation_or_unsupported_definition():
    fact = {"id": "doc:test", "text": "# Header\n\n| Thing | — |", "evidence_type": "reference_document"}
    text, ids = local_excerpt("What is Thing?", [fact])
    assert "Expand Source" in text
    assert ids == ["doc:test"]
