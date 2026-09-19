"""
Rail Corrugation pipeline. Model progression choice, per the architecture
review's philosophy (compact classifier over a small physically-meaningful
feature set, same as Door and ACV): a SINGLE pooled binary classifier
answering "is this side corrugated?", trained on Side I's and Side II's
feature vectors together (234 Normal-side examples x2 sides pooled as
negatives, 14+24=38 pooled positives) rather than two separate weak
per-side models on 14 and 24 examples respectively.

At inference, the same classifier scores a file's Side I vector and Side II
vector independently, and the two scores are combined into the final
3-class label.
"""
from __future__ import annotations

import glob
import os

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold

from railpulse.core.metrics import rail_macro_f1
from railpulse.core.schemas import RailResult
from railpulse.rail.features import side_feature_vector
from railpulse.rail.loader import load_file


def extract_features_to_cache(data_dir: str, out_csv: str, filenames: list[str] | None = None,
                               start: int = 0, limit: int | None = None) -> pd.DataFrame:
    """
    Batch-extracts (filename, side, feature_dict) long-format rows and
    appends to out_csv, skipping files already cached -- lets extraction
    run in resumable chunks (272 files x ~1.4s/file is too slow for a
    single short-lived call in some environments).
    """
    if filenames is None:
        filenames = sorted(
            os.path.basename(p) for p in glob.glob(f"{data_dir}/**/*.csv", recursive=True)
            if "Labels" not in os.path.basename(p)
        )
    filenames = filenames[start:]
    if limit is not None:
        filenames = filenames[:limit]

    done = set()
    if os.path.exists(out_csv):
        done = set(pd.read_csv(out_csv, usecols=["filename"])["filename"].unique())

    rows = []
    for fname in filenames:
        if fname in done:
            continue
        matches = glob.glob(f"{data_dir}/**/{fname}", recursive=True)
        if not matches:
            continue
        rf = load_file(matches[0])
        for side in ("Side I", "Side II"):
            feat = side_feature_vector(rf, side)
            feat["filename"] = fname
            feat["side"] = side
            rows.append(feat)

    if rows:
        new_df = pd.DataFrame(rows)
        header = not os.path.exists(out_csv)
        new_df.to_csv(out_csv, mode="a", header=header, index=False)
    return pd.DataFrame(rows)


def _feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in ("filename", "side", "y", "true_label", "label")]


class RailPipeline:
    def __init__(self, model=None, threshold: float = 0.5, random_state: int = 0):
        self.model = model if model is not None else GradientBoostingClassifier(random_state=random_state)
        self.threshold = threshold
        self.feature_cols: list[str] | None = None

    def _build_pooled_training_table(self, feature_cache: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
        labels = labels.rename(columns={"label": "true_label"})
        merged = feature_cache.merge(labels, on="filename", how="inner")
        merged["y"] = (
            ((merged["side"] == "Side I") & (merged["true_label"] == "Side I"))
            | ((merged["side"] == "Side II") & (merged["true_label"] == "Side II"))
        ).astype(int)
        return merged

    def fit(self, feature_cache: pd.DataFrame, labels: pd.DataFrame) -> None:
        pooled = self._build_pooled_training_table(feature_cache, labels)
        self.feature_cols = _feature_cols(pooled)
        self.model.fit(pooled[self.feature_cols], pooled["y"])

    def predict_file(self, path: str) -> RailResult:
        rf = load_file(path)
        scores = {}
        for side in ("Side I", "Side II"):
            feat = side_feature_vector(rf, side)
            x = pd.DataFrame([feat])[self.feature_cols]
            scores[side] = float(self.model.predict_proba(x)[0, 1])

        flagged = [s for s, p in scores.items() if p >= self.threshold]
        if not flagged:
            prediction = "Normal"
        elif len(flagged) == 1:
            prediction = flagged[0]
        else:
            # Both sides flagged -- labels are meant to be mutually exclusive
            # per the Info Kit; break the tie toward the higher-confidence side.
            prediction = max(scores, key=scores.get)

        return RailResult(file_id=os.path.basename(path), prediction=prediction, side_scores=scores)

    def evaluate_stratified_cv(self, feature_cache: pd.DataFrame, labels: pd.DataFrame,
                                n_splits: int = 5) -> pd.DataFrame:
        """File-level stratified k-fold on the 3-class label (never splitting
        a file's two side-vectors across folds), scored with the official
        macro F1 on the pooled out-of-fold predictions per fold."""
        labels = labels.copy()
        wide = feature_cache.pivot(index="filename", columns="side")
        wide.columns = [f"{side}__{col}" for col, side in wide.columns]
        wide = wide.reset_index().merge(labels, on="filename", how="inner")

        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=0)
        fold_rows = []
        for fold_i, (train_idx, test_idx) in enumerate(skf.split(wide, wide["label"])):
            train_files = wide.iloc[train_idx]["filename"]
            test_files = wide.iloc[test_idx]["filename"]

            train_cache = feature_cache[feature_cache["filename"].isin(train_files)]
            test_cache = feature_cache[feature_cache["filename"].isin(test_files)]

            fold_model = RailPipeline(model=type(self.model)(**self.model.get_params()),
                                       threshold=self.threshold)
            fold_model.fit(train_cache, labels)

            y_true, y_pred = [], []
            for fname in test_files:
                true_label = labels.loc[labels["filename"] == fname, "label"].iloc[0]
                sub = test_cache[test_cache["filename"] == fname]
                scores = {}
                for _, row in sub.iterrows():
                    x = row[fold_model.feature_cols].to_frame().T
                    scores[row["side"]] = float(fold_model.model.predict_proba(x)[0, 1])
                flagged = [s for s, p in scores.items() if p >= fold_model.threshold]
                if not flagged:
                    pred = "Normal"
                elif len(flagged) == 1:
                    pred = flagged[0]
                else:
                    pred = max(scores, key=scores.get)
                y_true.append(true_label)
                y_pred.append(pred)

            score = rail_macro_f1(y_true, y_pred)
            fold_rows.append({"fold": fold_i, "n_test_files": len(test_files), "macro_f1": score})

        return pd.DataFrame(fold_rows)
