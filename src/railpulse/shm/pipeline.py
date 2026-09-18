"""Frozen SHM inference shared by command line and application integrations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

import joblib
import numpy as np
import pandas as pd

from .loader import load_recording, list_recordings
from .rainflow_features import FEATURE_VERSION, extract_features, power_column

ARTIFACT_VERSION = 1


@dataclass(frozen=True)
class SHMResult:
    file_id: str
    prediction: float
    evidence: dict
    warnings: list[str]
    metadata: dict

    def to_dict(self):
        return asdict(self)


def environment_versions() -> dict:
    return {"python": platform.python_version(), **{
        name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn", "rainflow", "scipy", "joblib")}}


def save_artifact(path, model, features, manifest, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {"artifact_version": ARTIFACT_VERSION, "feature_version": FEATURE_VERSION,
                "model": model, "feature_schema": features.columns.tolist(),
                "training_min": features.min().to_dict(), "training_max": features.max().to_dict(),
                "training_files": manifest[["file_id", "sha256", "n_samples"]].to_dict("records"),
                "versions": environment_versions(), "metadata": metadata}
    joblib.dump(artifact, path)
    public = {key: value for key, value in artifact.items() if key != "model"}
    public["model_kind"] = model.kind
    if hasattr(model, "exponent_"):
        public.update({"effective_exponent": model.exponent_, "scale": model.scale_})
    public["artifact_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".json").write_text(json.dumps(public, indent=2, allow_nan=False) + "\n")
    return artifact


def load_artifact(path):
    """Load only a trusted local artifact: joblib/pickle files can execute code."""
    path = Path(path)
    sidecar = json.loads(path.with_suffix(".json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != sidecar["artifact_sha256"]:
        raise ValueError("Artifact checksum does not match metadata")
    artifact = joblib.load(path)
    if artifact.get("artifact_version") != ARTIFACT_VERSION or artifact.get("feature_version") != FEATURE_VERSION:
        raise ValueError("Unsupported artifact or feature version; retrain with matching code")
    for name in ("scikit-learn", "rainflow"):
        if artifact["versions"][name] != importlib.metadata.version(name):
            raise ValueError(f"Artifact requires {name}=={artifact['versions'][name]}; install matching dependencies")
    return artifact


def analyse_shm(path, artifact_path=None, *, artifact=None) -> SHMResult:
    if artifact is None:
        if artifact_path is None:
            raise ValueError("A fitted artifact is required")
        artifact = load_artifact(artifact_path)
    started = time.perf_counter()
    recording = load_recording(path)
    features = extract_features(recording.stress)
    frame = pd.DataFrame([features], columns=artifact["feature_schema"])
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Input features do not match artifact schema")
    prediction = float(artifact["model"].predict(frame)[0])
    warnings = []
    if features["cycle_count"] == 0:
        warnings.append("Constant stress: no alternating cycles; predictions outside the training domain need review.")
    outside = [name for name in ("n_samples", "stress_std", "amplitude_max", "cycle_count")
               if features[name] < artifact["training_min"][name] or features[name] > artifact["training_max"][name]]
    if outside:
        warnings.append("Outside observed training range: " + ", ".join(outside))
    evidence = {name: features[name] for name in ("n_samples", "stress_mean", "stress_rms", "stress_std",
                                               "cycle_count", "half_cycle_fraction", "amplitude_q90",
                                               "amplitude_q99", "amplitude_max")}
    model = artifact["model"]
    if hasattr(model, "exponent_"):
        evidence.update({"effective_exponent": model.exponent_, "calibrated_scale": model.scale_,
                         "rainflow_damage_proxy": features[power_column(model.exponent_)]})
    return SHMResult(recording.file_id, prediction, evidence, warnings,
                     {"model": model.kind, "feature_version": FEATURE_VERSION, "sha256": recording.sha256,
                      "seconds": time.perf_counter() - started, "stress_units": "source units (unspecified)",
                      "interpretation": "Damage for this recording; not remaining life or a maintenance deadline."})


def predict_directory(input_path, artifact_path) -> list[SHMResult]:
    artifact = load_artifact(artifact_path)
    return [analyse_shm(path, artifact=artifact) for path in list_recordings(input_path)]


def write_predictions(path, results: list[SHMResult], expected_ids=None):
    identifiers = [result.file_id for result in results]
    predictions = np.array([result.prediction for result in results])
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError("Expected nonempty predictions with unique file IDs")
    if any(Path(name).name != name or not name.lower().endswith(".csv") for name in identifiers):
        raise ValueError("file_id must be the source basename including .csv extension")
    if not np.isfinite(predictions).all() or np.any(predictions < 0):
        raise ValueError("Predictions must be finite and nonnegative")
    if expected_ids is not None and (set(identifiers) != set(expected_ids) or len(identifiers) != len(expected_ids)):
        raise ValueError("Prediction IDs do not exactly match input files")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"file_id": identifiers, "prediction": predictions}).to_csv(path, index=False, float_format="%.17g")
