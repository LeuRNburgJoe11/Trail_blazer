"""Score an existing SHM CSV against positive reference labels with exact ID matching."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd
from railpulse.shm.loader import load_labels
from railpulse.shm.metrics import regression_metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    args = parser.parse_args()
    prediction = pd.read_csv(args.predictions, dtype={"file_id": str})
    if list(prediction.columns) != ["file_id", "prediction"] or prediction.file_id.duplicated().any():
        raise ValueError("Expected unique file_id,prediction rows")
    target = load_labels(args.labels, prediction.file_id.tolist())
    print(json.dumps(regression_metrics(target, prediction.prediction), indent=2))


if __name__ == "__main__":
    main()

