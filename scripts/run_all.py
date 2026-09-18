"""Run the integrated training, evaluation, frozen inference and packaging workflow."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from railpulse.core.combined import run_all


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/combined" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                        help="New run directory; existing directories are never overwritten")
    parser.add_argument("--skip-data-verification", action="store_true",
                        help="Explicitly skip raw checksum/schema checks; recorded in the summary")
    args = parser.parse_args()
    result = run_all(ROOT, args.output, verify_data=not args.skip_data_verification)
    print(json.dumps({"status": result["status"], "output": str(args.output), "predictions": result["predictions"]}, indent=2))


if __name__ == "__main__":
    main()
