import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from railpulse.core.combined import run_all
from railpulse.core.data_preparation import inspect_files
from railpulse.core.inference import load_bundle, predict_file
from railpulse.core.metrics import door_iou_weighted_f1
from railpulse.core.predictions import csv_bytes, validate_predictions
from railpulse.rail.loader import load_recording
from railpulse.rail.spatial import extract_spatial_features
from railpulse.rail.speed import estimate_speed


def interval(start=0, end=100, status="Normal"):
    return {"start_time": f"2023-7-5-0-0-0-{start}", "end_time": f"2023-7-5-0-0-0-{end}", "prediction": status}


def test_door_official_metric_penalizes_wrong_labels_and_duplicates():
    assert door_iou_weighted_f1([interval()], [interval()]) == 1
    assert door_iou_weighted_f1([interval(status="Abnormal resistance")], [interval()]) == 0
    assert door_iou_weighted_f1([interval(), interval()], [interval()]) == pytest.approx(2 / 3)
    assert door_iou_weighted_f1([interval(end=50)], [interval()]) == .5
    assert door_iou_weighted_f1([], []) == 0


def test_official_door_export_has_three_columns():
    exported = csv_bytes("door", pd.DataFrame([interval()]))
    assert exported.splitlines()[0] == b"start_time,end_time,prediction"


def test_door_rejects_overlapping_predictions():
    with pytest.raises(ValueError, match="nonoverlapping"):
        validate_predictions("door", pd.DataFrame([interval(), interval()]))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_shm_rejects_invalid_damage(value):
    with pytest.raises(ValueError):
        validate_predictions("shm", pd.DataFrame({"file_id": ["test.csv"], "prediction": [value]}))


def test_prediction_ids_cover_exact_inputs():
    frame = pd.DataFrame({"file_id": ["test.csv"], "prediction": ["Normal"]})
    with pytest.raises(ValueError, match="exactly"):
        validate_predictions("rail", frame, expected_ids=["test.csv", "other.csv"])
    with pytest.raises(ValueError, match="Duplicate"):
        validate_predictions("rail", pd.concat([frame, frame]))


@pytest.mark.parametrize("ranking", ["01|01", "1|02", "01|03"])
def test_acv_requires_exact_unique_native_car_ids(ranking):
    frame = pd.DataFrame({"file_id": ["test.xlsx"], "ranked_cars": [ranking]})
    with pytest.raises(ValueError):
        validate_predictions("acv", frame, expected_cars={"test.xlsx": ["01", "02"]})


def test_speed_uses_fixed_binary_threshold_not_signal_median():
    signal = np.tile([0, 1, 1, 1, 1], 2000)
    assert estimate_speed(signal) == pytest.approx(2000 * np.pi * .85 / 90)


def test_spatial_features_are_finite_and_side_specific():
    values = np.zeros((10_000, 129))
    values[:, 1::4] = np.sin(np.arange(10_000)[:, None] * .1)
    features = extract_spatial_features(values)
    assert np.isfinite(list(features.values())).all()
    assert features["s0_0_rms_max"] > .5
    assert features["s1_0_rms_max"] == 0
    assert features["s0_1_rms_max"] == 0


def test_rail_does_not_silently_replace_malformed_values(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(",".join(["0"] * 129) + "\n")
    with pytest.raises(ValueError, match="10,000"):
        load_recording(path)


def test_missing_acv_artifact_never_falls_back():
    from railpulse.acv.pipeline import analyse_acv
    with pytest.raises(FileNotFoundError, match="artifact"):
        analyse_acv("unused.xlsx", "nonexistent-model.pkl")


def test_bundle_detects_tampering_before_deserialization(tmp_path):
    (tmp_path / "model.joblib").write_bytes(b"untrusted")
    (tmp_path / "bundle.json").write_text(json.dumps({"version": 1, "sha256": {"model.joblib": "wrong"}}))
    with patch("railpulse.core.inference.joblib.load") as deserialize:
        with pytest.raises(ValueError, match="checksum"):
            load_bundle(tmp_path)
        deserialize.assert_not_called()


def test_combined_run_refuses_to_overwrite_existing_output(tmp_path):
    with pytest.raises(FileExistsError):
        run_all(tmp_path, tmp_path)


def test_mixed_source_newlines_are_verified_exactly(tmp_path):
    source = b"header\n1\r\n2\r\n"
    local = source.replace(b"\r\n", b"\n")
    (tmp_path / "signal.csv").write_bytes(local)
    entry = {"path": "signal.csv", "bytes": len(source),
             "git_blob_sha1": hashlib.sha1(f"blob {len(source)}\0".encode() + source).hexdigest()}
    assert inspect_files(tmp_path, [entry])[0]["status"] == "verified_line_endings"
    assert (tmp_path / "signal.csv").read_bytes() == local
