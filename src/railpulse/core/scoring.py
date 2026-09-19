"""Rubric-facing scoring contracts; unknown labels are never treated as zero error."""
from __future__ import annotations

import math
from collections.abc import Mapping

from sklearn.metrics import f1_score

SUBSYSTEMS = ("door", "acv", "rail", "shm")
RAIL_CLASSES = ("Normal", "Side I", "Side II")


def rail_macro_f1(truth, prediction):
    """Always average all THREE official classes, even if a fold lacks one."""
    truth, prediction = list(truth), list(prediction)
    if not truth or len(truth) != len(prediction):
        raise ValueError("Expected matching nonempty Rail labels")
    if not set(truth) <= set(RAIL_CLASSES) or not set(prediction) <= set(RAIL_CLASSES):
        raise ValueError("Unknown Rail class")
    return float(f1_score(truth, prediction, labels=list(RAIL_CLASSES), average="macro", zero_division=0))


def acv_rank_score(true_car, ranked_cars, expected_cars):
    """Validate full native-ID coverage before calculating rank decay."""
    expected = list(expected_cars)
    ranked = list(ranked_cars)
    if not expected or len(expected) != len(set(expected)) or true_car not in expected:
        raise ValueError("Invalid reference car set")
    if len(ranked) != len(expected) or set(ranked) != set(expected):
        raise ValueError("Ranking must contain each source car exactly once")
    return (len(ranked) - ranked.index(true_car)) / len(ranked)


def combined_scores(scores: Mapping, *, attempted, basis="validation"):
    """Overall=sum/4; Average=sum/attempted. None means unscored, not failure.

    An attempted failure is an explicit 0. An unattempted task contributes 0 to
    Overall only. If ANY attempted score is unknown, both aggregates are unknown.
    Validation aggregation is a descriptive proxy, never an official test score.
    """
    attempted = list(attempted)
    if len(set(attempted)) != len(attempted) or not set(attempted) <= set(SUBSYSTEMS):
        raise ValueError("Invalid attempted subsystems")
    if not set(scores) <= set(attempted):
        raise ValueError("Cannot score a subsystem not attempted")
    if basis not in ("validation", "held_out"):
        raise ValueError("Unknown score basis")
    for score in scores.values():
        if score is not None and (isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError("Scores must be finite values in [0,1], or None")
    missing = [name for name in attempted if scores.get(name) is None]
    total = sum(scores[name] for name in attempted) if not missing else None
    return {"basis": basis, "status": "unscored" if missing else "scored" if attempted else "not_attempted",
            "attempted": attempted, "unscored": missing,
            "overall_score": total / 4 if total is not None else None,
            "average_score": total / len(attempted) if total is not None and attempted else None,
            "subsystem_scores": {name: scores.get(name) if name in attempted else 0.0 for name in SUBSYSTEMS},
            "note": "Validation proxy only; protocols differ and model-selection bias may apply."
                    if basis == "validation" else "Requires organiser-held ground truth; never inferred from predictions."}
