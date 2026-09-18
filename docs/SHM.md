# SHM implementation and run guide

SHM predicts one cumulative fatigue-damage value per stress recording. The current
model uses rainflow cycle amplitudes with a calibrated fifth-power damage proxy.
On two repetitions of nested eight-fold validation of the 64 training files, the
complete model-selection procedure achieved **MAPE 0.025623 (2.5623%) and score
0.974377**. These are local validation results, not an organiser test score.

## Setup and use

From the repository root, using Python 3.11 or later (tested on Python 3.13):

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-shm-app.txt
.venv/bin/python scripts/shm/download_data.py
.venv/bin/python scripts/shm/train.py
.venv/bin/python scripts/shm/predict.py \
  --input data/SHM/Test \
  --output outputs/shm/shm_predictions.csv \
  --evidence outputs/shm/test_evidence.json
.venv/bin/python scripts/shm/verify.py
.venv/bin/python -m pytest -q tests/shm
.venv/bin/python -m streamlit run app/shm.py
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
For backend-only installation, use `requirements-shm.txt`. The existing team-wide
tests additionally require the root `requirements.txt` dependencies. The supplied
model checks its scikit-learn and rainflow versions on loading. The frozen model is
available at `models/shm/model.joblib`; it can be used without retraining.

In the app, upload the 16 CSV files from `data/SHM/Test`, then download
`shm_predictions.csv`. The panel can be integrated into the team's shared app by
calling `render_shm_panel` from `app/shm.py`. The official specification requires a
single app for all attempted subsystems, a demonstration video, and prediction CSVs
inside `predictions.zip`; this component supplies the SHM workflow, not the team's
complete submission package.

The prediction command also accepts a single recording. Its `--output` argument is
a CSV filename, and `--artifact` can select another fitted model. Inference does not
load labels or fit any model or transformation.

## Verified dataset and assumptions

The data and references come from organiser commit
`966c976005db2e3e40a691cff268fdb8f396a5df`. The downloader retrieves only SHM files,
the official SHM Info Kit, the shared specification and the example output schema.
Every download is checked against the pinned Git blob hash, and SHA-256 hashes are
recorded in `references/SHM/source_manifest.json`. Existing files that differ from
the source are rejected rather than overwritten. Approximately 526 MB of raw data
are kept locally and excluded from Git; the downloader reproduces them.

There are 64 labelled training files and 16 unlabelled test files. The training
recordings each contain **581,120 samples in one numeric, headerless column**. The
first value is a sample and must not be consumed as a column heading. Training
damage ranges from approximately 0.028620 to 0.928339. File numbering is random,
not temporal and not a model feature. The documentation describes healthy operation
on two lines at AW0/AW4 loads, but does not provide per-file line/load/run metadata.
It also does not specify the stress units, sample rate, material S-N constants, or
all details of how the reference labels were generated.

The loader rejects empty, short, multicolumn, headed, missing, nonnumeric and
non-finite input. It does not smooth, interpolate, resample or normalise stress
magnitude. No time duration or stress unit is fabricated.

## Model and architecture choices

`rainflow==3.2.0` counts cycles using its ASTM E1049 implementation. Monotonic
stretches and plateaus are compressed before counting; this preserves reversals.
Tests compare the accelerated path against the uncompressed library output on
random signals and check known triangles, monotonic signals, plateaus and constant
stress. Residual half cycles receive weight 0.5. Stress amplitude means **range / 2**.

For exponent m, the damage proxy is:

```text
P_m = sum(cycle_count * amplitude ** m)
prediction = scale * P_m
```

The fitted scale minimises training MAPE exactly for each fixed exponent: it is
the weighted median of `damage / P_m` with weights `P_m / damage`. The scale is
learned anew inside every training fold. This makes the calibration directly match
the competition objective without inventing material constants. The fitted-exponent
challenger searches a predeclared grid from 2.0 to 8.0 in steps of 0.1, entirely
inside each fit. It also selected exponent 5.0, tying the simpler fixed-exponent
model; deterministic tie-breaking keeps the simpler model.

The fixed candidate portfolio contains a MAPE-optimal constant, exponent-3 and
exponent-5 physics models, a fitted-exponent model, log-target ridge regression on
statistics, ridge regression with cycle features, and compact Extra Trees.
Learned scalers are inside the ridge training pipeline. Exponent/scale parameters
are empirical calibration for this dataset, not measured material properties.
Mean-stress correction is not assumed because the required material parameters and
the organiser's correction convention are unavailable.

Features include stress distribution summaries, count-weighted amplitude quantiles,
residual half-cycle contribution, and amplitude power sums. Feature caching is
label-free and keyed by file checksum, feature version and rainflow version; a
fixed column schema is used whether the features come from cache or fresh signals.

## Evaluation evidence

| Candidate | Mean absolute percentage error | Score |
|---|---:|---:|
| Constant fitted for MAPE | 56.8284% | 0.431716 |
| Rainflow exponent 3 | 43.4672% | 0.565328 |
| Rainflow exponent 5 | **2.5623%** | **0.974377** |
| Rainflow fitted exponent | 2.5623% | 0.974377 |
| Ridge on generic statistics | 31.1515% | 0.688485 |
| Ridge including cycle features | 8.3852% | 0.916148 |
| Extra Trees | 5.5110% | 0.944890 |

Outer validation uses two shuffled eight-fold partitions (seeds 42 and 137).
Within each outer training subset, four-fold validation selects a candidate.
The selected candidate is fitted to that outer training subset and evaluated only
on the outer held-out files. Exponent 5 won in all 16 outer folds. The reported
selection score pools 128 predictions for **64 unique files**, not 128 independent
recordings. Its fold MAPE standard deviation was 0.008720; worst individual
held-out relative error was 13.6927%. A final eight-fold training-only comparison
selects the deployable model, which is then fitted to all 64 training labels.

The exact metric is `max(0, 1 - mean(abs(y - prediction) / abs(y)))`, using
fraction MAPE. Zero/negative reference targets are rejected because the official
zero-target rule is unspecified and all supplied targets are positive. Scores
are computed after pooling file errors, rather than averaging separately floored
fold scores. Invalid predictions are rejected instead of silently repaired.

All candidates use the same splits. `outputs/shm/out_of_fold_predictions.csv`
contains the per-file predictions for every candidate and the nested selection
procedure; `validation_splits.json` records both outer and inner membership.
`model_comparison.csv`, `training_summary.json`, and `train_manifest.csv` provide
the aggregate results, selection rationale, and data provenance. `model.json`
stores feature schema, training ranges, environment versions, code hashes, input
hashes, selection evidence and the fitted artifact checksum.

File-level validation cannot establish independence between recordings from the
same undisclosed acquisition run. If verified run or condition IDs become available,
pass `--groups groups.csv` with columns `filename,group` to training; nested
GroupKFold keeps those groups intact. At least three independent groups are needed
for nested splitting. Do not infer groups from filenames or damage labels.
No test labels are public, and no test features are used to select the model.

## Diagnostics and integration

Generate training diagnostics with:

```bash
.venv/bin/python scripts/shm/report.py
```

The resulting `validation_diagnostics.png` shows model comparison and held-out
errors. `signal_and_cycle_diagnostics.png` shows an actual training stress trace,
counted cycles, and amplitude contributions to the damage proxy.

```python
from railpulse.shm.pipeline import analyse_shm

result = analyse_shm("data/SHM/Test/test01.csv", "models/shm/model.joblib")
print(result.prediction)
print(result.evidence)
print(result.warnings)
```

For a non-installed checkout, add `src` to `PYTHONPATH` before importing. For
multiple files, load the artifact once and call `analyse_shm(..., artifact=artifact)`.
`SHMResult` supplies a numeric prediction, cycle/stress evidence, quality warnings,
source checksum and measured inference duration. The inference and export code is
identical for the CLI and the app adapter. Range warnings flag sample count, stress
scale, maximum amplitude and cycle count outside the training envelope; they are
diagnostics, not calibrated confidence intervals. Remaining useful life and
maintenance deadlines cannot be inferred from these per-record estimates alone.

`scripts/shm/verify.py` checks exact app/CLI CSV agreement for all distributed test
files, unchanged model bytes, complete source IDs, no exact train/test duplicates,
and inference timing. Results go to `outputs/shm/verification.json`. The CSV schema
is exactly `file_id,prediction`, with original filenames including `.csv`, one row
per input, and finite nonnegative values. The exporter rejects duplicate, missing
and unexpected IDs. Load only trusted joblib artifacts; the checksum checks file
integrity but is not a signature.

## Source references

- [Official SHM Info Kit](https://github.com/aochinwen/NebulaX-Hackathon-ProblemStatement/blob/966c976005db2e3e40a691cff268fdb8f396a5df/PS3/03_References/SHM/SHM_Info_Kit.md)
- [Official submission and scoring specification](https://github.com/aochinwen/NebulaX-Hackathon-ProblemStatement/blob/966c976005db2e3e40a691cff268fdb8f396a5df/PS3/01_Problem_Statement_3_Specifications.md)
- [Rainflow counting implementation](https://github.com/iamlikeme/rainflow)
