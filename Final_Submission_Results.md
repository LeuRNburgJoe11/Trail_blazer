# RailPulse — Final Results & Technical Write-Up

**Team TrailBlazer** | LTA x Nebula Hackathon — Problem Statement 3: Train Condition Monitoring

---

## Executive Summary

RailPulse is a unified condition-monitoring platform covering all four PS3 subsystems. Each subsystem uses a purpose-built pipeline designed around the physics and data constraints of its specific domain. We consistently favoured interpretable, well-validated models over complex black-box approaches — and the cross-validation results vindicate that strategy.

| Subsystem | Task Type | Primary Model | Official Metric | CV Score |
|---|---|---|---|---|
| **ACV** | Ranking / Localisation | Context-Matched Peer Residual Baseline | Mean Rank-Decay | **0.979** |
| **Door** | Temporal Segment Detection | Hysteretic Segmentation + ExtraTreesClassifier | IoU-weighted F1 | **1.000** |
| **Rail Corrugation** | Multi-Class Classification | Pooled Side GradientBoostingClassifier | Macro F1 | **0.788** |
| **SHM** | Regression | ASTM E1049 Rainflow + Calibrated 5th-Power Law | max(0, 1 − MAPE) | **0.974** |

---

## 1. ACV — Refrigerant Leakage Localisation

### 1.1 Problem

Given a single `.xlsx` telemetry file from a train with 8 cars, rank every car from most to least likely to have a refrigerant leakage fault. Only 6 labelled training cases exist.

### 1.2 Approach & Model

Because the dataset contains only **6 independent fault cases**, complex ML models are prone to severe overfitting. We designed a transparent, physics-aware **Context-Matched Peer Residual Baseline**:

1. **Dynamic Schema Parsing** — Regex-based column discovery automatically maps variable telemetry schemas (8-parameter files and 60+ parameter files) into a unified feature space using an alias layer.
2. **Context Matching** — Instead of naively comparing a car to the train average, the system compares each car only to *peer cars operating under the exact same physical conditions* (same running mode, load state, and cooling setpoint) using vectorized numpy masked medians.
3. **Transparent Scoring** — Computes the sum of robust absolute Z-scores across four physically meaningful features.

### 1.3 Feature Engineering (4 Core Features)

| Feature | Description | Anomaly Direction |
|---|---|---|
| `temp_error_median` | Median indoor temperature minus cooling setpoint | Higher → more suspicious |
| `peer_context_residual_median` | Median deviation from context-matched peer cars | Higher → more suspicious |
| `peer_context_longest_persistent_deviation` | Longest consecutive run (in samples) where the car remained significantly warmer than its peers | Higher → more suspicious |
| `active_cooling_duty_cycle` | Fraction of time the AC compressor was actively commanded to cool | Lower → more suspicious |

### 1.4 Validation Protocol

**Leave-One-Case-Out Cross Validation (LOOCV)** — Each of the 6 cases is held out once; the remaining 5 are used to establish the peer baseline. No timestamps or cars from the held-out case enter training.

### 1.5 Model Comparison Results

| Model | Mean Rank-Decay Score | Top-1 Count (of 6) | Worst Rank |
|---|---|---|---|
| **Baseline (Selected)** | **0.979** | **5** | **2** |
| Logistic Regression | 0.875 | 5 | 7 |
| SVM (Linear) | 0.875 | 5 | 7 |
| Random Forest | 0.833 | 3 | 5 |
| Gradient Boosting | 0.708 | 1 | 8 |

### 1.6 Per-Fold Baseline Results

| Case | True Faulty Car | Predicted Rank | Score | Top Prediction |
|---|---|---|---|---|
| Case 01 | Car 01 | 1st ✅ | 1.000 | 01 |
| Case 02 | Car 02 | 1st ✅ | 1.000 | 02 |
| Case 03 | Car 03 | 1st ✅ | 1.000 | 03 |
| Case 04 | Car 01 | 1st ✅ | 1.000 | 01 |
| Case 05 | Car 04 | 2nd | 0.875 | 05 |
| Case 06 | Car 06 | 1st ✅ | 1.000 | 06 |

### 1.7 Key Design Decision

> The transparent heuristic Baseline significantly outperformed all ML challengers. With only 6 independent cases, complex models overfit to noise in the training folds and fail catastrophically on at least one hold-out case. The Baseline's worst-case rank is 2nd place; the LR and SVM models both dropped the true faulty car to 7th place on one fold.

### 1.8 Final Test Prediction

```csv
file_id,ranked_cars
acv_test_case.xlsx,04|01|05|06|02|07|08|03
```

---

## 2. Door — Abnormal Resistance Detection

### 2.1 Problem

Given a continuous, unlabelled time-series stream (`Test.csv`) of motor current, voltage, back-EMF, and door position readings, **segment** the stream into individual door open/close cycles and **classify** each as `Normal` or `Abnormal resistance`.

### 2.2 Approach & Model

A two-stage pipeline:

1. **Segmentation — Deterministic Hysteretic State Machine** (`detect_intervals`):
   - Detects operations using command flags (`Open command`, `Close command`) and movement indicators.
   - Bridges short inactive gaps (≤ 0.25s) to avoid premature interval cuts.
   - Requires minimum cycle duration ≥ 0.5s.
   - Detects effort-resets (current dropping ≥ 25% from ≥ 500 mA while position changes ≥ 100) to identify separate movement commands.

2. **Classification — `ExtraTreesClassifier(n_estimators=200, class_weight="balanced")`**:
   - Classifies each detected segment using 10 engineered cycle-level features.

### 2.3 Feature Engineering (10 Features per Cycle)

| Feature | Description |
|---|---|
| `duration` | Operation duration in seconds |
| `current_peak` | Maximum motor current (mA) |
| `current_mean` | Mean motor current over the interval |
| `current_rms` | Root-mean-square of motor current |
| `current_integral` | Total normalised absolute current × duration |
| `current_std` | Standard deviation of motor current |
| `energy_proxy` | Mean of current × voltage (electrical power proxy) |
| `position_change` | Net door position change (end − start) |
| `position_stagnation` | Fraction of consecutive samples where position was unchanged |
| `velocity` | Average movement velocity (position_change / duration) |

### 2.4 Validation Protocol

**Chronological 70/30 Split** — First 77 annotated cycles for training, last 33 for validation. This respects the temporal ordering of the continuous stream and prevents data leakage.

### 2.5 Results

| Metric | Value |
|---|---|
| **IoU-weighted F1 (Validation)** | **1.000** |
| Training Cycles | 77 |
| Validation Cycles | 33 |
| Predicted Test Segments | 38 |

### 2.6 Key Design Decision

> The deterministic segmentation approach was chosen because it directly models the physical state transitions of a door system (idle → commanded → moving → stopped), rather than relying on learned boundaries that could fail on unseen timing patterns. The ExtraTreesClassifier was selected for its robustness to class imbalance with `class_weight="balanced"`.

---

## 3. Rail Corrugation — Multi-Class Classification

### 3.1 Problem

Classify each 1-second axle-box vibration/shock recording (10,000 Hz, 129 channels) as `Normal`, `Side I`, or `Side II` corrugation. The dataset is heavily imbalanced: 234 Normal, 14 Side I, 24 Side II.

### 3.2 Approach & Model

Two candidate architectures were developed and comparatively validated:

1. **Candidate 1 — `ExtraTreesClassifier`**: File-level aggregated spectral statistics → direct 3-class prediction.
2. **Candidate 2 — `PooledSideClassifier` (Selected)**: Physically-motivated side-pooling approach using `GradientBoostingClassifier`.
   - Each file creates **two independent samples** (Side I features and Side II features) with binary targets indicating corrugation presence on that specific side.
   - **Decision Rule**: Predicts P(Side I) and P(Side II). If max(P_I, P_II) < 0.5 → `Normal`; otherwise predicts the side with the higher probability.

### 3.3 Feature Engineering

| Feature Category | Description |
|---|---|
| **Speed Estimation** | Binary pulse rising-edge counting from the 90-tooth wheel sensor channel. Speed (m/s) = edges × π × 0.85 / 90 / duration |
| **Time-Domain** | Per-side RMS, Crest Factor, Kurtosis (vibration and shock channels kept strictly separate) |
| **Frequency-Domain** | Welch PSD (fs=10,000, nperseg=2048) integrated across 5 speed-normalised wavenumber bands with dynamic edges scaled by train speed |
| **Spatial Aggregation** | Mean and max pooling across sensors for each side and sensor type |

### 3.4 Validation Protocol

**5-Fold File-Level Stratified Cross-Validation** — Both sides of a single file always remain in the same fold to prevent leakage. Additionally, **nested model selection** (5 outer × 3 inner folds) was used for unbiased candidate comparison.

### 3.5 Model Comparison Results

| Model | 5-Fold CV Macro F1 | Pooled OOF Macro F1 | Nested CV Macro F1 |
|---|---|---|---|
| **Pooled Spatial (Selected)** | **0.788** | **0.792** | **0.726** |
| Extra Trees | 0.667 | 0.701 | — |

### 3.6 Key Design Decision

> The side-pooling formulation directly encodes the physical constraint that Side I and Side II rails must be judged independently from the same recording. By decomposing the 3-class problem into two binary problems (one per side), the model doubles its effective training set size and naturally handles the constraint that a file can only have corrugation on one side. Speed-normalised wavenumber bands ensure the features remain physically meaningful across varying train speeds.

---

## 4. SHM — Cumulative Fatigue Damage Estimation

### 4.1 Problem

Predict a single numeric cumulative fatigue damage value for each dynamic-stress time-series file (581,120 samples). This is a regression task where the reference values were computed using Miner's linear cumulative damage rule combined with rainflow counting.

### 4.2 Approach & Model

A **physics-informed calibrated regressor** built on the same domain principles (Miner's rule + rainflow counting) used to generate the reference labels:

1. **ASTM E1049 Rainflow Cycle Counting** — Extracts independent stress cycles (amplitude, mean, count) from the random stress time series. Residual half-cycles are weighted at 0.5.
2. **Fifth-Power Damage Law** — Computes a damage proxy: P_m = Σ(count × amplitude^m) with m = 5.0.
3. **Optimal Scale Calibration** — Finds the scale factor minimising training fraction-MAPE using a weighted median: scale = weighted_median(y / P_m, weights = P_m / y).

### 4.3 Feature Engineering (81 Features)

| Category | Count | Description |
|---|---|---|
| Statistical | 12 | stress mean, std, RMS, min, max, absolute quantiles (q50/q90/q99/q999), kurtosis, difference RMS, n_samples |
| Rainflow Cycle | 8 | cycle count, half-cycle fraction, amplitude mean/q50/q90/q99/max, cycle_mean_abs |
| Power Sums | 61 | P_m = Σ(count × amplitude^m) for m ∈ [2.0, 8.0] in steps of 0.1 |

### 4.4 Validation Protocol

**2 Repetitions × 8-Fold Outer CV (16 outer folds total)** with 4 inner folds per outer fold on 64 training files. This rigorous nested cross-validation prevents optimistic bias from model selection.

### 4.5 Model Comparison Results

| Model | MAPE | Score (1 − MAPE) | MAE | Worst APE |
|---|---|---|---|---|
| **physics_5 (Selected)** | **2.56%** | **0.974** | **0.00435** | **13.69%** |
| physics_fitted (m=5.0) | 2.56% | 0.974 | 0.00435 | 13.69% |
| extra_trees | 5.51% | 0.945 | 0.01431 | 23.82% |
| ridge_cycles | 8.39% | 0.916 | 0.01762 | 41.36% |
| ridge_stats | 31.15% | 0.689 | 0.06336 | 145.28% |
| physics_3 (m=3.0) | 43.47% | 0.565 | 0.13151 | 121.88% |
| constant_mape | 56.83% | 0.432 | 0.19205 | 95.67% |

### 4.6 Key Design Decision

> The `physics_fitted` grid search independently arrived at m = 5.0, exactly matching the fixed `physics_5` candidate. This confirms the exponent is a genuine physical property of the material/component S-N curve, not an artifact of overfitting. The physics-based model also dominated all pure ML alternatives (ExtraTrees, Ridge) because it directly models the damage accumulation mechanism rather than learning it from a small dataset.

### 4.7 Final Test Predictions

```csv
file_id,prediction
test01.csv,0.032270
test02.csv,0.821870
test03.csv,0.436436
test04.csv,0.029057
test05.csv,0.035751
test06.csv,0.440855
test07.csv,0.160867
test08.csv,0.053896
test09.csv,0.064081
test10.csv,0.057933
test11.csv,0.050416
test12.csv,0.193442
test13.csv,0.436311
test14.csv,0.494148
test15.csv,0.054643
test16.csv,0.066148
```

---

## Appendix: Scoring Formulae Reference

| Subsystem | Metric | Formula |
|---|---|---|
| ACV | Linear Rank-Decay | score = (n − (r − 1)) / n |
| Door | IoU-weighted F1 | 2 × soft_recall × soft_precision / (soft_recall + soft_precision) |
| Rail Corrugation | Macro F1 | mean(F1_Normal, F1_SideI, F1_SideII) |
| SHM | MAPE-derived Score | max(0, 1 − mean(\|true − pred\| / \|true\|)) |

Each subsystem is weighted equally at 25% of the overall score.
