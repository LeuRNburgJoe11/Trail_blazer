# RailPulse

**Current React dashboard setup:** use [DASHBOARD_SETUP.md](../../docs/DASHBOARD_SETUP.md).
It supersedes the historical installation commands below. Do **not** use
`pip install -e .` for the integrated dashboard. Door/SHM use canonical subprocess
inference, while ACV/Rail use the nested pipelines; SHM is not stubbed in this UI.

The dashboard now includes subsystem-scoped chat and an Assistant workspace.
See [integration startup and boundaries](../../docs/DASHBOARD_ASSISTANT_INTEGRATION.md).
Use the repository `.venv` for the backend; the assistant is isolated from this
directory's duplicate Python package. The separate port-8766 prototype is not needed.

> Integration note: this directory is a separate experimental React/FastAPI and
> legacy Streamlit package, not the audited four-subsystem deployment. The canonical
> runtime is the repository-root `src/railpulse`, launched through `app/main.py`,
> with `outputs/combined/architecture-audit-final/models`. See the
> [root README](../../README.md) and [architecture audit](../../docs/ARCHITECTURE_AUDIT.md).
> SHM's stub status below applies only to this nested prototype; the canonical SHM
> implementation is complete. This prototype uses its own model registry and has
> not been integrated with the audited decision layer. Do not install its duplicate
> `railpulse` package into the canonical runtime's Python environment.

Team TrailBlazer's submission for the LTA x NebulaX Hackathon, Problem Statement 3
(train condition monitoring). One shared platform, four specialist pipelines --
see the architecture review doc for the full reasoning behind this structure.

**Status:** Door, ACV, and Rail Corrugation are implemented and validated
against the real datasets. SHM is stubbed (`src/railpulse/shm`) -- not
started yet.

## Layout

```
railpulse/
  app/app.py                    # Streamlit app -- compulsory non-technical-user deliverable
  src/railpulse/
    core/
      schemas.py                 # shared result types (DoorResult, ACVResult, ...)
      metrics.py                 # official evaluators (IoU-weighted F1, rank-decay)
      submission.py               # exact submission CSV formats + export validation
      registry.py                  # fitted-artifact registry (model + metadata)
    door/
      loader.py  segmentation.py  features.py  pipeline.py
    acv/
      loader.py  peer_features.py  ranking.py  pipeline.py
    rail/
      loader.py  speed.py  spectral_features.py  features.py  pipeline.py
    shm/    pipeline.py           # NOT IMPLEMENTED -- stub, raises on import
  configs/door.yaml  configs/acv.yaml  configs/rail.yaml
  scripts/           # train / evaluate / predict CLI entry points
  tests/             # metrics + submission unit tests, data-gated smoke tests
```

## App: two options

**`app/app.py`** -- Streamlit, single process, zero setup beyond `pip install streamlit`.
Kept as the safe fallback.

**`backend/` + `frontend/`** -- FastAPI + React, if you want a more custom look for
the demo video. Both call the exact same `railpulse` pipeline code as the
Streamlit app and the CLI scripts -- no separate modelling logic to keep in sync.

```bash
# Terminal 1 -- backend (from the railpulse/ root, after pip install -e .)
pip install fastapi uvicorn python-multipart
uvicorn backend.main:app --reload --port 8000

# Terminal 2 -- frontend
cd frontend
npm install
npm run dev   # http://localhost:5173, talks to the backend on :8000
```

Both need the registry populated first (`scripts/train_door.py`,
`scripts/train_rail.py`) same as the Streamlit app. For a demo-video-ready
build: `cd frontend && npm run build`, then serve `frontend/dist/` any way
you like (`npx serve dist`, or point FastAPI's `StaticFiles` at it).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install streamlit pytest  # app + tests
```

## Get the data

Sparse-clone just Door + ACV from the organiser repo (full repo is ~7.6 GB
because of Rail/SHM; this is ~65 MB):

```bash
git clone --filter=blob:none --no-checkout --depth 1 \
  https://github.com/aochinwen/NebulaX-Hackathon-ProblemStatement.git nebula
cd nebula
git sparse-checkout init --cone
git sparse-checkout set \
  PS3/02_Datasets/Door PS3/02_Datasets/ACV PS3/02_Datasets/Rail_Corrugation \
  PS3/03_References/Door PS3/03_References/ACV PS3/03_References/Rail_Corrugation
git checkout main
cd ..
```

## Run it

```bash
# Door: train, evaluate end-to-end, register the fitted model
python scripts/train_door.py --data-dir nebula/PS3/02_Datasets/Door

# Door: predict on the held-out Test.csv
python scripts/predict_door.py --input nebula/PS3/02_Datasets/Door/Test.csv

# ACV: leave-one-case-out validation over the 6 labelled training cases
python scripts/evaluate_acv.py --data-dir nebula/PS3/02_Datasets/ACV

# ACV: predict on the held-out test case
python scripts/predict_acv.py --input nebula/PS3/02_Datasets/ACV/Test/acv_test_case.xlsx

# Rail: extract features in chunks (272 files is slow in one call in some
# environments -- rerun with increasing --start until it reports 0 new rows)
python scripts/extract_rail_features.py --data-dir nebula/PS3/02_Datasets/Rail_Corrugation/Train \
  --output rail_features_train.csv --start 0 --limit 100
python scripts/extract_rail_features.py --data-dir nebula/PS3/02_Datasets/Rail_Corrugation/Train \
  --output rail_features_train.csv --start 100

# Rail: validate with stratified CV, fit on all data, register
python scripts/train_rail.py --feature-cache rail_features_train.csv \
  --labels nebula/PS3/02_Datasets/Rail_Corrugation/Train_Labels.csv

# Rail: predict on the held-out test files
python scripts/predict_rail.py --input-dir nebula/PS3/02_Datasets/Rail_Corrugation/Test

# The app (needs scripts/train_door.py and scripts/train_rail.py run at least once first)
streamlit run app/app.py

# Tests -- metrics/submission run with no data; smoke tests need env vars
pytest tests/ -v
RAILPULSE_DOOR_DIR=nebula/PS3/02_Datasets/Door \
RAILPULSE_ACV_DIR=nebula/PS3/02_Datasets/ACV \
RAILPULSE_RAIL_FEATURE_CACHE=rail_features_train.csv \
RAILPULSE_RAIL_LABELS=nebula/PS3/02_Datasets/Rail_Corrugation/Train_Labels.csv \
  pytest tests/ -v
```

## Current validated numbers

- Door: held-out end-to-end IoU-weighted F1 ~0.985 (time-based holdout within Train.csv)
- ACV: mean leave-one-case-out rank-decay score ~0.958 across the 6 labelled cases
- Rail: mean 5-fold stratified-CV macro F1 ~0.63 (vs. ~0.33 for an always-predict-Normal model)

These are real, non-leaked pipeline evaluations (segmentation + classification
together for Door; independent per-case/per-fold scoring for ACV/Rail) -- not
idealised numbers computed only on perfectly-detected examples.

## Next steps (see architecture review for full detail)

- Door: try MiniRocket + linear classifier as the challenger; tighten
  boundary rules using position-derivative in addition to the current flags.
- ACV: add running-mode-aware peer grouping; try a PCA-reconstruction
  residual as an extra feature once you're ready to move past `v0_baseline`.
- Rail: tune the per-side decision threshold via CV (macro F1 rewards
  trading some Normal precision for minority-class recall); try order-domain
  features alongside the wavenumber features.
- SHM: not started -- read its Info Kit and architecture review Section 05
  before beginning.
