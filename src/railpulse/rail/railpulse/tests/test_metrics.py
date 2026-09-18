import pandas as pd
import pytest

from railpulse.core.metrics import acv_rank_decay_score, door_iou_weighted_f1, iou, rail_macro_f1


def ts(s):
    return pd.Timestamp(s)


def test_iou_perfect_overlap():
    assert iou(ts("2023-01-01 00:00:00"), ts("2023-01-01 00:00:10"),
               ts("2023-01-01 00:00:00"), ts("2023-01-01 00:00:10")) == 1.0


def test_iou_no_overlap():
    assert iou(ts("2023-01-01 00:00:00"), ts("2023-01-01 00:00:10"),
               ts("2023-01-01 00:00:20"), ts("2023-01-01 00:00:30")) == 0.0


def test_door_perfect_submission_scores_one():
    truth = pd.DataFrame({
        "start_ts": [ts("2023-01-01 00:00:00")],
        "end_ts": [ts("2023-01-01 00:00:10")],
        "status": ["Normal"],
    })
    pred = pd.DataFrame({
        "start_ts": [ts("2023-01-01 00:00:00")],
        "end_ts": [ts("2023-01-01 00:00:10")],
        "prediction": ["Normal"],
    })
    assert door_iou_weighted_f1(pred, truth) == pytest.approx(1.0)


def test_door_wrong_label_scores_same_as_miss_plus_spurious():
    truth = pd.DataFrame({
        "start_ts": [ts("2023-01-01 00:00:00")],
        "end_ts": [ts("2023-01-01 00:00:10")],
        "status": ["Normal"],
    })
    pred_wrong_label = pd.DataFrame({
        "start_ts": [ts("2023-01-01 00:00:00")],
        "end_ts": [ts("2023-01-01 00:00:10")],
        "prediction": ["Abnormal resistance"],
    })
    # Cannot match at all -- score must be 0, same as submitting nothing.
    assert door_iou_weighted_f1(pred_wrong_label, truth) == 0.0


def test_door_missing_segment_lowers_recall():
    truth = pd.DataFrame({
        "start_ts": [ts("2023-01-01 00:00:00"), ts("2023-01-01 00:01:00")],
        "end_ts": [ts("2023-01-01 00:00:10"), ts("2023-01-01 00:01:10")],
        "status": ["Normal", "Normal"],
    })
    pred = pd.DataFrame({
        "start_ts": [ts("2023-01-01 00:00:00")],
        "end_ts": [ts("2023-01-01 00:00:10")],
        "prediction": ["Normal"],
    })
    score = door_iou_weighted_f1(pred, truth)
    assert 0 < score < 1.0


@pytest.mark.parametrize("rank,expected", [
    (1, 1.000), (2, 0.875), (3, 0.750), (4, 0.625), (8, 0.125),
])
def test_acv_rank_decay_worked_example(rank, expected):
    # 8-car file, worked example straight from ACV_Subsystem_Info_Kit.md Section 4
    ranked = [str(i).zfill(2) for i in range(1, 9)]
    true_faulty = ranked[rank - 1]
    assert acv_rank_decay_score(ranked, true_faulty) == pytest.approx(expected)


def test_acv_rank_decay_missing_car_scores_zero():
    ranked = ["01", "02", "03"]
    assert acv_rank_decay_score(ranked, "99") == 0.0


def test_rail_macro_f1_always_normal_scores_far_below_its_accuracy():
    # Rail_Corrugation_Info_Kit.md Section 4's point: a model that always
    # predicts "Normal" can score ~90% plain accuracy while never once
    # detecting a fault, and macro F1 must NOT reward that.
    always_normal_true = ["Normal"] * 90 + ["Side I"] * 5 + ["Side II"] * 5
    always_normal_pred = ["Normal"] * 100
    accuracy = sum(t == p for t, p in zip(always_normal_true, always_normal_pred)) / 100
    score = rail_macro_f1(always_normal_true, always_normal_pred)
    assert accuracy == pytest.approx(0.90)
    assert score < 0.4, f"macro F1 ({score:.3f}) should be far below the {accuracy:.0%} accuracy"


def test_rail_macro_f1_perfect_predictions_scores_one():
    y_true = ["Normal", "Side I", "Side II", "Normal", "Side I"]
    assert rail_macro_f1(y_true, y_true) == pytest.approx(1.0)
