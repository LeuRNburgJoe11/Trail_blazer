"""
Fitted artifacts and model metadata (architecture review, core/registry.py).

Deliberately simple -- a joblib blob plus a metadata.json next to it -- but
captures every field the architecture review's Section 06 "Registry record"
asks for: subsystem, code/data version, feature schema, model parameters,
fold scores, out-of-fold predictions (path, not inlined -- can be large),
measured latency, artifact checksum and model-selection rationale.

Not a database. If this grows past a handful of models, swap the JSON index
for SQLite/MLflow and keep this same call signature.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import joblib


@dataclass
class ModelRecord:
    subsystem: str
    version: str
    feature_columns: list[str]
    model_params: dict
    fold_scores: dict  # e.g. {"held_out_iou_f1": 0.985} or {"loco_mean": 0.958}
    artifact_checksum: str
    measured_latency_s: float | None = None
    selection_rationale: str = ""
    oof_predictions_path: str | None = None
    created_at: float = field(default_factory=time.time)


class ModelRegistry:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _paths(self, subsystem: str, version: str):
        base = self.root / subsystem / version
        base.mkdir(parents=True, exist_ok=True)
        return base / "model.joblib", base / "metadata.json"

    def save(self, subsystem: str, version: str, model, *, feature_columns,
              model_params, fold_scores, measured_latency_s=None,
              selection_rationale="", oof_predictions_path=None) -> ModelRecord:
        model_path, meta_path = self._paths(subsystem, version)
        joblib.dump(model, model_path)
        checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()[:16]
        record = ModelRecord(
            subsystem=subsystem,
            version=version,
            feature_columns=list(feature_columns),
            model_params=model_params,
            fold_scores=fold_scores,
            artifact_checksum=checksum,
            measured_latency_s=measured_latency_s,
            selection_rationale=selection_rationale,
            oof_predictions_path=oof_predictions_path,
        )
        meta_path.write_text(json.dumps(asdict(record), indent=2))
        return record

    def load(self, subsystem: str, version: str):
        model_path, meta_path = self._paths(subsystem, version)
        if not model_path.exists():
            raise FileNotFoundError(f"No registered model at {model_path}")
        model = joblib.load(model_path)
        record = ModelRecord(**json.loads(meta_path.read_text()))
        # integrity check -- catch a silently corrupted/edited artifact
        checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()[:16]
        if checksum != record.artifact_checksum:
            raise ValueError(
                f"Checksum mismatch for {subsystem}/{version}: "
                f"registry says {record.artifact_checksum}, file is {checksum}"
            )
        return model, record

    def latest_version(self, subsystem: str) -> str | None:
        subdir = self.root / subsystem
        if not subdir.exists():
            return None
        versions = sorted(p.name for p in subdir.iterdir() if p.is_dir())
        return versions[-1] if versions else None
