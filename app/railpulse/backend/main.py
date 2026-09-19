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
import json
import os
import subprocess
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
from .assistant_bridge import router as assistant_router, remember

REGISTRY_DIR = "./registry"
PROTOTYPE_DIR = Path(__file__).resolve().parent.parent
ROOT_REPO = PROTOTYPE_DIR.parents[1]
DOOR_INFER = PROTOTYPE_DIR / "scripts/door_infer.py"
SHM_INFER = PROTOTYPE_DIR / "scripts/shm_infer.py"

# How the damage number is produced. Stated so the panel can explain the method
# without restating it in the UI, where it would drift from the pipeline.
SHM_METHOD = {
    "steps": [
        {"step": "Cycle extraction", "title": "Rainflow counting (ASTM E1049)",
         "detail": "Decomposes the stress time series into closed hysteresis loops. "
                   "Each cycle carries an amplitude; half cycles count 0.5."},
        {"step": "S-N relation", "title": "Basquin power law",
         "detail": "Relates amplitude to endurance life through (amplitude ** m) * N = C. "
                   "The exponent is selected by the pipeline, not assumed from a material spec."},
        {"step": "Damage summation", "title": "Palmgren-Miner linear rule",
         "detail": "Sums the fractional damage of every counted cycle: D = sum(n_i / N_i)."},
    ],
    "caveats": [
        "Stress units are unspecified in the source data, so D is dimensionless and comparable "
        "only between these recordings.",
        "D is the damage accumulated within one recording. It is not remaining life, a forecast, "
        "or a maintenance deadline.",
        "No approved damage threshold exists for this fleet. Alert bands, severity tiers and "
        "inspection intervals need domain-approved policy and independent validation "
        "(docs/DECISION_LAYER.md).",
    ],
}

# Operating context the UI shows as "readings in". Every entry is optional:
# case files genuinely carry different parameter sets, so a missing name must
# render as "not reported" rather than fail the request.
ACV_CONTEXT = {
    "outdoor_temp": "Outdoor Average Temperature",
    "indoor_temp": "Indoor Average Temperature",
    "cooling_setpoint": "ACV Control Temperature (Cooling)",
    "running_mode": "ACV Running Mode",
    "setting_mode": "ACV Setting Mode",
    "telemetry_valid": "ACV Information Valid",
}
# Running modes that count as the unit actively cooling, for duty cycle.
ACV_COOLING_MODES = {"Automatic Cooling", "Full Cooling"}
# Two cars apart in the ranking index by this or less are not meaningfully
# separated, so the runner-up is shown as a co-suspect instead of being
# silently dropped below the flagged car.
ACV_NEAR_TIE = 0.02
# Formation convention, NOT telemetry: an 8-car set drives from both ends.
# The case files carry no car-type column, so this is a stated assumption and
# is labelled as one in the UI rather than presented as a measurement.
ACV_CAB_POSITIONS = (1, 8)

app = FastAPI(title="RailPulse API")
app.include_router(assistant_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
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


def _acv_indicators(df: pd.DataFrame, cars: List[str]) -> dict:
    """Per-car physical evidence behind the ranking, from this file only.

    Deliberately narrow: every figure here is computed from columns the file
    actually carries. Quantities the telemetry does not support -- recovery lag
    to setpoint, for one -- are left out rather than estimated, because a
    plausible-looking number would send someone to the wrong car.
    """
    indoor = pd.DataFrame({
        car: pd.to_numeric(df.get(f"Car {car} - {ACV_CONTEXT['indoor_temp']}"), errors="coerce")
        for car in cars
    })
    if indoor.dropna(how="all").empty:
        return {car: {} for car in cars}
    residual = indoor.sub(indoor.median(axis=1), axis=0)
    # Rows where no car reported cannot have a warmest car; excluding them keeps
    # the share honest and avoids an all-NA idxmax.
    reported = indoor.dropna(how="all")
    warmest = reported.idxmax(axis=1) if not reported.empty else pd.Series(dtype=object)
    # Rows are evenly spaced, so a row count converts straight to hours.
    step_hours = _row_step_hours(df)
    out = {}
    for car in cars:
        values = residual[car].dropna()
        mode = df.get(f"Car {car} - {ACV_CONTEXT['running_mode']}")
        mode = mode.dropna().astype(str) if mode is not None else pd.Series(dtype=str)
        valid = df.get(f"Car {car} - {ACV_CONTEXT['telemetry_valid']}")
        out[car] = {
            "peer_residual_mean": round(float(values.mean()), 3) if len(values) else None,
            "peer_residual_p90": round(float(values.quantile(0.9)), 2) if len(values) else None,
            "warmest_share": round(float((warmest == car).mean()) * 100, 1) if len(warmest) else None,
            "hours_above_1c": round(float((values > 1).sum()) * step_hours, 2) if len(values) and step_hours else None,
            "persistent_run_minutes": _longest_run(residual[car], step_hours),
            "duty_cycle": round(float(mode.isin(ACV_COOLING_MODES).mean()) * 100, 1) if len(mode) else None,
            "telemetry_valid": (round(float((valid.dropna().astype(str) == "Valid").mean()) * 100, 1)
                                if valid is not None and not valid.dropna().empty else None),
        }
    return out


def _longest_run(residual: pd.Series, step_hours) -> float | None:
    """Longest unbroken stretch, in minutes, spent warmer than the peer median.

    A car that is briefly warm looks the same as one that never recovers when
    you only average; this separates them, which is what an engineer is
    actually deciding between.
    """
    if step_hours is None or residual.dropna().empty:
        return None
    best = current = 0
    for value in residual.fillna(0).to_numpy():
        current = current + 1 if value > 0 else 0
        best = max(best, current)
    return round(best * step_hours * 60, 1)


def _row_step_hours(df: pd.DataFrame) -> float | None:
    """Median sampling interval in hours, or None when there is no usable Time."""
    if "Time" not in df.columns:
        return None
    stamps = pd.to_datetime(df["Time"], errors="coerce").dropna()
    if len(stamps) < 2:
        return None
    step = stamps.diff().dropna().median()
    return float(step.total_seconds()) / 3600 if pd.notna(step) else None


def _headline(indicators: dict) -> str:
    """The one line the checklist shows as the car's key physical indicator."""
    parts = []
    if indicators.get("peer_residual_mean") is not None:
        value = indicators["peer_residual_mean"]
        parts.append(f"Peer residual {value:+.2f} °C")
    if indicators.get("warmest_share") is not None:
        parts.append(f"warmest car {indicators['warmest_share']:.0f}% of window")
    if indicators.get("persistent_run_minutes"):
        parts.append(f"{indicators['persistent_run_minutes']:.0f} min longest warm run")
    return "; ".join(parts) if parts else "No comparable telemetry in this file"


def _acv_summary(car: str, tier: str, indicators: dict, fleet_median) -> str:
    """Plain-language read of one car, built only from measured indicators."""
    residual = indicators.get("peer_residual_mean")
    warmest = indicators.get("warmest_share")
    run = indicators.get("persistent_run_minutes")
    if residual is None:
        return f"Car {car} has no comparable cabin-temperature telemetry in this file."
    direction = "warmer than" if residual > 0 else "cooler than" if residual < 0 else "level with"
    text = [f"Car {car} runs {abs(residual):.2f} °C {direction} the train median on average"]
    if warmest is not None:
        text.append(f", and is the warmest car {warmest:.0f}% of the recorded window")
    text.append(".")
    if run:
        text.append(f" Its longest unbroken warm stretch is {run:.0f} minutes.")
    if tier == "primary":
        text.append(" This is the strongest peer-relative deviation in the consist, which is why it ranks first.")
    elif tier == "co_suspect":
        text.append(" It sits within a tie margin of the car above it, so inspect both.")
    else:
        text.append(" Nothing here separates it from its peers; a nominal rank is not a clearance.")
    return "".join(text)


def _acv_series(df: pd.DataFrame, cars: List[str], points: int = 180) -> dict:
    """Measured cabin temperature per car over the window, thinned for plotting.

    Real samples on a stride, not a smoothed or synthesised curve: a viewer
    comparing a car against its peers has to be looking at the same numbers the
    ranking was computed from.
    """
    indoor = pd.DataFrame({
        car: pd.to_numeric(df.get(f"Car {car} - {ACV_CONTEXT['indoor_temp']}"), errors="coerce")
        for car in cars
    })
    if indoor.dropna(how="all").empty:
        return {"available": False}
    stride = max(1, len(indoor) // points)
    thinned = indoor.iloc[::stride]
    stamps = pd.to_datetime(df["Time"], errors="coerce").iloc[::stride] if "Time" in df.columns else None
    setpoint = pd.to_numeric(df.get(f"Car {cars[0]} - {ACV_CONTEXT['cooling_setpoint']}"), errors="coerce")
    return {
        "available": True,
        "stride": stride,
        "time": [None if stamps is None else str(value) for value in (stamps if stamps is not None else thinned.index)],
        "by_car": {car: [None if pd.isna(v) else round(float(v), 2) for v in thinned[car]] for car in cars},
        "peer_median": [None if pd.isna(v) else round(float(v), 2) for v in thinned.median(axis=1)],
        "setpoint": (None if setpoint is None or setpoint.dropna().empty
                     else round(float(setpoint.median()), 2)),
    }


def _acv_validation() -> dict:
    """Recorded leave-one-case-out results, read from the repository outputs.

    Read rather than hardcoded so the panel cannot drift from the numbers the
    team actually validated. Absent file means the panel simply shows nothing.
    """
    path = ROOT_REPO / "outputs/acv/validation_results_baseline.csv"
    if not path.exists():
        return {"available": False}
    frame = pd.read_csv(path)
    if not {"case_id", "true_car_rank", "rank_decay_score"} <= set(frame.columns):
        return {"available": False}
    return {
        "available": True,
        "protocol": "leave-one-case-out",
        "mean_rank_decay": round(float(frame.rank_decay_score.mean()), 4),
        "n_cases": int(len(frame)),
        "top1": int((frame.true_car_rank == 1).sum()),
        "worst_rank": int(frame.true_car_rank.max()),
        "cases": [{"case": str(row.case_id).replace(".xlsx", ""), "rank": int(row.true_car_rank),
                   "score": round(float(row.rank_decay_score), 3)} for row in frame.itertuples()],
        "source": "outputs/acv/validation_results_baseline.csv",
    }


def _acv_cars(df: pd.DataFrame, cars: List[str], ranked: List[str], display: dict) -> dict:
    """Rank, tier, margin and physical evidence per car, in formation order.

    Tiering follows the ranking margin, not a fixed count: the runner-up is a
    co-suspect only while it sits within ACV_NEAR_TIE of the car above it, so a
    clear winner produces exactly one flagged car.
    """
    indicators = _acv_indicators(df, cars)
    scores = {car: round(display[car] / 100, 3) for car in ranked}
    margins, cluster = {}, [ranked[0]] if ranked else []
    for position, car in enumerate(ranked):
        following = ranked[position + 1] if position + 1 < len(ranked) else None
        margins[car] = round(scores[car] - scores[following], 3) if following else None
        if following and margins[car] is not None and margins[car] <= ACV_NEAR_TIE and car in cluster:
            cluster.append(following)
    rows = []
    for car in sorted(cars, key=lambda value: (len(value), value)):
        rank = ranked.index(car) + 1 if car in ranked else None
        tier = "nominal"
        if rank == 1:
            tier = "primary"
        elif car in cluster:
            tier = "co_suspect"
        position = int(car) if car.isdigit() else None
        rows.append({
            "car": car,
            "position": position,
            "car_type": "Cab" if position in ACV_CAB_POSITIONS else "Trailer",
            "rank": rank,
            "score": scores.get(car),
            "margin_to_next": margins.get(car),
            "near_tie": bool(margins.get(car) is not None and margins[car] <= ACV_NEAR_TIE),
            "tier": tier,
            "indicators": indicators.get(car, {}),
            "headline": _headline(indicators.get(car, {})),
            "summary": _acv_summary(car, tier, indicators.get(car, {}), None),
        })
    return {
        "rows": rows,
        "cluster": cluster if len(cluster) > 1 else [],
        "near_tie_threshold": ACV_NEAR_TIE,
        "car_type_source": "formation convention (cars 1 and 8 are cabs); not present in the telemetry",
    }


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
    """Door runs on the canonical root pipeline, isolated in a subprocess.

    See scripts/door_infer.py: the two `railpulse` packages cannot share an
    interpreter, so the process boundary is what lets this panel show the
    audited segmentation and per-cycle evidence.
    """
    rows = []
    for upload in files:
        source = Path(_save_upload(upload, ".csv"))
        destination = source.with_suffix(".door.json")
        environment = dict(os.environ)
        # Replace, never append: inheriting this prototype's src would let its
        # own `railpulse` shadow the canonical one inside the child.
        environment["PYTHONPATH"] = str(ROOT_REPO / "src")
        finished = subprocess.run(
            [sys.executable, str(DOOR_INFER), "--input", str(source),
             "--output", str(destination), "--source-name", upload.filename],
            capture_output=True, text=True, env=environment, cwd=str(PROTOTYPE_DIR),
        )
        if finished.returncode != 0:
            detail = (finished.stderr or finished.stdout or "").strip().splitlines()
            raise HTTPException(500, f"Door inference failed: {detail[-1] if detail else 'unknown error'}")
        rows.extend(json.loads(destination.read_text(encoding="utf-8"))["rows"])

    # Official Door schema is start_time,end_time,prediction -- no file id.
    submission = pd.DataFrame([{key: row[key] for key in ("start_time", "end_time", "prediction")}
                               for row in rows], columns=["start_time", "end_time", "prediction"])
    return remember("door", {"rows": rows, "submission_csv": submission.to_csv(index=False), "model_score": None})


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
            "consist": _acv_cars(df, cars, ranked, display_scores),
            "series": _acv_series(df, cars),
            "context": _acv_context(df, cars),
        })

    validation = _acv_validation()

    submission = pd.DataFrame([{"file_id": r["file_id"], "ranked_cars": "|".join(r["ranked_cars"])} for r in rows])
    return remember("acv", {"rows": rows, "submission_csv": submission.to_csv(index=False), "validation": validation})


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
    return remember("rail", {
        "rows": rows,
        "submission_csv": submission.to_csv(index=False),
        "model_score": record.fold_scores.get("cv_macro_f1_mean"),
        "validation": record.fold_scores,
    })


@app.post("/api/shm/predict")
def predict_shm(files: List[UploadFile] = File(...)):
    """SHM runs on the canonical root pipeline, isolated in a subprocess.

    All recordings go to one child process so the artifact is loaded once:
    rainflow counting over ~581k samples per file dominates the runtime, and
    reloading the model per file would only add to it.
    """
    sources, names = [], []
    for upload in files:
        sources.append(_save_upload(upload, ".csv"))
        names.append(upload.filename)
    # Unique per request: pid + count collides for concurrent uploads and could
    # attach another request's result to an assistant snapshot.
    with tempfile.NamedTemporaryFile(suffix=".shm.json", delete=False) as output:
        destination = Path(output.name)

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT_REPO / "src")
    finished = subprocess.run(
        [sys.executable, str(SHM_INFER), "--inputs", *map(str, sources),
         "--names", *names, "--output", str(destination)],
        capture_output=True, text=True, env=environment, cwd=str(PROTOTYPE_DIR),
    )
    if finished.returncode != 0:
        detail = (finished.stderr or finished.stdout or "").strip().splitlines()
        raise HTTPException(500, f"SHM inference failed: {detail[-1] if detail else 'unknown error'}")
    rows = json.loads(destination.read_text(encoding="utf-8"))["rows"]

    # Official SHM schema is file_id,prediction -- evidence stays out of it.
    submission = pd.DataFrame([{"file_id": r["file_id"], "prediction": r["prediction"]} for r in rows],
                              columns=["file_id", "prediction"])
    return remember("shm", {
        "rows": rows,
        "submission_csv": submission.to_csv(index=False),
        "method": SHM_METHOD,
    })
