"""Replay frozen inference into dashboard JSON without retraining or changing CSVs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.dont_write_bytecode = True
from railpulse.core.decisions import analyse_decision, decision_payload
from railpulse.core.dashboard import dashboard_summary
from railpulse.core.inference import load_bundle
from railpulse.core.predictions import csv_bytes
from railpulse.core.runtime import DEFAULT_RUN


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/dashboard" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    bundle = load_bundle(args.run / "models")
    paths = {"door": [ROOT / "data/Door/Test.csv"],
             "acv": sorted((ROOT / "data/acv/Test").glob("*.xlsx")),
             "rail": sorted((ROOT / "data/Rail_Corrugation/Test").glob("*.csv")),
             "shm": sorted((ROOT / "data/SHM/Test").glob("*.csv"))}
    records, compared = [], {}
    for name, files in paths.items():
        print(f"Building {name} review records: {len(files)} inputs", flush=True)
        frames = []
        for path in files:
            result, decisions = analyse_decision(name, path, bundle)
            frames.append(result.frame)
            records.extend(record.to_dict() for record in decisions)
        exported = csv_bytes(name, pd.concat(frames, ignore_index=True),
                             expected_ids=None if name == "door" else [p.name for p in files])
        if exported != (args.run / f"{name}_predictions.csv").read_bytes():
            raise ValueError(f"{name} official predictions changed; decision layer must not alter exports")
        compared[name] = {"rows": sum(len(frame) for frame in frames), "official_csv_unchanged": True,
                          "sha256": hashlib.sha256(exported).hexdigest()}
    summary = dashboard_summary(records, {name: [p.name for p in files] for name, files in paths.items()})
    summary["verification"] = compared
    summary["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [ROOT / "src/railpulse/core/decisions.py", ROOT / "src/railpulse/core/dashboard.py",
                                          ROOT / "src/railpulse/core/scoring.py", ROOT / "app/main.py"]}
    (args.output / "decisions.json").write_bytes(decision_payload(records))
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(f"Verified unchanged official outputs; wrote {len(records)} review records to {args.output}")


if __name__ == "__main__":
    main()
