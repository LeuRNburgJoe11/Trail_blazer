"""Verify all distributed test files through the app adapter and compare with CLI output."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import pandas as pd
from railpulse.shm.loader import list_recordings
from railpulse.shm.uploads import analyse_uploads
from railpulse.shm.pipeline import load_artifact


def main():
    paths = list_recordings(ROOT / "data/SHM/Test")
    artifact_path = ROOT / "models/shm/model.joblib"
    artifact = load_artifact(artifact_path)
    checksum_before = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    results, exported = analyse_uploads([(path.name, path.read_bytes()) for path in paths], artifact_path)
    output = ROOT / "outputs/shm"
    if exported != (output / "shm_predictions.csv").read_bytes():
        raise AssertionError("Application and command-line exports differ")
    if checksum_before != hashlib.sha256(artifact_path.read_bytes()).hexdigest():
        raise AssertionError("Inference modified the model")
    train_hashes = {row["sha256"] for row in artifact["training_files"]}
    test_hashes = {result.metadata["sha256"] for result in results}
    if train_hashes.intersection(test_hashes) or len(test_hashes) != len(results):
        raise AssertionError("Exact duplicate recordings across training/test or within test")
    latency = np.array([r.metadata["seconds"] for r in results])
    summary = {"n_test_files": len(results), "app_cli_exports_identical": True,
               "frozen_artifact_unchanged": True, "no_exact_train_test_duplicates": True,
               "prediction_sha256": hashlib.sha256(exported).hexdigest(),
               "sample_counts": sorted({int(r.evidence["n_samples"]) for r in results}),
               "median_inference_seconds": float(np.median(latency)),
               "max_inference_seconds": float(latency.max()),
               "total_inference_seconds": float(latency.sum()),
               "warnings": {r.file_id: r.warnings for r in results if r.warnings},
               "test_labels_available": False}
    (output / "verification.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
