"""Reviewed explanation templates, not a second diagnostic model."""
import re

GLOSSARY = {
    "iou": ("Intersection over Union (IoU)", "How much a predicted time interval overlaps the reference interval, divided by their combined span. Better overlap means better timing alignment."),
    "precision": ("Precision", "Of the findings predicted as a particular class, how many were correct? Low precision means more false alarms for that class."),
    "recall": ("Recall", "Of the reference examples belonging to a class, how many did the model find? Low recall means more missed examples."),
    "false positive": ("False positive", "A class is predicted when the reference says it is absent. For Rail, define the class first; confusing Side I with Side II has different consequences from predicting Normal."),
    "false negative": ("False negative", "An example of a class is missed. A false-negative rate needs labelled reference examples and a clearly defined positive class."),
    "macro f1": ("Macro F1", "Calculate F1 separately for Normal, Side I and Side II, then average the three equally. A common Normal class cannot dominate this average through its sample count alone."),
    "f1": ("F1 score", "A balance of precision and recall: 2 × precision × recall / (precision + recall). The Door metric additionally evaluates interval overlap; ordinary classification F1 is not a substitute for its scoring contract."),
    "mape": ("Mean Absolute Percentage Error (MAPE)", "Average the absolute prediction error divided by the reference value. A fractional MAPE of 0.02 means 2% average error, not 2% confidence. SHM scores max(0, 1 − MAPE); zero-reference handling is not assumed."),
    "rank decay": ("Linear rank decay", "For n cars and the true faulty car at one-based rank r, the score is (n − r + 1) / n. Placing the true car nearer the top earns more credit. This is not a leak probability."),
    "cross validation": ("Cross-validation", "Repeatedly fit on part of the labelled data and evaluate on the held-out part. The split must respect the independent unit, such as an ACV case, not mix rows from that case across train and validation."),
    "nested": ("Nested validation", "Inner folds choose a model using only outer-training data. Outer held-out folds evaluate that selection procedure. This reduces selection optimism but does not fix unknown correlations between recordings."),
    "leakage": ("Data leakage in evaluation", "Information from held-out examples influences training or model selection, making evaluation look better than genuine unseen-data performance. This term is different from an ACV refrigerant leak."),
    "rainflow": ("Rainflow counting", "Summarises a stress recording as cycles of different ranges and counts. The SHM model uses amplitude (range divided by two) and gives residual half cycles a count of 0.5; larger amplitudes contribute strongly to its calibrated damage proxy."),
    "extrapolation": ("Extrapolation / training-range warning", "Some input evidence is outside the range seen in training. Check applicability before interpretation. A range warning is not a measured error bar, and being inside the range does not guarantee correctness."),
    "calibration": ("Probability calibration", "A validated relationship between reported probabilities and observed correctness. RailPulse does not provide calibrated fault probabilities; ranking scores and training-range checks must not be presented as confidence percentages."),
    "remaining life": ("Remaining useful life (RUL)", "The remaining service exposure until a defined endpoint. A per-recording SHM damage estimate alone cannot establish this; verified asset history, exposure and approved limits are missing."),
}

PIPELINES = {
    "door": {
        "meaning": "The model finds opening/closing operations and labels each Normal or Abnormal resistance. It does not identify the exact failed component.",
        "steps": "Validate the 17 telemetry columns and increasing timestamps → detect active operations with short-gap handling → calculate motor effort, position and timing features → apply the fitted Extra Trees classifier → export interval boundaries and labels.",
        "verify": "Check the intended operation boundaries, raw motor/position evidence, and whether the dataset-specific segmentation rule fits this operating context. Idle recordings do not prove healthy equipment.",
        "source": "docs/ARCHITECTURE_AUDIT.md",
    },
    "acv": {
        "meaning": "Cars are ordered for investigation using available relative operating evidence. The top car is a suspicion to corroborate, not a confirmed refrigerant leak.",
        "steps": "Validate native car/telemetry mappings and timestamps → derive control and peer-comparison features → score the context-matched residual baseline → rank every native car ID. Peer matching can use weaker fallback contexts when strict matches are unavailable.",
        "verify": "Review missing telemetry, validity encodings, operating context and the complete ranking. Confirm which peer comparisons were applicable; do not interpret raw score differences as probabilities.",
        "source": "docs/ARCHITECTURE_AUDIT.md",
    },
    "rail": {
        "meaning": "The output is Normal, Side I or Side II for the recording. Without verified location metadata, it does not identify an exact track position.",
        "steps": "Validate recording dimensions and finite samples → decode speed pulses and extract spatial/vibration features → apply the bundle-selected classifier → return the class and available feature evidence. The audited default is the pooled spatial model; other bundles must be checked individually.",
        "verify": "Check side mapping and speed-pulse availability. Missing pulses weaken speed-normalised evidence. A Normal prediction is not an operational clearance.",
        "source": "docs/ARCHITECTURE_AUDIT.md",
    },
    "shm": {
        "meaning": "The output estimates cumulative damage for this stress recording. It is not a percentage of asset lifetime used and does not say when to replace a component.",
        "steps": "Validate the headerless finite stress column → count rainflow cycles, preserving residual half cycles → calculate amplitude-power features → apply the frozen fitted scale and exponent → report the estimate and training-range warnings. The audited model uses a fifth-power proxy; its fitted constants are dataset calibration, not measured material properties.",
        "verify": "Confirm stress units, acquisition conditions, exposure history and engineering-approved limits before maintenance interpretation. Missing sample rate and material metadata prevent an invented time-to-failure estimate.",
        "source": "docs/SHM.md",
    },
}

EVALUATION = ("Software tests check implementation behavior; model validation measures performance on labelled held-out examples; input-quality checks assess the current recording's contract and warnings. Passing one does not establish the other two. Organiser test performance is unknown without their labels.")


def normalise(text):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def definition_facts(question):
    q = normalise(question)
    q = re.sub(r"\brul\b|\bremaining useful life\b", "remaining life", q)
    q = q.replace("false positives", "false positive").replace("false negatives", "false negative")
    if not any(t in q for t in ("mean", "define", "definition", "term", "glossary", "what is", "what are", "explain")):
        return []
    matches = [key for key in GLOSSARY if re.search(r"\b" + re.escape(key) + r"\b", q)]
    if "glossary" in q and not matches:
        matches = list(GLOSSARY)
    if "macro f1" in matches:
        matches.remove("f1")
    return [{"id": f"term:{key.replace(' ', '-')}", "text": f"{GLOSSARY[key][0]}: {GLOSSARY[key][1]}",
             "source": "docs/ENGINEERING_ASSISTANT.md#glossary", "value": None} for key in matches]


def profile(instructions, context, author, audience, detail, focus):
    for value, limit in ((instructions, 1500), (context, 2000), (author, 80)):
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("Engineer input exceeds its permitted length")
    if audience not in {"plain", "technician", "engineer"} or detail not in {"concise", "detailed"} or focus not in {"auto", "quality", "evaluation", "review"}:
        raise ValueError("Unknown explanation preference")
    # Bounded, transparent instruction interpretation. Never execute arbitrary
    # directives or pass notes to an LLM as authoritative policy.
    q = normalise(instructions)
    applied = []
    if "technician" in q:
        audience = "technician"
        applied.append("Technician-friendly explanations")
    if "plain language" in q or "non technical" in q:
        audience = "plain"
        applied.append("Plain-language explanations")
    if "detailed" in q or "step by step" in q:
        detail = "detailed"
        applied.append("Step-by-step detail")
    if "concise" in q or "brief" in q:
        detail = "concise"
        applied.append("Concise explanations")
    if "focus" in q:
        if "quality" in q or "missing telemetry" in q:
            focus = "quality"
        elif "evaluation" in q or "validation" in q:
            focus = "evaluation"
        elif "review" in q:
            focus = "review"
        applied.append(f"Supported focus: {focus}")
    return {"audience": audience, "detail": detail, "focus": focus, "instructions": instructions,
            "applied_hints": applied, "define_terms": "define" in q or "acronym" in q,
            "context": {"author": author.strip() or "Engineer (self-reported)", "text": context,
                        "status": "user_provided_unverified", "scope": "selected recordings only"},
            "boundary": "Only listed presentation/focus hints are applied. Other free-text directives are not executed. Notes are not verified metadata, approvals, thresholds or policy, and are not sent to the optional provider."}


def enrich(response, question, settings):
    domains = []
    explicit = response["scope"].get("subsystem")
    if explicit:
        domains = [explicit]
    else:
        named = [d for d in PIPELINES if re.search(rf"\b{d}\b", question.lower())]
        domains = named or response["scope"].get("subsystems") or list(PIPELINES)
    is_glossary = any(f["id"].startswith("term:") for f in response["facts"])
    supported = response["status"] == "answered"
    sections = []
    route = response.get("routing", {}).get("intent")
    if supported:
        if route == "pipeline" and (settings["detail"] == "detailed" or settings["audience"] == "engineer"):
            sections.append({"title": "How the backend works", "text": "\n\n".join(f"{d.upper()}: {PIPELINES[d]['steps']}" for d in domains), "sources": [PIPELINES[d]["source"] for d in domains]})
        if route in {"evaluation", "official_score"}:
            sections.append({"title": "What is being evaluated", "text": EVALUATION, "sources": ["docs/ARCHITECTURE_AUDIT.md"]})
        if settings["define_terms"] and not is_glossary:
            terms = definition_facts("Define " + " ".join(f["text"] for f in response["facts"]))[:5]
            if terms:
                sections.append({"title": "Terms in this answer", "text": "\n\n".join(f["text"] for f in terms), "sources": ["docs/ENGINEERING_ASSISTANT.md#glossary"]})
        if route in {"record", "briefing"}:
            sections.append({"title": "What to verify next", "text": "\n\n".join(f"{d.upper()}: {PIPELINES[d]['verify']}" for d in domains), "sources": list(dict.fromkeys(PIPELINES[d]["source"] for d in domains))})
    response["explanation"] = {"sections": sections, "audience": settings["audience"], "detail": settings["detail"],
                               "purpose": "Engineering explanation and review preparation; no maintenance authority"}
    response["engineer_input"] = settings
    if settings["context"]["text"] or settings["instructions"]:
        response["warnings"].append("Engineer input is attributed but unverified. It cannot change predictions, source evidence, review policy or operational limits.")
    response["next_questions"] = ["How does this model work?", "What does this term mean?", "Prepare an inspection briefing", "Explain validation metrics"]
    return response
