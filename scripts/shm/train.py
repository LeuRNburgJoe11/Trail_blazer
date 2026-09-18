"""Validate candidates on training files, select with CV, then freeze one SHM model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from railpulse.shm.loader import load_labels
from railpulse.shm.rainflow_features import build_features
from railpulse.shm.regression import DamageRegressor, CANDIDATES
from railpulse.shm.validation import evaluate, choose_candidate
from railpulse.shm.pipeline import save_artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/SHM/Train")
    parser.add_argument("--labels", type=Path, default=ROOT / "data/SHM/Train_Labels.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/shm")
    parser.add_argument("--artifact", type=Path, default=ROOT / "models/shm/model.joblib")
    parser.add_argument("--groups", type=Path, help="Optional verified acquisition metadata CSV: filename,group")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    features, manifest = build_features(args.input, args.output / "cache")
    if manifest.sha256.duplicated().any():
        raise ValueError("Duplicate training file contents; resolve duplicate groups before validation")
    target = load_labels(args.labels, features.index.tolist())
    groups = None
    if args.groups:
        group_frame = pd.read_csv(args.groups, dtype=str)
        if list(group_frame.columns) != ["filename", "group"] or group_frame.filename.duplicated().any():
            raise ValueError("Groups require unique filename,group columns")
        if set(group_frame.filename) != set(features.index):
            raise ValueError("Group IDs must exactly cover the training recordings")
        groups = group_frame.set_index("filename").loc[features.index, "group"].to_numpy()
    features.to_csv(args.output / "train_features.csv")
    manifest.to_csv(args.output / "train_manifest.csv", index=False)
    comparison, oof, splits = evaluate(features, target, groups=groups)
    comparison.to_csv(args.output / "model_comparison.csv", index=False)
    oof.to_csv(args.output / "out_of_fold_predictions.csv", index=False)
    (args.output / "validation_splits.json").write_text(json.dumps(splits, indent=2) + "\n")
    winner, selection_scores, final_splits = choose_candidate(features, target, folds=8, groups=groups)
    model = DamageRegressor(winner).fit(features, target)
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for folder in (ROOT / "src/railpulse/shm", ROOT / "scripts/shm")
                     for p in sorted(folder.glob("*.py"))}
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    metadata = {"git_head": git_head, "source_sha256": source_hashes,
                "labels_sha256": hashlib.sha256(args.labels.read_bytes()).hexdigest(),
                "candidate_order": list(CANDIDATES), "selection_mape": selection_scores,
                "selected_model": winner, "nested_evaluation": comparison.query("model == 'nested_selection'").to_dict("records")[0],
                "validation": "grouped nested CV" if groups is not None else "2x8 outer folds, 4 inner folds; shuffled by file",
                "groups_supplied": groups is not None,
                "group_assignments": dict(zip(features.index, groups)) if groups is not None else None,
                "final_selection_splits": [{"train": features.index[a].tolist(), "validation": features.index[b].tolist()}
                                           for a, b in final_splits],
                "caveat": "Acquisition run/line/load IDs are unavailable. File CV cannot exclude dependence across recordings.",
                "target_min": float(target.min()), "target_max": float(target.max()),
                "test_used_in_selection": False}
    artifact = save_artifact(args.artifact, model, features, manifest, metadata)
    (args.output / "training_summary.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(comparison.to_string(index=False))
    print(f"Frozen {winner}: {args.artifact}")


if __name__ == "__main__":
    main()

