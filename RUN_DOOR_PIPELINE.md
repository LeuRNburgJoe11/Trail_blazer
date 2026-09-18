# Run the Door Pipeline

Run these commands from the repository root:

```powershell
@'
import sys
from pathlib import Path

sys.path.insert(0, "src")

from railpulse.core.submission import write_intervals
from railpulse.door.pipeline import run

base = Path("FOR PARTICIPANTS/02_Datasets/Door")
predictions = run(
    train_path=base / "Train.csv",
    labels_path=base / "Train_Segments_Answer.csv",
    test_path=base / "Test.csv",
)
write_intervals("predictions.csv", predictions)
print(f"Wrote {len(predictions)} intervals to predictions.csv")
'@ | python -
```

The command runs the modules in this order:

1. `door.loader`: loads and preserves the original timestamps.
2. `door.segmentation`: detects operation boundaries.
3. `door.features`: extracts cycle features for each interval.
4. `door.pipeline`: trains the Extra Trees baseline and predicts test statuses.
5. `core.submission`: writes the required interval CSV columns.

## Smoke Check

To verify the training boundaries against the supplied reference annotations:

```powershell
$env:PYTHONPATH = "src"
python -c "from pathlib import Path; import csv; from railpulse.door.loader import load_stream; from railpulse.door.segmentation import detect_intervals; b=Path('FOR PARTICIPANTS/02_Datasets/Door'); s=load_stream(b/'Train.csv'); i=detect_intervals(s); r=list(csv.DictReader((b/'Train_Segments_Answer.csv').open(encoding='utf-8'))); assert len(i)==len(r)==110; assert [s[x.start_index].timestamp for x in i]==[x['start_time'] for x in r]; assert [s[x.end_index].timestamp for x in i]==[x['end_time'] for x in r]; print('Door boundary check passed')"
```

`door_predictions.csv` is written to the repository root and uses:

```text
segment_id,start_time,end_time,operation,status,n_rows
```
