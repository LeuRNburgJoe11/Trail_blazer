#!/usr/bin/env python3
"""
Leave-one-case-out evaluation of the ACV pipeline against the 6 labelled
training cases. There's no separate "train_acv.py" -- v0_baseline is a
rule-based peer-residual score with no fitted parameters, so predict() IS
the pipeline. Once a learned ranker (configs/acv.yaml v1_logistic) is added,
give it its own train_acv.py that mirrors train_door.py.

Usage:
    python scripts/evaluate_acv.py --data-dir path/to/PS3/02_Datasets/ACV
"""
import argparse

from railpulse.acv.pipeline import ACVPipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    args = ap.parse_args()

    pipeline = ACVPipeline()
    results = pipeline.leave_one_case_out(
        data_dir=args.data_dir, labels_path=f"{args.data_dir}/Train_Labels.csv"
    )
    print(results.to_string(index=False))

    found = results[results["found"]]
    if len(found):
        print(f"\nMean LOCO rank-decay score: {found['score'].mean():.3f}  (n={len(found)} cases)")
    else:
        print("No labelled cases found under --data-dir.")


if __name__ == "__main__":
    main()
