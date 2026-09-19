"""Door data loading. Keeps original timestamps throughout -- never rebase
or drop precision, since boundary scoring is IoU on exact time ranges."""
from __future__ import annotations

import pandas as pd


def parse_datetime(series: pd.Series) -> pd.Series:
    """Dataset format: Y-M-D-H-M-S-ms, hyphen separated, NOT zero-padded,
    e.g. '2023-7-5-0-0-3-760'."""
    parts = series.str.split("-", expand=True).astype(int)
    parts.columns = ["Y", "M", "D", "h", "m", "s", "ms"]
    return pd.to_datetime(
        dict(year=parts.Y, month=parts.M, day=parts.D, hour=parts.h, minute=parts.m, second=parts.s)
    ) + pd.to_timedelta(parts.ms, unit="ms")


def load_stream(path: str) -> pd.DataFrame:
    """Load Train.csv / Test.csv: continuous controller-reading stream."""
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    df["ts"] = parse_datetime(df["Datetime"])
    return df.sort_values("ts").reset_index(drop=True)


def load_answer(path: str) -> pd.DataFrame:
    """Load Train_Segments_Answer.csv: ground-truth cycle boundaries + labels."""
    ans = pd.read_csv(path)
    ans.columns = [c.strip() for c in ans.columns]
    ans["start_ts"] = parse_datetime(ans["start_time"])
    ans["end_ts"] = parse_datetime(ans["end_time"])
    return ans


def format_native_ts(ts: pd.Timestamp) -> str:
    return f"{ts.year}-{ts.month}-{ts.day}-{ts.hour}-{ts.minute}-{ts.second}-{ts.microsecond // 1000}"
