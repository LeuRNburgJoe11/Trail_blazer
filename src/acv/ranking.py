import pandas as pd
import numpy as np

def calculate_robust_z_scores(df: pd.DataFrame, feature_cols: list[str], epsilon: float = 1e-9) -> pd.DataFrame:
    """
    Calculates robust Z-scores for specified features within a DataFrame (which represents one case).
    z_i = abs(x_i - median_x) / (1.4826 * MAD_x + epsilon)
    """
    df_scores = df.copy()
    
    for col in feature_cols:
        if col not in df.columns:
            df_scores[f"z_{col}"] = 0.0
            continue
            
        x = df[col]
        median_x = x.median()
        
        # Calculate MAD, ignoring NaNs
        mad_x = (x - median_x).abs().median()
        
        if pd.isna(mad_x):
            mad_x = 0.0
            
        # Standard robust Z-score formula
        # Notice we use absolute deviation as per PRD "abs(x_i - median_x)"
        z = (x - median_x).abs() / (1.4826 * mad_x + epsilon)
        
        # Fill NaNs with 0 (median behavior)
        z = z.fillna(0.0)
        df_scores[f"z_{col}"] = z
        
    return df_scores

def baseline_ranking(case_features: pd.DataFrame) -> pd.DataFrame:
    """
    Ranks cars using a simple transparent baseline.
    """
    if case_features.empty:
        return pd.DataFrame()
        
    # Define the features to use for the baseline ranking
    baseline_features = [
        "temp_error_median", 
        "peer_context_residual_median",
        "peer_context_longest_persistent_deviation",
        "active_cooling_duty_cycle"
    ]
    
    df_scores = calculate_robust_z_scores(case_features, baseline_features)
    
    # Calculate sum of Z-scores
    z_cols = [f"z_{c}" for c in baseline_features]
    
    df_scores["ranking_score"] = df_scores[z_cols].sum(axis=1)
    
    # Sort descending
    df_scores = df_scores.sort_values(by=["ranking_score", "car_id"], ascending=[False, True]).reset_index(drop=True)
    
    # Assign ranks (1-based)
    df_scores["rank"] = df_scores.index + 1
    
    # Select output columns
    result = df_scores[["car_id", "ranking_score", "rank"]].copy()
    return result
