# Trail_blazer
This is Team TrailBlazer's submission for LTA x Nebula Hackathon. Our solution, known as Railpulse, provides advanced condition-monitoring and predictive maintenance pipelines.

See the [19 September architecture audit](docs/ARCHITECTURE_AUDIT.md) for verified
fixes, current validation evidence and remaining limitations. The active model
bundle is `outputs/combined/architecture-audit-final/models`; earlier run folders
are preserved historical results, not interchangeable runtime deployments.

The [rubric audit and dashboard decision layer](docs/DECISION_LAYER.md) adds
traceable review findings, data-quality gates, honest uncertainty and coverage
without changing official predictions. Launch `app/main.py` for the review
dashboard or run `python scripts/build_decisions.py` for dashboard JSON exports.

The separate React/FastAPI prototype in [`app/railpulse/`](app/railpulse/README.md)
is preserved for future UI integration. It has its own duplicate Python package and
model registry; it is not yet wired to the audited four-subsystem decision layer.

The [evidence assistant](docs/ASSISTANT.md) is available in `app/main.py`: local
question answering without a key, source cards, metric explanations and optional
LangChain-based evidence selection. Its backend is reusable by the dashboard team.

A standalone [React agent-interface prototype](app/assistant-ui/README.md) adds
the model picker, OpenAI/Anthropic key connection, source notebook and scoped chat.
It runs on port 5174 with the local canonical assistant API on port 8766.

The [engineering assistant guide](docs/ENGINEERING_ASSISTANT.md) covers attributed
engineer notes, bounded instructions, contextual definitions and review briefings.
Restart an already-running backend after updating to this schema-2 interface.

## Run all four subsystems

```bash
python -m pip install -r requirements-all.txt
python scripts/prepare_data.py --subsystem all
python scripts/run_all.py
python -m streamlit run app/main.py
```

The unified runner validates data, fits on training data only, evaluates Door/ACV/Rail,
loads the frozen SHM model, and writes all four official prediction CSVs plus
`predictions.zip` into a new directory under `outputs/combined/`.
The unified app uses the same frozen inference code. See
[integration and validation details](docs/INTEGRATION.md).
The completed merge run is in [`outputs/combined/merged-main/`](outputs/combined/merged-main/).

## Prepare the official datasets

```bash
python scripts/prepare_data.py --subsystem all --plan
python scripts/prepare_data.py --subsystem all
python scripts/prepare_data.py --subsystem all --verify-only
```

The shared pipeline downloads missing data, references, and example schemas from a
pinned organiser version into the existing subsystem folders. It verifies checksums,
validates schemas and labels, and preserves existing files. A clean setup downloads
approximately 6.46 GB; use `--subsystem door acv` or `--subsystem shm` for a subset.
See [the data preparation guide](docs/DATA_PREPARATION.md) for setup and validation details.

## Structural Health Monitoring

The SHM implementation predicts cumulative fatigue damage from a headerless stress CSV.
It includes verified data download, rainflow features, nested model evaluation, a frozen
model, exact prediction exports, and an upload/download panel. See
[the SHM implementation and run guide](docs/SHM.md) for setup, measured validation results,
limitations, and integration instructions.

## ACV Refrigerant Leakage Localisation
This module contains the backend data-science pipeline for identifying air conditioning ventilation (ACV) refrigerant leakage faults from train telemetry. 

### Approach & Methodology
Because the dataset contains a limited number of independent fault cases (6 labelled cases), we deliberately avoided complex, "black-box" models that are prone to severe overfitting. Instead, we designed a highly robust, explainable pipeline based on **Context-Matched Peer Residuals**:

1. **Dynamic Schema Parsing**: Automatically maps highly variable telemetry columns (e.g., disparate temperature sensor names across different train versions) into a unified, standardised feature space.
2. **Context Matching**: Instead of naively comparing a car's temperature to the rest of the train, the system only compares a car to *valid peer cars operating under the exact same physical conditions* (same running mode, load state, and cooling setpoint).
3. **Transparent Scoring**: Extracts robust median deviations and duty-cycle discrepancies to flag cars that persistently struggle to reach their cooling setpoints compared to their context-matched peers.

### Model Performance (Cross-Validation)
We rigorously evaluated the pipeline using **Leave-One-Case-Out Cross Validation (LOOCV)** to guarantee no data leakage between cases. 

Our transparent Baseline model actually outperformed standard machine learning classifiers (like Logistic Regression) due to its robustness against overfitting on a small dataset. 

**Baseline Evaluation Metrics:**
- **Mean Rank-Decay Score:** `0.979` (out of 1.0)
- **Top-1 Accuracy:** The model correctly placed the true faulty car in exactly **1st place** in 5 out of 6 test folds.
- **Worst-Case Rank:** The model placed the true faulty car in **2nd place** for the single remaining fold.

The final pipeline uses this highly validated logic to generate safe, explainable predictions for unlabelled data.

### Quick Links to Results
All generated results and evaluation reports are stored in the `outputs/acv/` directory. Here are direct links to the key files:

* **Final Model Comparison Summary**: [`model_comparison.csv`](outputs/acv/model_comparison.csv)
  *(This shows the overall performance comparison between the Baseline, Logistic Regression, Random Forest, Gradient Boosting, and SVM).*

* **Final Hackathon Submission (Predictions)**: [`acv_predictions.csv`](outputs/acv/acv_predictions.csv)
  *(This is the official prediction file for `acv_test_case.xlsx` that you will submit for scoring).*

* **Detailed Fold-by-Fold Results**: 
  If you want to see exactly how a specific model ranked cars on a case-by-case basis during cross-validation, you can check its specific breakdown:
  * [`validation_results_baseline.csv`](outputs/acv/validation_results_baseline.csv)
  * [`validation_results_logistic_regression.csv`](outputs/acv/validation_results_logistic_regression.csv)
  * [`validation_results_random_forest.csv`](outputs/acv/validation_results_random_forest.csv)

---

## Running the Pipeline

### 1. Data Preparation
Ensure the dataset is structured in the `data/acv/` folder as follows:
- Training files: `data/acv/Train/*.xlsx`
- Test files: `data/acv/Test/*.xlsx`
- Labels: `data/acv/Train_Labels.csv`

### 2. Feature Engineering
Build the car-level feature dataset across all files by running:
```bash
python scripts/acv/build_features.py
```
This extracts all thermal, control, and peer features into `outputs/acv/train_features.csv`. *(Note: Case 04 is very large and may take a few minutes to process)*.

### 3. Model Training & Evaluation
Train the model and evaluate it using Leave-One-Case-Out Cross Validation (LOOCV). This script evaluates both the transparent Baseline and multiple machine learning challengers:
```bash
python scripts/acv/train.py
```
- **Output reports**: `outputs/acv/model_comparison.csv`
- **Frozen model artifact**: `models/acv/acv_model_artifact.pkl`

### 4. Inference / Prediction
Generate predictions for an unlabelled test case without retraining the model:
```bash
python scripts/acv/predict.py --input data/acv/Test/acv_test_case.xlsx --output outputs/acv/acv_predictions.csv
```
The output CSV perfectly matches the official submission schema (`file_id,ranked_cars`).

### 5. Backend UI Integration
For frontend developers, the analysis pipeline can be called directly to generate rich explanations for the UI:
```python
from railpulse.acv.pipeline import analyse_acv

result = analyse_acv("data/acv/Test/acv_test_case.xlsx", artifact_path="models/acv/acv_model_artifact.pkl")

# Access ranked cars, prediction scores, and top feature contributors for explanations
print(result.ranked_cars)
print(result.top_feature_contributors)
```

## Rail Corrugation

Generate one prediction for every recording in `data/Rail_Corrugation/Test/`:

```bash
python scripts/rail/predict.py
```

The predictions are written to `outputs/rail_predictions.csv` with the columns
`file_id` and `prediction`. To use different paths, pass `--input`, `--labels`, and
`--output`:

```bash
python scripts/rail/predict.py \
	--input data/Rail_Corrugation/Test \
	--labels data/Rail_Corrugation/Train_Labels.csv \
	--output outputs/rail_predictions.csv
```
