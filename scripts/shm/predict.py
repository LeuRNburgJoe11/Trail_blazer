"""Predict SHM damage from one recording or a folder, without any fitting."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from railpulse.shm.loader import list_recordings
from railpulse.shm.pipeline import predict_directory, write_predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Output CSV path")
    parser.add_argument("--artifact", type=Path, default=ROOT / "models/shm/model.joblib")
    parser.add_argument("--evidence", type=Path, help="Optional JSON of per-file features, warnings and measured latency")
    args = parser.parse_args()
    results = predict_directory(args.input, args.artifact)
    write_predictions(args.output, results, [p.name for p in list_recordings(args.input)])
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps([r.to_dict() for r in results], indent=2, allow_nan=False) + "\n")
    print(f"Wrote {len(results)} SHM predictions to {args.output}")


if __name__ == "__main__":
    main()
