"""
Official task evaluators (architecture review, core/metrics.py).

These implement the organiser's exact matching/aggregation rules, not a
generic metric with a similar name -- see:
  - Door_Subsystem_Info_Kit.md Section 4 (IoU-weighted F1)
  - ACV_Subsystem_Info_Kit.md Section 4 (linear rank-decay score)

Keep this module dependency-light and side-effect-free so it can be
unit-tested directly (see tests/test_metrics.py) without touching any data
files.
"""
from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Door: IoU-weighted F1
# ---------------------------------------------------------------------------
def iou(a_start, a_end, b_start, b_end) -> float:
    inter = max(pd.Timedelta(0), min(a_end, b_end) - max(a_start, b_start))
    union = (a_end - a_start) + (b_end - b_start) - inter
    if union <= pd.Timedelta(0):
        return 0.0
    return inter / union


def door_iou_weighted_f1(pred: pd.DataFrame, truth: pd.DataFrame) -> float:
    """
    pred: DataFrame with columns start_ts, end_ts, prediction
    truth: DataFrame with columns start_ts, end_ts, status
    Implements: same-label-only candidates, IoU > 0 required, greedy
    highest-IoU-first one-to-one matching, credit = matched IoU itself,
    score = harmonic mean of soft_recall and soft_precision.
    """
    pairs = []
    for pi, p in pred.iterrows():
        for ti, t in truth.iterrows():
            if p["prediction"] != t["status"]:
                continue
            v = iou(p["start_ts"], p["end_ts"], t["start_ts"], t["end_ts"])
            if v > 0:
                pairs.append((v, pi, ti))
    pairs.sort(key=lambda x: -x[0])

    used_p, used_t = set(), set()
    matched_iou_sum = 0.0
    for v, pi, ti in pairs:
        if pi in used_p or ti in used_t:
            continue
        used_p.add(pi)
        used_t.add(ti)
        matched_iou_sum += v

    n_true, n_pred = len(truth), len(pred)
    soft_recall = matched_iou_sum / n_true if n_true else 0.0
    soft_precision = matched_iou_sum / n_pred if n_pred else 0.0
    if soft_recall + soft_precision == 0:
        return 0.0
    return 2 * soft_recall * soft_precision / (soft_recall + soft_precision)


# ---------------------------------------------------------------------------
# ACV: linear rank-decay score
# ---------------------------------------------------------------------------
def acv_rank_decay_score(ranked_cars: list[str], true_faulty: str) -> float:
    """score = (n - (r - 1)) / n, where r is the 1-indexed rank of the true
    faulty car; 0 if it's missing from ranked_cars entirely."""
    n = len(ranked_cars)
    if n == 0 or true_faulty not in ranked_cars:
        return 0.0
    r = ranked_cars.index(true_faulty) + 1
    return (n - (r - 1)) / n


# ---------------------------------------------------------------------------
# Rail: file-level macro F1 across {Normal, Side I, Side II}
# (Rail_Corrugation_Info_Kit.md Section 4). Unweighted mean of per-class F1
# -- NOT sklearn's default average="weighted", which would let the 234
# Normal files drown out the 14 Side I / 24 Side II files.
# ---------------------------------------------------------------------------
RAIL_LABELS = ["Normal", "Side I", "Side II"]


def rail_macro_f1(y_true, y_pred) -> float:
    from sklearn.metrics import f1_score

    return float(f1_score(y_true, y_pred, labels=RAIL_LABELS, average="macro", zero_division=0))


# ---------------------------------------------------------------------------
# SHM: placeholder -- wire up once that pipeline is built.
# See the architecture review Section 05 for the intended metric
# (max(0, 1 - MAPE)).
# ---------------------------------------------------------------------------
def shm_score(*args, **kwargs):
    raise NotImplementedError("SHM pipeline not yet implemented -- see src/railpulse/shm/pipeline.py")
