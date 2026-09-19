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

- **Explicit inference boundaries.** The canonical batch workflow uses its frozen bundle. The React dashboard uses canonical Door/SHM inference, a dashboard ACV ranker and a separate Rail registry model; their validation must not be presented as interchangeable.
- **Frozen, checksum-verified model bundles** with runtime metadata. Uploads never trigger retraining or model selection.
- **Contract validation on every export:** Door timestamps, native two-digit ACV car IDs, Rail class names, SHM numeric constraints, exact file coverage, and CSV schemas.
- **Non-invasive diagnostics.** The dashboard surfaces evidence, warnings, coverage, uncertainty, and review priorities without modifying the official predictions. Outputs are review candidates, not maintenance directives.

## Stack and deployment

React provides the dashboard and RailPulser interface, with a FastAPI backend running Python 3.13 in Docker. Numerical pipelines use NumPy, pandas, SciPy, scikit-learn, joblib, rainflow and openpyxl. The dashboard exports per-subsystem CSVs; the canonical batch workflow creates the validated predictions ZIP. Cloud Run deployment is planned, not yet verified: **[URL pending deployment]**.

## Results

[Per-subsystem validation metrics, split strategy, and baseline comparison]
