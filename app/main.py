"""Unified local RailPulse application using the same frozen path as run_all.py."""
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from railpulse.core.inference import load_bundle
from railpulse.core.decisions import analyse_decision, decision_payload
from railpulse.core.dashboard import dashboard_summary
from railpulse.core.runtime import DEFAULT_RUN
from railpulse.core.predictions import csv_bytes

st.set_page_config(page_title="RailPulse", layout="wide")
st.title("RailPulse — four-subsystem condition monitoring")
st.caption("Frozen model inference. Test labels are unavailable; predictions are not maintenance instructions.")
st.info("Review support only. Fault classes and rankings are model findings—not confirmed faults. SHM damage is not remaining life.")
model_directory = st.sidebar.text_input("Trusted local model bundle", str(DEFAULT_RUN / "models"))
subsystem = st.selectbox("Subsystem", ["door", "acv", "rail", "shm"])
uploads = st.file_uploader("Upload recordings", type=["xlsx"] if subsystem == "acv" else ["csv"],
                           accept_multiple_files=subsystem != "door")
items = uploads if isinstance(uploads, list) else [uploads] if uploads else []
if "exports" not in st.session_state:
    st.session_state.exports = {}
if "decisions" not in st.session_state:
    st.session_state.decisions = {}
if "failures" not in st.session_state:
    st.session_state.failures = {}
# Invalidate displayed results immediately when the bundle changes, even before
# a new upload is analysed. Never relabel stale outputs with a new model path.
try:
    current_signature = hashlib.sha256((Path(model_directory) / "bundle.json").read_bytes()).hexdigest()
except OSError:
    current_signature = None
if st.session_state.get("bundle_signature") != current_signature:
    st.session_state.exports = {}
    st.session_state.decisions = {}
    st.session_state.failures = {}
    st.session_state.bundle_signature = current_signature
if st.sidebar.button("Clear session predictions"):
    st.session_state.exports = {}
    st.session_state.decisions = {}
    st.session_state.failures = {}
if st.button("Analyse", disabled=not items):
    # Do not show a stale successful export for a failed replacement upload.
    previous = st.session_state.exports.pop(subsystem, None)
    previous_decisions = st.session_state.decisions.pop(subsystem, {})
    st.session_state.failures.pop(subsystem, None)
    try:
        names = [upload.name for upload in items]
        if len(names) != len(set(names)) or any(Path(name).name != name or "\\" in name for name in names):
            raise ValueError("Upload names must be unique basenames")
        if sum(upload.size for upload in items) > 250 * 1024 * 1024:
            raise ValueError("Upload at most 250 MB per batch")
        with st.spinner("Running frozen inference…"), tempfile.TemporaryDirectory(prefix="railpulse-upload-") as directory:
            bundle = load_bundle(model_directory)
            signature = hashlib.sha256((Path(model_directory) / "bundle.json").read_bytes()).hexdigest()
            if st.session_state.get("bundle_signature") != signature:
                st.session_state.exports = {}
                st.session_state.decisions = {}
                st.session_state.failures = {}
                previous = None
                previous_decisions = {}
            st.session_state.bundle_signature = signature
            results = []
            decisions = {} if subsystem == "door" else dict(previous_decisions)
            for upload in items:
                path = Path(directory) / upload.name
                path.write_bytes(upload.getvalue())
                result, records = analyse_decision(subsystem, path, bundle)
                decisions[upload.name] = [record.to_dict() for record in records]
                results.append(result.frame)
                for warning in result.warnings:
                    st.warning(f"{upload.name}: {warning}")
            frame = pd.concat(results, ignore_index=True)
            # Rail inputs exceed a gigabyte altogether. Accumulate small batches
            # in the session; rerunning a filename replaces its earlier prediction.
            if previous is not None and subsystem != "door":
                old = pd.read_csv(io.BytesIO(previous), dtype={"file_id": str, "ranked_cars": str})
                frame = pd.concat([old, frame], ignore_index=True).drop_duplicates("file_id", keep="last")
                frame = frame.sort_values("file_id").reset_index(drop=True)
            exported = csv_bytes(subsystem, frame)
            st.session_state.exports[subsystem] = exported
            st.session_state.decisions[subsystem] = decisions
    except Exception as exc:
        st.session_state.failures[subsystem] = {"status": "rejected", "error": str(exc),
                                               "filenames": [upload.name for upload in items]}

if subsystem == "rail":
    st.divider()
    st.header("Rail corrugation dashboard")
    st.caption("Side-aware review of 1-second axle-box recordings. Red indicates a model fault candidate; it is not a confirmed maintenance diagnosis.")

    rail_cols = st.columns([1.35, 1, 1])
    with rail_cols[0]:
        diagram = ROOT / "references" / "Rail_Corrugation" / "images" / "image2.png"
        if diagram.is_file():
            st.image(str(diagram), caption="Axle-box positions used by the rail pipeline", width="stretch")
        else:
            st.warning("Rail sensor layout image is unavailable in this checkout.")
    with rail_cols[1]:
        st.subheader("Sensor map")
        st.metric("Channels per recording", "129")
        st.metric("Sampling window", "10,000 samples / 1 s")
        st.markdown("**Side I**  · positions 1, 3, 5, 7")
        st.markdown("**Side II** · positions 2, 4, 6, 8")
    with rail_cols[2]:
        labels_path = ROOT / "data" / "Rail_Corrugation" / "Train_Labels.csv"
        if labels_path.is_file():
            label_counts = pd.read_csv(labels_path)["label"].value_counts().reindex(
                ["Normal", "Side I", "Side II"], fill_value=0
            )
            st.subheader("Training balance")
            st.metric("Training recordings", f"{int(label_counts.sum())}")
            st.bar_chart(label_counts.rename("recordings"), height=170, color="#e45756")
        else:
            st.warning("Training labels are unavailable; class balance cannot be shown.")

    run_report = Path(model_directory).parent / "run_summary.json"
    if run_report.is_file():
        rail_validation = json.loads(run_report.read_text(encoding="utf-8")).get("validation", {}).get("rail", {})
        st.subheader("Model evidence")
        evidence_cols = st.columns(4)
        evidence_cols[0].metric("Selected model", rail_validation.get("selected_model", "Unavailable"))
        evidence_cols[1].metric("Nested CV macro F1", f"{rail_validation.get('nested_selection_mean_macro_f1', float('nan')):.3f}")
        evidence_cols[2].metric("Pooled OOF macro F1", f"{rail_validation.get('candidates', {}).get('pooled_spatial', {}).get('pooled_oof_macro_f1', float('nan')):.3f}")
        evidence_cols[3].metric("CV folds", len(rail_validation.get("candidates", {}).get("pooled_spatial", {}).get("fold_macro_f1", [])))
        fold_scores = rail_validation.get("candidates", {}).get("pooled_spatial", {}).get("fold_macro_f1", [])
        if fold_scores:
            st.line_chart(pd.Series(fold_scores, index=[f"Fold {index}" for index in range(1, len(fold_scores) + 1)], name="macro F1"), height=180)
        st.caption(rail_validation.get("limitations", "Validation evidence is unavailable."))
    else:
        st.info("Run evidence is unavailable for this model directory. Live predictions can still be reviewed after analysis.")

    rail_export = st.session_state.exports.get("rail")
    if rail_export:
        rail_predictions = pd.read_csv(io.BytesIO(rail_export))
        distribution = rail_predictions["prediction"].value_counts().reindex(
            ["Normal", "Side I", "Side II"], fill_value=0
        )
        st.subheader("Current batch")
        result_cols = st.columns(4)
        result_cols[0].metric("Files analysed", len(rail_predictions))
        result_cols[1].metric("Normal", int(distribution["Normal"]))
        result_cols[2].metric("Side I candidates", int(distribution["Side I"]))
        result_cols[3].metric("Side II candidates", int(distribution["Side II"]))
        st.bar_chart(distribution.rename("files"), height=180, color="#f2c14e")
        flagged = rail_predictions[rail_predictions["prediction"] != "Normal"]
        if flagged.empty:
            st.success("No corrugation candidates in the current batch.")
        else:
            st.warning(f"{len(flagged)} file(s) require rail-side review.")
            st.dataframe(flagged, hide_index=True, width="stretch")

if subsystem == "shm":
    st.divider()
    st.header("Structural health monitoring dashboard")
    st.caption(
        "Cumulative fatigue-damage regression via ASTM E1049 Rainflow counting "
        "+ calibrated 5th-power Basquin law (physics_5). "
        "Miner\u2019s rule: D = \u03a3(n\u1d62 / N\u1d62), N\u1d62 = C / \u03c3\u2090\u1d62\u2075. "
        "D \u2265 1.0 indicates crack-initiation risk. "
        "Model output is not remaining useful life \u2014 refer to engineering authority before maintenance action."
    )

    # --- Physics & sensor overview ---
    shm_cols = st.columns([1.2, 1, 1])
    with shm_cols[0]:
        sig_diag = ROOT / "outputs" / "shm" / "signal_and_cycle_diagnostics.png"
        if sig_diag.is_file():
            st.image(str(sig_diag), caption="Signal & rainflow-cycle diagnostics (training set)", use_container_width=True)
        else:
            st.info("Diagnostic image unavailable in this checkout.")
    with shm_cols[1]:
        st.subheader("Physics model")
        st.metric("Selected model", "physics_5")
        st.metric("Fatigue exponent (m)", "5.0  (Basquin / ASTM E1049)")
        st.metric("Damage rule", "Miner linear accumulation")
        st.markdown("**Input**: stress amplitude time-series (CSV)")
        st.markdown("**Rainflow**: half-cycle counts per amplitude bin")
        st.markdown("**Output**: cumulative damage index D \u2208 [0, \u221e)")
    with shm_cols[2]:
        st.subheader("Validation protocol")
        st.metric("CV scheme", "2\u00d78 outer / 4 inner folds")
        st.metric("Training files", "64")
        st.metric("Score formula", "max(0, 1 \u2212 MAPE)")
        st.markdown("File-level cross-validation \u2014 no sample leakage across files.")

    # --- Nested-CV validation evidence ---
    run_report_shm = Path(model_directory).parent / "run_summary.json"
    training_summary = ROOT / "outputs" / "shm" / "training_summary.json"
    shm_validation = {}
    if run_report_shm.is_file():
        shm_validation = json.loads(run_report_shm.read_text(encoding="utf-8")).get("validation", {}).get("shm", {})
    if not shm_validation and training_summary.is_file():
        shm_validation = json.loads(training_summary.read_text(encoding="utf-8")).get("nested_evaluation", {})

    if shm_validation:
        st.subheader("Model evidence (nested cross-validation)")
        ev_cols = st.columns(5)
        mape_val = shm_validation.get("mape", float("nan"))
        score_val = shm_validation.get("score", float("nan"))
        mae_val = shm_validation.get("mae", float("nan"))
        worst_ape = shm_validation.get("worst_ape", float("nan"))
        fold_std = shm_validation.get("fold_mape_std", float("nan"))
        ev_cols[0].metric("Nested MAPE", f"{mape_val * 100:.2f} %")
        ev_cols[1].metric("Score (1 \u2212 MAPE)", f"{score_val:.4f}")
        ev_cols[2].metric("Nested MAE", f"{mae_val:.4f}")
        ev_cols[3].metric("Worst-fold APE", f"{worst_ape * 100:.1f} %")
        ev_cols[4].metric("Fold MAPE std", f"{fold_std * 100:.2f} %")
        st.caption(
            f"n_files={shm_validation.get('n_files', '?')}, "
            f"n_predictions={shm_validation.get('n_predictions', '?')}. "
            "Nested CV prevents model-selection bias; score reported here differs from held-out test score."
        )
        val_diag = ROOT / "outputs" / "shm" / "validation_diagnostics.png"
        if val_diag.is_file():
            with st.expander("Validation diagnostics (predicted vs actual)"):
                st.image(str(val_diag), use_container_width=True)
    else:
        st.info("Run evidence unavailable for this model directory. Live predictions can still be reviewed after analysis.")

    # --- Current batch results ---
    shm_export = st.session_state.exports.get("shm")
    if shm_export:
        shm_df = pd.read_csv(io.BytesIO(shm_export))

        def _rag(d):
            try:
                v = float(d)
            except (TypeError, ValueError):
                return "Unknown"
            if v >= 0.40:
                return "\U0001f534 Red"
            if v >= 0.10:
                return "\U0001f7e0 Amber"
            return "\U0001f7e2 Green"

        damage_col = next((c for c in shm_df.columns if "damage" in c.lower()), None)
        if damage_col:
            shm_df["RAG status"] = shm_df[damage_col].apply(_rag)
            rag_counts = shm_df["RAG status"].value_counts()

            st.subheader("Current batch")
            batch_cols = st.columns(4)
            batch_cols[0].metric("Files analysed", len(shm_df))
            batch_cols[1].metric("\U0001f7e2 Green (D < 0.10)", int(rag_counts.get("\U0001f7e2 Green", 0)))
            batch_cols[2].metric("\U0001f7e0 Amber (0.10 \u2013 0.40)", int(rag_counts.get("\U0001f7e0 Amber", 0)))
            batch_cols[3].metric("\U0001f534 Red (D \u2265 0.40)", int(rag_counts.get("\U0001f534 Red", 0)))

            rag_order = ["\U0001f7e2 Green", "\U0001f7e0 Amber", "\U0001f534 Red"]
            rag_series = rag_counts.reindex(rag_order, fill_value=0).rename("files")
            st.bar_chart(rag_series, height=180, color="#e45756")

            red_files = shm_df[shm_df["RAG status"] == "\U0001f534 Red"]
            amber_files = shm_df[shm_df["RAG status"] == "\U0001f7e0 Amber"]
            if not red_files.empty:
                st.warning(
                    f"\U0001f534 {len(red_files)} file(s) with D \u2265 0.40 \u2014 "
                    "priority weld NDT inspection recommended. Refer to engineering authority."
                )
            if not amber_files.empty:
                st.info(f"\U0001f7e0 {len(amber_files)} file(s) in Amber zone (0.10 \u2264 D < 0.40) \u2014 schedule routine inspection.")
            if red_files.empty and amber_files.empty:
                st.success("All files in current batch are Green (D < 0.10). No immediate inspection triggered.")

            display_cols = (
                [c for c in ["file_id", damage_col, "RAG status"] if c in shm_df.columns]
                + [c for c in shm_df.columns if c not in ["file_id", damage_col, "RAG status"]]
            )
            st.dataframe(shm_df[display_cols], hide_index=True, use_container_width=True)
        else:
            st.dataframe(shm_df, hide_index=True, use_container_width=True)
            st.warning("Could not identify a damage column for RAG classification.")

for name, failure in st.session_state.failures.items():
    st.error(f"{name.upper()} analysis rejected: {failure['error']}")
    st.caption("No export is available for the rejected subsystem batch. Fix the input/model issue and retry; other subsystem results are unchanged.")
if st.session_state.failures:
    st.download_button("Download rejected-batch diagnostics", json.dumps(st.session_state.failures, indent=2),
                       "rejected_batches.json", "application/json")

records = [record for files in st.session_state.decisions.values() for rows in files.values() for record in rows]
lock = json.loads((ROOT / "configs/dataset_lock.json").read_text())
expected_files = {name: sorted({Path(entry["path"]).name for entry in lock["files"]
                              if entry["subsystem"] == name and ("/Test/" in entry["path"] or entry["path"] == "data/Door/Test.csv")
                              and Path(entry["path"]).suffix in (".csv", ".xlsx")}) for name in ("door", "acv", "rail", "shm")}
summary = dashboard_summary(records, expected_files)
st.subheader("Review dashboard")
panels = st.columns(4)
panels[0].metric("Subsystems analysed", f"{len(st.session_state.exports)} / 4")
panels[1].metric("Findings needing review", sum(record["review_required"] for record in records))
panels[2].metric("Overall test score", "Not available")
panels[3].metric("Average test score", "Not available")
st.caption("Overall = sum of four subsystem scores ÷ 4. Average = sum ÷ attempted subsystems. Neither can be calculated without ground truth.")
coverage = pd.DataFrame(summary["subsystems"])
st.dataframe(coverage[["subsystem", "uploaded_files", "expected_files", "filename_coverage", "review_required", "quality_flags"]], hide_index=True)
st.caption(summary["coverage_note"])
with st.expander("Metric contracts and validation evidence"):
    st.table(pd.DataFrame([
        {"Subsystem": "Door", "Task": "Temporal segmentation + binary status", "Metric": "IoU-weighted F1", "Weight": "25%"},
        {"Subsystem": "ACV", "Task": "Rank all native car IDs", "Metric": "(n - rank + 1) / n", "Weight": "25%"},
        {"Subsystem": "Rail", "Task": "Normal / Side I / Side II", "Metric": "Macro F1 over all three classes", "Weight": "25%"},
        {"Subsystem": "SHM", "Task": "Cumulative damage regression", "Metric": "max(0, 1 - fractional MAPE)", "Weight": "25%"},
    ]))
    run_report = Path(model_directory).parent / "run_summary.json"
    if run_report.is_file():
        st.caption("Stored training/validation evidence, not live test scores. Different protocols and model-selection bias apply.")
        st.json(json.loads(run_report.read_text()).get("validation", {}))
if records:
    ordered = json.loads(decision_payload(records))["records"]
    table = pd.DataFrame([{key: record[key] for key in ("subsystem", "file_id", "entity_id", "finding", "quality", "review_priority", "summary", "suggested_review")} for record in ordered])
    st.caption("Priority 30: quality/model warnings; 20: fault/localisation review; 10: engineering context; 0: retain observation. These are queue priorities—not severity or failure probabilities.")
    review_only = st.checkbox("Show only findings needing review", value=False)
    if review_only:
        table = table.loc[[record["review_required"] for record in ordered]]
    st.dataframe(table, hide_index=True)
    st.bar_chart(pd.Series([record["finding"] for record in records]).value_counts().rename("Findings"))
    with st.expander("Evidence, reasons, uncertainty and provenance"):
        st.json(json.loads(decision_payload(ordered)))
    st.download_button("Download dashboard decisions (JSON)", decision_payload(records), "dashboard_decisions.json", "application/json")
    st.download_button("Download review queue (CSV)", table.to_csv(index=False).encode(), "review_queue.csv", "text/csv")
    with st.expander("Official model predictions (unchanged)"):
        for name, exported in st.session_state.exports.items():
            st.write(name.upper())
            st.dataframe(pd.read_csv(io.BytesIO(exported)), hide_index=True)
for name, exported in st.session_state.exports.items():
    st.download_button(f"Download {name} predictions", exported, f"{name}_predictions.csv", "text/csv", key=name)
if st.session_state.exports:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, exported in sorted(st.session_state.exports.items()):
            archive.writestr(f"{name}_predictions.csv", exported)
    st.download_button("Download predictions.zip", archive_bytes.getvalue(), "predictions.zip", "application/zip")
    st.caption("The ZIP contains only the subsystem uploads analysed in this session; check test-file coverage before submission.")
