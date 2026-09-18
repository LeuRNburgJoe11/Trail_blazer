#!/usr/bin/env python3
"""
Train the Door pipeline on Train.csv, evaluate end-to-end on a held-out time
slice of Train.csv (never Test.csv -- that has no labels), and register the
fitted artifact with its fold score.

Usage:
    python scripts/train_door.py --data-dir path/to/PS3/02_Datasets/Door \
        --registry-dir ./registry --version v0_baseline
"""
import argparse
import time

from railpulse.core.registry import ModelRegistry
from railpulse.door.loader import load_answer, load_stream
from railpulse.door.pipeline import DoorPipeline, time_holdout_split


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--registry-dir", default="./registry")
    ap.add_argument("--version", default="v0_baseline")
    ap.add_argument("--holdout-frac", type=float, default=0.3)
    args = ap.parse_args()

    stream = load_stream(f"{args.data_dir}/Train.csv")
    answer = load_answer(f"{args.data_dir}/Train_Segments_Answer.csv")
    fit_stream, held_stream, fit_answer, held_answer = time_holdout_split(
        stream, answer, args.holdout_frac
    )
    print(f"Fit rows={len(fit_stream)}, held-out rows={len(held_stream)}")

    pipeline = DoorPipeline()
    labeled = pipeline.fit(fit_stream, fit_answer)
    print(f"Fit: {labeled['status'].value_counts().to_dict()}")

    t0 = time.time()
    score = pipeline.evaluate(held_stream, held_answer)
    latency = (time.time() - t0) / max(1, len(held_stream))
    print(f"Held-out end-to-end IoU-weighted F1: {score:.3f}")

    registry = ModelRegistry(args.registry_dir)
    record = registry.save(
        subsystem="door",
        version=args.version,
        model=pipeline.model,
        feature_columns=pipeline.feature_cols,
        model_params=pipeline.model.get_params(),
        fold_scores={"held_out_iou_f1": score},
        measured_latency_s=latency,
        selection_rationale="First model in portfolio: state-based segmentation + Extra Trees (architecture review Section 08).",
    )
    print(f"Registered door/{args.version} (checksum {record.artifact_checksum})")


if __name__ == "__main__":
    main()
