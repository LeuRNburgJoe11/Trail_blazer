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

from railpulse.acv.pipeline import ACVPipeline
from railpulse.core.registry import ModelRegistry
from railpulse.core.submission import door_result_to_frame
from railpulse.door.loader import load_stream
from railpulse.door.pipeline import DoorPipeline
from railpulse.rail.pipeline import RailPipeline

REGISTRY_DIR = "./registry"

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
    pipeline = ACVPipeline()
    rows = []
    for upload in files:
        result = pipeline.predict_file(_save_upload(upload, ".xlsx"))
        result.file_id = upload.filename
        scores = pd.Series(result.scores)
        lo, hi = scores.min(), scores.max()
        display = ((scores - lo) / (hi - lo) * 100) if hi > lo else scores * 0 + 50
        rows.append({
            "file_id": result.file_id,
            "ranked_cars": result.ranked_cars,
            "display_scores": {c: round(float(display[c]), 1) for c in result.ranked_cars},
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
