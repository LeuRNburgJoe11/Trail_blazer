"""Local, read-only hybrid knowledge retrieval; no downloads or model execution.

TF-IDF + latent semantic analysis (LSA), not pretrained neural embeddings.
Only allowlisted documentation is cached, never session records or credentials.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import re

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.preprocessing import normalize

VERSION = "hybrid-tfidf-lsa-v1"
ALIASES = {
    "dcsr": "door close switch right", "dcsl": "door close switch left",
    "dlsr": "door locked switch right", "dlsl": "door locked switch left",
    "back emf": "back electromotive force", "sn curve": "s n curve stress life fatigue amplitude",
    "s n curve": "stress life fatigue amplitude", "miner": "linear cumulative fatigue damage cycles",
    "wavy wear": "rail corrugation periodic wavelength vibration",
    "ripples": "rail corrugation periodic wavelength", "refrigerant": "cooling vapour compression leakage acv",
    "air conditioning": "acv cooling ventilation", "stress reversals": "rainflow stress cycles",
    "teeth": "speed sensor rotational wheel transitions", "millivolts": "motor voltage 10mv",
}
CAUTIONS = {
    "shm": "Theoretical Miner's-rule D >= 1 is not an approved threshold for the fitted recording-level proxy. Do not infer lifetime or maintenance action. AW0/AW4 are named but not defined in this kit.",
    "rail": "The kit's scoring prose has inconsistent approximate training counts and an illustrative all-Normal F1 of 1.0. Use Section 2.2 or verified labels for counts; compute actual class F1, not that illustrative value.",
    "door": "The header glossary includes identifier fields beyond the released 17-column stream; do not change the loader contract from this glossary. Door's phrase 'other subsystems plain accuracy' is not their actual scoring contract.",
    "acv": "Background industry percentages are claims in the supplied kit, not measured results or probabilities for this replay. Parameter availability differs by file.",
}


def words(text):
    return re.findall(r"[a-z0-9]+", text.casefold())


def expand(text):
    normal = " ".join(words(text))
    return normal + " " + " ".join(value for key, value in ALIASES.items()
                                      if re.search(r"\b" + re.escape(key) + r"\b", normal))


def chunks(relative, content):
    """Heading-aware chunks with exact source line ranges; never drop long blocks."""
    domain = next((d for d in CAUTIONS if d in relative.lower()), None)
    if "references/Door/" in relative:
        domain = "door"
    sha = hashlib.sha256(content.encode()).hexdigest()
    lines = content.splitlines()
    heading, pending, start = [], [], 1
    result = []

    def emit(end):
        if not pending or not "\n".join(pending).strip():
            return
        text = "\n".join(pending).strip()
        if not any(line.strip() and not line.startswith("#") for line in pending):
            return
        result.append({"id": f"doc:{sha[:16]}:{start}:{len(result)}", "text": text,
                       "source": relative, "section": " > ".join(heading) or "Overview",
                       "sha256": sha, "line_start": start, "line_end": end,
                       "subsystem": domain, "evidence_type": "reference_document",
                       "caveat": CAUTIONS.get(domain, "Implementation documentation, not live operational evidence.")})

    for number, line in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+)", line)
        if match:
            emit(number - 1)
            pending = []
            level = len(match[1])
            heading = heading[:level - 1] + [match[2]]
            start = number
        if pending and sum(len(p) + 1 for p in pending) + len(line) > 2400:
            emit(number - 1)
            pending, start = [], number
        # Even an unusually long single line is kept, in bounded pieces.
        for offset in range(0, max(1, len(line)), 2400):
            part = line[offset:offset + 2400]
            if offset:
                emit(number)
                pending, start = [], number
            pending.append(part)
    emit(len(lines))
    return result


class KnowledgeIndex:
    def __init__(self, sources):
        self.documents = [chunk for relative, content in sources for chunk in chunks(relative, content)]
        self.vectorizer = self.svd = None
        if not self.documents:
            return
        texts = [" ".join(words(d["text"])) for d in self.documents]
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
        try:
            self.matrix = self.vectorizer.fit_transform(texts)
        except ValueError:
            self.vectorizer = None
            return
        dimensions = min(32, self.matrix.shape[0] - 1, self.matrix.shape[1] - 1)
        if dimensions >= 2:
            self.svd = TruncatedSVD(n_components=dimensions, random_state=42)
            self.latent = normalize(self.svd.fit_transform(self.matrix))

    def search(self, question, subsystem=None, limit=4):
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
            raise ValueError("Question must contain 1–2000 characters")
        if subsystem not in {None, "door", "acv", "rail", "shm"} or not 1 <= limit <= 8:
            raise ValueError("Invalid knowledge scope")
        if self.vectorizer is None:
            return []
        expanded = expand(question)
        query = self.vectorizer.transform([expanded])
        if query.nnz == 0:
            return []
        lexical = (self.matrix @ query.T).toarray().ravel()
        semantic = (self.latent @ normalize(self.svd.transform(query)).T).ravel() if self.svd else lexical
        # Semantic similarity is a ranking aid, never a truth/confidence score.
        scores = .7 * lexical + .3 * np.maximum(semantic, 0)
        anchors = set(words(expanded)) - set(ENGLISH_STOP_WORDS) - {"explain", "describe", "mean", "means", "please", "document", "documentation", "kit", "model"}
        results = []
        for i in sorted(range(len(scores)), key=lambda i: (-scores[i], self.documents[i]["id"])):
            d = self.documents[i]
            body = re.sub(r"(?m)^#.*$", "", d["text"])
            if len(words(body)) < 10:
                continue
            if subsystem and d["subsystem"] not in {None, subsystem}:
                continue
            overlap = anchors & set(words(d["text"] + " " + d["section"]))
            if not overlap or lexical[i] < .055 or scores[i] < .12:
                continue
            copy = deepcopy(d)
            copy["retrieval"] = {"method": VERSION, "score": round(float(scores[i]), 5),
                                 "lexical_score": round(float(lexical[i]), 5), "meaning": "relevance, not confidence"}
            results.append(copy)
            if len(results) == limit:
                break
        return results


@lru_cache(maxsize=4)
def cached_index(sources):
    # Content (not mtime) is the cache key: edited/deleted files cannot leave stale chunks.
    return KnowledgeIndex(sources)


def load_knowledge(root, allowlist):
    sources, warnings = [], []
    for relative in allowlist:
        path = root / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 2_000_000:
            warnings.append(f"Knowledge source unavailable or disallowed: {relative}")
            continue
        try:
            sources.append((relative, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError):
            warnings.append(f"Knowledge source unreadable: {relative}")
    return cached_index(tuple(sources)), warnings
