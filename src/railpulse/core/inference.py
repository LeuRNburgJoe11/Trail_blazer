"""One frozen inference path for all four subsystems; never trains on uploads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd

from .predictions import PredictionResult, SCHEMAS, validate_predictions


def load_bundle(directory):
    """Only load trusted local model bundles (pickle/joblib can execute code)."""
    directory = Path(directory)
    metadata = json.loads((directory / "bundle.json").read_text())
    if metadata["version"] != 1:
        raise ValueError("Unsupported bundle version")
    for name, checksum in metadata["sha256"].items():
        if Path(name).name != name:
            raise ValueError("Invalid artifact name")
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != checksum:
            raise ValueError(f"Model checksum mismatch: {name}")
    from railpulse.shm.pipeline import load_artifact
    return {"directory": directory, "metadata": metadata,
            "door": joblib.load(directory / "door.joblib"),
            "rail": joblib.load(directory / "rail.joblib"),
            "shm": load_artifact(directory / "shm.joblib")}


def predict_file(subsystem, path, bundle):
    path = Path(path)
    evidence, warnings = {}, []
    expected_cars = None
    if subsystem == "door":
        from railpulse.door.loader import load_stream
        from railpulse.door.pipeline import predict_intervals
        intervals = predict_intervals(load_stream(path), bundle["door"])
        rows = [{"start_time": item["start_time"], "end_time": item["end_time"],
                 "prediction": item["status"]} for item in intervals]
        evidence = {"intervals": intervals}
    elif subsystem == "acv":
        from railpulse.acv.pipeline import analyse_acv
        result = analyse_acv(str(path), str(bundle["directory"] / "acv.pkl"))
        rows = [{"file_id": path.name, "ranked_cars": "|".join(result.ranked_cars)}]
        # The feature table contains one row per source car, before ranking.
        expected_cars = {path.name: result.car_features.car_id.tolist()}
        evidence = {"ranking_scores": result.ranking_scores,
                    "top_feature_contributors": result.top_feature_contributors}
        warnings = result.warnings
    elif subsystem == "rail":
        from railpulse.rail.loader import load_recording
        from railpulse.rail.spectral_features import extract_features
        from railpulse.rail.spatial import extract_spatial_features
        extractor = extract_spatial_features if bundle["metadata"]["rail_model"] == "pooled_spatial" else extract_features
        features = extractor(load_recording(path).values)
        rows = [{"file_id": path.name, "prediction": bundle["rail"].predict([features])[0]}]
        evidence = {"model": bundle["metadata"]["rail_model"], "features": features}
    elif subsystem == "shm":
        from railpulse.shm.pipeline import analyse_shm
        result = analyse_shm(path, artifact=bundle["shm"])
        rows = [{"file_id": path.name, "prediction": result.prediction}]
        evidence, warnings = result.evidence, result.warnings
    else:
        raise ValueError(f"Unknown subsystem: {subsystem}")
    frame = pd.DataFrame(rows, columns=SCHEMAS[subsystem])
    validate_predictions(subsystem, frame, expected_ids=None if subsystem == "door" else [path.name],
                         expected_cars=expected_cars)
    return PredictionResult(frame, evidence, warnings)
