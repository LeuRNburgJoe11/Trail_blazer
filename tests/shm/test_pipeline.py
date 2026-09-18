from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

from railpulse.shm.pipeline import analyse_shm, load_artifact, save_artifact, write_predictions
from railpulse.shm.regression import DamageRegressor
from railpulse.shm.rainflow_features import extract_features, power_column
from railpulse.shm.uploads import analyse_uploads
from railpulse.shm.validation import evaluate, make_splits


@pytest.fixture
def fitted(tmp_path):
    signals = [np.array([0, a, -a, a, 0.0]) for a in range(1, 9)]
    features = pd.DataFrame([extract_features(x) for x in signals], index=[f"f{i}.csv" for i in range(8)])
    target = features[power_column(5)].to_numpy() * 0.01
    model = DamageRegressor("physics_5").fit(features, target)
    manifest = pd.DataFrame({"file_id": features.index, "sha256": ["a"] * 8, "n_samples": [5] * 8})
    path = tmp_path / "model.joblib"
    save_artifact(path, model, features, manifest, {})
    return path, features, target


def test_physics_calibration_recovers_law(fitted):
    _, features, target = fitted
    model = DamageRegressor("physics_fitted").fit(features, target)
    assert model.exponent_ == 5
    assert model.scale_ == pytest.approx(0.01)
    np.testing.assert_allclose(model.predict(features), target, rtol=1e-12)


def test_scale_optimizes_mape_and_not_absolute_error(fitted):
    _, features, _ = fitted
    frame = features.iloc[:3]
    proxy = frame[power_column(5)].to_numpy()
    target = proxy * [1, 2, 20]
    model = DamageRegressor("physics_5").fit(frame, target)
    assert model.scale_ == pytest.approx(1)


def test_inference_never_fits_and_matches_upload_export(tmp_path, fitted, monkeypatch):
    artifact, _, _ = fitted
    def forbidden(*args, **kwargs):
        raise AssertionError("Inference attempted to fit")
    monkeypatch.setattr(DamageRegressor, "fit", forbidden)
    path = tmp_path / "test01.csv"
    content = b"0\n2\n-2\n2\n0\n"
    path.write_bytes(content)
    direct = analyse_shm(path, artifact)
    results, csv_bytes = analyse_uploads([(path.name, content)], artifact)
    assert results[0].prediction == direct.prediction
    output = tmp_path / "expected.csv"
    write_predictions(output, [direct], [path.name])
    assert csv_bytes == output.read_bytes()
    assert list(pd.read_csv(output).columns) == ["file_id", "prediction"]
    assert json.loads(json.dumps(direct.to_dict()))["file_id"] == path.name


def test_artifact_checksum_and_version_guard(tmp_path, fitted):
    path, _, _ = fitted
    assert load_artifact(path)["feature_version"]
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="checksum"):
        load_artifact(path)


def test_export_rejects_missing_duplicate_or_nonfinite(tmp_path, fitted):
    artifact, _, _ = fitted
    path = tmp_path / "test.csv"
    path.write_text("0\n2\n0\n")
    result = analyse_shm(path, artifact)
    for results, ids in [([result, result], None), ([result], ["missing.csv"]),
                         ([replace(result, prediction=np.nan)], None),
                         ([replace(result, prediction=-1)], None), ([], None)]:
        with pytest.raises(ValueError):
            write_predictions(tmp_path / "out.csv", results, ids)


@pytest.mark.parametrize("files", [[("../x.csv", b"0")], [("x.csv", b"0"), ("x.csv", b"0")], []])
def test_upload_names_rejected(files, fitted):
    with pytest.raises(ValueError):
        analyse_uploads(files, fitted[0])


def test_nested_validation_is_disjoint_and_prediction_is_out_of_fold(fitted):
    _, features, target = fitted
    comparison, oof, splits = evaluate(features, target, outer_folds=4, inner_folds=2,
                                       seeds=(42,), candidates=("constant_mape", "physics_5"))
    assert len(oof.query("model == 'nested_selection'")) == len(target)
    for split in splits:
        held = set(split["validation"])
        assert not held.intersection(split["train"])
        for inner in split["inner_splits"]:
            assert not held.intersection(inner["train"] + inner["validation"])
            assert not set(inner["train"]).intersection(inner["validation"])
        train = features.index.get_indexer(split["train"])
        valid = features.index.get_indexer(split["validation"])
        manual = DamageRegressor(split["selected"]).fit(features.iloc[train], target[train])
        rows = oof[(oof.model == "nested_selection") & (oof.fold == split["fold"])]
        np.testing.assert_allclose(rows.prediction, manual.predict(features.iloc[valid]))


def test_group_splits_keep_related_files_together():
    groups = np.repeat(["run_a", "run_b", "run_c", "run_d"], 2)
    for train, valid in make_splits(8, 4, 42, groups):
        assert not set(groups[train]).intersection(groups[valid])
