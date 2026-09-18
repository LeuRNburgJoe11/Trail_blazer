# ACV Pipeline Results

This directory contains all generated outputs, feature datasets, and evaluation reports for the ACV condition-monitoring pipeline.

## 📁 File Directory

### Final Predictions (Hackathon Submission)
* **`acv_predictions.csv`**
  * The final generated predictions for the unlabelled test case (`acv_test_case.xlsx`). 
  * Formatted to meet the exact official submission schema (`file_id,ranked_cars`).

### Model Evaluation & Cross-Validation
* **`model_comparison.csv`**
  * A high-level summary table comparing the performance of our heuristic Baseline against various machine learning challengers (Logistic Regression, Random Forest, SVM, Gradient Boosting).
  * Metrics include Mean rank-decay score, Median true-car rank, and Top-1 count.
  * *Note: The Baseline drastically outperforms complex models here due to its robustness against overfitting on small case counts.*

* **`validation_results_[model_name].csv`**
  * Detailed, fold-by-fold evaluation logs for each model.
  * Shows exactly how the model performed on each of the 6 held-out cases during Leave-One-Case-Out Cross Validation (LOOCV), including the predicted ranks and the specific score for that fold.

### Feature Datasets
* **`train_features.csv`**
  * The aggregated, car-level feature dataset generated from the raw Excel telemetry.
  * Contains thermal tracking errors, control-state duty cycles, and context-matched peer residuals.
  * Contains exactly one row per car per case.

## 🔄 Regenerating these Results

If you modify the source code or receive new data, you can completely regenerate this folder by running the following scripts in order from the project root:

1. **Rebuild Features**: `python scripts/acv/build_features.py`
2. **Re-run Cross-Validation**: `python scripts/acv/train.py`
3. **Regenerate Predictions**: `python scripts/acv/predict.py --input data/acv/Test/acv_test_case.xlsx --output outputs/acv/acv_predictions.csv`

