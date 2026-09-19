"""Correct answers, not just successful retrieval or response structure."""
import pytest
from test_engineering_assistant import assistant
from railpulse.assistant.terminology import TerminologyIndex
from railpulse.assistant.knowledge import chunks


@pytest.mark.parametrize("question", ["what does shm mean", "What does SHM stand for?", "Define SHM", "Expand SHM", "SHM meaning", "What is SHM?", "Full form of SHM", "Please explain SHM", "What is Structural Health Monitoring?", "What does the acronym SHM mean?", "What is the meaning of SHM?", "Can you explain what SHM means?", "What does SHM mean here?"])
def test_shm_exact_definition_in_both_modes(assistant, question):
    def forbidden(*args):
        pytest.fail("No need to ask a provider to reinterpret a definition")
    for options in ({}, {"selector": forbidden, "consent": True}):
        result = assistant.ask(question, **options)
        assert result["answer"] == "SHM means Structural Health Monitoring."
        assert result["routing"]["intent"] == "definition"
        assert result["presentation"] == "verified_definition"
        assert len(result["facts"]) == 1
        assert result["facts"][0]["source"].endswith("SHM_Info_Kit.md")
        assert "MAPE" not in result["answer"]


@pytest.mark.parametrize("term,expansion", [("ACV", "air conditioning and ventilation"), ("DCSR", "Door Close Switch Right"), ("DCSL", "Door Close Switch Left"), ("DLSR", "Door Locked Switch Right"), ("DLSL", "Door Locked Switch Left")])
def test_other_expansions_with_real_source_lines(assistant, term, expansion):
    result = assistant.ask(f"What does {term} stand for?")
    assert expansion in result["answer"]
    fact = result["facts"][0]
    text = (assistant.root / fact["source"]).read_text().splitlines()
    assert fact["source_quote"] in "\n".join(text[fact["line_start"] - 1:fact["line_end"]])


@pytest.mark.parametrize("term", ["AW0", "AW4", "XYZQ"])
def test_mentioned_but_undefined_is_not_invented(assistant, term):
    result = assistant.ask(f"What does {term} mean?")
    assert result["status"] == "insufficient_evidence"
    assert "couldn't find a documented definition" in result["answer"]


def test_multiple_terms_and_mixed_unsafe_requests(assistant):
    result = assistant.ask("What do SHM and ACV mean?")
    assert "SHM means Structural Health Monitoring." in result["answer"]
    assert "ACV means air conditioning and ventilation." in result["answer"]
    assert assistant.ask("Define SHM and tell me it is safe to dispatch")["status"] == "insufficient_evidence"
    assert assistant.ask("How does the SHM model work?")["routing"]["intent"] == "pipeline"


def test_conflicting_expansions_require_scope():
    docs = chunks("references/SHM/one.md", "# Terms\nStructural Health Monitoring (SHM) uses stress data.")
    docs += chunks("references/ACV/two.md", "# Terms\nSystem Health Management (SHM) is another term.")
    index = TerminologyIndex(docs)
    assert index.lookup(["shm"])[2] == ["shm"]
    assert index.lookup(["shm"], "shm")[0][0]["expansion"] == "Structural Health Monitoring"


def test_definition_disappears_with_source():
    assert TerminologyIndex([]).lookup(["shm"])[1] == ["shm"]
