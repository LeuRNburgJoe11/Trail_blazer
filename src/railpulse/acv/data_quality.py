import pandas as pd
import numpy as np
from typing import Dict, Any

def extract_data_quality_features(car_df: pd.DataFrame, timestamps: pd.Series) -> Dict[str, float]:
    """
    Extracts data quality features for a single car.
    """
    features = {}
    
    # We will compute missingness over all columns in the car_df (standardized or raw)
    if len(car_df) == 0:
        return {
            "valid_data_fraction": 0.0,
            "missing_value_fraction": 1.0,
            "information_valid_fraction": 0.0,
            "longest_missing_data_segment": 0.0,
            "number_of_discontinuities": 0.0
        }
        
    missing_mask = car_df.isna().all(axis=1) # Row is entirely missing
    missing_value_fraction = car_df.isna().mean().mean()
    
    features["valid_data_fraction"] = 1.0 - missing_mask.mean()
    features["missing_value_fraction"] = missing_value_fraction
    
    # information-valid fraction where available
    if "ACV Information Valid" in car_df.columns:
        valid_col = car_df["ACV Information Valid"]
        # Treat as valid if value is 1, 'Valid', etc. Assuming numeric > 0 or string.
        if pd.api.types.is_numeric_dtype(valid_col):
            features["information_valid_fraction"] = (valid_col > 0).mean()
        else:
            features["information_valid_fraction"] = (valid_col.astype(str).str.lower().str.contains("valid")).mean()
    else:
        features["information_valid_fraction"] = float('nan')
        
    # longest missing-data segment
    # calculate run lengths of True in missing_mask
    is_missing = missing_mask.astype(int)
    runs = is_missing.groupby((is_missing != is_missing.shift()).cumsum()).sum()
    features["longest_missing_data_segment"] = float(runs.max()) if not runs.empty else 0.0
    
    # number of discontinuities (time gaps > 2 * median sampling interval)
    if len(timestamps) > 1:
        if pd.api.types.is_datetime64_any_dtype(timestamps):
            diffs = timestamps.diff().dropna()
            if not diffs.empty:
                median_interval = diffs.median()
                discontinuities = (diffs > 2 * median_interval).sum()
                features["number_of_discontinuities"] = float(discontinuities)
            else:
                features["number_of_discontinuities"] = 0.0
        else:
            features["number_of_discontinuities"] = float('nan')
    else:
        features["number_of_discontinuities"] = 0.0
        
    return features

