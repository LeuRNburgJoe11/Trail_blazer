import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from .ranking import baseline_ranking, calculate_robust_z_scores
from .metrics import rank_decay_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

def evaluate_baseline_loocv(features_df: pd.DataFrame, labels_map: Dict[str, str]) -> pd.DataFrame:
    """
    Evaluates the baseline ranking model using Leave-One-Case-Out cross validation.
    """
    cases = features_df['case_id'].unique()
    results = []
    
    for val_case in cases:
        val_df = features_df[features_df['case_id'] == val_case].copy()
        
        # Rank using baseline
        ranked_df = baseline_ranking(val_df)
        
        true_faulty = labels_map.get(val_case)
        if not true_faulty:
            continue
            
        ranked_cars = ranked_df['car_id'].tolist()
        score = rank_decay_score(true_faulty, ranked_cars)
        
        try:
            rank = ranked_cars.index(true_faulty) + 1
        except ValueError:
            rank = -1
            
        results.append({
            "case_id": val_case,
            "true_faulty_car": true_faulty,
            "predicted_ranked_cars": "|".join(ranked_cars),
            "true_car_rank": rank,
            "rank_decay_score": score,
            "top_prediction": ranked_cars[0] if ranked_cars else ""
        })
        
    return pd.DataFrame(results)

def evaluate_logistic_regression_loocv(features_df: pd.DataFrame, labels_map: Dict[str, str]) -> pd.DataFrame:
    """
    Evaluates Logistic Regression using LOOCV.
    """
    cases = features_df['case_id'].unique()
    results = []
    
    # Exclude ID columns and faulty label
    exclude_cols = ['case_id', 'car_id', 'faulty', 'filename']
    feature_cols = [c for c in features_df.columns if c not in exclude_cols]
    
    for val_case in cases:
        train_df = features_df[features_df['case_id'] != val_case].copy()
        val_df = features_df[features_df['case_id'] == val_case].copy()
        
        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df['faulty']
        
        X_val = val_df[feature_cols].fillna(0)
        
        # Standardize using training folds only (Leakage prevention)
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        
        # Train
        model = LogisticRegression(penalty="l2", class_weight="balanced", max_iter=5000, random_state=42)
        model.fit(X_train_scaled, y_train)
        
        # Predict ranking scores (probability of faulty)
        scores = model.predict_proba(X_val_scaled)[:, 1]
        
        val_df['ranking_score'] = scores
        val_df = val_df.sort_values(by=['ranking_score', 'car_id'], ascending=[False, True]).reset_index(drop=True)
        val_df['rank'] = val_df.index + 1
        
        true_faulty = labels_map.get(val_case)
        if not true_faulty:
            continue
            
        ranked_cars = val_df['car_id'].tolist()
        score = rank_decay_score(true_faulty, ranked_cars)
        
        try:
            rank = ranked_cars.index(true_faulty) + 1
        except ValueError:
            rank = -1
            
        results.append({
            "case_id": val_case,
            "true_faulty_car": true_faulty,
            "predicted_ranked_cars": "|".join(ranked_cars),
            "true_car_rank": rank,
            "rank_decay_score": score,
            "top_prediction": ranked_cars[0] if ranked_cars else ""
        })
        
    return pd.DataFrame(results)

def generate_summary_table(results_df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """
    Generates the summary table for a given evaluation result.
    """
    if results_df.empty:
        return pd.DataFrame()
        
    return pd.DataFrame([{
        "Model": model_name,
        "Mean rank-decay score": results_df["rank_decay_score"].mean(),
        "Median true-car rank": results_df["true_car_rank"].median(),
        "Top-1 count": (results_df["true_car_rank"] == 1).sum(),
        "Top-2 count": (results_df["true_car_rank"] <= 2).sum(),
        "Worst true-car rank": results_df["true_car_rank"].max()
    }])

