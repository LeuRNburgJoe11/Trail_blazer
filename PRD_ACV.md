# PRD — RailPulse ACV Refrigerant Leakage Localisation

## 1. Project Overview

Build an ACV-only condition-monitoring pipeline for the NebulaX Hackathon PS3 dataset.

The system must analyse one train ACV telemetry `.xlsx` file containing measurements from multiple train cars and rank every car from most likely to least likely to have a refrigerant leakage fault.

This is a ranking/localisation problem, not a generic anomaly-detection problem and not a binary file-level classification problem.

The implementation should prioritise:

- correct data handling
- physically meaningful feature engineering
- peer-relative comparison between cars
- operating-context awareness
- prevention of data leakage
- interpretable ranking
- reproducible leave-one-case-out validation
- exact competition output formatting

Do not build a user interface in this project. Another developer will integrate this ACV pipeline into the final application later.

---

# 2. Dataset Context

Training data consists of six labelled ACV case files.

Each case:

- is stored as one `.xlsx` file
- contains continuous telemetry from all train cars
- contains exactly one refrigerant-leakage faulty car
- contains approximately 8 cars
- is sampled approximately every 30 seconds
- contains identifying columns plus car-specific telemetry
- may contain a different set of telemetry parameters from other cases

Training labels are stored in:

`Train_Labels.csv`

with columns conceptually equivalent to:

```text
filename,faulty_car
acv_case_01.xlsx,01
acv_case_02.xlsx,02
...
```

The test dataset contains an unlabelled ACV `.xlsx` file.

The model must rank all cars in the file.

Required competition output:

```csv
file_id,ranked_cars
acv_test_case.xlsx,03|01|05|02|04|06|07|08
```

Car identifiers must be preserved exactly as strings.

For example:

`03`

must remain:

`03`

and must never become:

`3`

or:

`Car 3`.

---

# 3. Core Modelling Principle

Treat the ACV problem as:

> Which car behaves most abnormally relative to other cars operating under comparable conditions in the same train case?

Do not treat individual timestamps as independent labelled training samples.

The true number of independent labelled examples is governed primarily by the six case files.

The high-level pipeline must be:

```text
ACV .xlsx
    ↓
Dynamic schema parsing
    ↓
Automatic car identification
    ↓
Per-car telemetry extraction
    ↓
Data-quality analysis
    ↓
Thermal + control feature extraction
    ↓
Context-aware peer-relative features
    ↓
One feature vector per car
    ↓
Transparent baseline ranking
    ↓
Optional supervised ranking model
    ↓
Rank all cars
    ↓
Generate competition-format CSV
```

---

# 4. Out of Scope

Do not implement the following in the initial ACV project:

* web UI
* Streamlit
* authentication
* dashboards
* Door subsystem
* Rail Corrugation subsystem
* SHM subsystem
* real-time telemetry streaming
* fleet-wide monitoring
* remaining-useful-life prediction
* Transformers
* LSTMs
* GDN
* TranAD
* large neural networks
* large hyperparameter searches
* complex ensembles

The ACV dataset is too small at the case level to justify beginning with large sequence models.

A simple model must establish a validated baseline before any sophisticated approach is considered.

---

# 5. Proposed Repository Structure

Create the project with the following structure:

```text
railpulse_acv/
│
├── data/
│   ├── Train/
│   ├── Test/
│   └── Train_Labels.csv
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_exploration.ipynb
│   └── 03_model_validation.ipynb
│
├── src/
│   └── acv/
│       ├── __init__.py
│       ├── loader.py
│       ├── schema.py
│       ├── preprocessing.py
│       ├── thermal_features.py
│       ├── control_features.py
│       ├── peer_features.py
│       ├── feature_pipeline.py
│       ├── baseline.py
│       ├── models.py
│       ├── ranking.py
│       ├── validation.py
│       ├── metrics.py
│       ├── explain.py
│       └── pipeline.py
│
├── scripts/
│   ├── inspect_dataset.py
│   ├── build_features.py
│   ├── evaluate.py
│   ├── train.py
│   └── predict.py
│
├── models/
│
├── outputs/
│
├── tests/
│   ├── test_loader.py
│   ├── test_schema.py
│   ├── test_features.py
│   ├── test_peer_features.py
│   ├── test_metric.py
│   ├── test_ranking.py
│   └── test_export.py
│
├── requirements.txt
├── README.md
└── PRD.md
```

---

# 6. Phase 1 — Dataset Inspection

Before implementing any machine-learning model, inspect all training and test files.

Build a dataset manifest containing, for every file:

```text
filename
number of rows
number of columns
detected car IDs
number of cars
timestamp column
start timestamp
end timestamp
estimated sampling interval
available parameters per car
parameters common to all cars
parameters unique to individual files
missing-value fraction
duplicate timestamps
invalid/non-numeric values
```

Save the manifest in a machine-readable format such as:

```text
outputs/dataset_manifest.csv
```

and optionally:

```text
outputs/dataset_manifest.json
```

The implementation must not assume that all case files contain the same columns.

---

# 7. ACV Column Parser

Per-car columns are expected to follow a pattern similar to:

```text
Car 03 - ACV Running Mode
Car 03 - Indoor Average Temperature
Car 03 - Outdoor Average Temperature
```

Implement automatic parsing using a regex similar to:

```python
r"Car\s+(\d+)\s*-\s*(.+)"
```

The parser must return:

```python
car_id
parameter_name
original_column_name
```

Example internal representation:

```python
{
    "01": {
        "Indoor Average Temperature": "Car 01 - Indoor Average Temperature",
        "ACV Running Mode": "Car 01 - ACV Running Mode"
    },
    "02": {
        ...
    }
}
```

Never identify cars using fixed column positions.

Never assume cars are always ordered from `01` to `08`.

---

# 8. Normalised Internal Data Representation

Implement:

```python
load_acv_case(path) -> ACVCase
```

Suggested logical structure:

```python
ACVCase(
    filename="acv_case_01.xlsx",
    timestamps=<Series>,
    metadata=<dict>,
    car_ids=["01", "02", "03", ...],
    cars={
        "01": <DataFrame>,
        "02": <DataFrame>,
        ...
    },
    available_parameters=<dict>,
    warnings=<list>
)
```

The loader must:

* preserve original identifiers
* preserve original timestamps
* sort timestamps if required
* report duplicate timestamps
* convert clearly numeric telemetry into numeric types
* leave categorical states categorical
* retain missing values rather than blindly filling everything
* never modify the source files

---

# 9. Feature Availability Strategy

Divide features into:

## Core features

Features derived from signals available across most/all case files.

Likely candidates include:

```text
Indoor average temperature
Outdoor average temperature
Cooling control temperature / setpoint
Heating control temperature / setpoint
ACV running mode
Setting mode
Load-halved status
Information-valid status
```

Do not hard-code these names without first confirming the actual dataset column strings.

Create a mapping layer for equivalent parameter names if required.

## Optional features

Some files may contain additional telemetry.

Optional signals may be used experimentally but must never be required for the main baseline model.

For every optional feature, generate an availability indicator where useful.

Example:

```python
compressor_signal_available = True
```

Do not silently replace missing optional telemetry with zero if zero has a physical meaning.

---

# 10. Data Exploration

Create `01_data_exploration.ipynb`.

For every training case:

* identify the known faulty car
* compare all cars visually
* inspect missing values
* inspect temperature signals
* inspect operating modes
* inspect setpoints
* inspect load status
* inspect control-state transitions

Generate plots comparing all cars for available signals such as:

```text
Indoor temperature vs time
Outdoor temperature vs time
Cooling setpoint vs time
Indoor temperature minus cooling setpoint
Running mode vs time
Setting mode vs time
Load-halved status vs time
```

For training-data exploration only, visibly highlight the known faulty car.

The purpose of this notebook is to identify patterns that repeatedly distinguish faulty cars across multiple independent cases.

Do not use test labels or hidden information.

---

# 11. Feature Engineering Unit

The main modelling unit is:

```text
one car within one case
```

Therefore:

```text
time-series telemetry
       ↓
feature extraction
       ↓
one feature vector per car
```

Six cases with eight cars each produce approximately:

```text
48 car-case feature rows
```

but these must not be treated as 48 completely independent cases during validation.

Expected feature table:

```text
case_id
car_id
temp_error_median
temp_error_p90
peer_temp_residual_median
peer_temp_residual_p90
cooling_duty
mode_switch_rate
valid_data_fraction
...
faulty
```

`case_id` and `car_id` are identifiers only.

They must not be used as predictive model inputs.

---

# 12. Thermal Features

Where the relevant signals exist, calculate:

```text
indoor_temperature
outdoor_temperature
cooling_setpoint
```

Define temperature tracking error:

```text
temperature_error =
indoor_temperature - cooling_setpoint
```

Candidate thermal features:

```text
median temperature error
mean absolute temperature error
90th percentile absolute temperature error
95th percentile absolute temperature error
maximum absolute temperature error
temperature-error standard deviation
temperature-error MAD
fraction of valid time error > 1°C
fraction of valid time error > 2°C
fraction of valid time error > 3°C
```

Also calculate indoor-to-outdoor thermal difference where possible:

```text
indoor_temperature - outdoor_temperature
```

Potential derived features:

```text
median indoor-outdoor difference
temperature slope during active cooling
temperature recovery slope
temperature variability
temperature response persistence
```

Only retain features that can be defined consistently and sensibly.

Do not force recovery-time features if the dataset does not contain identifiable recovery events.

---

# 13. Control-State Features

Categorical operating modes must be treated as categorical/state variables unless documentation establishes a numeric interpretation.

For each categorical signal, derive features such as:

```text
fraction of time in each state
number of state changes
state-transition rate
longest continuous state duration
active-cooling duty cycle
load-halved fraction
valid-information fraction
```

Do not calculate statistics such as:

```python
mean_running_mode
```

unless the values are genuinely ordinal/continuous.

---

# 14. Peer-Relative Analysis

Peer-relative behaviour is the central ACV modelling concept.

Cars in the same train are exposed to broadly similar external conditions, but operating mode, cabin conditions, setpoints and load status may differ.

Implement peer comparison in two stages.

## Stage A — Simple peer baseline

At each timestamp, for signal `x` and car `i`:

```text
peer_median_i(t) =
median(x_j(t)) for all valid j != i
```

Then calculate:

```text
peer_residual_i(t) =
x_i(t) - peer_median_i(t)
```

Initially use this simple approach to establish a baseline.

## Stage B — Context-matched peer comparison

Improve the peer group by comparing car `i` only with cars under sufficiently comparable conditions.

Candidate context variables:

```text
running mode
setting mode
cooling setpoint
load-halved status
information-valid status
timestamp
```

A peer should only contribute to the reference if its operating context is considered comparable.

Avoid making matching criteria so restrictive that insufficient peer observations remain.

Where exact matching is impossible, implement a documented relaxed matching hierarchy.

Example:

```text
Level 1:
same running mode
same load state
similar setpoint

Level 2:
same running mode
similar setpoint

Level 3:
same running mode

Fallback:
all valid peers
```

The implementation must record which matching level was used.

---

# 15. Peer-Relative Features

From peer residual time series derive features such as:

```text
median peer residual
median absolute peer residual
90th percentile absolute peer residual
95th percentile absolute peer residual
maximum absolute peer residual
peer-residual MAD
fraction of time peer residual exceeds threshold
longest persistent peer deviation
peer-residual variability
```

Use robust statistics wherever appropriate.

---

# 16. Robust Within-Case Scores

For car-level feature `x`, calculate a robust score relative to the other cars in the same case.

Use:

```text
median_x = median(x across cars)

MAD_x =
median(abs(x - median_x))
```

Robust Z-score:

```text
z_i =
abs(x_i - median_x) /
(1.4826 * MAD_x + epsilon)
```

Use a small epsilon only for numerical stability.

The sign of a feature may matter.

For example:

```text
higher temperature tracking error
```

may be suspicious, while some other features could be abnormal in either direction.

Feature definitions must explicitly state whether:

```text
high only
low only
absolute deviation
```

is considered suspicious.

---

# 17. Baseline Ranking Model

Build a transparent non-ML ranking baseline before training a classifier.

For each car:

```text
ranking_score =
weighted sum of selected robust feature scores
```

Start with a deliberately small feature set.

Candidate initial score:

```text
ranking_score =
    z_temperature_tracking_error
  + z_peer_temperature_deviation
  + z_peer_deviation_persistence
  + z_cooling_duty_deviation
```

Initial weights may all be `1.0`.

Do not tune many weights using the six cases.

Rank cars by descending ranking score.

Example result:

```text
car_id    ranking_score    rank

03        4.81             1
06        2.33             2
01        1.84             3
...
```

This baseline must always remain available for comparison against learned models.

---

# 18. Ranking Output Contract

Implement:

```python
rank_cars(case) -> DataFrame
```

Expected output:

```text
car_id
ranking_score
rank
```

Requirements:

* every detected car appears exactly once
* ranks start at 1
* highest score receives rank 1
* car IDs remain strings
* leading zeros are preserved
* deterministic tie handling must be defined

Do not use car number as a tie-breaker in a way that could influence model behaviour.

Use deterministic stable ordering only for exact ties.

---

# 19. Supervised Challenger — Logistic Regression

After the baseline is complete, implement regularised logistic regression as the first supervised challenger.

Target:

```text
faulty = 1
normal = 0
```

Possible starting configuration:

```python
LogisticRegression(
    penalty="l2",
    class_weight="balanced",
    max_iter=5000,
    random_state=42
)
```

Input features must exclude:

```text
case_id
car_id
filename
train number
known labels
```

Use model scores to rank the cars within each case.

Do not automatically call the output a calibrated probability.

Call it:

```text
model score
```

or:

```text
ranking score
```

unless explicit probability calibration is later validated.

---

# 20. Optional Supervised Challenger

After logistic regression, implement only one compact non-linear challenger.

Preferred candidates:

```text
Gradient Boosting
or
Extra Trees
```

Keep model complexity deliberately small.

Do not perform broad automated hyperparameter optimisation.

Any parameter tuning must occur entirely within the training folds.

---

# 21. Optional Unsupervised Challenger

Only after the peer baseline and supervised models are working may the implementation optionally evaluate:

```text
PCA reconstruction residual
Isolation Forest
```

These should operate on car-level/common comparable features rather than treating every raw timestamp as an independent training example.

These methods are challengers only.

They must not replace the peer-relative baseline without better validation performance.

---

# 22. Validation Strategy

Use Leave-One-Case-Out Cross Validation.

For six cases:

```text
Fold 1
Validation: case 01
Training: cases 02–06

Fold 2
Validation: case 02
Training: cases 01, 03–06

...

Fold 6
Validation: case 06
Training: cases 01–05
```

All:

```text
cars
timestamps
feature rows
```

from one case must remain in the same fold.

Never randomly divide timestamps from the same case between training and validation.

Never randomly divide cars from the same case between training and validation.

---

# 23. Preprocessing Leakage Prevention

Any learned preprocessing must be fitted using training folds only.

This includes:

```text
standardisation
normalisation
PCA
feature selection
imputation parameters
learned anomaly thresholds
model calibration
feature weighting learned from data
```

Peer-relative calculations that use only the cars inside the currently analysed input case are allowed at inference time because they are part of the available case data.

Hidden labels must never influence peer-feature computation.

---

# 24. Competition Metric

Implement the official ACV linear rank-decay metric.

For:

```text
n = number of cars
r = rank of the true faulty car
```

calculate:

```text
score = (n - (r - 1)) / n
```

For eight cars:

```text
rank 1 = 1.000
rank 2 = 0.875
rank 3 = 0.750
rank 4 = 0.625
rank 5 = 0.500
rank 6 = 0.375
rank 7 = 0.250
rank 8 = 0.125
```

If the true car is missing:

```text
score = 0
```

Implement:

```python
rank_decay_score(true_car, ranked_cars) -> float
```

---

# 25. Validation Report

For every model and every held-out case, save:

```text
case_id
true_faulty_car
predicted_ranked_cars
true_car_rank
rank_decay_score
top_prediction
```

Example:

```text
case_01
true: 01
ranking: 01|03|06|...
true rank: 1
score: 1.000
```

Generate a summary table:

```text
Model
Mean rank-decay score
Median true-car rank
Top-1 count
Top-2 count
Worst true-car rank
```

The mean official rank-decay score is the primary model-selection metric.

Always show individual case results because six independent cases are too few for the mean alone to be fully informative.

---

# 26. Ablation Testing

Evaluate whether added complexity genuinely helps.

Required comparisons:

```text
thermal features only

thermal + control features

thermal + naive peer features

thermal + context-matched peer features

baseline ranking vs logistic regression

best simple model vs optional tree model
```

Record case-by-case differences.

Do not keep features merely because they appear theoretically useful.

Retain additions only if they improve performance or robustness across held-out cases.

---

# 27. Robustness Tests

Implement automated tests for the following.

## Column order invariance

Randomly rearrange Excel columns.

Prediction should not materially change.

## Car-ID rename invariance

Map:

```text
01 → A
02 → B
...
```

while keeping the same telemetry.

The corresponding physical car should retain the same rank.

This ensures the model is not learning that certain car numbers fail more frequently.

## Timestamp ordering

Temporarily shuffle row order.

After sorting by timestamp, prediction must match the original result.

## Optional-feature removal

Remove optional columns.

The core baseline must still execute.

## Missing values

Introduce controlled missing sections.

The pipeline should either:

* continue with warnings, or
* clearly report insufficient data

but must not silently generate corrupted features.

## Duplicate IDs

Reject or flag duplicate/ambiguous car identifiers.

---

# 28. Data-Quality Features

For each car calculate:

```text
valid-data fraction
missing-value fraction
information-valid fraction where available
longest missing-data segment
number of discontinuities
```

These values may:

* become ranking features where scientifically justified
* be used only as warnings
* be used to suppress unreliable derived features

Do not assume that missingness itself indicates refrigerant leakage.

---

# 29. Explanation Output

Even though no UI is being built, the backend should return explanation information for later integration.

Implement:

```python
analyse_acv(path) -> ACVResult
```

Suggested structure:

```python
ACVResult(
    filename="acv_test_case.xlsx",

    ranked_cars=[
        "03",
        "05",
        "01",
        ...
    ],

    ranking_scores={
        "03": 4.82,
        "05": 2.41,
        ...
    },

    car_features=<DataFrame>,

    top_feature_contributors={
        "03": [
            {
                "feature": "peer_temperature_deviation",
                "value": ...,
                "robust_score": ...
            },
            ...
        ]
    },

    warnings=[
        ...
    ],

    metadata={
        ...
    }
)
```

Do not generate unsupported statements such as:

```text
"The compressor is definitely faulty."
```

Describe observable evidence instead.

Example:

```text
Car 03 showed the largest persistent indoor-temperature
deviation from context-matched peer cars during active cooling.
```

---

# 30. Feature Definitions Registry

Create a machine-readable feature registry.

Example:

```python
FEATURE_DEFINITIONS = {
    "temp_error_median": {
        "description":
            "Median indoor temperature minus cooling setpoint",
        "direction":
            "higher_is_more_suspicious",
        "requires": [
            "indoor_temperature",
            "cooling_setpoint"
        ]
    }
}
```

Every feature should document:

```text
name
description
required inputs
units
aggregation
expected anomaly direction
handling of missing data
```

This prevents feature meaning from becoming unclear later.

---

# 31. Model Artifact

The training script should save a complete fitted pipeline rather than only a classifier.

The artifact should contain where applicable:

```text
feature schema/version
feature ordering
scaler
imputation logic
trained model
configuration
training case list
validation scores
model version
```

Inference must not retrain any model.

Inference must not update preprocessing parameters.

---

# 32. Prediction Script

Implement:

```bash
python scripts/predict.py \
    --input data/acv/Test/acv_test_case.xlsx \
    --output outputs/acv_predictions.csv
```

The script must:

```text
load input file
validate schema
extract features
load frozen model/configuration
rank every car
generate explanation metadata
write official CSV
```

---

# 33. Submission CSV

Output exactly:

```csv
file_id,ranked_cars
acv_test_case.xlsx,03|05|01|07|06|02|08|04
```

Implement export validation ensuring:

```text
correct filename
exactly one row per input file
all car IDs included
no duplicated car IDs
no missing car IDs
leading zeros preserved
pipe separator used
no accidental index column
```

---

# 34. Training Script

Implement:

```bash
python scripts/train.py
```

It must:

```text
load all training files
load Train_Labels.csv
build car-level feature dataset
run leave-one-case-out validation
evaluate baseline
evaluate logistic regression
evaluate optional challenger
save fold-level results
select best validated approach
fit final model using all training cases
save final artifact
```

The model-selection result should explicitly show why one model was selected.

Do not automatically select the most complex model.

---

# 35. Evaluation Script

Implement:

```bash
python scripts/evaluate.py
```

Output:

```text
Per-case ranking results

Case 01
True faulty car: ...
Rank: ...
Score: ...

...

Overall
Mean rank-decay score: ...
Top-1 cases: ...
Top-2 cases: ...
Worst-case rank: ...
```

Also save:

```text
outputs/validation_results.csv
outputs/model_comparison.csv
```

---

# 36. Implementation Order

Implement in the following order.

### Phase 1 — Data understanding

```text
loader
schema parser
dataset manifest
data exploration notebook
```

### Phase 2 — Basic features

```text
thermal features
control features
data-quality features
```

### Phase 3 — Peer baseline

```text
simple peer median
peer residuals
robust car scores
transparent ranking
```

### Phase 4 — Correct evaluation

```text
rank-decay metric
leave-one-case-out framework
case-by-case evaluation
```

### Phase 5 — Context matching

```text
operating-context matching
context-matched peer residuals
ablation against naive peer baseline
```

### Phase 6 — Supervised model

```text
logistic regression
small tree challenger
model comparison
```

### Phase 7 — Production inference

```text
model artifact
predict.py
CSV export
explanation structure
robustness tests
```

Do not begin Phase 6 until Phases 1–5 are working.

---

# 37. Acceptance Criteria

The ACV backend is complete when all of the following are satisfied.

```text
[ ] All six training case files can be loaded.

[ ] Test ACV files can be loaded without using training-specific
    column positions.

[ ] Cars are discovered automatically from column names.

[ ] Car identifiers preserve leading zeros.

[ ] Variable column sets are supported.

[ ] Dataset manifest is generated.

[ ] Core thermal features are generated.

[ ] Control-state features are generated correctly.

[ ] Naive peer residuals are implemented.

[ ] Context-aware peer comparison is implemented.

[ ] One feature row is generated per car per case.

[ ] Car ID is not used as a predictive feature.

[ ] Train number is not used as a predictive feature.

[ ] Transparent ranking baseline exists.

[ ] Official rank-decay metric exists.

[ ] Leave-one-case-out validation works.

[ ] No timestamps/cars from the held-out case enter training.

[ ] Logistic regression challenger exists.

[ ] At least one baseline-vs-model comparison is generated.

[ ] Individual fold results are stored.

[ ] Car renaming does not materially change ranking.

[ ] Column order does not affect predictions.

[ ] Optional columns can be missing without crashing the
    core pipeline.

[ ] Frozen model/preprocessing artifact can be saved and loaded.

[ ] predict.py operates without retraining.

[ ] acv_predictions.csv exactly matches the required schema.

[ ] Every detected car appears exactly once in ranked_cars.

[ ] Backend returns explanation information for later UI use.

[ ] Automated tests pass.
```

---

# 38. Important Development Rules

Do not optimise against the provided unlabelled test case.

Do not manually inspect the test case and hard-code a result.

Do not learn car-specific failure priors from car identifiers.

Do not randomly split timestamps.

Do not randomly split cars from the same case.

Do not fit preprocessing using validation data.

Do not call arbitrary anomaly scores failure probabilities.

Do not assume more complexity produces better performance.

Do not discard physical signal magnitude through per-file normalisation without justification.

Do not silently ignore unavailable parameters.

Do not invent missing telemetry.

Do not hard-code the faulty-car labels anywhere inside prediction code.

---

# 39. First Development Gate

Before building any model, complete the dataset inspection stage.

Run:

```bash
python scripts/inspect_dataset.py
```

and produce a report showing:

```text
all discovered files
file dimensions
car IDs per file
parameter names
parameters common across all training cases
parameters only available in some cases
sampling interval
missing-value summary
data-type summary
schema differences
```

Then inspect:

```text
01_data_exploration.ipynb
```

for all six labelled cases.

Only after this stage should feature definitions be finalised.

Do not implement logistic regression, boosted trees, PCA or
Isolation Forest until the actual telemetry structure has been
confirmed.

---

# 40. Final Technical Goal

The final ACV backend should perform:

```text
analyse unseen ACV telemetry
        ↓
identify cars automatically
        ↓
understand available signals
        ↓
compare each car against suitable peers
        ↓
extract thermal/control/relative behaviour
        ↓
calculate ranking scores
        ↓
rank every detected car
        ↓
provide supporting feature evidence
        ↓
produce exact competition CSV
```

The system should favour a simple, validated and explainable
solution over a more complex model that cannot demonstrate
better leave-one-case-out performance.
