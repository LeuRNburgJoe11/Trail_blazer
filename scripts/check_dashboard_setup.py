#!/usr/bin/env python3
"""Read-only dashboard preflight. --require-all makes missing inference assets fatal."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app/railpulse"


def check(require_all=False):
    errors, missing = [], []
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        errors.append("Use Python 3.11–3.13 for the pinned runtime.")
    probe = subprocess.run(
        [sys.executable, "-c", "import fastapi, uvicorn, python_multipart, httpx, openpyxl, rainflow; import backend.main"],
        cwd=APP, capture_output=True, text=True,
    )
    if probe.returncode:
        errors.append("Backend import failed. Install requirements-dashboard.txt in this interpreter.\n" + probe.stderr[-2000:])
    probe = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); from railpulse.assistant.dashboard import DashboardAssistant; a=DashboardAssistant('general'); assert a.answer('What does SHM mean?')['answer'] == 'SHM means Structural Health Monitoring.'"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if probe.returncode:
        errors.append("Local assistant check failed. Keep the full repository including references/docs.\n" + probe.stderr[-2000:])
    for domain in ("door", "shm"):
        candidates = [ROOT / f"outputs/combined/{bundle}/models/{domain}.joblib"
                      for bundle in ("architecture-audit-final", "merged-main")]
        if not any(p.is_file() for p in candidates):
            missing.append(f"{domain.upper()}: checked-in canonical model artifact is missing.")
    reference = APP / "registry/door/normal_reference.json"
    try:
        value = json.loads(reference.read_text())
        if value.get("version") != 1 or not value.get("operations"):
            raise ValueError("invalid reference")
    except (OSError, ValueError, AttributeError):
        missing.append("Door: build registry/door/normal_reference.json using labelled training data.")
    registry = APP / "registry/rail"
    versions = sorted(p for p in registry.iterdir() if p.is_dir()) if registry.is_dir() else []
    if not versions or not all((versions[-1] / f).is_file() for f in ("model.joblib", "metadata.json")):
        missing.append("Rail: train or obtain a trusted dashboard registry model (not the canonical bundle).")
    for message in errors:
        print("ERROR:", message)
    for message in missing:
        print("ASSET NEEDED:", message)
    if not errors:
        print("PASS: backend imports and General/local assistant. Asset presence checks are not model-accuracy tests.")
    print("See docs/DASHBOARD_SETUP.md for Node setup, asset preparation and upload tests.")
    return 1 if errors or (require_all and missing) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-all", action="store_true")
    raise SystemExit(check(parser.parse_args().require_all))
