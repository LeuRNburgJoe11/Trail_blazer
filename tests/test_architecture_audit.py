import hashlib
import importlib.metadata
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from railpulse.acv.data_quality import extract_data_quality_features
from railpulse.acv.peer_features import extract_peer_features, get_context_matched_peer_median
from railpulse.acv.preprocessing import resolve_parameter
from railpulse.acv.validation import evaluate_baseline_loocv
from railpulse.acv.control_features import extract_control_features
from railpulse.core.bundle_contract import ARTIFACTS, inference_fingerprint
from railpulse.core.inference import load_bundle
from railpulse.core.predictions import csv_bytes, SCHEMAS
from railpulse.core.runtime import DEFAULT_RUN
from railpulse.door.loader import DoorSample
from railpulse.door.segmentation import detect_intervals
from railpulse.door.pipeline import DoorModel
from railpulse.rail.side_model import RailClassifier


def test_invalid_status_is_not_valid_and_unknown_is_not_invented():
    frame = pd.DataFrame({"ACV Information Valid": ["Valid", "Invalid", None]})
    assert extract_data_quality_features(frame, pd.Series(range(3)))["information_valid_fraction"] == pytest.approx(1 / 3)
    assert resolve_parameter(pd.DataFrame({"ACV Grounding Detection Status": [1]}), "ACV Information Valid").isna().all()


def test_canonical_setpoints_do_not_get_lost_in_alias_resolution():
    assert resolve_parameter(pd.DataFrame({"Cooling Setpoint": [24.]}), "Cooling Setpoint").iloc[0] == 24


def test_peer_mad_is_symmetric_and_missingness_breaks_persistence():
    result = extract_peer_features(pd.Series([-3., -3., np.nan, -3.]), pd.Series([0.] * 4))
    assert result["peer_residual_mad"] == 0
    assert result["peer_longest_persistent_deviation"] == 2


def test_absent_peers_remain_missing_without_runtime_warnings():
    frame = pd.DataFrame({"Indoor Average Temperature": [np.nan], "ACV Running Mode": ["Cooling"], "Cooling Setpoint": [24.], "Load Halved": [0]})
    with __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("error", RuntimeWarning)
        result = get_context_matched_peer_median({"01": frame, "02": frame}, "Indoor Average Temperature")
    assert result.isna().all().all()


def test_control_negation_and_unknown_duration_are_not_misclassified():
    frame = pd.DataFrame({"ACV Running Mode": ["Not cooling", "Cooling", None, "Cooling"]})
    result = extract_control_features(frame, pd.Series(["unknown"] * 4))
    assert result["active_cooling_duty_cycle"] == .5
    assert np.isnan(result["state_transition_rate_per_hour"])
    assert result["number_of_state_changes"] == 1


def samples(active):
    return [DoorSample(f"2023-7-5-0-0-{i}-0", float(i), {"Open command": float(flag)}) for i, flag in enumerate(active)]


def test_idle_stream_does_not_invent_a_door_cycle():
    assert detect_intervals(samples([0, 0, 0, 0])) == []
    assert csv_bytes("door", pd.DataFrame(columns=SCHEMAS["door"])) == b"start_time,end_time,prediction\n"


def test_idle_gaps_trim_and_separate_door_operations():
    intervals = detect_intervals(samples([0, 1, 1, 0, 0, 1, 1, 0]))
    assert [(item.start_index, item.end_index) for item in intervals] == [(1, 2), (5, 6)]


def test_short_idle_gap_is_bridged():
    stream = [DoorSample(str(i), i / 10, {"Open command": float(i != 5)}) for i in range(12)]
    assert len(detect_intervals(stream)) == 1


@pytest.mark.parametrize("model", [DoorModel(), RailClassifier()])
def test_unfitted_classifiers_never_silently_predict_normal(model):
    with pytest.raises(ValueError, match="not fitted"):
        model.predict([{}])


def test_acv_evaluation_rejects_unlabelled_cases_instead_of_skipping():
    with pytest.raises(ValueError, match="coverage"):
        evaluate_baseline_loocv(pd.DataFrame({"case_id": ["case"], "car_id": ["01"]}), {})


@pytest.fixture
def bundle_metadata(tmp_path):
    for name in ARTIFACTS:
        (tmp_path / name).write_bytes(b"not-deserialized-by-tests")
    return {"version": 2, "rail_model": "pooled_spatial", "inference_sha256": inference_fingerprint(),
            "sha256": {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() for name in ARTIFACTS},
            "runtime_versions": {name: importlib.metadata.version(name) for name in
                                 ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "rainflow", "openpyxl")}}


@pytest.mark.parametrize("fault", ["missing_artifact", "code_drift", "runtime", "unknown_model", "tampered_artifact"])
def test_bundle_fails_before_deserialization(tmp_path, bundle_metadata, fault):
    metadata = bundle_metadata
    if fault == "missing_artifact":
        metadata["sha256"].pop("acv.pkl")
    elif fault == "code_drift":
        metadata["inference_sha256"] = {}
    elif fault == "runtime":
        metadata["runtime_versions"]["pandas"] = "invalid"
    elif fault == "unknown_model":
        metadata["rail_model"] = "typo"
    else:
        (tmp_path / "door.joblib").write_bytes(b"tampered")
    (tmp_path / "bundle.json").write_text(json.dumps(metadata))
    with patch("railpulse.core.inference.joblib.load") as deserialize:
        with pytest.raises(ValueError):
            load_bundle(tmp_path)
        deserialize.assert_not_called()


def test_rail_nested_selection_excludes_outer_validation():
    folds = json.loads((DEFAULT_RUN / "rail_nested_validation.json").read_text())
    held_out = []
    for fold in folds:
        outer_train, outer_valid = set(fold["training_files"]), set(fold["validation_files"])
        assert not outer_train & outer_valid
        held_out.extend(outer_valid)
        for inner in fold["inner_splits"]:
            train, valid = set(inner["training_files"]), set(inner["validation_files"])
            assert train | valid == outer_train
            assert not train & valid
            assert not (train | valid) & outer_valid
    assert len(held_out) == len(set(held_out)) == 272


def test_shared_cli_never_fits_and_refuses_overwrite(tmp_path, monkeypatch):
    import runpy
    import sys
    from railpulse.rail.spatial import PooledSideClassifier
    from railpulse.shm.regression import DamageRegressor
    root = Path(__file__).resolve().parents[1]
    source = root / "data/Rail_Corrugation/Test/Test1.csv"
    if not source.is_file():
        pytest.skip("Prepare raw data to exercise the frozen CLI")
    def forbidden(*args, **kwargs):
        raise AssertionError("Prediction attempted training")
    for cls in (DoorModel, RailClassifier, PooledSideClassifier, DamageRegressor):
        monkeypatch.setattr(cls, "fit", forbidden)
    output = tmp_path / "prediction.csv"
    monkeypatch.setattr(sys, "argv", ["predict.py", "--subsystem", "rail", "--input", str(source), "--output", str(output)])
    runpy.run_path(str(root / "scripts/predict.py"), run_name="__main__")
    actual = pd.read_csv(output)
    expected = pd.read_csv(DEFAULT_RUN / "rail_predictions.csv")
    pd.testing.assert_frame_equal(actual, expected[expected.file_id == "Test1.csv"].reset_index(drop=True))
    with pytest.raises(FileExistsError):
        runpy.run_path(str(root / "scripts/predict.py"), run_name="__main__")
