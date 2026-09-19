"""Conservative, inspectable routing. Unknown intent is not a batch query."""
import re


def intent(question):
    q = " ".join(question.lower().strip().split())
    if re.fullmatch(r"(?:hi|hello|hey|help|thanks|thank you)[!.?]*", q) or "what can you" in q:
        return "help"
    if re.fullmatch(r"(?:explain|why|review|explain (?:it|this|that)|what (?:about|does|is) (?:it|this|that)(?: mean)?)[?.!]*", q):
        return "help"
    # Physical concepts / telemetry definitions are documentation questions, not
    # requests to choose a recording merely because they start with 'why'.
    if re.search(r"\b(?:miner|rainflow|s[- ]n curve|stress.life|dcsr|dcsl|dlsr|dlsl|back.emf|electromotive|wavy wear|ripples|vapour.compression|refrigerant|axle.box|toothed wheel)\b", q) and re.search(r"\b(?:what|why|how|explain|define|describe)\b", q) and not re.search(r"\b(?:this result|this prediction|this recording|ranked|ranking)\b|\.(?:csv|xlsx)\b", q):
        return "reference"
    if re.search(r"\b(?:review|queue|priority)\s+(?:policy|rules?|meaning)\b", q) or "how is review priority" in q:
        return "review_policy"
    if any(t in q for t in ("how does this model", "how does the model", "pipeline", "backend", "step by step", "how did the system")) or ("how" in q and "work" in q):
        return "pipeline"
    if any(t in q for t in ("test score", "leaderboard", "overall score", "average score")):
        return "official_score"
    if any(t in q for t in ("metric", "validat", "evaluat", "reliable", "model select", "model chosen", "model selected", "performance", "f1", "mape", "accuracy", "benchmark")):
        return "evaluation"
    if re.search(r"\b(?:explain|describe)\b.*\bmodel\b", q) and not re.search(r"\b(?:prediction|result|output)\b", q):
        return "pipeline"
    if "compare" in q:
        return "compare"
    if any(t in q for t in ("warning", "quality", "missing telemetry")):
        return "quality"
    if any(t in q for t in ("briefing", "handover", "inspection")):
        return "briefing"
    if any(t in q for t in ("need review", "require review", "findings", "flagged", "review findings")):
        return "review"
    if any(t in q for t in ("this result", "this prediction", "this output", "why was", "why is", "why did", "looking at", "is it abnormal")) or re.search(r"\bexplain\b.*\.(csv|xlsx)\b", q):
        return "record"
    if any(t in q for t in ("summar", "coverage", "batch", "results", "predictions", "show evidence", "explain evidence", "ranking", "damage estimate")):
        return "summary"
    return "reference"


TITLES = {
    "pipeline": "How the selected model works:",
    "review_policy": "How the advisory review queue works:",
    "official_score": "Official scoring and what is currently unknown:",
    "evaluation": "Evaluation for the selected scope:",
    "quality": "Input-quality warnings in the selected scope:",
    "briefing": "Inspection preparation—not a maintenance instruction:",
    "review": "Findings requiring human review:",
    "record": "Evidence for the selected recording:",
    "summary": "Summary of the selected recordings:",
    "compare": "Recording comparison (no shared asset identity assumed):",
    "reference": "Matching reference passages:",
}

REVIEW_POLICY = (
    "The advisory queue orders human review; it is not physical severity or failure probability. "
    "Door/Rail abnormal classes and ACV localization start at priority 20; SHM estimates require engineering context at 10. "
    "Warnings or unverified/degraded quality require review and raise priority to at least 30. "
    "A Normal classification may therefore still require review. Passing quality checks is not an operational clearance."
)
