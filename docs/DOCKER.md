# Docker deployment (local development/demo)

This stack serves only the React dashboard and RailPulser backend. Streamlit and
the legacy standalone prototype are not deployed, and Streamlit is not installed
in the runtime image. Their source files remain in the repository unchanged.

Install Docker Engine with Compose v2, or start Docker Desktop. No host Python
or Node installation is needed. Build from the repository root:

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 backend dashboard
```

Open **http://127.0.0.1:5173**. If that host port is occupied, choose another
one with `DASHBOARD_PORT=5174 docker compose up --build -d` (PowerShell:
`$env:DASHBOARD_PORT=5174; docker compose up --build -d`). React is built once and served by nginx, which
proxies `/api` to the private backend. Port 8000 is not published. The assistant
retains its localhost host/origin restrictions; do not change the public port
without updating those restrictions. Stop any previous local Vite process on
the selected host port first.
Only ports 5173 and 5174 are currently allowed by the assistant's browser-origin
policy. Other values can load the UI but will reject chat requests.
Provider SDKs are included. Enter your key and consent in the UI; do not bake keys
into images or pass them as Docker build arguments. API use needs internet access.

The Python container runs as a non-root user. Canonical and nested Python packages
remain isolated by the existing subprocess boundaries. Only one backend worker is
used because uploaded-result snapshots are process-local. Restarting the backend
invalidates chat snapshots; upload/run analysis again. Runtime uploads are temporary,
not a durable archive, and are not automatically cleaned per request. Recreate the
backend periodically to clear its temporary files. Do not expose this unauthenticated
demo publicly; Docker does not add authentication, TLS or production isolation.

## Check and test

```bash
docker compose run --rm tools
docker compose run --rm -e PYTHONPATH=/workspace/src tools python -m pytest tests/test_dashboard_assistant.py tests/test_dashboard_general.py tests/test_assistant_api.py -q
docker compose exec backend python /workspace/scripts/smoke_dashboard_http.py --base-url http://dashboard:8080
```

In the UI, ask General “What does SHM mean?”, then upload an SHM recording, run
analysis and ask “Explain this result”. Confirm the filename and damage agree.
General has documentation only; choose a subsystem for uploaded results.

The full canonical suite includes real-data tests. After preparing the datasets,
run `docker compose run --rm tools python -m pytest -p no:cacheprovider -q`.
Without those datasets, some tests fail or skip; the targeted integration tests
above do not need raw training data. The copied root `pytest.ini` keeps the
duplicate legacy suites separate.

## Door and Rail assets are still required

Docker includes committed models and reference documentation, **not** untracked
local registries or the 6+ GB raw datasets. SHM and ACV can analyse valid uploads
immediately. Door needs its Normal reference; Rail needs the nested dashboard's
trained registry model. Prepare them once in persistent named volumes:

```bash
docker compose run --rm tools python scripts/prepare_data.py --subsystem door rail
docker compose run --rm tools python app/railpulse/scripts/build_door_reference.py
docker compose run --rm -w /workspace/app/railpulse -e PYTHONPATH=/workspace/app/railpulse/src tools python scripts/extract_rail_features.py --data-dir /workspace/data/Rail_Corrugation/Train --output /workspace/data/rail_features_train.csv
docker compose run --rm -w /workspace/app/railpulse -e PYTHONPATH=/workspace/app/railpulse/src tools python scripts/train_rail.py --feature-cache /workspace/data/rail_features_train.csv --labels /workspace/data/Rail_Corrugation/Train_Labels.csv
docker compose run --rm tools python scripts/check_dashboard_setup.py --require-all
```

This downloads training data and trains the Rail model; allow disk space and time.
Do not substitute the canonical Rail model: it uses a different pipeline.
Alternatively copy a trusted compatible registry into the volume. Never load
untrusted joblib/pickle files. See [setup caveats](DASHBOARD_SETUP.md).

## Supporting batch tools

Batch training/evaluation/data preparation (explicit, never run at image build):

```bash
docker compose run --rm tools python scripts/prepare_data.py --subsystem all
docker compose run --rm tools python scripts/run_all.py --output /workspace/run-output/my-run-001
```

Use a new output directory for every run. Models baked into the image remain
unchanged. Export generated results before removing volumes, for example:

```bash
docker compose create tools
docker compose cp tools:/workspace/run-output/my-run-001 ./my-run-001
```

The optional `tools` service is for setup, tests and batch processing only;
it does not run another UI. It shares the backend runtime image.

## Shutdown / rebuild

```bash
docker compose down
# After pulling code updates:
docker compose up --build -d
```

Named data, registry and run volumes survive `down`. **Do not use `down -v` unless
you intend to permanently delete downloaded data, trained registry and batch outputs.**
Raw datasets, node_modules, venvs, git history, local registries and credential files
are excluded from the build context. Images use version-line tags rather than
immutable digests; record digests and fully lock transitive packages for a release.
