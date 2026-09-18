import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from railpulse.core.data_preparation import download_file, fingerprints, inspect_files, load_lock, prepare, safe_path
from railpulse.core.data_validation import RAIL_COLUMNS, labels, validate_acv_recording, validate_numeric_recording, validate_door


def entry(content=b"1\n2\n3\n", path="data/SHM/Train/train01.csv", subsystem="shm"):
    return {"path": path, "source": "PS3/02_Datasets/SHM/Train/train01.csv", "subsystem": subsystem,
            "bytes": len(content), "git_blob_sha1": hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()}


def inventory(files):
    return {"version": 1, "repository": "owner/repo", "commit": "a" * 40,
            "subsystems": {"shm": {"destination": "SHM", "train_files": 1, "test_files": 1}}, "files": files}


def test_download_validates_before_atomic_publication(tmp_path):
    content = b"1\n2\n3\n"
    item = entry(content)
    result = download_file(tmp_path, item, inventory([item]), opener=lambda *a, **kw: io.BytesIO(content))
    assert (tmp_path / item["path"]).read_bytes() == content
    assert result["actual"] == fingerprints(tmp_path / item["path"])
    assert not list(tmp_path.rglob(".download-*"))


@pytest.mark.parametrize("content", [b"1\n2\n", b"3\n2\n1\n", b"1\n2\n3\n4\n"])
def test_bad_download_never_installs_partial_file(tmp_path, content):
    item = entry()
    with pytest.raises(ValueError):
        download_file(tmp_path, item, inventory([item]), opener=lambda *a, **kw: io.BytesIO(content))
    assert not (tmp_path / item["path"]).exists()
    assert not list(tmp_path.rglob(".download-*"))


def test_concurrently_created_destination_is_preserved(tmp_path):
    item = entry()
    path = tmp_path / item["path"]
    path.parent.mkdir(parents=True)
    path.write_bytes(b"user data")
    with pytest.raises(ValueError, match="preserved"):
        download_file(tmp_path, item, inventory([item]), opener=lambda *a, **kw: io.BytesIO(b"1\n2\n3\n"))
    assert path.read_bytes() == b"user data"


def test_conflict_preflight_prevents_any_download(tmp_path):
    item = entry(path="existing.csv")
    (tmp_path / "existing.csv").write_bytes(b"edited")
    with patch("railpulse.core.data_preparation.download_file") as download:
        with pytest.raises(ValueError, match="no files were downloaded"):
            prepare(tmp_path, inventory([item, entry(path="missing.csv")]), ["shm"])
        download.assert_not_called()


def test_line_endings_are_verified_without_rewriting(tmp_path):
    original = b"1\r\n2\r\n3\r\n"
    item = entry(original, "signal.csv")
    path = tmp_path / "signal.csv"
    path.write_bytes(original.replace(b"\r\n", b"\n"))
    result = inspect_files(tmp_path, [item])[0]
    assert result["status"] == "verified_line_endings"
    assert path.read_bytes() == b"1\n2\n3\n"
    path.write_bytes(b"1\n4\n3\n")
    assert inspect_files(tmp_path, [item])[0]["status"] == "modified"


def test_plan_and_missing_verify_are_offline_and_do_not_write(tmp_path):
    lock = inventory([entry()])
    with patch("railpulse.core.data_preparation.urlopen", side_effect=AssertionError("Network forbidden")):
        assert prepare(tmp_path, lock, ["shm"], plan=True)["missing_files"] == 1
        with pytest.raises(ValueError, match="Missing files"):
            prepare(tmp_path, lock, ["shm"], verify_only=True)
    assert list(tmp_path.iterdir()) == []


def test_complete_verify_is_read_only_and_prepare_skips_downloads(tmp_path):
    item = entry(path="existing.csv")
    (tmp_path / "existing.csv").write_bytes(b"1\n2\n3\n")
    with patch("railpulse.core.data_validation.validate_subsystem", return_value={"ok": True}), \
         patch("railpulse.core.data_preparation.download_file") as download:
        prepare(tmp_path, inventory([item]), ["shm"], verify_only=True)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["existing.csv"]
        prepare(tmp_path, inventory([item]), ["shm"])
        download.assert_not_called()
        manifest = json.loads((tmp_path / "outputs/data_preparation/shm_manifest.json").read_text())
        assert manifest["files"][0]["sha256"] == fingerprints(tmp_path / "existing.csv")["sha256"]


@pytest.mark.parametrize("path", ["../escape", "/absolute", "data/../../escape", "data\\escape"])
def test_unsafe_paths_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, path)


def test_symlink_rejected(tmp_path):
    (tmp_path / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink"):
        safe_path(tmp_path, "link/file.csv")


def test_lock_rejects_duplicate_destinations_and_branch_pins(tmp_path):
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(inventory([entry(), entry()])))
    with pytest.raises(ValueError, match="Duplicate"):
        load_lock(path)
    lock = inventory([entry()])
    lock["commit"] = "main"
    path.write_text(json.dumps(lock))
    with pytest.raises(ValueError, match="pinned"):
        load_lock(path)


def test_shm_headerless_first_row_and_invalid_signal(tmp_path):
    path = tmp_path / "stress.csv"
    path.write_text("10\n20\n30\n")
    assert validate_numeric_recording(path, "shm")["rows"] == 3
    path.write_text("10\n\n30\n")
    with pytest.raises(ValueError):
        validate_numeric_recording(path, "shm")


def test_rail_rejects_reordered_header(tmp_path):
    path = tmp_path / "rail.csv"
    path.write_text(",".join(RAIL_COLUMNS[::-1]) + "\n")
    with pytest.raises(ValueError, match="ordered channels"):
        validate_numeric_recording(path, "rail")


def test_label_coverage_and_leading_zero_car_ids(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text("filename,faulty_car\ncase.xlsx,03\n")
    assert labels(path, ["case.xlsx"], ["filename", "faulty_car"]).faulty_car.iloc[0] == "03"
    with pytest.raises(ValueError, match="coverage"):
        labels(path, ["another.xlsx"], ["filename", "faulty_car"])


def test_dynamic_acv_schema_and_missing_telemetry(tmp_path):
    path = tmp_path / "case.xlsx"
    data = {"Time": pd.date_range("2023-01-01", periods=3, freq="30s")}
    data.update({f"Car {i:02d} - Temperature": [20, None, "None"] for i in range(1, 9)})
    pd.DataFrame(data).to_excel(path, index=False)
    result = validate_acv_recording(path)
    assert result["car_ids"] == [f"{i:02d}" for i in range(1, 9)]
    assert result["missing_telemetry_fraction"] == pytest.approx(2 / 3)
    assert result["warnings"]


def test_door_dataset_labels_are_consistent():
    base = Path(__file__).resolve().parents[1] / "data/Door"
    assert validate_door(base)["labelled_segments"] == 110


def test_pinned_inventory_has_expected_split_counts_and_mappings():
    root = Path(__file__).resolve().parents[1]
    lock = load_lock(root / "configs/dataset_lock.json")
    assert lock["subsystems"]["acv"]["destination"] == "acv"
    for key in ("acv", "rail", "shm"):
        for split, count_key in (("Train", "train_files"), ("Test", "test_files")):
            count = sum(e["subsystem"] == key and f"/{split}/" in e["path"] for e in lock["files"])
            assert count == lock["subsystems"][key][count_key]
