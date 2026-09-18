#!/usr/bin/env python3
"""
RailPulse app -- the compulsory "non-technical user" deliverable (Problem
Statement 3 Section 4.1, item 3): pick a subsystem, drag in the held-out
TEST SET files, see which ones are flagged with a fault, download the exact
*_predictions.csv the organiser's judge_leaderboard.py scores.

This is a batch tool, not a single-file demo: Rail's test set alone is 68
files, and the deliverable is "run the held-out test input files through
your app" (Section 2.3/4.1) -- so every subsystem here accepts multiple
files at once and produces one combined submission-ready CSV.

Same pipeline code as the batch scripts (scripts/predict_door.py, etc.) --
this file is a thin UI over it, per the architecture review's "use the same
inference code for the app and batch submissions."

Run:
    streamlit run app/app.py

Before first use: run scripts/train_door.py and scripts/train_rail.py once
to populate the registry (ACV needs no training -- v0_baseline is rule-based).
"""
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from railpulse.acv.pipeline import ACVPipeline
from railpulse.core.registry import ModelRegistry
from railpulse.core.submission import door_result_to_frame
from railpulse.door.loader import load_stream
from railpulse.door.pipeline import DoorPipeline
from railpulse.rail.pipeline import RailPipeline

REGISTRY_DIR = "./registry"

st.set_page_config(page_title="RailPulse", layout="centered")
st.title("RailPulse")
st.caption("Upload the held-out test set for a subsystem and see which files or cycles are flagged with a fault.")

DOOR_LABEL_COLOR = {"Normal": "var(--text-secondary)", "Abnormal resistance": "#D85A30"}
RAIL_LABEL_COLOR = {"Normal": "var(--text-secondary)", "Side I": "#D85A30", "Side II": "#D4537E"}


def save_upload(uploaded, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(uploaded.getvalue())
        return tmp.name


def badge(text: str, color: str) -> str:
    return f'<span style="color:{color};font-weight:500">{text}</span>'


subsystem = st.radio(
    "Subsystem", ["Door", "ACV", "Rail corrugation", "SHM (coming soon)"],
    horizontal=True, label_visibility="collapsed",
)

# ---------------------------------------------------------------------------
# Door: one continuous stream (Test.csv) -- but accept several in case you
# have more than one recording to run through.
# ---------------------------------------------------------------------------
if subsystem == "Door":
    st.subheader("Door -- fault detection in a continuous stream")

    @st.cache_resource
    def get_door_pipeline():
        registry = ModelRegistry(REGISTRY_DIR)
        version = registry.latest_version("door")
        if version is None:
            return None, None
        model, record = registry.load("door", version)
        return DoorPipeline(model=model), record

    pipeline, record = get_door_pipeline()
    if pipeline is None:
        st.error("No trained Door model found. Run `python scripts/train_door.py --data-dir <path>` once, then reload.")
    else:
        st.caption(f"Model held-out score (IoU-weighted F1): {record.fold_scores.get('held_out_iou_f1', float('nan')):.3f}")
        uploads = st.file_uploader("Drop the test-set stream file(s) (.csv)", type="csv", accept_multiple_files=True)
        if uploads and st.button("Run fault detection", type="primary"):
            all_rows = []
            progress = st.progress(0.0, text="Starting...")
            for i, uploaded in enumerate(uploads):
                progress.progress((i) / len(uploads), text=f"Segmenting and classifying {uploaded.name}...")
                stream = load_stream(save_upload(uploaded, ".csv"))
                result = pipeline.predict(stream)
                df = door_result_to_frame(result)
                df.insert(0, "source_file", uploaded.name)
                all_rows.append(df)
            progress.progress(1.0, text="Done.")
            combined = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()

            if combined.empty:
                st.warning("No door cycles were detected in the uploaded file(s).")
            else:
                n_abnormal = (combined["prediction"] == "Abnormal resistance").sum()
                st.markdown(f"**{len(combined)} cycles found across {len(uploads)} file(s) -- {n_abnormal} flagged as abnormal resistance.**")

                def style_row(row):
                    color = DOOR_LABEL_COLOR.get(row["prediction"], "inherit")
                    return [f"color: {color}; font-weight: 500" if col == "prediction" else "" for col in row.index]

                st.dataframe(combined.style.apply(style_row, axis=1), width='stretch', hide_index=True)

                # Official schema has NO source_file/file_id column for Door --
                # it's scored against one continuous Test.csv stream.
                submission = combined.drop(columns=["source_file"])
                st.download_button(
                    "Download door_predictions.csv", submission.to_csv(index=False).encode(),
                    file_name="door_predictions.csv", mime="text/csv",
                )

# ---------------------------------------------------------------------------
# ACV: batch of case files (currently one in the released test set, but the
# UI supports more without changes).
# ---------------------------------------------------------------------------
elif subsystem == "ACV":
    st.subheader("ACV -- which car has the refrigerant leak")
    st.caption("Rule-based peer-relative ranking -- no training step needed.")
    uploads = st.file_uploader("Drop the test-set case file(s) (.xlsx)", type="xlsx", accept_multiple_files=True)
    if uploads and st.button("Run fault localisation", type="primary"):
        pipeline = ACVPipeline()
        rows = []
        progress = st.progress(0.0, text="Starting...")
        for i, uploaded in enumerate(uploads):
            progress.progress(i / len(uploads), text=f"Scoring {uploaded.name}...")
            result = pipeline.predict_file(save_upload(uploaded, ".xlsx"))
            result.file_id = uploaded.name
            rows.append(result)
        progress.progress(1.0, text="Done.")

        for result in rows:
            top_car = result.ranked_cars[0]
            scores = pd.Series(result.scores)
            # Display-only 0-100 rescale -- ranking/order is untouched, this
            # just keeps the on-screen number readable for a non-technical
            # viewer (raw residual scores can run into the tens of thousands
            # for some files' units).
            lo, hi = scores.min(), scores.max()
            display_scores = ((scores - lo) / (hi - lo) * 100).fillna(50) if hi > lo else scores * 0 + 50
            st.markdown(f"**{result.file_id}** -- most likely faulty car: {badge(top_car, '#D85A30')} "
                        f"(suspicion {display_scores[top_car]:.0f}/100)", unsafe_allow_html=True)
            chart_df = pd.DataFrame({"car": result.ranked_cars, "suspicion (0-100)": [display_scores[c] for c in result.ranked_cars]})
            st.bar_chart(chart_df.set_index("car"), height=160)

        submission = pd.DataFrame(
            [{"file_id": r.file_id, "ranked_cars": "|".join(r.ranked_cars)} for r in rows]
        )
        st.download_button(
            "Download acv_predictions.csv", submission.to_csv(index=False).encode(),
            file_name="acv_predictions.csv", mime="text/csv",
        )

# ---------------------------------------------------------------------------
# Rail: batch of up to ~70 one-second recordings -- the case batch upload
# matters most for.
# ---------------------------------------------------------------------------
elif subsystem == "Rail corrugation":
    st.subheader("Rail corrugation -- Normal / Side I / Side II across the test set")

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
        st.error("No trained Rail model found. Run scripts/extract_rail_features.py then scripts/train_rail.py, then reload.")
    else:
        st.caption(f"Model mean CV macro F1: {record.fold_scores.get('cv_macro_f1_mean', float('nan')):.3f}")
        uploads = st.file_uploader("Drop the test-set recordings (.csv, select all at once)", type="csv", accept_multiple_files=True)
        if uploads and st.button("Run fault classification", type="primary"):
            rows = []
            progress = st.progress(0.0, text="Starting...")
            for i, uploaded in enumerate(uploads):
                progress.progress(i / len(uploads), text=f"Analysing {uploaded.name} ({i + 1}/{len(uploads)})...")
                result = pipeline.predict_file(save_upload(uploaded, ".csv"))
                result.file_id = uploaded.name
                rows.append(result)
            progress.progress(1.0, text="Done.")

            table = pd.DataFrame([
                {"file_id": r.file_id, "prediction": r.prediction,
                 "side_I_score": r.side_scores["Side I"], "side_II_score": r.side_scores["Side II"]}
                for r in rows
            ])
            n_flagged = (table["prediction"] != "Normal").sum()
            st.markdown(f"**{n_flagged} of {len(table)} files flagged with corrugation** "
                        f"({(table['prediction'] == 'Side I').sum()} Side I, {(table['prediction'] == 'Side II').sum()} Side II).")

            flagged = table[table["prediction"] != "Normal"].sort_values("prediction")
            if not flagged.empty:
                st.markdown("**Flagged files:**")

                def style_row(row):
                    color = RAIL_LABEL_COLOR.get(row["prediction"], "inherit")
                    return [f"color: {color}; font-weight: 500" if col == "prediction" else "" for col in row.index]

                st.dataframe(flagged.style.apply(style_row, axis=1), width='stretch', hide_index=True)

            with st.expander(f"Show all {len(table)} files"):
                st.dataframe(table, width='stretch', hide_index=True)

            submission = table[["file_id", "prediction"]]
            st.download_button(
                "Download rail_predictions.csv", submission.to_csv(index=False).encode(),
                file_name="rail_predictions.csv", mime="text/csv",
            )

else:
    st.warning("This subsystem's pipeline isn't implemented yet -- see src/railpulse/shm.")
