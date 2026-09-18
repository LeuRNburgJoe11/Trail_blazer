import pytest

from railpulse.core.schemas import ACVResult, DoorResult, DoorSegment
from railpulse.core.submission import (
    _validate_acv_export,
    _validate_door_export,
    acv_result_to_frame,
    door_result_to_frame,
)


def test_door_export_rejects_invalid_label():
    result = DoorResult(segments=[
        DoorSegment(start_time="2023-1-1-0-0-0-0", end_time="2023-1-1-0-0-1-0", prediction="Broken")
    ])
    df = door_result_to_frame(result)
    with pytest.raises(ValueError, match="invalid prediction labels"):
        _validate_door_export(df)


def test_door_export_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        _validate_door_export(door_result_to_frame(DoorResult(segments=[])))


def test_door_export_accepts_valid():
    result = DoorResult(segments=[
        DoorSegment(start_time="2023-1-1-0-0-0-0", end_time="2023-1-1-0-0-1-0", prediction="Normal")
    ])
    _validate_door_export(door_result_to_frame(result))  # should not raise


def test_acv_export_rejects_duplicate_car_in_ranking():
    result = ACVResult(file_id="f.xlsx", ranked_cars=["01", "02", "01"])
    with pytest.raises(ValueError, match="duplicate car IDs"):
        _validate_acv_export(acv_result_to_frame(result))


def test_acv_export_rejects_duplicate_file_id():
    r1 = ACVResult(file_id="f.xlsx", ranked_cars=["01", "02"])
    r2 = ACVResult(file_id="f.xlsx", ranked_cars=["02", "01"])
    import pandas as pd
    df = pd.concat([acv_result_to_frame(r1), acv_result_to_frame(r2)], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate file_id"):
        _validate_acv_export(df)
