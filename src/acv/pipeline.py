import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Any
import os
import pickle

from .loader import load_acv_case, ACVCase
from .feature_pipeline import build_features_for_case
from .ranking import calculate_robust_z_scores

@dataclass
class ACVResult:
    filename: str
    ranked_cars: List[str]
    ranking_scores: Dict[str, float]
    car_features: pd.DataFrame
    top_feature_contributors: Dict[str, List[Dict[str, Any]]]
    warnings: List[str]
    metadata: Dict[str, Any]

def analyse_acv(path: str, artifact_path: str = None) -> ACVResult:
    """
    Complete analysis pipeline for a single ACV file.
    Loads data, builds features, applies the pre-trained model (if provided),
    and returns a structured explanation result.
    """
    case = load_acv_case(path)
    features_df = build_features_for_case(case)
    
    if features_df.empty:
        return ACVResult(
            filename=case.filename,
            ranked_cars=[],
            ranking_scores={},
            car_features=pd.DataFrame(),
            top_feature_contributors={},
            warnings=case.warnings + ["No features generated."],
            metadata=case.metadata
        )
        
    pipeline = None
    feature_schema = []
    
    if artifact_path and os.path.exists(artifact_path):
        with open(artifact_path, 'rb') as f:
            artifact = pickle.load(f)
        pipeline = artifact["pipeline"]
        feature_schema = artifact["feature_schema"]
        
        for col in feature_schema:
            if col not in features_df.columns:
                features_df[col] = 0.0
                
        X_test = features_df[feature_schema].fillna(0)
        scores = pipeline.predict_proba(X_test)[:, 1]
    else:
        # Fallback to baseline sum of z-scores if no model is provided
        baseline_features = [
            "temp_error_median", 
            "peer_context_residual_median",
            "peer_context_longest_persistent_deviation",
            "active_cooling_duty_cycle"
        ]
        scored_df = calculate_robust_z_scores(features_df, baseline_features)
        scores = scored_df[[f"z_{c}" for c in baseline_features]].sum(axis=1)
        feature_schema = baseline_features
        case.warnings.append("No pre-trained model provided. Using baseline ranking.")
        
    features_df['ranking_score'] = scores
    
    # Sort
    features_df = features_df.sort_values(by=['ranking_score', 'car_id'], ascending=[False, True]).reset_index(drop=True)
    
    ranked_cars = features_df['car_id'].tolist()
    ranking_scores = dict(zip(features_df['car_id'], features_df['ranking_score']))
    
    # Generate explanations using absolute robust scores of the features
    top_feature_contributors = {}
    scored_for_explain = calculate_robust_z_scores(features_df, [c for c in features_df.columns if c.startswith('peer_') or c.startswith('temp_')])
    
    for _, row in scored_for_explain.iterrows():
        car_id = row['car_id']
        # Find features with highest z-scores
        z_cols = [c for c in scored_for_explain.columns if c.startswith('z_')]
        car_z = row[z_cols].astype(float)
        top_z = car_z.sort_values(ascending=False).head(3)
        
        contributors = []
        for z_col, z_val in top_z.items():
            orig_feat = z_col[2:] # strip 'z_'
            contributors.append({
                "feature": orig_feat,
                "value": row.get(orig_feat, None),
                "robust_score": z_val
            })
        top_feature_contributors[car_id] = contributors
        
    return ACVResult(
        filename=case.filename,
        ranked_cars=ranked_cars,
        ranking_scores=ranking_scores,
        car_features=features_df.drop(columns=['ranking_score']),
        top_feature_contributors=top_feature_contributors,
        warnings=case.warnings,
        metadata=case.metadata
    )
