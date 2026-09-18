"""
Dynamic case/schema parsing (architecture review Section 03). The exact
parameter set genuinely differs between case files (confirmed: one file has
~8 params/car, another has 60+), so nothing here assumes a fixed column list
-- every file's own headers are the source of truth.
"""
from __future__ import annotations

import re

import pandas as pd

CAR_COL_RE = re.compile(r"^Car (\d+) - (.+)$")


def load_case(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def discover_cars(df: pd.DataFrame) -> list[str]:
    """Car IDs exactly as they appear in this file's own headers -- this is
    the same identifier `ranked_cars` must use in the submission."""
    cars = set()
    for col in df.columns:
        m = CAR_COL_RE.match(col)
        if m:
            cars.add(m.group(1))
    return sorted(cars)


def pick_param(df: pd.DataFrame, cars: list[str], candidates: list[str]) -> str | None:
    """First candidate parameter name present for at least half the cars in
    this file. Returns None if nothing on the candidate list is present --
    callers should treat that as "this file needs a different signal", not
    silently fall through to a placeholder."""
    for cand in candidates:
        n_present = sum(f"Car {c} - {cand}" in df.columns for c in cars)
        if n_present >= max(1, len(cars) // 2):
            return cand
    return None


def car_series(df: pd.DataFrame, car: str, param: str) -> pd.Series:
    col = f"Car {car} - {param}"
    if col not in df.columns:
        return pd.Series(dtype=float, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")
