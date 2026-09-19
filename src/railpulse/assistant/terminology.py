"""Source-backed terminology, resolved before approximate passage retrieval.

Conservative pattern extraction, not an LLM guess: expansions must spell the
acronym's initials. Table definitions retain their exact source wording.
"""
import re


def normal(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def initials(text):
    return "".join(w[0] for w in normal(text).split() if w not in {"and", "of", "the"})


def definition_targets(question):
    q = question.strip().rstrip("?!.").strip()
    q = re.sub(r"^(?:please|can you|could you)\s+", "", q, flags=re.I)
    q = re.sub(r"\s+(?:here|in this context|in railpulse)$", "", q, flags=re.I)
    patterns = (
        r"(?:what is|what's) (?:the )?(?:meaning|definition|full (?:form|name)|expansion) of (.+)",
        r"(?:explain|tell me) what (.+?) (?:means|stands for)",
        r"what (?:does|do) (.+?) (?:mean|stand for)",
        r"(?:what is|what are|what's|define|explain|expand) (.+)",
        r"(?:meaning|definition|full (?:form|name)|expansion) of (.+)",
        r"(.+?) (?:meaning|definition|full form)",
    )
    target = next((m[1] for p in patterns if (m := re.fullmatch(p, q, re.I))), None)
    if target is None:
        return []
    target = re.sub(r"^(?:the (?:acronym|abbreviation|term)\s+|the\s+)", "", target, flags=re.I)
    parts = re.split(r"\s+(?:and|or)\s+|\s*[,/]\s*", target)
    # Complex/mixed operational questions must continue through normal guards.
    if len(parts) > 4 or any(len(normal(p).split()) > 6 for p in parts):
        return []
    targets = [normal(p) for p in parts if normal(p)]
    if any(t in {"it", "this", "that", "model", "the model", "evidence", "results", "warnings", "quality"} for t in targets):
        return []
    return targets


class TerminologyIndex:
    def __init__(self, documents):
        self.entries = {}
        for doc in documents:
            if not doc["source"].startswith("references/"):
                continue
            text = doc["text"]
            # Both documented forms: Structural Health Monitoring (SHM), and
            # ACV (air conditioning and ventilation). Headings aren't discarded.
            patterns = (
                r"\b([A-Z][a-z]+(?:[ -][A-Z][a-z]+){1,7})\s*\(([A-Z][A-Za-z0-9]{1,7})\)",
                r"\b([A-Z][A-Za-z0-9]{1,7})\s*\(([A-Za-z][A-Za-z -]{3,100})\)",
            )
            for reverse, pattern in enumerate(patterns):
                for match in re.finditer(pattern, text):
                    expansion, acronym = (match[2], match[1]) if reverse else (match[1], match[2])
                    if initials(expansion) != acronym.lower():
                        continue
                    self.add(acronym, expansion, f"{acronym} means {expansion}.", doc, match.start(), match.group())
            for match in re.finditer(r"(?m)^\|\s*([A-Z]{2,8})\s*\|\s*([^|\n]+)\|", text):
                acronym, definition = match[1], match[2].strip()
                expansion = definition.split(".")[0]
                if initials(expansion) == acronym.lower():
                    self.add(acronym, expansion, f"{acronym}: {definition}", doc, match.start(), match.group())

    def add(self, acronym, expansion, answer, doc, offset, quote):
        line = doc["line_start"] + doc["text"][:offset].count("\n")
        entry = {"id": f"term:source-{acronym.lower()}:{doc['sha256'][:12]}:{line}",
                 "text": answer, "source": doc["source"], "section": doc["section"],
                 "sha256": doc["sha256"], "line_start": line,
                 "line_end": line + quote.count("\n"), "source_quote": quote,
                 "evidence_type": "verified_definition", "acronym": acronym,
                 "expansion": expansion, "subsystem": doc.get("subsystem"), "value": None}
        for key in {normal(acronym), normal(expansion)}:
            existing = self.entries.setdefault(key, [])
            if not any(e["text"] == answer for e in existing):
                existing.append(entry)

    def lookup(self, targets, subsystem=None):
        found, missing, ambiguous = [], [], []
        for target in targets:
            matches = self.entries.get(target, [])
            if subsystem:
                matches = [m for m in matches if m["subsystem"] in {None, subsystem}]
            if not matches:
                missing.append(target)
            elif len({normal(m["expansion"]) for m in matches}) > 1:
                ambiguous.append(target)
            else:
                found.append(matches[0].copy())
        return found, missing, ambiguous
