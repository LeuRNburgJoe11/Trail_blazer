import os
import pandas as pd
import sys
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
from railpulse.acv.validation import evaluate_baseline_loocv, evaluate_sklearn_model_loocv, generate_summary_table

def main():
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'outputs', 'acv'))
    features_path = os.path.join(output_dir, 'train_features.csv')
    
    if not os.path.exists(features_path):
        print(f"Features file not found at {features_path}. Please run build_features.py first.")
        return
        
    features_df = pd.read_csv(features_path)
    # Ensure car_id is string with leading zeros
    features_df['car_id'] = features_df['car_id'].astype(str).str.zfill(2)
    
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'acv'))
    labels_path = os.path.join(data_dir, 'Train_Labels.csv')
    labels_df = pd.read_csv(labels_path)
    labels_map = dict(zip(labels_df['filename'], labels_df['faulty_car'].astype(str).str.zfill(2)))
    
    summaries = []
    
    print("Evaluating Baseline Model...")
    baseline_results = evaluate_baseline_loocv(features_df, labels_map)
    baseline_summary = generate_summary_table(baseline_results, "Baseline")
    baseline_results.to_csv(os.path.join(output_dir, "validation_results_baseline.csv"), index=False)
    print(baseline_summary.to_string(index=False))
    summaries.append(baseline_summary)
    
    models = {
        "Logistic Regression": lambda: LogisticRegression(penalty="l2", class_weight="balanced", max_iter=5000, random_state=42),
        "Random Forest": lambda: RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42),
        "Gradient Boosting": lambda: GradientBoostingClassifier(n_estimators=100, random_state=42),
        "SVM (Linear)": lambda: SVC(kernel="linear", class_weight="balanced", probability=True, random_state=42)
    }
    
    all_results = {"Baseline": baseline_results}
    
    for name, factory in models.items():
        print(f"\nEvaluating {name}...")
        results = evaluate_sklearn_model_loocv(features_df, labels_map, factory)
        summary = generate_summary_table(results, name)
        print(summary.to_string(index=False))
        summaries.append(summary)
        all_results[name] = results
        results.to_csv(os.path.join(output_dir, f"validation_results_{name.replace(' ', '_').lower()}.csv"), index=False)
        
    # Compare
    comparison = pd.concat(summaries, ignore_index=True)
    comparison = comparison.sort_values(by="Mean rank-decay score", ascending=False)
    print("\n--- Final Model Comparison ---")
    print(comparison.to_string(index=False))
    
    comparison.to_csv(os.path.join(output_dir, "model_comparison.csv"), index=False)
    
    # Decide best model based on Mean rank-decay score
    best_model_name = comparison.iloc[0]["Model"]
    print(f"\nBest model selected: {best_model_name}")
    
    if best_model_name == "Baseline":
        print("Freezing Baseline artifact...")
        baseline_features = [
            "temp_error_median", 
            "peer_context_residual_median",
            "peer_context_longest_persistent_deviation",
            "active_cooling_duty_cycle"
        ]
        artifact = {
            "model_type": "baseline",
            "feature_schema": baseline_features,
            "version": "1.0",
            "training_cases": features_df['case_id'].unique().tolist()
        }
    else:
        print(f"Fitting final {best_model_name} model on all training data...")
        factory = models[best_model_name]
        
        exclude_cols = ['case_id', 'car_id', 'faulty', 'filename']
        feature_cols = [c for c in features_df.columns if c not in exclude_cols]
        
        X_train = features_df[feature_cols].fillna(0)
        y_train = features_df['faulty']
        
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', factory())
        ])
        
        pipeline.fit(X_train, y_train)
        
        artifact = {
            "model_type": "sklearn",
            "feature_schema": feature_cols,
            "pipeline": pipeline,
            "version": "1.0",
            "training_cases": features_df['case_id'].unique().tolist()
        }
    
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'acv'))
    os.makedirs(models_dir, exist_ok=True)
    
    artifact_path = os.path.join(models_dir, 'acv_model_artifact.pkl')
    with open(artifact_path, 'wb') as f:
        pickle.dump(artifact, f)
        
    print(f"Model artifact saved to {artifact_path}")

if __name__ == "__main__":
    main()
