# Scripts

Training, evaluation, prediction, and validation entry points belong here.

- `run_all.py` trains/validates on training data and packages all four test outputs.
- `predict.py --subsystem NAME --input PATH --output NEW_PATH` uses a validated frozen bundle; it never trains and refuses to overwrite output.
- `acv/predict.py` and `rail/predict.py` are compatibility wrappers around that shared inference CLI.
- `build_decisions.py` replays the active bundle into dashboard review records.
