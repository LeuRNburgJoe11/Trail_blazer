"""
Door pipeline (architecture review Section 02 + Section 07 inference
contract). Wraps segmentation -> features -> classifier behind one object so
the app, batch scripts, and tests all call the same code path -- "use the
same inference code for the app and batch submissions."
"""
from __future__ import annotations

import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier

from railpulse.core.metrics import door_iou_weighted_f1
from railpulse.core.schemas import DoorResult, DoorSegment
from railpulse.door.features import FEATURE_COLS, build_feature_table
from railpulse.door.loader import format_native_ts, load_answer, load_stream
from railpulse.door.segmentation import segment_stream


def label_candidates(cand: pd.DataFrame, ans: pd.DataFrame) -> pd.DataFrame:
    """Training-time only: assign each candidate cycle the label of its
    best-IoU true segment (IoU > 0); candidates matching nothing are
    treated as segmentation noise and dropped, not mislabelled."""
    from railpulse.core.metrics import iou

    labels, keep_idx = [], []
    for i, row in cand.iterrows():
        best_iou, best_label = 0.0, None
        for _, a in ans.iterrows():
            v = iou(row.start_ts, row.end_ts, a.start_ts, a.end_ts)
            if v > best_iou:
                best_iou, best_label = v, a.status
        if best_iou > 0:
            labels.append(best_label)
            keep_idx.append(i)
    return cand.loc[keep_idx].assign(status=labels)


class DoorPipeline:
    def __init__(self, model=None, random_state: int = 0):
        self.model = model or ExtraTreesClassifier(
            n_estimators=300, max_depth=6, class_weight="balanced", random_state=random_state
        )
        self.feature_cols = FEATURE_COLS

    def fit(self, stream_df: pd.DataFrame, answer_df: pd.DataFrame) -> pd.DataFrame:
        """Segments the stream, labels candidates via IoU, fits the
        classifier. Returns the labelled training table for inspection."""
        cycles = segment_stream(stream_df)
        cand = build_feature_table(cycles)
        labeled = label_candidates(cand, answer_df)
        self.model.fit(labeled[self.feature_cols], labeled["status"])
        return labeled

    def predict(self, stream_df: pd.DataFrame) -> DoorResult:
        """Full pipeline on a raw stream: segment, featurize, classify."""
        cycles = segment_stream(stream_df)
        cand = build_feature_table(cycles)
        if cand.empty:
            return DoorResult(segments=[])
        preds = self.model.predict(cand[self.feature_cols])
        segments = [
            DoorSegment(
                start_time=format_native_ts(row.start_ts),
                end_time=format_native_ts(row.end_ts),
                prediction=pred,
            )
            for row, pred in zip(cand.itertuples(), preds)
        ]
        return DoorResult(segments=segments)

    def evaluate(self, stream_df: pd.DataFrame, answer_df: pd.DataFrame) -> float:
        """End-to-end score on a held-out stream slice: run the SAME
        predict() path used at inference, then score with the official
        metric. This is the number to trust -- not a metric computed only
        on cycles the segmenter happened to find perfectly."""
        cycles = segment_stream(stream_df)
        cand = build_feature_table(cycles)
        if cand.empty:
            return 0.0
        cand = cand.copy()
        cand["prediction"] = self.model.predict(cand[self.feature_cols])
        return door_iou_weighted_f1(cand, answer_df.rename(columns={"status": "status"}))


def time_holdout_split(stream_df: pd.DataFrame, answer_df: pd.DataFrame, holdout_frac: float = 0.3):
    """Split Train.csv itself in time so the FULL pipeline (segmentation +
    classification together) can be evaluated before touching Test.csv."""
    split_ts = stream_df["ts"].quantile(1 - holdout_frac)
    fit_stream = stream_df[stream_df["ts"] < split_ts]
    held_stream = stream_df[stream_df["ts"] >= split_ts]
    fit_answer = answer_df[answer_df["end_ts"] < split_ts]
    held_answer = answer_df[answer_df["start_ts"] >= split_ts]
    return fit_stream, held_stream, fit_answer, held_answer


__all__ = ["DoorPipeline", "label_candidates", "time_holdout_split", "load_stream", "load_answer"]
