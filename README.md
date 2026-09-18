# Trail_blazer
This is Team TrailBlazer's submission for LTA x Nebula Hackathon. Our solution, known as Railpulse, provides advanced condition-monitoring and predictive maintenance pipelines.

## ACV Refrigerant Leakage Localisation
This module contains the backend data-science pipeline for identifying air conditioning ventilation (ACV) refrigerant leakage faults from train telemetry. 

The pipeline uses dynamic schema parsing, thermal/control feature engineering, and context-matched peer residuals to rank cars from most likely to least likely to have a fault.

### 1. Data Preparation
Ensure the dataset is structured in the `data/` folder as follows:
- Training files: `data/Train/*.xlsx`
- Test files: `data/Test/*.xlsx`
- Labels: `data/Train_Labels.csv`

### 2. Feature Engineering
Build the car-level feature dataset across all files by running:
```bash
python scripts/build_features.py
```
This extracts all thermal, control, and peer features into `outputs/train_features.csv`. *(Note: Case 04 is very large and may take a few minutes to process)*.

### 3. Model Training & Evaluation
Train the model and evaluate it using Leave-One-Case-Out Cross Validation (LOOCV). This script evaluates both a transparent heuristic Baseline and a Logistic Regression challenger:
```bash
python scripts/train.py
```
- **Output reports**: `outputs/model_comparison.csv`
- **Frozen model artifact**: `models/acv_model_artifact.pkl`

### 4. Inference / Prediction
Generate predictions for an unlabelled test case without retraining the model:
```bash
python scripts/predict.py --input data/Test/acv_test_case.xlsx --output outputs/acv_predictions.csv
```
The output CSV perfectly matches the official submission schema (`file_id,ranked_cars`).

### 5. Backend UI Integration
For frontend developers, the analysis pipeline can be called directly to generate rich explanations for the UI:
```python
from railpulse.acv.pipeline import analyse_acv

result = analyse_acv("data/Test/acv_test_case.xlsx", artifact_path="models/acv_model_artifact.pkl")

# Access ranked cars, prediction scores, and top feature contributors for explanations
print(result.ranked_cars)
print(result.top_feature_contributors)
```
