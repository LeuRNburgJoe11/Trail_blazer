#!/usr/bin/env python3
"""
Extract (filename, side, feature_dict) rows from a folder of Rail
Corrugation CSVs into a cache CSV, resumable in chunks -- 272 files at
~0.8s/file for both sides is too slow for some single short-lived runs.

Usage:
    python scripts/extract_rail_features.py --data-dir path/to/Rail_Corrugation/Train \
        --output rail_features_train.csv --start 0 --limit 100
    # repeat with increasing --start until it reports 0 new rows
"""
import argparse

from railpulse.rail.pipeline import extract_features_to_cache


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    df = extract_features_to_cache(args.data_dir, args.output, start=args.start, limit=args.limit)
    print(f"Extracted {len(df)} new (file, side) rows -> {args.output}")


if __name__ == "__main__":
    main()
