# Run the Rail Corrugation Pipeline

Run these commands from the repository root.

## 1. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

The rail pipeline requires `numpy`, `pandas`, and `scikit-learn`.

## 2. Arrange the data

Place the Rail Corrugation dataset under `data/Rail_Corrugation/`:

```text
data/Rail_Corrugation/
  Train/
    Train1.csv
    Train2.csv
    ...
  Train_Labels.csv
  Test/
    Test1.csv
    Test2.csv
    ...
```

`Train_Labels.csv` must contain these columns:

```text
filename,label
Train1.csv,Normal
Train2.csv,Side I
```

Allowed labels are `Normal`, `Side I`, and `Side II`.

Each recording must be a headerless CSV with 129 columns: one speed-sensor column followed by 128 vibration/shock columns. The loader accepts an optional header row and removes it when the first row is non-numeric.

## 3. Train and predict

This repository exposes the rail pipeline as Python functions rather than a standalone command-line script. Run the following from the repository root:

```powershell
New-Item -ItemType Directory -Force outputs | Out-Null
$env:PYTHONPATH = "src"
@'
from pathlib import Path

from railpulse.rail.pipeline import predict, train, write_predictions

base = Path("data/Rail_Corrugation")
model = train(base / "Train", base / "Train_Labels.csv")
predictions = predict(model, base / "Test")
write_predictions("outputs/rail_predictions.csv", predictions)
print(f"Wrote {len(predictions)} predictions to outputs/rail_predictions.csv")
'@ | python -
```

The output file has the required submission columns:

```text
file_id,prediction
Test1.csv,Normal
```

The classifier uses extracted time/frequency features and a class-weighted Extra Trees model. If scikit-learn is unavailable, it falls back to the majority training label.

## 4. Validate the output

```powershell
python -c "import csv; from pathlib import Path; p=Path('outputs/rail_predictions.csv'); rows=list(csv.DictReader(p.open(encoding='utf-8'))); assert rows and all(set(row)=={'file_id','prediction'} for row in rows); assert all(row['prediction'] in {'Normal','Side I','Side II'} for row in rows); print(f'Rail prediction check passed: {len(rows)} rows')"
```

The number of output rows should equal the number of CSV recordings in `data/Rail_Corrugation/Test/`.

## 5. Run the rail tests

```powershell
python -m pytest tests -q
```

The current checkout must contain the training recordings and labels before the train-and-predict command can run. The documentation file in `data/Rail_Corrugation/Test/` is not a recording and is ignored by the loader.
