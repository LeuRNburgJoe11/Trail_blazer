#!/usr/bin/env python3
"""
RailPulse backend -- thin FastAPI wrapper over the SAME pipeline code used
by the batch scripts and the Streamlit app (scripts/predict_*.py,
app/app.py). No new modelling logic lives here; this file only does
HTTP <-> pipeline plumbing, so a bug here can't silently change what gets
predicted.

Run:
    uvicorn backend.main:app --reload --port 8000

Endpoints:
    GET  /api/status              -- which models are loaded, their fold scores
    POST /api/door/predict        -- multipart file(s), continuous stream csv(s)
    POST /api/acv/predict         -- multipart file(s), .xlsx case file(s)
    POST /api/rail/predict        -- multipart file(s), .csv recording(s)

Each predict endpoint returns JSON: {"rows": [...], "submission_csv": "..."}
-- "rows" is what the frontend renders, "submission_csv" is the exact
official-schema CSV text ready to download as-is (no client-side CSV
construction, so the frontend can't accidentally drift from the schema).
"""
import sys
import tempfile
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from railpulse.acv.loader import car_series, discover_cars, load_case, pick_param
from railpulse.acv.peer_features import PRESSURE_PARAM_CANDIDATES, TEMP_PARAM_CANDIDATES
from railpulse.acv.ranking import rank_cars
from railpulse.core.registry import ModelRegistry
from railpulse.core.submission import door_result_to_frame
from railpulse.door.loader import load_stream
from railpulse.door.pipeline import DoorPipeline
from railpulse.rail.pipeline import RailPipeline

REGISTRY_DIR = "./registry"

# Operating context the UI shows as "readings in". Every entry is optional:
# case files genuinely carry different parameter sets, so a missing name must
# render as "not reported" rather than fail the request.
ACV_CONTEXT = {
    "outdoor_temp": "Outdoor Average Temperature",
    "indoor_temp": "Indoor Average Temperature",
    "cooling_setpoint": "ACV Control Temperature (Cooling)",
    "running_mode": "ACV Running Mode",
    "setting_mode": "ACV Setting Mode",
}

app = FastAPI(title="RailPulse API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only -- tighten before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


def _save_upload(upload: UploadFile, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(upload.file.read())
        return tmp.name


def _load_registered(subsystem: str):
    registry = ModelRegistry(REGISTRY_DIR)
    version = registry.latest_version(subsystem)
    if version is None:
        return None, None
    model, record = registry.load(subsystem, version)
    return model, record


def _median_across_cars(df: pd.DataFrame, cars: List[str], param: str):
    """Median of a numeric per-car parameter pooled over every car, or None."""
    present = [s for s in (car_series(df, c, param).dropna() for c in cars) if len(s)]
    return float(pd.concat(present).median()) if present else None


def _mode_across_cars(df: pd.DataFrame, cars: List[str], param: str):
    """Most frequent categorical value across cars, or None when absent."""
    cols = [f"Car {c} - {param}" for c in cars if f"Car {c} - {param}" in df.columns]
    if not cols:
        return None
    stacked = pd.concat([df[c] for c in cols]).dropna().astype(str)
    return stacked.value_counts().idxmax() if not stacked.empty else None


def _time_bounds(df: pd.DataFrame):
    """First and last timestamp as ISO strings, if the file carries a Time column."""
    if "Time" not in df.columns:
        return None, None
    stamps = pd.to_datetime(df["Time"], errors="coerce").dropna()
    if stamps.empty:
        return None, None
    return str(stamps.min()), str(stamps.max())


def _acv_context(df: pd.DataFrame, cars: List[str]) -> dict:
    """Operating conditions and per-car cabin temperatures behind the ranking.

    Presentation only -- it reports what the case file already contains so an
    engineer can see where and when, and never feeds back into rank_cars().
    """
    start, end = _time_bounds(df)
    train = df["Train number"].dropna() if "Train number" in df.columns else pd.Series(dtype=object)
    indoor_param = ACV_CONTEXT["indoor_temp"]
    per_car = {c: _median_across_cars(df, [c], indoor_param) for c in cars}
    reported = [v for v in per_car.values() if v is not None]
    fleet_median = float(pd.Series(reported).median()) if reported else None
    return {
        "train_number": str(train.iloc[0]) if not train.empty else None,
        "time_start": start,
        "time_end": end,
        "n_samples": int(len(df)),
        "n_cars": len(cars),
        "outdoor_temp": _median_across_cars(df, cars, ACV_CONTEXT["outdoor_temp"]),
        "cooling_setpoint": _median_across_cars(df, cars, ACV_CONTEXT["cooling_setpoint"]),
        "running_mode": _mode_across_cars(df, cars, ACV_CONTEXT["running_mode"]),
        "setting_mode": _mode_across_cars(df, cars, ACV_CONTEXT["setting_mode"]),
        # Which signals the ranker could actually use in THIS file.
        "temp_signal": pick_param(df, cars, TEMP_PARAM_CANDIDATES),
        "pressure_signal": pick_param(df, cars, PRESSURE_PARAM_CANDIDATES),
        "indoor_temp_median": fleet_median,
        "indoor_temp_by_car": per_car,
        "indoor_deviation_by_car": {
            c: (None if per_car[c] is None or fleet_median is None else round(per_car[c] - fleet_median, 2))
            for c in cars
        },
    }


@app.get("/api/status")
def status():
    out = {}
    for subsystem in ("door", "acv", "rail"):
        _, record = _load_registered(subsystem) if subsystem != "acv" else (None, None)
        if subsystem == "acv":
            out[subsystem] = {"available": True, "note": "rule-based, no training needed", "fold_scores": None}
        else:
            out[subsystem] = {
                "available": record is not None,
                "fold_scores": record.fold_scores if record else None,
            }
    return out


@app.post("/api/door/predict")
def predict_door(files: List[UploadFile] = File(...)):
    model, record = _load_registered("door")
    if model is None:
        raise HTTPException(503, "No trained Door model registered. Run scripts/train_door.py first.")
    pipeline = DoorPipeline(model=model)

    all_rows = []
    for upload in files:
        stream = load_stream(_save_upload(upload, ".csv"))
        result = pipeline.predict(stream)
        df = door_result_to_frame(result)
        df.insert(0, "source_file", upload.filename)
        all_rows.append(df)

    combined = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame(
        columns=["source_file", "start_time", "end_time", "prediction"]
    )
    submission = combined.drop(columns=["source_file"])  # official Door schema has no file id
    return {
        "rows": combined.to_dict(orient="records"),
        "submission_csv": submission.to_csv(index=False),
        "model_score": record.fold_scores.get("held_out_iou_f1"),
    }


@app.post("/api/acv/predict")
def predict_acv(files: List[UploadFile] = File(...)):
    rows = []
    for upload in files:
        # load_case + rank_cars is exactly what ACVPipeline.predict_file does;
        # calling them directly reads each workbook once instead of twice.
        df = load_case(_save_upload(upload, ".xlsx"))
        cars = discover_cars(df)
        ranked, scores = rank_cars(df)
        lo, hi = scores.min(), scores.max()
        display = ((scores - lo) / (hi - lo) * 100) if hi > lo else scores * 0 + 50
        display_scores = {c: round(float(display[c]), 1) for c in ranked}
        rows.append({
            "file_id": upload.filename,
            "ranked_cars": ranked,
            "display_scores": display_scores,
            "flagged_car": ranked[0] if ranked else None,
            # Lead over the runner-up: a narrow lead means the ranking is a
            # close call between two cars, which the engineer needs to see.
            "lead_over_next": (round(display_scores[ranked[0]] - display_scores[ranked[1]], 1)
                               if len(ranked) > 1 else None),
            "context": _acv_context(df, cars),
        })

    submission = pd.DataFrame([{"file_id": r["file_id"], "ranked_cars": "|".join(r["ranked_cars"])} for r in rows])
    return {"rows": rows, "submission_csv": submission.to_csv(index=False)}


@app.post("/api/rail/predict")
def predict_rail(files: List[UploadFile] = File(...)):
    model, record = _load_registered("rail")
    if model is None:
        raise HTTPException(503, "No trained Rail model registered. Run scripts/train_rail.py first.")
    pipeline = RailPipeline(model=model)
    pipeline.feature_cols = record.feature_columns

    rows = []
    for upload in files:
        result = pipeline.predict_file(_save_upload(upload, ".csv"))
        result.file_id = upload.filename
        rows.append({
            "file_id": result.file_id,
            "prediction": result.prediction,
            "side_scores": {k: round(v, 4) for k, v in result.side_scores.items()},
        })

    submission = pd.DataFrame([{"file_id": r["file_id"], "prediction": r["prediction"]} for r in rows])
    return {
        "rows": rows,
        "submission_csv": submission.to_csv(index=False),
        "model_score": record.fold_scores.get("cv_macro_f1_mean"),
    }
