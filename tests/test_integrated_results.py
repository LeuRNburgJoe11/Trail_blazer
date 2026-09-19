"""Regression checks on the checked-in successful integration run (no raw data needed)."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pandas as pd
import pytest

from railpulse.core.inference import load_bundle
from railpulse.core.predictions import validate_predictions

ROOT = Path(__file__).resolve().parents[1]
from railpulse.core.runtime import DEFAULT_RUN as RUN


def test_packaged_results_have_exact_coverage_and_hashes():
    summary = json.loads((RUN / "run_summary.json").read_text())
    lock = json.loads((ROOT / "configs/dataset_lock.json").read_text())
    assert summary["status"] == "complete"
    assert summary["data_integrity_verified"] and summary["frozen_artifacts_unchanged"]
    with zipfile.ZipFile(RUN / "predictions.zip") as archive:
        assert sorted(archive.namelist()) == [f"{name}_predictions.csv" for name in ("acv", "door", "rail", "shm")]
        assert archive.testzip() is None
        for subsystem in ("door", "acv", "rail", "shm"):
            filename = f"{subsystem}_predictions.csv"
            data = archive.read(filename)
            assert data == (RUN / filename).read_bytes()
            assert hashlib.sha256(data).hexdigest() == summary["predictions"][subsystem]["sha256"]
            frame = pd.read_csv(io.BytesIO(data))
            expected = [Path(entry["path"]).name for entry in lock["files"]
                        if entry["subsystem"] == subsystem and "/Test/" in entry["path"]
                        and Path(entry["path"]).suffix in (".csv", ".xlsx")]
            validate_predictions(subsystem, frame, expected_ids=None if subsystem == "door" else expected)
    assert hashlib.sha256((RUN / "predictions.zip").read_bytes()).hexdigest() == summary["predictions_zip_sha256"]


def test_integrated_shm_predictions_and_artifact_are_unchanged():
    assert (RUN / "shm_predictions.csv").read_bytes() == (ROOT / "outputs/shm/shm_predictions.csv").read_bytes()
    assert (RUN / "models/shm.joblib").read_bytes() == (ROOT / "models/shm/model.joblib").read_bytes()
    assert (RUN / "models/acv.pkl").read_bytes() == (ROOT / "models/acv/acv_model_artifact.pkl").read_bytes()


def test_frozen_bundle_is_loadable():
    bundle = load_bundle(RUN / "models")
    assert bundle["metadata"]["rail_model"] == "pooled_spatial"


def test_run_source_snapshot_matches_canonical_implementation():
    summary = json.loads((RUN / "run_summary.json").read_text())
    for relative, checksum in summary["source_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == checksum, relative


def test_rail_cv_covers_each_train_file_once_per_candidate():
    folds = pd.read_csv(RUN / "rail_oof_predictions.csv")
    for _, rows in folds.groupby("model"):
        assert len(rows) == 272
        assert rows.file_id.nunique() == 272
        assert rows.fold.nunique() == 5
    assert folds.groupby("file_id").fold.nunique().eq(1).all()


def test_unified_app_renders_all_four_modes():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(ROOT / "app/main.py")).run()
    for name in ("door", "acv", "rail", "shm"):
        app.selectbox[0].select(name).run()
        assert not app.exception
