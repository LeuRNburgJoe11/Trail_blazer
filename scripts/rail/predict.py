"""Train the rail-corrugation baseline and write test predictions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from railpulse.rail.pipeline import predict, train, write_predictions


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--input",
		type=Path,
		default=ROOT / "data" / "Rail_Corrugation" / "Test",
		help="Directory containing unlabelled rail recordings",
	)
	parser.add_argument(
		"--labels",
		type=Path,
		default=ROOT / "data" / "Rail_Corrugation" / "Train_Labels.csv",
		help="Training labels CSV",
	)
	parser.add_argument(
		"--output",
		type=Path,
		default=ROOT / "outputs" / "rail_predictions.csv",
		help="Prediction CSV to create",
	)
	args = parser.parse_args()

	model = train(ROOT / "data" / "Rail_Corrugation" / "Train", args.labels)
	predictions = predict(model, args.input)
	args.output.parent.mkdir(parents=True, exist_ok=True)
	write_predictions(args.output, predictions)
	print(f"Wrote {len(predictions)} predictions to {args.output}")


if __name__ == "__main__":
	main()