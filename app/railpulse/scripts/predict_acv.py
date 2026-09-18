#!/usr/bin/env python3
"""
Run the ACV pipeline on one or more case files and write the exact
submission CSV.

Usage:
    python scripts/predict_acv.py --input path/to/ACV/Test/acv_test_case.xlsx \
        --output acv_predictions.csv
    # or, for every file in a folder:
    python scripts/predict_acv.py --input-dir path/to/ACV/Test --output acv_predictions.csv
"""
import argparse
import glob

from railpulse.acv.pipeline import ACVPipeline
from railpulse.core.submission import write_acv_predictions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="A single .xlsx case file")
    ap.add_argument("--input-dir", help="A folder of .xlsx case files")
    ap.add_argument("--output", default="acv_predictions.csv")
    args = ap.parse_args()

    if not args.input and not args.input_dir:
        raise SystemExit("Provide --input or --input-dir")

    paths = [args.input] if args.input else sorted(glob.glob(f"{args.input_dir}/*.xlsx"))
    pipeline = ACVPipeline()
    results = [pipeline.predict_file(p) for p in paths]
    write_acv_predictions(results, args.output)
    for r in results:
        print(f"{r.file_id}: {'|'.join(r.ranked_cars)}")
    print(f"\nWrote {args.output} with {len(results)} file(s).")


if __name__ == "__main__":
    main()
