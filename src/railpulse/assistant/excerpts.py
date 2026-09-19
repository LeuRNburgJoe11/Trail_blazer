"""Small, deterministic extracts for keyless answers; never invent a summary."""
import re
from .knowledge import words, expand
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


def plain(text):
    # Formatting only: do not rewrite units, equations, numbers or negations.
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text).replace("`", "").replace("**", "").strip()


def local_excerpt(question, facts):
    terms = [f for f in facts if f["id"].startswith("term:")]
    if terms:
        return "\n\n".join(f["text"] for f in terms[:2]), [f["id"] for f in terms[:2]]
    docs = [f for f in facts if f.get("evidence_type") == "reference_document"]
    if not docs:
        return None
    query = set(words(question)) - set(ENGLISH_STOP_WORDS) - {"mean", "means", "explain", "define", "stand", "does", "please"}
    # An exact table key beats a whole table containing the same abbreviation.
    rows = []
    for doc in docs:
        for line in doc["text"].splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [plain(c) for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            if len(cells) != 2 or not cells[0]:
                continue
            key = set(words(cells[0]))
            if key and key <= query and cells[1] not in {"", "—", "-"}:
                item = (f"{cells[0]}: {cells[1]}", doc["id"])
                if item[0] not in {r[0] for r in rows}:
                    rows.append(item)
    if rows:
        return "\n\n".join(r[0] for r in rows[:2]), list(dict.fromkeys(r[1] for r in rows[:2]))
    # One top-ranked passage, one best complete paragraph. No JSON, tables,
    # headings, or code dumps in the conversational answer.
    doc = docs[0]
    expanded = set(words(expand(question))) - set(ENGLISH_STOP_WORDS)
    candidates = []
    fenced = False
    clean_lines = []
    for line in doc["text"].splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            clean_lines.append("")
            continue
        if fenced or line.lstrip().startswith(("#", "|", "![", "{", "}", "$$")):
            clean_lines.append("")
        else:
            clean_lines.append(line)
    for number, block in enumerate(re.split(r"\n\s*\n", "\n".join(clean_lines))):
        paragraph = plain(" ".join(block.split()))
        if not 40 <= len(paragraph) <= 1200:
            continue
        tokens = set(words(paragraph))
        score = 3 * len(query & tokens) + len(expanded & tokens)
        if score:
            candidates.append((score, -number, paragraph))
    if not candidates:
        return "The closest source contains a table or formula rather than a short explanation. Expand Source evidence & structured details to inspect it.", [doc["id"]]
    return max(candidates)[2], [doc["id"]]
