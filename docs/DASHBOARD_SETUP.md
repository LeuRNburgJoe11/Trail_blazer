# Teammate setup: dashboard + RailPulser

Use the `agentic-addition` branch and the **integrated** UI on port 5173.
The standalone prototype on 5174/8766 is not needed.

## First install (macOS/Linux)

Prerequisites: Git, Python 3.11–3.13, Node 22.12+ (or Node 20.19+).
Use a fresh environment without `--system-site-packages`. Do not install the
nested `app/railpulse` Python package with `pip install -e .`.

```bash
git clone --branch agentic-addition https://github.com/LeuRNburgJoe11/Trail_blazer.git
cd Trail_blazer
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dashboard.txt
# Optional: needed only for OpenAI/Anthropic answers, not local mode.
.venv/bin/python -m pip install -r requirements-dashboard.txt -r requirements-assistant.txt
.venv/bin/python scripts/check_dashboard_setup.py
cd app/railpulse/frontend
npm ci
npm run build
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
The shell commands below use macOS/Linux syntax.

## Run (two terminals)

Terminal 1, from the repository root:

```bash
cd app/railpulse
../../.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Terminal 2, from the repository root:

```bash
cd app/railpulse/frontend
npm run dev
```

Open **http://127.0.0.1:5173**. Use one backend worker. If a port is occupied,
stop your own earlier server or coordinate the change with the Vite proxy;
do not terminate an unidentified process. Refresh after backend changes.

## What works after installation?

- General/local chat: uses the committed knowledge documents; no key required.
- SHM: canonical fitted artifact is committed; upload a valid stress recording.
- ACV: rule-based ranking needs a valid uploaded ACV workbook, not a fitted registry.
- Door: classifier is committed, but its Normal reference must be generated below.
- Rail: the dashboard uses a separate registry model; train it below or obtain
  the matching trusted registry from the dashboard maintainer. Do not copy the
  canonical Rail artifact into this registry: they are different pipelines.

The preflight reports missing assets without stopping General/SHM/ACV testing.
Use `--require-all` to fail until all required asset files are present. Even a
passing preflight does not certify inference correctness; test real uploads.
Only load trusted model artifacts: joblib/pickle can execute code.

## Prepare missing Door and Rail assets

From the repository root, download the official training data using the existing
data-preparation pipeline (requires network and substantial disk space for Rail):

```bash
.venv/bin/python scripts/prepare_data.py --subsystem door
.venv/bin/python scripts/prepare_data.py --subsystem rail
.venv/bin/python app/railpulse/scripts/build_door_reference.py
cd app/railpulse
PYTHONPATH=src ../../.venv/bin/python scripts/extract_rail_features.py --data-dir ../../data/Rail_Corrugation/Train --output rail_features_train.csv
PYTHONPATH=src ../../.venv/bin/python scripts/train_rail.py --feature-cache rail_features_train.csv --labels ../../data/Rail_Corrugation/Train_Labels.csv
cd ../..
.venv/bin/python scripts/check_dashboard_setup.py --require-all
```

Generated registries and downloaded raw data are intentionally ignored by Git.
Door's current status badge checks the old registry and can still report no model;
successful upload inference is the relevant check for its canonical classifier.
Rail's static UI reference scores are not the validation of a newly trained model.

## Acceptance test

1. Open Assistant workspace. General should be selected; ask “What does SHM mean?”
   and expect “SHM means Structural Health Monitoring.”
2. Expand Instructions and Sample queries; change scopes and verify tailored defaults.
3. Upload a valid SHM file and run analysis. Ask “Explain this result”; compare the
   filename and damage with the dashboard. Choose the chat row selector explicitly.
4. Analyse another file: chat must use the new results, not old repository recordings.
5. Switch to a subsystem with no analysis: result questions should request data/scope.
6. General must ask for subsystem selection for uploaded-result questions.
7. Optionally select a provider/model, enter your own key and consent to sending
   compact evidence. Ask a non-definition explanation question. Verify the answer
   is labelled AI; errors must visibly fall back to local evidence. Exact verified
   definitions intentionally need no provider call. Provider account access/billing
   is required; a listed model is not a guarantee of account access.

Keys are session-memory only. Do not commit keys or expose the local demo publicly.
Snapshots expire after one hour and are lost on backend restart; rerun analysis.

Automated checks (repository root):

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_dashboard_assistant.py tests/test_dashboard_general.py -q
cd app/railpulse/frontend
npm run lint
npm run build
```
