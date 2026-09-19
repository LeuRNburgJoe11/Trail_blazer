"""Validate generated presentation, never replace canonical evidence.

Citation/numeric checks are defensive, not a proof of semantic entailment.
Generated prose is explicitly labelled; original evidence remains inspectable.
"""
import re


def validate_explanation(value, cards):
    if not isinstance(value, dict) or set(value) != {"paragraphs"}:
        raise ValueError("Invalid explanation")
    paragraphs = value["paragraphs"]
    if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 4:
        raise ValueError("Invalid paragraph count")
    sources = {c["id"]: c["text"] for c in cards}
    result = []
    for p in paragraphs:
        if not isinstance(p, dict) or set(p) != {"text", "citation_ids"}:
            raise ValueError("Invalid paragraph")
        text, ids = p["text"], p["citation_ids"]
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Invalid text")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 4 or any(not isinstance(i, str) or i not in sources for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("Unknown citation")
        evidence = " ".join(sources[i] for i in ids)
        numbers = lambda s: set(re.findall(r"(?<![\w])\d+(?:\.\d+)?%?", s))
        if not numbers(text) <= numbers(evidence):
            raise ValueError("Unsupported number")
        # Operational authority is outside this assistant's remit, including
        # when a provider follows an instruction embedded in the query.
        if re.search(r"\b(dispatch|replace|repair|shut down|safe to|confirmed|definitely|guarantee|deadline|remaining life|remaining useful life)\b", text, re.I):
            raise ValueError("Operational claim requires local boundary response")
        result.append({"text": text, "citation_ids": ids})
    return result
