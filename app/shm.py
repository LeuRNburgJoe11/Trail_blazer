"""Run with: streamlit run app/shm.py. render_shm_panel can join the team's shared app."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd
import streamlit as st

from railpulse.shm.uploads import analyse_uploads

 
def render_shm_panel(artifact_path=ROOT / "models/shm/model.joblib"):
    st.title("Structural fatigue assessment")
    st.write("Upload stress recordings to estimate cumulative fatigue damage for each recording.")
    st.caption("Use CSV files containing one numeric stress column without a header. Values must use the original dataset's stress scale.")
    files = st.file_uploader("Stress recordings", type=["csv"], accept_multiple_files=True)
    if not Path(artifact_path).exists():
        st.error("The trained SHM model is unavailable. Ask your project administrator to install it.")
        return
    if files:
        try:
            with st.spinner("Analysing stress cycles…"):
                results, csv_bytes = analyse_uploads([(f.name, f.getvalue()) for f in files], artifact_path)
            st.dataframe(pd.DataFrame([{"Recording": r.file_id, "Estimated damage": r.prediction}
                                      for r in results]), hide_index=True)
            st.download_button("Download predictions", csv_bytes, "shm_predictions.csv", "text/csv")
            for result in results:
                with st.expander(f"Evidence — {result.file_id}"):
                    for warning in result.warnings:
                        st.warning(warning)
                    st.write({"Counted stress cycles": result.evidence["cycle_count"],
                              "RMS stress (source units)": result.evidence["stress_rms"],
                              "Largest cycle amplitude (source units)": result.evidence["amplitude_max"],
                              "Samples": int(result.evidence["n_samples"])})
                    st.caption("Higher-amplitude cycles contribute more to the fitted fatigue estimate.")
        except (ValueError, OSError, KeyError) as exc:
            st.error(f"Unable to analyse these recordings: {exc}")
    st.caption("Estimates apply to the uploaded recording. They do not establish remaining service life or a maintenance deadline.")


if __name__ == "__main__":
    st.set_page_config(page_title="RailPulse · Structural fatigue", layout="centered")
    render_shm_panel()

