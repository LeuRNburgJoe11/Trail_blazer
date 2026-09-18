#!/usr/bin/env python3
"""
RailPulse app -- the compulsory "non-technical user" deliverable (Problem
Statement 3 Section 4.1, item 3): pick a subsystem, drag in a data file, see
the prediction on screen, download it. Same pipeline code as the batch
scripts (scripts/predict_door.py, scripts/predict_acv.py) -- this file is
just a thin UI over it, per the architecture review's "use the same
inference code for the app and batch submissions."

Run:
    streamlit run app/app.py -- --registry-dir ./registry

Before first use of Door: run scripts/train_door.py once to populate the
registry (ACV needs no training -- v0_baseline is rule-based).
"""
import io
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from railpulse.acv.pipeline import ACVPipeline
from railpulse.core.registry import ModelRegistry
from railpulse.core.submission import acv_result_to_frame, door_result_to_frame
from railpulse.door.loader import load_stream
from railpulse.door.pipeline import DoorPipeline
from railpulse.rail.pipeline import RailPipeline

REGISTRY_DIR = "./registry"

st.set_page_config(page_title="RailPulse", layout="centered")
st.title("RailPulse")
st.caption("One platform, specialist condition-monitoring pipelines. SHM is not wired up yet.")

subsystem = st.selectbox("Subsystem", ["Door", "ACV", "Rail Corrugation", "SHM (coming soon)"])


@st.cache_resource
def get_door_pipeline():
    registry = ModelRegistry(REGISTRY_DIR)
    version = registry.latest_version("door")
    if version is None:
        return None, None
    model, record = registry.load("door", version)
    return DoorPipeline(model=model), record


if subsystem == "Door":
    pipeline, record = get_door_pipeline()
    if pipeline is None:
        st.error(
            "No trained Door model found. Run "
            "`python scripts/train_door.py --data-dir <path/to/Door>` once, then reload this page."
        )
    else:
        st.success(f"Loaded model (held-out IoU-weighted F1: {record.fold_scores.get('held_out_iou_f1', '?'):.3f})")
        uploaded = st.file_uploader("Upload a continuous door-controller stream (.csv)", type="csv")
        if uploaded is not None:
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            with st.spinner("Segmenting cycles and classifying..."):
                stream = load_stream(tmp_path)
                result = pipeline.predict(stream)
            if not result.segments:
                st.warning("No door cycles were detected in this file.")
            else:
                df = door_result_to_frame(result)
                st.write(f"Found {len(df)} predicted cycles:")
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    "Download door_predictions.csv",
                    df.to_csv(index=False).encode(),
                    file_name="door_predictions.csv",
                    mime="text/csv",
                )

elif subsystem == "ACV":
    st.info("Rule-based peer-relative ranking -- no training step needed.")
    uploaded = st.file_uploader("Upload an ACV case file (.xlsx)", type="xlsx")
    if uploaded is not None:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = tmp.name
        with st.spinner("Computing peer-relative residuals..."):
            pipeline = ACVPipeline()
            result = pipeline.predict_file(tmp_path)
            result.file_id = uploaded.name  # report the name the user actually uploaded
        st.write("Cars ranked most- to least-likely faulty:")
        scores_df = pd.DataFrame(
            {"car": result.ranked_cars, "suspicion_score": [result.scores[c] for c in result.ranked_cars]}
        )
        st.dataframe(scores_df, use_container_width=True)
        out_df = acv_result_to_frame(result)
        st.download_button(
            "Download acv_predictions.csv",
            out_df.to_csv(index=False).encode(),
            file_name="acv_predictions.csv",
            mime="text/csv",
        )

elif subsystem == "Rail Corrugation":
    @st.cache_resource
    def get_rail_pipeline():
        registry = ModelRegistry(REGISTRY_DIR)
        version = registry.latest_version("rail")
        if version is None:
            return None, None
        model, record = registry.load("rail", version)
        pipeline = RailPipeline(model=model)
        pipeline.feature_cols = record.feature_columns
        return pipeline, record

    pipeline, record = get_rail_pipeline()
    if pipeline is None:
        st.error(
            "No trained Rail model found. Run "
            "`python scripts/extract_rail_features.py ...` then "
            "`python scripts/train_rail.py ...` once, then reload this page."
        )
    else:
        st.success(f"Loaded model (mean CV macro F1: {record.fold_scores.get('cv_macro_f1_mean', '?'):.3f})")
        uploaded = st.file_uploader("Upload a 1-second, 129-column axle-box recording (.csv)", type="csv")
        if uploaded is not None:
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            with st.spinner("Recovering speed and computing wavenumber-band features..."):
                result = pipeline.predict_file(tmp_path)
                result.file_id = uploaded.name
            st.metric("Prediction", result.prediction)
            st.write("Per-side suspicion scores:")
            st.dataframe(pd.DataFrame([result.side_scores]), use_container_width=True)
            out_df = pd.DataFrame([{"file_id": result.file_id, "prediction": result.prediction}])
            st.download_button(
                "Download rail_predictions.csv",
                out_df.to_csv(index=False).encode(),
                file_name="rail_predictions.csv",
                mime="text/csv",
            )

else:
    st.warning("This subsystem's pipeline isn't implemented yet -- see src/railpulse/shm.")
