# Integrated RailPulse workflow

**Current deployment:** the [architecture audit](ARCHITECTURE_AUDIT.md) supersedes
the original merge-run model paths below. Use
`outputs/combined/architecture-audit-final/models` (the app/CLI default).
The `merged-main` figures and artifacts below remain historical evidence;
version-1 bundles are not accepted by the source-bound version-2 runtime.

The canonical implementation is `src/railpulse/`. All four subsystems now share
`railpulse.core.inference.predict_file` for both the batch runner and the unified
Streamlit application. Fitting only reads training data. Uploads never retrain.

## Setup and full run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-all.txt
python scripts/prepare_data.py --subsystem all
python scripts/run_all.py
python -m pytest -q
```

`run_all.py` creates a new timestamped directory under `outputs/combined/`.
Choose another **new** directory with `--output PATH`; existing directories are
refused, including incomplete runs. By default, all raw checksums, channel
schemas, train/test counts and label coverage are checked before training.
`--skip-data-verification` is an explicit debugging option and is recorded in
the report; it is not recommended for final predictions.

Each completed run contains:

- `door_predictions.csv`: `start_time,end_time,prediction` (not the legacy
  six-column diagnostic interval format).
- `acv_predictions.csv`: `file_id,ranked_cars`, preserving native two-digit IDs.
- `rail_predictions.csv`: `file_id,prediction` with the three official classes.
- `shm_predictions.csv`: `file_id,prediction` with finite nonnegative damage.
- `predictions.zip`: exactly those four CSVs, directly at the ZIP root.
- `models/`: frozen models and a checksum-protected `bundle.json`.
- Training feature tables, Rail out-of-fold predictions, ACV validation folds,
  and `run_summary.json` containing source/runtime/data provenance, validation
  results, test-file coverage, output hashes and warnings.

Failed runs retain `status: failed` and their error in `run_summary.json`. The
ZIP is not published until all four predictions pass validation. Existing
successful runs are never overwritten. Inference checks that artifacts stay
unchanged, and all test filenames must be covered exactly once.

## Models and validation

| Subsystem | Integrated implementation | Validation |
|---|---|---|
| Door | Existing deterministic segmentation + Extra Trees | Chronological 70/30 split between complete cycles; end-to-end official IoU-weighted F1 |
| ACV | ACV branch's selected, frozen context-matched baseline | Re-extract all six training cases and rerun leave-one-case-out ranking evaluation |
| Rail | Compare existing Extra Trees against pooled side classifier with speed-normalized spectral bands | Identical five stratified file-level folds; a file's two sides never enter different folds |
| SHM | Existing checksum-verified frozen rainflow damage model | Retain existing nested-CV report; rerun test inference, not model selection |

Rail adopts the new branch's physical side-pooling design in the canonical
`rail/spatial.py`. Vibration and shock features are aggregated separately to
avoid mixing units. Speed decoding uses a fixed binary pulse threshold rather
than the signal median (which can be 1 for high-duty-cycle signals). Its loader
now rejects malformed channels and nonfinite values instead of silently
replacing missing sensor readings with zero. The selected model is determined
using training folds only, before any test inference.

The nested `src/railpulse/rail/railpulse/` tree is preserved as a historical
prototype from the Rail branch; it is **not** imported by the integrated runner
or app. Do not add its `src` directory to `PYTHONPATH` or install that nested
package over this one. Existing subsystem entry points are retained for
backward compatibility; use the unified runner for the combined results.

Validation results are not held-out test scores. ACV has only six independent
cases, and Rail CV is also used to select between candidates, so those estimates
can be optimistic. Recording/session grouping information for Rail is not
available. The four validation protocols differ; no purported official overall
test score is calculated. Only the organisers have the test labels.

### Completed merge run

`outputs/combined/merged-main/run_summary.json` records a successful full run:

| Subsystem | Validation result | Test output |
|---|---|---|
| Door | 1.000 IoU-weighted F1 on 33 chronological holdout cycles | 38 predicted segments |
| ACV | 0.97917 rank-decay; correct car ranked first in 5/6 cases | 1 eight-car ranking |
| Rail | 0.78764 mean fold macro F1 (pooled spatial), versus 0.66740 (Extra Trees) | 68 file predictions |
| SHM | Existing nested-CV report retained; frozen predictions byte-identical | 16 damage predictions |

The full run took approximately 191 seconds on the integration machine. Two SHM
recordings retain out-of-training-range warnings (`test03.csv`: maximum cycle
amplitude; `test06.csv`: cycle count). These warnings are not suppressed.

## Unified application

```bash
python -m streamlit run app/main.py
```

The default model path points to the checked-in `outputs/combined/merged-main/models`
bundle. Change it in the sidebar to a new run's `models/` directory if needed.
Choose Door, ACV, Rail or SHM; upload CSV (or ACV XLSX) recordings; analyse; and
download the corresponding CSV. Door accepts one continuous stream. Other
subsystems accept multiple files and accumulate predictions across batches of
up to 250 MB; re-uploading the same filename replaces its previous prediction.
Changing the model bundle clears prior session predictions to avoid mixing
models. The ZIP download contains only the subsystems analysed in that session.
Check full test coverage before submission; a partial upload is not a complete
official submission. Only load trusted local pickle/joblib model bundles.

The application and batch runner share inference and export validation; the
integration run's ZIP is a reproducible batch result, not evidence that the
complete UI/demo-video submission requirement has been fulfilled.

## Merge and dataset notes

Latest remote `main` already included `Rail__Corrugation`. ACV was merged first,
then SHM, then data preparation, preserving their history and selected artifacts.
There were no textual merge conflicts. Semantic fixes include the Door export
contract, rejecting missing ACV artifacts rather than silently switching models,
Rail source consolidation, and official mixed-header/data newline verification.

Some historical branches tracked raw data and Python bytecode. These are not
necessary versioned build artifacts: data is reproduced from
`configs/dataset_lock.json`; Python creates its own caches. Historical commits
are retained without rewriting history. Raw inputs remain on disk.
