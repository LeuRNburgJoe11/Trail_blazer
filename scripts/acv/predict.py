import os
import sys
import argparse
import pandas as pd
import pickle

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
from railpulse.acv.loader import load_acv_case
from railpulse.acv.feature_pipeline import build_features_for_case

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True, help="Input ACV xlsx file")
    parser.add_argument('--output', type=str, required=True, help="Output predictions csv")
    args = parser.parse_args()
    
    print(f"Loading {args.input}...")
    case = load_acv_case(args.input)
    
    print("Building features...")
    features_df = build_features_for_case(case)
    
    # Load artifact
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'acv'))
    artifact_path = os.path.join(models_dir, 'acv_model_artifact.pkl')
    
    if not os.path.exists(artifact_path):
        print(f"Model artifact not found at {artifact_path}. Please train first.")
        return
        
    from railpulse.acv.ranking import calculate_robust_z_scores
    
    with open(artifact_path, 'rb') as f:
        artifact = pickle.load(f)
        
    feature_schema = artifact["feature_schema"]
    model_type = artifact.get("model_type", "sklearn")
    
    # Prepare features, filling missing schema cols with 0
    for col in feature_schema:
        if col not in features_df.columns:
            features_df[col] = 0.0
            
    if model_type == "baseline":
        scored_df = calculate_robust_z_scores(features_df, feature_schema)
        scores = scored_df[[f"z_{c}" for c in feature_schema]].sum(axis=1)
        features_df['ranking_score'] = scores
    else:
        pipeline = artifact["pipeline"]
        X_test = features_df[feature_schema].fillna(0)
        # Predict
        scores = pipeline.predict_proba(X_test)[:, 1]
        features_df['ranking_score'] = scores
    
    # Rank
    features_df = features_df.sort_values(by=['ranking_score', 'car_id'], ascending=[False, True]).reset_index(drop=True)
    ranked_cars = features_df['car_id'].tolist()
    
    # Save CSV
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    with open(args.output, 'w') as f:
        f.write("file_id,ranked_cars\n")
        f.write(f"{case.filename},{'|'.join(ranked_cars)}\n")
        
    print(f"Predictions saved to {args.output}")

if __name__ == "__main__":
    main()
