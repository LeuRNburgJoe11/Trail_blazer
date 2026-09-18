"""Unified local RailPulse application using the same frozen path as run_all.py."""
import io
import hashlib
from pathlib import Path
import sys
import tempfile
import zipfile

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from railpulse.core.inference import load_bundle, predict_file
from railpulse.core.predictions import csv_bytes

st.set_page_config(page_title="RailPulse", layout="wide")
st.title("RailPulse — four-subsystem condition monitoring")
st.caption("Frozen model inference. Test labels are unavailable; predictions are not maintenance instructions.")
model_directory = st.sidebar.text_input("Trusted local model bundle", str(ROOT / "outputs/combined/merged-main/models"))
subsystem = st.selectbox("Subsystem", ["door", "acv", "rail", "shm"])
uploads = st.file_uploader("Upload recordings", type=["xlsx"] if subsystem == "acv" else ["csv"],
                           accept_multiple_files=subsystem != "door")
items = uploads if isinstance(uploads, list) else [uploads] if uploads else []
if "exports" not in st.session_state:
    st.session_state.exports = {}
if st.sidebar.button("Clear session predictions"):
    st.session_state.exports = {}
if st.button("Analyse", disabled=not items):
    # Do not show a stale successful export for a failed replacement upload.
    previous = st.session_state.exports.pop(subsystem, None)
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
                previous = None
            st.session_state.bundle_signature = signature
            results = []
            for upload in items:
                path = Path(directory) / upload.name
                path.write_bytes(upload.getvalue())
                result = predict_file(subsystem, path, bundle)
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
            st.dataframe(frame, hide_index=True)
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
for name, exported in st.session_state.exports.items():
    st.download_button(f"Download {name} predictions", exported, f"{name}_predictions.csv", "text/csv", key=name)
if st.session_state.exports:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, exported in sorted(st.session_state.exports.items()):
            archive.writestr(f"{name}_predictions.csv", exported)
    st.download_button("Download predictions.zip", archive_bytes.getvalue(), "predictions.zip", "application/zip")
    st.caption("The ZIP contains only the subsystem uploads analysed in this session; check test-file coverage before submission.")
