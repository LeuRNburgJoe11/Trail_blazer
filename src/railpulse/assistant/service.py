"""Deterministic scoped evidence retrieval with optional cited explanations.

Canonical facts remain local and unchanged. Generated presentation is labelled
and validated for citation membership, numeric support and bounded authority.
These checks do not prove semantic entailment.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from .explanations import PIPELINES, GLOSSARY, definition_facts, profile, enrich
from .routing import intent, TITLES, REVIEW_POLICY
from .generation import validate_explanation
from .knowledge import load_knowledge, VERSION as KNOWLEDGE_VERSION
from .excerpts import local_excerpt
from .terminology import TerminologyIndex, definition_targets

ROOT = Path(__file__).resolve().parents[3]
SUBSYSTEMS = ("door", "acv", "rail", "shm")
DOCUMENTS = (
    "docs/ARCHITECTURE_AUDIT.md", "docs/SHM.md",
    "references/Door/Door_Subsystem_Info_Kit.md",
    "references/Door/Door Data Headers.md",
    "references/ACV/ACV_Subsystem_Info_Kit.md",
    "references/Rail_Corrugation/Rail_Corrugation_Info_Kit.md",
    "references/SHM/SHM_Info_Kit.md",
    "references/Problem_Statement_3_Specifications.md",
    "docs/ENGINEERING_ASSISTANT.md",
)
LIMIT = ("Review support only: no safety clearance, confirmed root cause, calibrated "
         "fault probability, maintenance deadline or remaining-life estimate. "
         "Recordings are not linked to a common asset or journey. Validation is not held-out test performance.")
METRICS = {
    "door": "Door: IoU-weighted F1 evaluates operation timing and Normal/Abnormal resistance labels.",
    "acv": "ACV: linear rank-decay = (n - rank + 1) / n, with one-based rank and complete native-car coverage. Ranking scores are not leak probabilities.",
    "rail": "Rail: macro F1 is the unweighted mean of F1 for Normal, Side I and Side II, not accuracy.",
    "shm": "SHM: score = max(0, 1 - mean(abs(truth - prediction) / abs(truth))). MAPE is fractional; no rule for zero targets is assumed. Damage is per recording, not lifetime consumed.",
}
SUGGESTIONS = ["Summarise this batch", "How does this model work?", "What does macro F1 mean?",
               "Prepare an inspection briefing", "Show quality warnings", "Explain validation metrics",
               "Why was this model selected?", "What information is missing for remaining life?"]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def tokens(text):
    stop = {"the", "a", "an", "is", "what", "how", "of", "for", "in", "to", "this", "and", "i", "it", "my", "me"}
    return set(re.findall(r"[a-z0-9]+", text.lower())) - stop


class EvidenceAssistant:
    """Caller supplies ONLY authorised session records and a trusted run directory.

    No global cache, persistent conversation, filesystem tool or user-supplied
    retrieval path. A future HTTP adapter must authenticate before constructing it.
    """

    def __init__(self, records, *, run_directory, bundle_sha256, failures=None, root=ROOT):
        self.root = Path(root).resolve()
        self.run = Path(run_directory).resolve()
        self.bundle_hash = bundle_sha256
        self.records = deepcopy(records)
        self.failures = deepcopy(failures or {})
        self.validation = {}
        self.source_warnings = []
        for record in self.records:
            if record["subsystem"] not in SUBSYSTEMS or record["provenance"]["bundle_sha256"] != bundle_sha256:
                raise ValueError("Record does not belong to the selected bundle")
        manifest = self.run / "models/bundle.json"
        if not manifest.is_file() or hashlib.sha256(manifest.read_bytes()).hexdigest() != bundle_sha256:
            if self.records:
                raise ValueError("Selected bundle is missing or has changed")
            self.source_warnings.append("No matching bundle: validation evidence unavailable.")
        else:
            report = self.run / "run_summary.json"
            if report.is_file():
                self.validation = json.loads(report.read_text()).get("validation", {})
        self.knowledge, knowledge_warnings = load_knowledge(self.root, DOCUMENTS)
        self.documents = deepcopy(self.knowledge.documents)
        self.terminology = TerminologyIndex(self.documents)
        self.source_warnings.extend(knowledge_warnings)
        self.corpus_hash = digest(self.documents)
        self.snapshot = digest({"records": self.records, "failures": self.failures,
                                "bundle": bundle_sha256, "validation": self.validation,
                                "corpus": self.corpus_hash})

    def search_reference_docs(self, question, subsystem=None):
        return self.knowledge.search(question, subsystem)

    def ask(self, question, *, subsystem=None, file_ids=None, decision_id=None, selector=None, consent=False,
            engineer_instructions="", engineer_context="", engineer_author="", audience="plain", detail="concise", focus="auto",
            previous_question=None):
        settings = profile(engineer_instructions, engineer_context, engineer_author, audience, detail, focus)
        requested_domains = [d for d in SUBSYSTEMS if re.search(rf"\b{d}\b", engineer_instructions.lower())]
        if subsystem is None and len(requested_domains) == 1:
            subsystem = requested_domains[0]
            settings["applied_hints"].append(f"Narrowed to {subsystem.upper()}")
        # Focus hints refine a generic briefing, never replace a specific query,
        # broaden scope or weaken a refusal. Notes never enter model context.
        routed = question
        if previous_question is not None:
            # Recompute options from authorised current scope, never trust client
            # supplied evidence or a stale conversation's scope.
            previous = self._ask(previous_question, subsystem=subsystem, file_ids=file_ids, decision_id=decision_id)
            options = previous.get("clarification", {}).get("options", [])
            reply = re.sub(r"\b(?:please|thanks|thank you)\b", "", question.casefold()).strip().rstrip(".!?").strip()
            match = next((o for o in options if reply in
                          {o["label"].casefold().rstrip(".!?"), o["question"].casefold().rstrip(".!?")}), None)
            if match:
                routed = match["question"]
        if isinstance(question, str) and question.strip().lower() in {"summarise this batch", "summarize this batch", "prepare an inspection briefing", "prepare a handover"}:
            routed = {"quality": "Show quality warnings", "evaluation": "Explain validation metrics",
                      "review": "Prepare an inspection briefing"}.get(settings["focus"], question)
        result = self._ask(routed, subsystem=subsystem, file_ids=file_ids, decision_id=decision_id,
                           selector=selector, consent=consent)
        result["routing"] = {"intent": "definition" if any(f["id"].startswith("term:") for f in result["facts"]) else intent(routed),
                             "question": routed, "original_question": question,
                             "clarified": routed != question and previous_question is not None}
        result = enrich(result, routed, settings)
        if subsystem and requested_domains and subsystem not in requested_domains:
            result["warnings"].append("Instruction subsystem conflicts with the selected scope. The selected scope was retained; change it explicitly to investigate another subsystem.")
        result["provenance"]["engineer_input_sha256"] = digest(settings)
        result["provenance"]["explanation_templates_sha256"] = digest({"pipelines": PIPELINES, "glossary": GLOSSARY})
        result["provenance"]["policy_version"] = "assistant-policy-v2"
        result["provenance"]["retrieval_version"] = KNOWLEDGE_VERSION
        result["knowledge"] = {"method": KNOWLEDGE_VERSION, "documents": len({d["source"] for d in self.documents}),
                               "chunks": len(self.documents), "local_only": True}
        result["schema_version"] = 2
        sections = result["explanation"]["sections"]
        if sections:
            extra = [s for s in sections if s["text"] not in result["answer"]]
            if extra:
                result["answer"] += "\n\n" + "\n\n".join(s["title"] + ":\n" + s["text"] for s in extra)
        return result

    def _ask(self, question, *, subsystem=None, file_ids=None, decision_id=None, selector=None, consent=False):
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise ValueError("Question must contain 1–2000 characters")
        if subsystem is not None and subsystem not in SUBSYSTEMS:
            raise ValueError("Unknown subsystem")
        rows = [r for r in self.records if subsystem is None or r["subsystem"] == subsystem]
        if file_ids:
            if not set(file_ids) <= {r["file_id"] for r in rows}:
                raise ValueError("File is outside this session/subsystem")
            rows = [r for r in rows if r["file_id"] in file_ids]
        if decision_id:
            rows = [r for r in rows if r["decision_id"] == decision_id]
            if not rows:
                raise ValueError("Finding is outside the selected scope")
        q = question.lower()
        # Explicit names in the question narrow context; unknown names never fall
        # through to a batch answer or another session's similarly named file.
        mentioned = re.findall(r"[\w.-]+\.(?:csv|xlsx)\b", question, re.I)
        if mentioned:
            available = {r["file_id"].lower(): r["file_id"] for r in rows}
            if any(name.lower() not in available for name in mentioned):
                return self._response([], "needs_clarification", "Select files available in this session.", subsystem, rows)
            rows = [r for r in rows if r["file_id"].lower() in {n.lower() for n in mentioned}]
        named = [s for s in SUBSYSTEMS if re.search(rf"\b{s}\b", q)]
        if named and subsystem and any(d != subsystem for d in named):
            return self._response([], "needs_clarification", "The question and selected subsystem differ. Change the scope.", subsystem, rows)
        if named:
            rows = [r for r in rows if r["subsystem"] in named]
        domains = named or ([subsystem] if subsystem else list(SUBSYSTEMS))
        if not named and not subsystem and (file_ids or decision_id or mentioned):
            domains = sorted({r["subsystem"] for r in rows})
        facts = []

        def add(text, source, value=None):
            facts.append({"id": f"fact:{len(facts)}", "text": text, "source": source, "value": value})

        unsafe = any(re.search(r"\b" + re.escape(term) + r"\b", q) for term in ("remaining life", "remaining useful", "rul", "safe to", "safety", "deadline", "dispatch", "root cause", "failure probability", "lifetime", "when will", "forecast", "tomorrow", "next month"))
        definitions = definition_facts(question)
        if re.search(r"\b(?:performance|evaluated|results|prediction)\b", q):
            definitions = []
        definition_only = bool(re.fullmatch(r"\s*(?:define (?:rul|remaining useful life|remaining life)|what does (?:rul|remaining useful life|remaining life) mean)\??\s*", q))
        targets = definition_targets(question)
        if targets and not unsafe and not definitions:
            entries, missing, ambiguous = self.terminology.lookup(targets, domains[0] if len(domains) == 1 else None)
            if ambiguous:
                return self._clarify(question, "The documentation gives multiple expansions for this term. Please specify the subsystem or full name.", subsystem, rows, [])
            if entries and not missing:
                response = self._response(entries, "answered", "", subsystem, rows)
                response["answer"] = "\n\n".join(e["text"] for e in entries)
                response["answer_citation_ids"] = [e["id"] for e in entries]
                response["presentation"] = "verified_definition"
                # Exact documented definitions are authoritative for this lookup;
                # a configured provider must not reinterpret their expansion.
                return response
            if missing and all(re.fullmatch(r"[a-z][a-z0-9]{1,7}", t) for t in targets):
                response = self._response(entries, "insufficient_evidence", "", subsystem, rows)
                response["answer"] = ("\n\n".join(e["text"] for e in entries) + "\n\n" if entries else "") + "I couldn't find a documented definition for " + ", ".join(t.upper() for t in missing) + ". Please provide the expansion or clarify which term you mean."
                return response
        if definitions and (not unsafe or definition_only):
            # Definitions remain reviewed templates, supplemented with source passages.
            references = self.search_reference_docs(question, domains[0] if len(domains) == 1 else None)[:2] if not unsafe else []
            response = self._response(definitions + references, "answered", "Terminology and supporting documentation:", subsystem, rows)
            return self._with_provider(response, question, selector, consent) if not unsafe else response
        if unsafe:
            add(LIMIT, "assistant-policy-v1")
            add("Needed: verified asset linkage, longitudinal exposure and outcomes, physical units, material properties and engineering-approved limits. Filenames do not establish chronology.", "assistant-policy-v1")
            return self._response(facts, "insufficient_evidence", "The available data cannot establish that conclusion.", subsystem, rows)
        route = intent(question)
        if route == "help":
            return self._clarify(question, "I can explain models and metrics, describe review policy, or inspect recorded findings. Which would help?", subsystem, rows,
                                 [("Model walkthrough", "How does this model work?"), ("Review findings", "Which findings need review?"),
                                  ("Review policy", "Explain the review policy"), ("Metrics", "Explain validation metrics")])
        if route == "pipeline" and len(domains) > 1 and not re.search(r"\b(all|four|4|overview)\b", q):
            return self._clarify(question, "Which subsystem's model should I explain? You can also ask for an overview of all four.", subsystem, rows,
                                 [(d.upper(), f"How does the {d.upper()} model work?") for d in domains] +
                                 [("All four", "Explain all four model pipelines")])
        if route == "evaluation" and len(domains) > 1 and re.search(r"\b(?:this model|model selected|model chosen)\b", q):
            return self._clarify(question, "Which subsystem's model selection should I explain? Their evaluation protocols differ.", subsystem, rows,
                                 [(d.upper(), f"Explain {d.upper()} model selection and validation") for d in domains])
        if route == "record" and len({(r["subsystem"], r["file_id"]) for r in rows}) != 1:
            return self._clarify(question, "Which recording do you mean? Select a file above, or choose one below. I won't infer a recording from batch order.", subsystem, rows,
                                 [(f"{d.upper()} / {f}", f"Explain this result for {d.upper()} {f}")
                                  for d, f in sorted({(r["subsystem"], r["file_id"]) for r in rows})])
        if route == "review_policy":
            add(REVIEW_POLICY, "src/railpulse/core/decisions.py#decision_records")
        elif route == "pipeline":
            for domain in domains:
                add(f"{domain.upper()}: {PIPELINES[domain]['steps']}", PIPELINES[domain]["source"])
                add(PIPELINES[domain]["meaning"], PIPELINES[domain]["source"])
        elif route == "official_score":
            add("Organiser-held test labels are unavailable. Overall = sum / 4; Average = sum / attempted. An unknown attempted score leaves aggregates unknown; an explicit failed attempt is zero. Different validation protocols must not be presented as official scores.", "assistant-policy-v1")
        elif route == "evaluation":
            for domain in domains:
                add(METRICS[domain], f"metric-contract:{domain}")
                if domain in self.validation:
                    value = self.validation[domain]
                    add(f"{domain.upper()} stored validation: {json.dumps(value, sort_keys=True)}", f"run_summary.json#/validation/{domain}", value)
            # SHM's linked report is loaded only if its recorded hash matches.
            shm = self.validation.get("shm", {})
            if "shm" in domains and shm.get("report"):
                path = (self.root / shm["report"]).resolve()
                if path.is_relative_to(self.root / "outputs") and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == shm.get("report_sha256"):
                    report = json.loads(path.read_text())
                    value = {key: report.get(key) for key in ("selected_model", "nested_evaluation", "validation", "groups_supplied", "selection_mape")}
                    add(f"SHM linked validation (hash verified): {json.dumps(value, sort_keys=True)}. Repeated folds contain 64 unique recordings, not 128 independent examples.", shm["report"], value)
        elif route in {"summary", "quality", "review", "briefing", "record", "compare"}:
            if "compare" in q and len({(r["subsystem"], r["file_id"]) for r in rows}) != 2:
                return self._response([], "needs_clarification", "Select exactly two recordings to compare; no common asset identity is assumed.", subsystem, rows)
            if "compare" in q and len({r["subsystem"] for r in rows}) != 1:
                return self._response([], "needs_clarification", "Compare recordings within one subsystem; outputs have different meanings and units.", subsystem, rows)
            if not rows:
                add("No analysed recordings in the selected scope. Upload and analyse data first; absence of findings does not establish healthy equipment.", "session")
            else:
                counts = Counter(r["subsystem"] for r in rows)
                value = {"recordings": len({(r["subsystem"], r["file_id"]) for r in rows}), "findings": len(rows),
                         "review_required": sum(bool(r["review_required"]) for r in rows), "findings_by_subsystem": dict(counts)}
                add(f"Selected-session coverage: {json.dumps(value)}. Findings are not unique assets or faults.", "session", value)
                candidates = sorted(rows, key=lambda r: (-r["review_priority"], r["decision_id"]))
                if route == "quality":
                    candidates = [r for r in candidates if r["warnings"] or r["quality"] != "passed"]
                    if not candidates:
                        add("No recorded quality warnings in this scope; this is not proof of sensor validity or model applicability.", "session")
                elif route in {"review", "briefing"}:
                    candidates = [r for r in candidates if r["review_required"]]
                    add(f"{len(candidates)} findings require review under the advisory queue policy. Human review is required before using this briefing operationally.", "session")
                for r in candidates[:8]:
                    add(f"{r['subsystem'].upper()} / {r['file_id']} / {r['entity_id']}: {r['summary']}. Quality: {r['quality']}. Review priority: {r['review_priority']} (queue order, not severity). {r['suggested_review']}",
                        f"decision:{r['decision_id']}", {"evidence": r["evidence"], "warnings": r["warnings"], "provenance": r["provenance"]})
                    if route == "record":
                        add(f"Recorded review reasons: {', '.join(r.get('reasons', []))}. These explain queue policy, not a verified physical cause.", f"decision:{r['decision_id']}")
                    for warning in r["warnings"]:
                        add(f"{r['file_id']}: {warning}", f"decision:{r['decision_id']}")
                if len(candidates) > 8:
                    add(f"Showing 8 of {len(candidates)} matching findings. Narrow the file/finding scope for full detail.", "session")
            for domain, failure in self.failures.items():
                if domain in domains:
                    add(f"{domain.upper()}: rejected batch; no valid export. Inspect dashboard rejection diagnostics.", "session", {"status": failure.get("status")})
        else:
            docs = self.search_reference_docs(question, domains[0] if len(domains) == 1 else subsystem)
            facts.extend(docs)
            if not facts:
                return self._clarify(question, "Do you mean a model explanation, a metric definition, or recorded findings? Please name the term or select a use case; I don't have enough information to choose reliably.", subsystem, rows,
                                     [("Model walkthrough", "How does this model work?"), ("Review findings", "Which findings need review?"),
                                      ("Review policy", "Explain the review policy"), ("Quality warnings", "Show quality warnings")])

        response = self._response(facts, "answered", TITLES[route], subsystem, rows)
        return self._with_provider(response, question, selector, consent)

    def _with_provider(self, response, question, selector, consent):
        facts = response["facts"]
        if all(f.get("evidence_type") == "reference_document" or f["id"].startswith("term:") for f in facts):
            excerpt = local_excerpt(question, facts)
            if excerpt:
                response["answer"], response["answer_citation_ids"] = excerpt
                response["presentation"] = "focused_local_excerpt"
                response["reference_caveats"] = list(dict.fromkeys(f["caveat"] for f in facts if f.get("caveat")))
        if selector is not None and consent and facts:
            # Only compact, displayed text goes to the provider, never raw telemetry,
            # model artifacts, private paths or arbitrary tool execution privileges.
            cards = [{"id": f["id"], "text": (f["text"] + ("\nREFERENCE CAVEAT: " + f["caveat"] if f.get("caveat") else ""))[:4000]} for f in facts][:16]
            try:
                selected = selector(question, cards)
                ids = {c["id"] for c in cards}
                if isinstance(selected, dict):
                    paragraphs = validate_explanation(selected, cards)
                    response["generated_explanation"] = paragraphs
                    response.pop("answer_citation_ids", None)
                    response["answer"] = "AI explanation (check cited evidence):\n\n" + "\n\n".join(p["text"] + " [" + ", ".join(p["citation_ids"]) + "]" for p in paragraphs)
                    response["mode"] = "grounded_llm"
                    response["selected_citation_ids"] = list(dict.fromkeys(i for p in paragraphs for i in p["citation_ids"]))
                    return response
                if not isinstance(selected, list) or not selected or len(selected) > 8 or any(not isinstance(i, str) or i not in ids for i in selected) or len(set(selected)) != len(selected):
                    raise ValueError("Invalid evidence selection")
                chosen = {i: next(f for f in facts if f["id"] == i) for i in selected}
                response["answer"] = "Relevant evidence (LLM-selected, source text unchanged):\n\n" + "\n\n".join(chosen[i]["text"] for i in selected)
                response.pop("answer_citation_ids", None)
                response["mode"] = "grounded_llm"
                response["selected_citation_ids"] = selected
            except Exception:
                # Never echo provider exceptions: they can contain credentials or payloads.
                response["warnings"].append("Optional LLM unavailable or returned invalid evidence; using deterministic fallback.")
        return response

    def _clarify(self, question, prompt, subsystem, rows, options):
        response = self._response([], "needs_clarification", prompt, subsystem, rows)
        response["clarification"] = {"question": question, "options": [
            {"label": label, "question": query} for label, query in options[:100]]}
        return response

    def _response(self, facts, status, intro, subsystem, rows):
        def display(f):
            if f.get("evidence_type") == "reference_document":
                return f"Reference: {f['source']} · {f['section']} · lines {f['line_start']}–{f['line_end']}\n{f['text']}"
            return f["text"]
        return {"schema_version": 1, "answer": intro + ("\n\n" + "\n\n".join(display(f) for f in facts) if facts else ""),
                "mode": "evidence_template", "status": status,
                "scope": {"run_id": self.run.name, "subsystem": subsystem,
                          "subsystems": sorted({r["subsystem"] for r in rows}),
                          "file_ids": sorted({r["file_id"] for r in rows}), "decision_ids": [r["decision_id"] for r in rows]},
                "facts": deepcopy(facts), "citations": [{k: v for k, v in f.items() if k not in ("value", "text")} for f in facts],
                "warnings": list(dict.fromkeys([*self.source_warnings, *(f["caveat"] for f in facts if f.get("caveat"))])), "limitations": [LIMIT], "suggested_questions": SUGGESTIONS,
                "provenance": {"bundle_sha256": self.bundle_hash, "corpus_sha256": self.corpus_hash,
                               "snapshot_sha256": self.snapshot, "policy_version": "assistant-policy-v1"}}
