import os
import pandas as pd
import sys
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from railpulse.acv.validation import evaluate_baseline_loocv, evaluate_logistic_regression_loocv, generate_summary_table

def main():
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs'))
    features_path = os.path.join(output_dir, 'train_features.csv')
    
    if not os.path.exists(features_path):
        print(f"Features file not found at {features_path}. Please run build_features.py first.")
        return
        
    features_df = pd.read_csv(features_path)
    # Ensure car_id is string with leading zeros
    features_df['car_id'] = features_df['car_id'].astype(str).str.zfill(2)
    
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    labels_path = os.path.join(data_dir, 'Train_Labels.csv')
    labels_df = pd.read_csv(labels_path)
    labels_map = dict(zip(labels_df['filename'], labels_df['faulty_car'].astype(str).str.zfill(2)))
    
    print("Evaluating Baseline Model...")
    baseline_results = evaluate_baseline_loocv(features_df, labels_map)
    baseline_summary = generate_summary_table(baseline_results, "Baseline")
    print(baseline_summary.to_string(index=False))
    
    print("\nEvaluating Logistic Regression...")
    lr_results = evaluate_logistic_regression_loocv(features_df, labels_map)
    lr_summary = generate_summary_table(lr_results, "Logistic Regression")
    print(lr_summary.to_string(index=False))
    
    # Save fold-level results
    baseline_results.to_csv(os.path.join(output_dir, "validation_results_baseline.csv"), index=False)
    lr_results.to_csv(os.path.join(output_dir, "validation_results_lr.csv"), index=False)
    
    # Compare
    comparison = pd.concat([baseline_summary, lr_summary], ignore_index=True)
    comparison.to_csv(os.path.join(output_dir, "model_comparison.csv"), index=False)
    
    # Decide best model (for simplicity we just train LR as the final artifact since baseline doesn't need fitting)
    # The PRD requires a frozen model/preprocessing artifact
    
    print("\nFitting final LR model on all training data...")
    exclude_cols = ['case_id', 'car_id', 'faulty', 'filename']
    feature_cols = [c for c in features_df.columns if c not in exclude_cols]
    
    X_train = features_df[feature_cols].fillna(0)
    y_train = features_df['faulty']
    
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression(penalty="l2", class_weight="balanced", max_iter=5000, random_state=42))
    ])
    
    pipeline.fit(X_train, y_train)
    
    artifact = {
        "feature_schema": feature_cols,
        "pipeline": pipeline,
        "version": "1.0",
        "training_cases": features_df['case_id'].unique().tolist()
    }
    
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
    os.makedirs(models_dir, exist_ok=True)
    
    artifact_path = os.path.join(models_dir, 'acv_model_artifact.pkl')
    with open(artifact_path, 'wb') as f:
        pickle.dump(artifact, f)
        
    print(f"Model artifact saved to {artifact_path}")

if __name__ == "__main__":
    main()
