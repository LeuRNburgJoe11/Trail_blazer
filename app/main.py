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
