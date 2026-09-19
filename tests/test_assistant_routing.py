"""Intent distinctions, clarification round trips and generated-output boundaries."""
import json

import pytest
from test_engineering_assistant import assistant


def forbidden(*args):
    pytest.fail("Clarification must not invoke a provider")


@pytest.mark.parametrize("question", ["Explain it", "why?", "What does it mean?", "Please explain the model", "How does this model work?", "What am I looking at?", "Why was this model selected?"])
def test_ambiguous_queries_clarify(assistant, question):
    result = assistant.ask(question, selector=forbidden, consent=True)
    assert result["status"] == "needs_clarification"
    assert result["clarification"]["options"]
    assert result["facts"] == []


def test_policy_is_not_batch_review(assistant):
    policy = assistant.ask("Explain the review policy")
    findings = assistant.ask("Which findings need review?")
    assert policy["routing"]["intent"] == "review_policy"
    assert findings["routing"]["intent"] == "review"
    assert not any(f["source"].startswith("decision:") for f in policy["facts"])
    assert any(f["source"].startswith("decision:") for f in findings["facts"])
    assert policy["answer"] != findings["answer"]
    assert not policy["explanation"]["sections"]
    assert "Cars are ordered" not in policy["answer"]
    assert assistant.ask("Explain review rules")["status"] == "answered"
    assert assistant.ask("Explain MAPE performance", subsystem="shm")["routing"]["intent"] == "evaluation"


def test_multistep_clarification(assistant):
    first = assistant.ask("Explain it")
    second = assistant.ask("Model walkthrough", previous_question=first["clarification"]["question"])
    assert second["status"] == "needs_clarification"
    third = assistant.ask("SHM please", previous_question=second["clarification"]["question"])
    assert third["status"] == "answered"
    assert third["routing"]["intent"] == "pipeline"
    assert third["routing"]["clarified"]
    assert third["scope"]["subsystems"] == ["shm"]
    assert "rainflow" in third["answer"]
    assert "Extra Trees" not in third["answer"]


def test_record_choice_and_current_scope_validation(assistant):
    first = assistant.ask("Explain this result", subsystem="shm")
    choice = first["clarification"]["options"][0]
    second = assistant.ask(choice["label"], subsystem="shm", previous_question="Explain this result")
    assert second["status"] == "answered"
    assert len(second["scope"]["file_ids"]) == 1
    assert "Recorded review reasons" in second["answer"]
    stale = assistant.ask(choice["label"], subsystem="rail", previous_question="Explain this result")
    assert stale["status"] == "needs_clarification"
    assert not stale["facts"]


def test_new_question_replaces_pending_clarification(assistant):
    answer = assistant.ask("Define MAPE", previous_question="How does this model work?")
    assert answer["routing"]["intent"] == "definition"
    assert answer["status"] == "answered"


def test_explicit_all_and_selected_file_need_no_clarification(assistant):
    assert assistant.ask("Explain all four model pipelines")["status"] == "answered"
    scoped = assistant.ask("How does this model work?", subsystem="shm", file_ids=["test01.csv"])
    assert scoped["status"] == "answered"
    assert assistant.ask("Explain ACV and SHM results", subsystem="shm")["status"] == "needs_clarification"


def test_generated_explanation_keeps_canonical_evidence(assistant):
    def generate(question, cards):
        assert "review policy" in question
        return {"paragraphs": [{"text": "A Normal classification may still require review.", "citation_ids": [cards[0]["id"]]}]}
    local = assistant.ask("Explain the review policy")
    result = assistant.ask("Explain the review policy", selector=generate, consent=True)
    assert result["mode"] == "grounded_llm"
    assert result["facts"] == local["facts"]
    assert "AI explanation" in result["answer"]
    assert result["generated_explanation"][0]["citation_ids"] == ["fact:0"]


@pytest.mark.parametrize("paragraph", [
    {"text": "A result", "citation_ids": ["forged"]},
    {"text": "There are 99999 failures", "citation_ids": ["fact:0"]},
    {"text": "Safe to dispatch", "citation_ids": ["fact:0"]},
    {"text": "Replace the component", "citation_ids": ["fact:0"]},
    {"text": "A result", "citation_ids": []},
    {"text": "A result", "citation_ids": ["fact:0"], "extra": "oops"},
])
def test_invalid_generation_falls_back(assistant, paragraph):
    result = assistant.ask("Explain review policy", selector=lambda *args: {"paragraphs": [paragraph]}, consent=True)
    assert result["mode"] == "evidence_template"
    assert "generated_explanation" not in result
    assert result["warnings"]
    assert "99999" not in json.dumps(result)
