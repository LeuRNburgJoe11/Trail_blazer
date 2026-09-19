# Run the Door Pipeline

For the official three-column submission and all four subsystems, use
`python scripts/run_all.py`; see [the integration guide](../../../../docs/INTEGRATION.md).
The legacy command below produces a **six-column diagnostic export**, not the
official `start_time,end_time,prediction` submission format.

Run these commands from the **repository root** -- every path below is relative to it,
not to this file's directory.

```powershell
@'
import sys
from pathlib import Path

sys.path.insert(0, "src")

from railpulse.core.submission import write_intervals
from railpulse.door.pipeline import run

base = Path("data/Door")
predictions = run(
    train_path=base / "Train.csv",
    labels_path=base / "Train_Segments_Answer.csv",
    test_path=base / "Test.csv",
)
write_intervals("door_predictions.csv", predictions)
print(f"Wrote {len(predictions)} intervals to door_predictions.csv")
'@ | python -
```

## How the pipeline works

The command runs five stages in order. In one sentence: it turns a continuous stream of
door-controller readings into discrete open/close operations, describes each operation by
how hard the motor had to work to complete it, and asks a tree ensemble which ones look
abnormal.

1. **Load** -- `door.loader.load_stream` reads the CSV as `utf-8-sig`, rejects the file up
   front if any of the 17 required fields is missing, requires finite numeric values and
   unique increasing timestamps, and builds one `DoorSample` per row. Each sample keeps the original timestamp
   *string* verbatim next to an epoch-seconds copy used only for arithmetic -- the string
   is what gets emitted at the end, so reported boundaries are byte-identical to the source
   and never lose precision to reformatting.

2. **Segment** -- `door.segmentation.detect_intervals` cuts the stream wherever the asserted
   command changes (`Close command` / `Open command`), plus an *effort-reset* heuristic:
   motor current falling from >=500 mA to <=500 mA and to <=75% of the previous sample while
   the leaf travels >=100 units. That second rule catches a fresh operation starting while
   the command line stays asserted, which a pure command-change detector would merge into
   one oversized interval. Activity comes from commands or movement flags; inactive gaps
   up to 0.25 s are bridged, while longer gaps end at the last active sample. Idle-only
   streams produce no operations. Anything under 0.5 s is discarded, and each interval
   is tagged `Open` or `Close`.

3. **Featurize** -- `door.features.extract_features` reduces each interval to ten numbers:
   duration; motor-current peak, mean, RMS, integral and standard deviation; an energy proxy
   (mean of current x voltage); net leaf-position change; *position stagnation*, the fraction
   of consecutive samples where the leaf did not move at all; and mean velocity. Stagnation
   and the current statistics are the pair that matter -- a door meeting abnormal resistance
   draws more current while moving less.

4. **Classify** -- `door.pipeline.DoorModel` fits a class-balanced Extra Trees (200 trees,
   `random_state=42`). Training rows come from `labelled_training_rows`, which keeps only
   those detected intervals whose start timestamp matches a row in
   `Train_Segments_Answer.csv` *exactly*, and takes that row's `status` as the label;
   intervals matching nothing are left out rather than mislabelled. Training validates
   labels and requires usable rows. Missing dependencies and unfitted inference fail
   explicitly: there is no silent majority-class fallback. Single-class training still
   fits the estimator.

5. **Emit** -- `predict_intervals` re-runs detection on the test stream, scores each interval,
   and `core.submission.write_intervals` writes the legacy diagnostic interval CSV columns in
   the fixed order below. Column order is enforced there, so the CSV cannot drift out of that
   schema. Note this is the six-column diagnostic export, not the official submission --
   use `scripts/run_all.py` for that.

## Smoke Check

To verify the training boundaries against the supplied reference annotations:

```powershell
$env:PYTHONPATH = "src"
python -c "from pathlib import Path; import csv; from railpulse.door.loader import load_stream; from railpulse.door.segmentation import detect_intervals; b=Path('data/Door'); s=load_stream(b/'Train.csv'); i=detect_intervals(s); r=list(csv.DictReader((b/'Train_Segments_Answer.csv').open(encoding='utf-8'))); assert len(i)==len(r)==110; assert [s[x.start_index].timestamp for x in i]==[x['start_time'] for x in r]; assert [s[x.end_index].timestamp for x in i]==[x['end_time'] for x in r]; print('Door boundary check passed')"
```

`door_predictions.csv` is written to the repository root and uses:

```text
segment_id,start_time,end_time,operation,status,n_rows
```
