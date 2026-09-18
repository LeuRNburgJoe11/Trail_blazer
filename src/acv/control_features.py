import pandas as pd
import numpy as np
from typing import Dict, Any

def extract_control_features(car_df: pd.DataFrame, timestamps: pd.Series) -> Dict[str, float]:
    """
    Extracts control-state features from a standardized car dataframe.
    """
    features = {}
    
    total_time = len(car_df)
    if total_time == 0:
        return {}
        
    mode = car_df.get("ACV Running Mode")
    if mode is not None and not mode.isna().all():
        # Clean string representing mode
        mode_str = mode.astype(str).str.lower().str.strip()
        
        # State changes
        # forward fill to avoid counting NaNs as state changes if we want to ignore missing gaps
        mode_filled = mode_str.replace("nan", np.nan).ffill()
        state_changes = (mode_filled != mode_filled.shift()).sum() - 1 # -1 for first element
        state_changes = max(0, state_changes)
        
        features["number_of_state_changes"] = float(state_changes)
        
        duration_hours = 1.0
        if pd.api.types.is_datetime64_any_dtype(timestamps) and len(timestamps) > 1:
            duration_hours = (timestamps.max() - timestamps.min()).total_seconds() / 3600.0
            if duration_hours <= 0:
                duration_hours = 1.0
        
        features["state_transition_rate_per_hour"] = float(state_changes / duration_hours)
        
        # Fraction of time in cooling
        # E.g., 'cooling', 'cool', 'refrigeration'
        cooling_mask = mode_str.str.contains("cool|refrigeration", na=False, regex=True)
        features["active_cooling_duty_cycle"] = float(cooling_mask.mean())
        
        # longest continuous state duration
        is_cooling = cooling_mask.astype(int)
        runs = is_cooling.groupby((is_cooling != is_cooling.shift()).cumsum()).sum()
        longest_cooling = runs.max()
        features["longest_continuous_cooling_ticks"] = float(longest_cooling) if not np.isnan(longest_cooling) else 0.0
    else:
        features["number_of_state_changes"] = float('nan')
        features["state_transition_rate_per_hour"] = float('nan')
        features["active_cooling_duty_cycle"] = float('nan')
        features["longest_continuous_cooling_ticks"] = float('nan')

    load_halved = car_df.get("Load Halved")
    if load_halved is not None and not load_halved.isna().all():
        # could be 0/1 or string
        if pd.api.types.is_numeric_dtype(load_halved):
            features["load_halved_fraction"] = float((load_halved > 0).mean())
        else:
            features["load_halved_fraction"] = float(load_halved.astype(str).str.lower().str.contains("half|shed|1").mean())
    else:
        features["load_halved_fraction"] = float('nan')
        
    return features
