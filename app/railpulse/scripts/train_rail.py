#!/usr/bin/env python3
"""
Validate the Rail pipeline with file-level stratified k-fold (macro F1),
then fit on all training data and register the artifact.

Usage:
    python scripts/train_rail.py --feature-cache rail_features_train.csv \
        --labels path/to/Rail_Corrugation/Train_Labels.csv --registry-dir ./registry
"""
import argparse

import pandas as pd

from railpulse.core.registry import ModelRegistry
from railpulse.rail.pipeline import RailPipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature-cache", required=True, help="Output of extract_rail_features.py")
    ap.add_argument("--labels", required=True)
    ap.add_argument("--registry-dir", default="./registry")
    ap.add_argument("--version", default="v0_baseline")
    ap.add_argument("--n-splits", type=int, default=5)
    args = ap.parse_args()

    cache = pd.read_csv(args.feature_cache)
    labels = pd.read_csv(args.labels)

    pipeline = RailPipeline()
    cv_results = pipeline.evaluate_stratified_cv(cache, labels, n_splits=args.n_splits)
    print(cv_results.to_string(index=False))
    mean_score = cv_results["macro_f1"].mean()
    print(f"\nMean stratified-CV macro F1: {mean_score:.3f}")
    print("(Rule of thumb from the Info Kit: an always-predict-Normal model scores ~0.33 -- "
          "this number should clear that comfortably before you trust it further.)")

    # Fit the deployed model on ALL labelled data (the CV above is what
    # tells you how good it likely is; this is the artifact that ships).
    pipeline.fit(cache, labels)

    registry = ModelRegistry(args.registry_dir)
    record = registry.save(
        subsystem="rail",
        version=args.version,
        model=pipeline.model,
        feature_columns=pipeline.feature_cols,
        model_params=pipeline.model.get_params(),
        fold_scores={"cv_macro_f1_mean": mean_score, "cv_macro_f1_per_fold": cv_results["macro_f1"].tolist()},
        selection_rationale="Pooled side-binary GradientBoostingClassifier over wavenumber-band + time-domain features (architecture review Section 04 / this pipeline's docstring).",
    )
    print(f"\nRegistered rail/{args.version} (checksum {record.artifact_checksum})")


if __name__ == "__main__":
    main()
