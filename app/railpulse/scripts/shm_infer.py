#!/usr/bin/env python3
"""Run SHM inference with the canonical root pipeline, in its own process.

Same reason as scripts/door_infer.py: this prototype ships its own `railpulse`
package and the repository root ships another, so the canonical stack runs
behind a process boundary rather than fighting over the package name.

Nothing here reinterprets the model. `analyse_shm` already returns the damage
value, its rainflow evidence, and its own warnings; this only forwards them.

    {"rows": [{file_id, prediction, evidence, warnings, metadata}, ...]}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import warnings

PROTOTYPE = Path(__file__).resolve().parents[1]
REPO = PROTOTYPE.parents[1]
sys.path.insert(0, str(REPO / "src"))

BUNDLES = ("architecture-audit-final", "merged-main")


def default_artifact() -> Path:
    for name in BUNDLES:
        candidate = REPO / "outputs/combined" / name / "models/shm.joblib"
        if candidate.exists():
            return candidate
    raise SystemExit("No SHM artifact found; run scripts/run_all.py at the repository root first")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--names", nargs="+", help="Reported file_id per input, in the same order")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()

    warnings.filterwarnings("ignore")
    from railpulse.shm.pipeline import analyse_shm, load_artifact

    artifact = load_artifact(args.artifact or default_artifact())
    names = args.names or [path.name for path in args.inputs]
    rows = []
    for path, name in zip(args.inputs, names):
        result = analyse_shm(path, artifact=artifact)
        row = result.to_dict()
        # The temp file's name is meaningless; report what the user uploaded.
        row["file_id"] = name
        rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"rows": rows}, allow_nan=False), encoding="utf-8")
    print(f"{len(rows)} recordings -> {args.output}")


if __name__ == "__main__":
    main()
