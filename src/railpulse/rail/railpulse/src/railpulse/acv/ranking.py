"""
Model progression (architecture review Section 03): First = transparent
peer-residual ranking score (implemented here). Second = regularised
logistic regression or a shallow boosted model on car-level summaries --
add as `LearnedRanker` in this module once enough cases exist to justify a
fitted model; keep the same rank_cars() signature so the pipeline and app
don't need to change.
"""
from __future__ import annotations

import pandas as pd

from railpulse.acv.loader import discover_cars
from railpulse.acv.peer_features import peer_residual_score


def rank_cars(df: pd.DataFrame) -> tuple[list[str], pd.Series]:
    """Returns (ranked_car_ids, raw_scores) -- most to least suspicious."""
    cars = discover_cars(df)
    scores = peer_residual_score(df, cars)
    ranked = scores.sort_values(ascending=False).index.tolist()
    return ranked, scores
