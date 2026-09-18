"""
Exact export formats (architecture review, core/submission.py), matching
01_Problem_Statement_3_Specifications.md Section 4.1 item 2 precisely:

  door_predictions.csv : start_time, end_time, prediction   (no file_id)
  acv_predictions.csv  : file_id, ranked_cars                (no prediction)

Centralising this means the app and the batch scripts write the same bytes.
"""
from __future__ import annotations

import pandas as pd

from railpulse.core.schemas import ACVResult, DoorResult


def _fmt_ts(ts: pd.Timestamp) -> str:
    """Round-trip to the dataset's native, not-zero-padded timestamp format."""
    return f"{ts.year}-{ts.month}-{ts.day}-{ts.hour}-{ts.minute}-{ts.second}-{ts.microsecond // 1000}"


def door_result_to_frame(result: DoorResult) -> pd.DataFrame:
    rows = [
        {"start_time": s.start_time, "end_time": s.end_time, "prediction": s.prediction}
        for s in result.segments
    ]
    return pd.DataFrame(rows, columns=["start_time", "end_time", "prediction"])


def write_door_predictions(result: DoorResult, path: str) -> None:
    df = door_result_to_frame(result)
    _validate_door_export(df)
    df.to_csv(path, index=False)


def acv_result_to_frame(result: ACVResult) -> pd.DataFrame:
    return pd.DataFrame(
        [{"file_id": result.file_id, "ranked_cars": "|".join(result.ranked_cars)}]
    )


def write_acv_predictions(results: list[ACVResult], path: str) -> None:
    df = pd.concat([acv_result_to_frame(r) for r in results], ignore_index=True)
    _validate_acv_export(df)
    df.to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Export tests (architecture review Section 07): duplicate/missing IDs,
# malformed timestamps, non-finite outputs, invalid labels, omitted files.
# ---------------------------------------------------------------------------
_DOOR_LABELS = {"Normal", "Abnormal resistance"}


def _validate_door_export(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("door export is empty -- no segments predicted")
    bad_labels = set(df["prediction"].unique()) - _DOOR_LABELS
    if bad_labels:
        raise ValueError(f"door export has invalid prediction labels: {bad_labels}")
    if df[["start_time", "end_time"]].isna().any().any():
        raise ValueError("door export has missing/malformed timestamps")


def _validate_acv_export(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("acv export is empty -- no files predicted")
    if df["file_id"].duplicated().any():
        dupes = df.loc[df["file_id"].duplicated(), "file_id"].tolist()
        raise ValueError(f"acv export has duplicate file_id rows: {dupes}")
    for _, row in df.iterrows():
        cars = row["ranked_cars"].split("|")
        if len(cars) != len(set(cars)):
            raise ValueError(f"acv export has duplicate car IDs in ranking for {row['file_id']}")
        if any(c.strip() == "" for c in cars):
            raise ValueError(f"acv export has an empty car ID in ranking for {row['file_id']}")
