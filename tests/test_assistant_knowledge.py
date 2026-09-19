"""Offline retrieval regression set, plus provenance and isolation checks."""
import hashlib

import pytest
from test_engineering_assistant import assistant
from railpulse.assistant.knowledge import KnowledgeIndex, load_knowledge, chunks


@pytest.mark.parametrize("question,domain,source,section", [
    ("What does DCSR mean?", "door", "Door Data Headers.md", "Door Parameter List"),
    ("What does DLSL stand for?", "door", "Door Data Headers.md", "Door Parameter List"),
    ("Explain the S-N curve", "shm", "SHM_Info_Kit.md", "S-N Curve"),
    ("How does Miner sum fatigue from stress cycles?", "shm", "SHM_Info_Kit.md", "Miner"),
    ("Why do ripples form on the rail?", "rail", "Rail_Corrugation_Info_Kit.md", "Business Background"),
    ("How does refrigerant transport heat?", "acv", "ACV_Subsystem_Info_Kit.md", "Business background"),
    ("How are axle box positions mapped to Side I?", "rail", "Rail_Corrugation_Info_Kit.md", "Data File Format"),
])
def test_retrieval_top_hit(assistant, question, domain, source, section):
    hits = assistant.search_reference_docs(question, domain)
    assert hits and hits[0]["source"].endswith(source)
    assert section in hits[0]["section"]
    assert all(h["subsystem"] in {None, domain} for h in hits)
    assert assistant.ask(question, subsystem=domain)["status"] == "answered"


def test_all_user_documents_indexed_and_exact_lines(assistant):
    sources = {d["source"] for d in assistant.documents}
    assert len([s for s in sources if s.startswith("references/") and (s.endswith("Info_Kit.md") or s.endswith("Headers.md"))]) == 5
    for hit in assistant.search_reference_docs("DCSR", "door"):
        content = (assistant.root / hit["source"]).read_text()
        assert hit["sha256"] == hashlib.sha256(content.encode()).hexdigest()
        assert hit["text"] in "\n".join(content.splitlines()[hit["line_start"] - 1:hit["line_end"]])


def test_unknown_and_cross_domain_abstain(assistant):
    assert assistant.search_reference_docs("banana quantum unicorn") == []
    assert assistant.search_reference_docs("DCSR", "shm") == []
    assert assistant.ask("Explain it")["status"] == "needs_clarification"


def test_long_content_not_dropped():
    text = "# Physics\n" + "stress " * 1600
    result = chunks("references/SHM/test.md", text)
    assert len(result) > 2
    assert all(len(c["text"]) <= 2400 for c in result)
    assert sum(c["text"].count("stress") for c in result) >= 1595


def test_cache_updates_deletions_and_no_arbitrary_paths(tmp_path):
    path = tmp_path / "kit.md"
    path.write_text("# Science\nA measured stress cycle contributes fatigue damage to a material component under alternating loads.")
    first, _ = load_knowledge(tmp_path, ("kit.md",))
    path.write_text("# Science\nRefrigerant transports heat through a vapour compression cycle to provide cooling in the passenger compartment.")
    second, _ = load_knowledge(tmp_path, ("kit.md",))
    assert first is not second
    path.unlink()
    empty, warnings = load_knowledge(tmp_path, ("kit.md",))
    assert empty.documents == [] and warnings
    outside = tmp_path / "link.md"
    outside.symlink_to("/etc/hosts")
    denied, warnings = load_knowledge(tmp_path, ("link.md",))
    assert denied.documents == [] and warnings


def test_search_results_are_copies(assistant):
    hit = assistant.search_reference_docs("DCSR", "door")[0]
    hit["text"] = "poison"
    assert assistant.search_reference_docs("DCSR", "door")[0]["text"] != "poison"


def test_provider_receives_cited_reference_and_caveat_not_notes(assistant):
    captured = []
    def selector(question, cards):
        captured.extend(cards)
        return [cards[0]["id"]]
    result = assistant.ask("Explain the S-N curve", subsystem="shm", selector=selector, consent=True, engineer_context="PRIVATE-NOTE")
    assert result["mode"] == "grounded_llm"
    assert captured[0]["id"].startswith("doc:")
    assert "REFERENCE CAVEAT" in captured[0]["text"]
    assert all("PRIVATE-NOTE" not in c["text"] for c in captured)
    assert result["knowledge"]["local_only"]


def test_theory_never_overrides_operational_boundary(assistant):
    def forbidden(*args):
        pytest.fail("Must not call provider for operational authority")
    result = assistant.ask("Use Miner's rule to tell me when will this fail", selector=forbidden, consent=True)
    assert result["status"] == "insufficient_evidence"
    theory = assistant.ask("Explain Miner's rule", subsystem="shm")
    assert any("not an approved threshold" in w for w in theory["warnings"])


def test_empty_index_and_invalid_scope():
    assert KnowledgeIndex([]).search("stress") == []
    with pytest.raises(ValueError):
        KnowledgeIndex([]).search("stress", "other")
