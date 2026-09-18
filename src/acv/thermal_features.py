import pandas as pd
import numpy as np
from typing import Dict, Any

def calculate_mad(series: pd.Series) -> float:
    """Calculates Median Absolute Deviation."""
    median = series.median()
    return float((series - median).abs().median())

def extract_thermal_features(car_df: pd.DataFrame) -> Dict[str, float]:
    """
    Extracts thermal features from a standardized car dataframe.
    """
    features = {}
    
    indoor = car_df.get("Indoor Average Temperature")
    outdoor = car_df.get("Outdoor Average Temperature")
    cooling_sp = car_df.get("Cooling Setpoint")
    mode = car_df.get("ACV Running Mode")
    
    has_indoor = indoor is not None and not indoor.isna().all()
    has_cooling_sp = cooling_sp is not None and not cooling_sp.isna().all()
    
    if has_indoor and has_cooling_sp:
        # Some setpoints might be 0 when off, filter invalid setpoints (e.g., < 10 or > 40)
        valid_sp_mask = (cooling_sp >= 10) & (cooling_sp <= 40)
        
        # Calculate error only where setpoint is valid
        temp_error = (indoor - cooling_sp)[valid_sp_mask].dropna()
        
        if len(temp_error) > 0:
            abs_temp_error = temp_error.abs()
            
            features["temp_error_median"] = float(temp_error.median())
            features["temp_error_abs_mean"] = float(abs_temp_error.mean())
            features["temp_error_abs_p90"] = float(abs_temp_error.quantile(0.90))
            features["temp_error_abs_p95"] = float(abs_temp_error.quantile(0.95))
            features["temp_error_abs_max"] = float(abs_temp_error.max())
            features["temp_error_std"] = float(temp_error.std())
            features["temp_error_mad"] = calculate_mad(temp_error)
            
            features["fraction_error_gt_1"] = float((abs_temp_error > 1).mean())
            features["fraction_error_gt_2"] = float((abs_temp_error > 2).mean())
            features["fraction_error_gt_3"] = float((abs_temp_error > 3).mean())
        else:
            for k in ["temp_error_median", "temp_error_abs_mean", "temp_error_abs_p90", "temp_error_abs_p95", 
                      "temp_error_abs_max", "temp_error_std", "temp_error_mad", 
                      "fraction_error_gt_1", "fraction_error_gt_2", "fraction_error_gt_3"]:
                features[k] = float('nan')
    else:
        for k in ["temp_error_median", "temp_error_abs_mean", "temp_error_abs_p90", "temp_error_abs_p95", 
                  "temp_error_abs_max", "temp_error_std", "temp_error_mad", 
                  "fraction_error_gt_1", "fraction_error_gt_2", "fraction_error_gt_3"]:
            features[k] = float('nan')

    has_outdoor = outdoor is not None and not outdoor.isna().all()
    if has_indoor and has_outdoor:
        indoor_outdoor_diff = (indoor - outdoor).dropna()
        if len(indoor_outdoor_diff) > 0:
            features["median_indoor_outdoor_diff"] = float(indoor_outdoor_diff.median())
            features["temp_variability"] = float(indoor.std())
        else:
            features["median_indoor_outdoor_diff"] = float('nan')
            features["temp_variability"] = float('nan')
    else:
        features["median_indoor_outdoor_diff"] = float('nan')
        features["temp_variability"] = float('nan')
        
    return features
