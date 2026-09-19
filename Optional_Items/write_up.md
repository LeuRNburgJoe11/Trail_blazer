# RailPulse

**A reproducible condition-monitoring pipeline for four rail-vehicle subsystems, built around a single canonical inference path and contract-validated outputs.**

## Subsystem models

| Subsystem | Approach |
|---|---|
| **Door resistance** | Segments the continuous signal into complete open/close cycles, then classifies each cycle as Normal or Abnormal. |
| **ACV refrigerant leak** | Ranks native car IDs by residuals against context-matched peers (compatible operating conditions), avoiding a global-mean baseline that operating-condition variance would dominate. |
| **Rail corrugation** | Vibration and shock signals are transformed into spectral and spatial features. Pooling is side-aware, so Side I and Side II faults are not masked by aggregation. |
| **SHM** | Rainflow cycle counting produces stress-cycle features, which feed a frozen cumulative-fatigue-damage model. |

## Architecture

- **Single inference path.** Training, validation, batch prediction, and the UI all call the same canonical inference code, so there is no train/serve divergence.
- **Frozen, checksum-verified model bundles** with runtime metadata. Uploads never trigger retraining or model selection.
- **Contract validation on every export:** Door timestamps, native two-digit ACV car IDs, Rail class names, SHM numeric constraints, exact file coverage, and CSV schemas.
- **Non-invasive diagnostics.** The dashboard surfaces evidence, warnings, coverage, uncertainty, and review priorities without modifying the official predictions. Outputs are review candidates, not maintenance directives.

## Stack and deployment

Python 3.11 with NumPy, pandas, SciPy, scikit-learn, joblib, rainflow, and openpyxl. Streamlit provides upload, analysis, review, and export (per-subsystem CSVs plus a compliant predictions ZIP). The app is containerised and deployed through Cloud Build and Artifact Registry to Cloud Run: **[URL]**

## Results

[Per-subsystem validation metrics, split strategy, and baseline comparison]