"""Nested validation with complete files as the indivisible hold-out unit."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, KFold

from .metrics import regression_metrics
from .regression import CANDIDATES, DamageRegressor


def make_splits(n: int, folds: int, seed: int, groups=None):
    if folds < 2:
        raise ValueError("Validation requires at least two folds")
    if groups is not None:
        groups = np.asarray(groups)
        if len(groups) != n or pd.isna(groups).any():
            raise ValueError("Every recording must have a group")
        count = len(set(groups))
        if count < 2:
            raise ValueError("Validation requires at least two independent groups")
        return list(GroupKFold(n_splits=min(folds, count)).split(np.arange(n), groups=groups))
    if n < folds:
        raise ValueError("Fewer recordings than requested folds")
    return list(KFold(n_splits=folds, shuffle=True, random_state=seed).split(np.arange(n)))


def choose_candidate(frame, target, *, folds=4, seed=42, groups=None, candidates=CANDIDATES):
    splits = make_splits(len(frame), folds, seed, groups)
    scores = {}
    for kind in candidates:
        prediction = np.empty(len(frame))
        for train, valid in splits:
            model = DamageRegressor(kind).fit(frame.iloc[train], target[train])
            prediction[valid] = model.predict(frame.iloc[valid])
        scores[kind] = regression_metrics(target, prediction)["mape"]
    # Stable tie-breaking follows the predeclared simple-to-complex candidate order.
    winner = min(candidates, key=lambda kind: scores[kind])
    return winner, scores, splits


def evaluate(frame, target, *, outer_folds=8, inner_folds=4, seeds=(42, 137), groups=None,
             candidates=CANDIDATES):
    """Outer scores estimate the entire selection procedure, not its best-looking candidate.

    GroupKFold is deterministic, so use one repetition when explicit groups are supplied.
    No filename-derived or target-derived acquisition groups are invented.
    """
    target = np.asarray(target, dtype=float)
    records, split_log = [], []
    groups = np.asarray(groups) if groups is not None else None
    repetitions = seeds[:1] if groups is not None else seeds
    for repeat, seed in enumerate(repetitions):
        for fold, (train, valid) in enumerate(make_splits(len(frame), outer_folds, seed, groups)):
            train_frame, train_y = frame.iloc[train], target[train]
            train_groups = groups[train] if groups is not None else None
            selected, inner_scores, inner_splits = choose_candidate(
                train_frame, train_y, folds=inner_folds, seed=seed + fold + 1,
                groups=train_groups, candidates=candidates)
            split_log.append({"repeat": repeat, "fold": fold, "seed": seed, "selected": selected,
                              "train": frame.index[train].tolist(), "validation": frame.index[valid].tolist(),
                              "inner_mape": inner_scores,
                              "inner_splits": [{"train": train_frame.index[a].tolist(),
                                                "validation": train_frame.index[b].tolist()}
                                               for a, b in inner_splits]})
            for kind in candidates:
                fitted = DamageRegressor(kind).fit(train_frame, train_y)
                prediction = fitted.predict(frame.iloc[valid])
                for index, predicted in zip(valid, prediction):
                    base = {"repeat": repeat, "fold": fold, "file_id": frame.index[index],
                            "target": target[index], "prediction": predicted,
                            "ape": abs(target[index] - predicted) / target[index],
                            "selected_kind": selected}
                    records.append({**base, "model": kind})
                    if kind == selected:
                        records.append({**base, "model": "nested_selection"})
            print(f"Repeat {repeat + 1}, fold {fold + 1}: selected {selected}", flush=True)
    oof = pd.DataFrame(records)
    summaries = []
    for kind, rows in oof.groupby("model", sort=False):
        summary = {"model": kind, **regression_metrics(rows.target, rows.prediction)}
        fold_mapes = rows.groupby(["repeat", "fold"]).ape.mean()
        summary.update({"fold_mape_std": float(fold_mapes.std(ddof=1)),
                        "n_files": rows.file_id.nunique(), "n_predictions": len(rows)})
        summaries.append(summary)
    return pd.DataFrame(summaries), oof, split_log

