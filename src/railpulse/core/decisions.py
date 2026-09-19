"""Versioned, advisory-only decision records independent of official CSV schemas."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .data_validation import DOOR_COLUMNS, door_time, read_header, validate_acv_recording
from .inference import predict_file
from .predictions import PredictionResult, validate_predictions

POLICY_VERSION = "review-policy-v1"


def json_safe(value):
    """Encode missing evidence as null, not non-standard NaN/Infinity JSON."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


@dataclass
class Decision:
    decision_id: str
    subsystem: str
    file_id: str
    entity_id: str
    finding: str
    disposition: str
    review_priority: int
    quality: str
    review_required: bool
    summary: str
    suggested_review: str
    reasons: list[str]
    evidence: dict
    provenance: dict
    warnings: list[str] = field(default_factory=list)
    confidence: dict = field(default_factory=lambda: {
        "value": None, "status": "not_calibrated",
        "meaning": "No validated probability of correctness is available."})
    policy_version: str = POLICY_VERSION
    schema_version: int = 1

    def to_dict(self):
        return json_safe(asdict(self))


def decision_records(subsystem, result: PredictionResult, *, file_id, source_sha256,
                     bundle_sha256, quality="not_assessed", quality_evidence=None):
    if quality not in ("passed", "degraded", "not_assessed"):
        raise ValueError("Invalid input quality state")
    expected = None if subsystem == "door" else [file_id]
    validate_predictions(subsystem, result.frame, expected_ids=expected)
    provenance = {"input_sha256": source_sha256, "bundle_sha256": bundle_sha256,
                  "scope": "uploaded recording only; no asset identity or fleet linkage inferred"}
    records = []
    if subsystem == "door" and result.frame.empty:
        identity = f"{POLICY_VERSION}|door|{file_id}|no_operations|{source_sha256}|{bundle_sha256}"
        needs_review = quality != "passed" or bool(result.warnings)
        return [Decision(hashlib.sha256(identity.encode()).hexdigest(), "door", file_id, "recording",
                         "no_operations_detected", "record_observation", 30 if needs_review else 0,
                         "degraded" if result.warnings else quality, needs_review, "No door operations detected",
                         "Confirm that an idle recording was intended; no health conclusion can be drawn.",
                         ["NO_DETECTED_OPERATIONS"], {"data_quality": quality_evidence or {}}, provenance,
                         list(result.warnings))]
    for index, row in enumerate(result.frame.to_dict("records")):
        entity = f"segment:{row['start_time']}:{row['end_time']}" if subsystem == "door" else file_id
        reasons, evidence = [], {"prediction": row, "data_quality": quality_evidence or {}}
        warnings = list(result.warnings)
        review, priority = False, 0
        if subsystem in ("door", "rail"):
            abnormal = row["prediction"] != "Normal"
            finding = "fault_candidate" if abnormal else "no_fault_detected"
            summary = f"Model predicts {row['prediction']}"
            disposition = "inspect_candidate" if abnormal else "record_observation"
            review, priority = abnormal, 20 if abnormal else 0
            action = "Review the flagged interval/side with a qualified maintainer; corroborate with independent evidence." if abnormal else "Retain this observation; a Normal prediction is not a safety clearance."
            reasons.append("MODEL_FAULT_CLASS" if abnormal else "MODEL_NORMAL_CLASS")
            if subsystem == "door":
                intervals = result.evidence.get("intervals", [])
                evidence["interval"] = intervals[index] if index < len(intervals) else row
            else:
                evidence["model_evidence"] = result.evidence
        elif subsystem == "acv":
            cars = row["ranked_cars"].split("|")
            scores = result.evidence.get("ranking_scores", {})
            values = [scores.get(car) for car in cars]
            usable = all(isinstance(value, (int, float, np.number)) and math.isfinite(value) for value in values)
            ambiguous = not usable or len(cars) < 2 or math.isclose(float(values[0]), float(values[1]), rel_tol=1e-9, abs_tol=1e-9)
            finding = "ambiguous_localization" if ambiguous else "suspected_car"
            summary = "Ranking is tied or lacks usable evidence" if ambiguous else f"Car {cars[0]} ranks first for suspected leakage"
            disposition, review, priority = "review_localization", True, 20
            action = "Review the complete ranking and telemetry; the top-ranked car is not a confirmed leak diagnosis."
            reasons.append("AMBIGUOUS_RANKING" if ambiguous else "RANKING_NOT_DIAGNOSIS")
            evidence.update(result.evidence)
            evidence["ranked_cars"] = cars
            evidence["raw_score_margin"] = float(values[0] - values[1]) if usable and len(cars) > 1 else None
            evidence["score_interpretation"] = "Relative ranking scores, not calibrated leak probabilities."
        else:
            finding, disposition, review, priority = "damage_estimate", "engineering_context_required", True, 10
            summary = f"Estimated recording damage: {row['prediction']:.6g}"
            action = "Obtain engineering-approved units, exposure history, and asset-specific limits before any maintenance decision."
            reasons.append("NO_APPROVED_DAMAGE_LIMIT")
            evidence.update(result.evidence)
            evidence["remaining_life"] = None
            evidence["forecast"] = None
        if warnings or quality != "passed":
            reasons.append("MODEL_WARNING" if warnings else "QUALITY_NOT_VERIFIED")
            if quality == "degraded":
                reasons.append("DEGRADED_INPUT")
            review, priority = True, max(priority, 30)
        actual_quality = "degraded" if warnings and quality == "passed" else quality
        identity = f"{POLICY_VERSION}|{subsystem}|{file_id}|{entity}|{source_sha256}|{bundle_sha256}"
        records.append(Decision(hashlib.sha256(identity.encode()).hexdigest(), subsystem, file_id, entity,
                                finding, disposition, priority, actual_quality, review, summary, action,
                                reasons, evidence, provenance, warnings))
    return records


def input_quality(subsystem, path):
    """Strict checks before inference, without cleaning or overwriting uploads."""
    if subsystem == "door":
        if read_header(path) != DOOR_COLUMNS:
            raise ValueError("Door requires the 17 documented telemetry columns in order")
        frame = pd.read_csv(path)
        if frame.empty or not np.isfinite(frame.iloc[:, 1:].to_numpy(dtype=float)).all():
            raise ValueError("Door telemetry must be nonempty and finite")
        times = pd.DatetimeIndex([door_time(value) for value in frame.Datetime])
        if times.has_duplicates or not times.is_monotonic_increasing:
            raise ValueError("Door timestamps must increase uniquely")
        return {"rows": len(frame), "warnings": []}
    if subsystem == "acv":
        report = validate_acv_recording(path)
        if report["missing_telemetry_fraction"] == 1:
            raise ValueError("ACV has no usable telemetry")
        return report
    # The frozen SHM and Rail loaders enforce finite numeric samples and dimensions.
    return {"validation": "frozen subsystem loader", "warnings": []}


def analyse_decision(subsystem, path, bundle):
    """Return unchanged model predictions plus dashboard records. Invalid data raises."""
    path = Path(path)
    quality = input_quality(subsystem, path)
    result = predict_file(subsystem, path, bundle)
    warnings = list(dict.fromkeys([*result.warnings, *quality.get("warnings", [])]))
    if subsystem == "rail":
        features = result.evidence.get("features", {})
        speed = features.get("s0_speed", features.get("speed"))
        if speed is not None and speed <= 0:
            warnings.append("No speed pulses detected: speed-normalized spectral evidence is unavailable.")
    dashboard_result = PredictionResult(result.frame, result.evidence, warnings)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    bundle_hash = hashlib.sha256((bundle["directory"] / "bundle.json").read_bytes()).hexdigest()
    records = decision_records(subsystem, dashboard_result, file_id=path.name,
                               source_sha256=source_hash, bundle_sha256=bundle_hash,
                               quality="degraded" if quality.get("warnings") else "passed",
                               quality_evidence=quality)
    return result, records


def decision_payload(records):
    items = [item.to_dict() if isinstance(item, Decision) else item for item in records]
    # Stable order means priorities and exports do not depend on upload order.
    items = sorted(items, key=lambda item: (-item["review_priority"], item["subsystem"], item["file_id"], item["entity_id"]))
    payload = {"schema_version": 1, "policy_version": POLICY_VERSION,
               "purpose": "Advisory review queue, not an automated safety or maintenance controller",
               "review_priority_meaning": "Queue order only; not physical severity or failure probability",
               "records": items}
    return json.dumps(json_safe(payload), indent=2, allow_nan=False).encode()
