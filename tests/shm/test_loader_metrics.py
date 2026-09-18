import numpy as np
import pytest

from railpulse.shm.loader import load_labels, load_recording, list_recordings
from railpulse.shm.metrics import regression_metrics


def test_headerless_loader_preserves_first_sample_and_scale(tmp_path):
    path = tmp_path / "train01.csv"
    path.write_text("2.5\n-1\n3.2\n")
    result = load_recording(path)
    np.testing.assert_array_equal(result.stress, [2.5, -1, 3.2])
    assert result.file_id == "train01.csv" and len(result.sha256) == 64


@pytest.mark.parametrize("content", ["", "1\n2\n", "stress\n1\n2\n", "1,2\n3,4\n5,6\n",
                                    "1\n\n3\n", "1\nnan\n3\n", "1\ninf\n3\n", "1\ntext\n3\n"])
def test_loader_rejects_invalid_signals(tmp_path, content):
    path = tmp_path / "bad.csv"
    path.write_text(content)
    with pytest.raises(ValueError):
        load_recording(path)


def test_labels_strict_identity_and_order(tmp_path):
    path = tmp_path / "Train_Labels.csv"
    path.write_text("filename,damage\na.csv,0.1\nb.csv,0.2\n")
    np.testing.assert_array_equal(load_labels(path, ["b.csv", "a.csv"]), [0.2, 0.1])
    with pytest.raises(ValueError, match="exactly matching"):
        load_labels(path, ["a.csv"])
    with pytest.raises(ValueError, match="containing labels"):
        list_recordings(tmp_path)


@pytest.mark.parametrize("rows", ["a.csv,0\n", "a.csv,-1\n", "a.csv,nan\n", "a.csv,1\na.csv,2\n"])
def test_bad_labels(tmp_path, rows):
    path = tmp_path / "labels.csv"
    path.write_text("filename,damage\n" + rows)
    with pytest.raises(ValueError):
        load_labels(path, ["a.csv"])


def test_official_mape_example_and_floor():
    y = [0.1, 0.3, 0.5, 0.7, 0.9]
    p = [0.15, 0.28, 0.55, 0.68, 0.85]
    expected = np.mean(np.abs(np.array(y) - p) / y)
    result = regression_metrics(y, p)
    assert result["mape"] == pytest.approx(expected)
    assert result["score"] == pytest.approx(1 - expected)
    assert regression_metrics(y, [0.5] * 5)["score"] == 0
    assert regression_metrics(y, y)["score"] == 1


@pytest.mark.parametrize("y,p", [([0], [1]), ([1], [-1]), ([1], [np.nan]), ([], []), ([1], [1, 2])])
def test_metric_rejects_undefined_cases(y, p):
    with pytest.raises(ValueError):
        regression_metrics(y, p)

