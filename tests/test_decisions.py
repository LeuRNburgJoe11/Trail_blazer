import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from railpulse.core.dashboard import dashboard_summary
from railpulse.core.decisions import decision_records, decision_payload, input_quality, json_safe
from railpulse.core.predictions import PredictionResult, csv_bytes
from railpulse.core.scoring import acv_rank_score, combined_scores, rail_macro_f1


def decide(subsystem, frame, evidence=None, warnings=None, quality="passed"):
    return decision_records(subsystem, PredictionResult(frame, evidence or {}, warnings or []),
                            file_id="sample.csv" if subsystem != "acv" else "sample.xlsx",
                            source_sha256="a" * 64, bundle_sha256="b" * 64, quality=quality)


@pytest.mark.parametrize("subsystem,label,finding,review", [
    ("rail", "Normal", "no_fault_detected", False),
    ("rail", "Side I", "fault_candidate", True),
    ("rail", "Side II", "fault_candidate", True),
])
def test_classification_decisions(subsystem, label, finding, review):
    frame = pd.DataFrame({"file_id": ["sample.csv"], "prediction": [label]})
    record = decide(subsystem, frame)[0]
    assert record.finding == finding and record.review_required is review
    assert record.confidence["value"] is None


def test_door_preserves_interval_and_prediction_contract():
    frame = pd.DataFrame([{"start_time": "2023-7-5-0-0-0-0", "end_time": "2023-7-5-0-0-1-0", "prediction": "Abnormal resistance"}])
    original = csv_bytes("door", frame)
    records = decide("door", frame)
    assert records[0].finding == "fault_candidate"
    assert records[0].entity_id.startswith("segment:")
    assert csv_bytes("door", frame) == original


@pytest.mark.parametrize("scores,finding", [
    ({"01": 9., "02": 1.}, "suspected_car"),
    ({"01": 1., "02": 1.}, "ambiguous_localization"),
    ({}, "ambiguous_localization"),
    ({"01": float("nan"), "02": 1.}, "ambiguous_localization"),
])
def test_acv_rankings_are_not_probabilities(scores, finding):
    frame = pd.DataFrame({"file_id": ["sample.xlsx"], "ranked_cars": ["01|02"]})
    record = decide("acv", frame, {"ranking_scores": scores})[0]
    assert record.finding == finding
    assert record.confidence["value"] is None
    assert "not calibrated" in record.evidence["score_interpretation"]
    json.loads(decision_payload([record]))


@pytest.mark.parametrize("damage", [0., .2, 1., 10000.])
def test_shm_never_invents_a_fault_threshold_or_remaining_life(damage):
    frame = pd.DataFrame({"file_id": ["sample.csv"], "prediction": [damage]})
    record = decide("shm", frame)[0]
    assert record.finding == "damage_estimate"
    assert record.disposition == "engineering_context_required"
    assert record.evidence["remaining_life"] is None
    assert record.evidence["forecast"] is None


@pytest.mark.parametrize("quality,warnings", [("degraded", []), ("not_assessed", []), ("passed", ["Out of training range"])])
def test_quality_or_model_warning_escalates_even_normal_predictions(quality, warnings):
    frame = pd.DataFrame({"file_id": ["sample.csv"], "prediction": ["Normal"]})
    record = decide("rail", frame, warnings=warnings, quality=quality)[0]
    assert record.review_required and record.review_priority == 30
    assert record.quality != "passed"
    assert record.finding == "no_fault_detected"  # no silent relabeling


def test_decisions_are_stable_json_safe_and_do_not_mutate_evidence():
    frame = pd.DataFrame({"file_id": ["sample.csv"], "prediction": [1.]})
    evidence = {"sample_count": np.int64(3), "missing": np.nan, "array": np.array([1, np.inf])}
    before = copy.deepcopy(evidence)
    first, second = decide("shm", frame, evidence), decide("shm", frame, evidence)
    assert decision_payload(first) == decision_payload(second)
    parsed = json.loads(decision_payload(first))
    assert parsed["records"][0]["evidence"]["array"] == [1., None]
    assert evidence["array"][1] == before["array"][1]


def test_quality_rejects_malformed_door_before_inference(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Datetime,Current\ninvalid,inf\n")
    with pytest.raises(ValueError, match="17 documented"):
        input_quality("door", path)


def test_rail_metric_includes_absent_classes():
    assert rail_macro_f1(["Normal"], ["Normal"]) == pytest.approx(1 / 3)
    assert rail_macro_f1(["Normal", "Side I", "Side II"], ["Normal", "Side I", "Side II"]) == 1


def test_acv_official_rank_formula_and_coverage():
    assert acv_rank_score("02", ["01", "02"], ["01", "02"]) == .5
    with pytest.raises(ValueError):
        acv_rank_score("02", ["01", "01"], ["01", "02"])


def test_overall_vs_average_with_two_attempts():
    report = combined_scores({"door": 1., "shm": .8}, attempted=["door", "shm"])
    assert report["overall_score"] == .45
    assert report["average_score"] == .9


def test_failed_attempt_zero_is_not_excluded_from_average():
    report = combined_scores({"door": 1., "shm": 0.}, attempted=["door", "shm"])
    assert report["overall_score"] == .25 and report["average_score"] == .5


def test_unknown_scores_stay_unknown_not_zero_or_perfect():
    report = combined_scores({"door": 1.}, attempted=["door", "shm"], basis="held_out")
    assert report["overall_score"] is None and report["average_score"] is None
    assert report["unscored"] == ["shm"]
    assert combined_scores({}, attempted=[])["average_score"] is None


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -.1, 1.1, True])
def test_invalid_scores_rejected(score):
    with pytest.raises(ValueError):
        combined_scores({"door": score}, attempted=["door"])


def test_dashboard_coverage_counts_files_not_door_segments():
    frame = pd.DataFrame([{"start_time": "2023-7-5-0-0-0-0", "end_time": "2023-7-5-0-0-1-0", "prediction": "Normal"}])
    record = decide("door", frame)[0].to_dict()
    summary = dashboard_summary([record, {**record, "entity_id": "second"}], {"door": ["sample.csv"]})
    assert summary["subsystems"][0]["uploaded_files"] == 1
    assert summary["subsystems"][0]["findings"] == 2
    assert summary["scoring"]["overall_score"] is None


def test_all_four_attempts_have_equal_overall_and_average():
    report = combined_scores({"door": .8, "acv": .6, "rail": .4, "shm": .2},
                             attempted=["door", "acv", "rail", "shm"])
    assert report["overall_score"] == pytest.approx(.5)
    assert report["average_score"] == pytest.approx(.5)


def test_dashboard_replay_preserves_all_official_predictions():
    import hashlib
    root = Path(__file__).resolve().parents[1]
    summary = json.loads((root / "outputs/dashboard/summary.json").read_text())
    payload = json.loads((root / "outputs/dashboard/decisions.json").read_text())
    assert len(payload["records"]) == 123
    assert len({record["decision_id"] for record in payload["records"]}) == 123
    for name, report in summary["verification"].items():
        exported = root / "outputs/combined/merged-main" / f"{name}_predictions.csv"
        assert hashlib.sha256(exported.read_bytes()).hexdigest() == report["sha256"]
        assert report["official_csv_unchanged"]
    assert summary["scoring"]["overall_score"] is None
    assert summary["scoring"]["average_score"] is None
