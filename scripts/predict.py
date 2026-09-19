"""Frozen prediction CLI shared by every subsystem; never fits on prediction calls."""
import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from railpulse.core.inference import load_bundle, predict_file
from railpulse.core.predictions import csv_bytes
from railpulse.core.runtime import DEFAULT_RUN


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subsystem", choices=("door", "acv", "rail", "shm"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_RUN / "models")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Output already exists: {args.output}")
    if args.subsystem == "door" and not args.input.is_file():
        raise ValueError("Door requires one continuous CSV stream")
    extension = "*.xlsx" if args.subsystem == "acv" else "*.csv"
    files = [args.input] if args.input.is_file() else sorted(args.input.glob(extension))
    if not files:
        raise ValueError("No input recordings found")
    bundle = load_bundle(args.bundle)
    frame = pd.concat([predict_file(args.subsystem, path, bundle).frame for path in files], ignore_index=True)
    output = csv_bytes(args.subsystem, frame, expected_ids=None if args.subsystem == "door" else [path.name for path in files])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(output)
    print(f"Wrote {len(frame)} predictions to {args.output}")


if __name__ == "__main__":
    main()
