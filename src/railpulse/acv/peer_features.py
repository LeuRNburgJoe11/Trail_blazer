import pandas as pd
import numpy as np
from typing import Dict, List, Any

def get_simple_peer_median(cars_data: Dict[str, pd.DataFrame], signal: str) -> pd.DataFrame:
    """
    Returns a dataframe where each column is a car_id and its values are the median 
    of the signal across all OTHER valid cars at that timestamp.
    """
    car_ids = list(cars_data.keys())
    if not car_ids:
        return pd.DataFrame()
        
    # Build a combined df for the signal
    combined = pd.DataFrame({car_id: pd.to_numeric(cars_data[car_id].get(signal, pd.Series(dtype=float)), errors='coerce') for car_id in car_ids})
    
    peer_medians = pd.DataFrame(index=combined.index, columns=car_ids)
    
    for car_id in car_ids:
        other_cars = [c for c in car_ids if c != car_id]
        peer_medians[car_id] = combined[other_cars].median(axis=1)
        
    return peer_medians

def get_context_matched_peer_median(cars_data: Dict[str, pd.DataFrame], signal: str) -> pd.DataFrame:
    """
    Returns a dataframe of peer medians using context matching.
    Context matching logic:
    Level 1: Same running mode, same load state, similar setpoint (<= 1C diff)
    Level 2: Same running mode, similar setpoint
    Level 3: Same running mode
    Fallback: All valid peers
    """
    car_ids = list(cars_data.keys())
    if not car_ids:
        return pd.DataFrame()
        
    combined_signal = pd.DataFrame({c: pd.to_numeric(cars_data[c].get(signal, pd.Series(dtype=float)), errors='coerce') for c in car_ids})
    combined_mode = pd.DataFrame({c: cars_data[c].get("ACV Running Mode", pd.Series(dtype=str)) for c in car_ids})
    combined_load = pd.DataFrame({c: pd.to_numeric(cars_data[c].get("Load Halved", pd.Series(dtype=float)), errors='coerce') for c in car_ids})
    combined_sp = pd.DataFrame({c: pd.to_numeric(cars_data[c].get("Cooling Setpoint", pd.Series(dtype=float)), errors='coerce') for c in car_ids})
    
    peer_medians = pd.DataFrame(np.nan, index=combined_signal.index, columns=car_ids)
    
    # We will compute row by row which is slow, but acceptable for small data
    # We can vectorize it for performance
    for car_id in car_ids:
        other_cars = [c for c in car_ids if c != car_id]
        if not other_cars:
            continue
            
        target_mode = combined_mode[car_id]
        target_load = combined_load[car_id]
        target_sp = combined_sp[car_id]
        
        # Build masks for other cars
        for other_car in other_cars:
            # We construct the matching level directly, but since we want the median over all valid peers at a timestamp,
            # we should compute masks.
            pass
            
        modes = combined_mode[other_cars].values
        loads = combined_load[other_cars].values
        sps = combined_sp[other_cars].values
        signals = combined_signal[other_cars].values
        
        mode_i = target_mode.values[:, None]
        load_i = target_load.values[:, None]
        sp_i = target_sp.values[:, None]
        
        # Level 1 mask
        l1_mask = (modes == mode_i) & (loads == load_i) & (np.abs(sps - sp_i) <= 1.0)
        
        # Level 2 mask
        l2_mask = (modes == mode_i) & (np.abs(sps - sp_i) <= 1.0)
        
        # Level 3 mask
        l3_mask = (modes == mode_i)
        
        # Fallback mask (all valid peers)
        fb_mask = np.ones_like(modes, dtype=bool)
        
        # We need to compute the median for each row based on the highest level mask that has at least one True.
        # We can calculate medians for all levels, and then select the first valid one.
        def masked_median(mask):
            # Fill masked out elements with NaN, then compute nanmedian along axis 1
            masked_signals = np.where(mask, signals, np.nan)
            with np.errstate(all='ignore'):
                return np.nanmedian(masked_signals, axis=1)
                
        l1_med = masked_median(l1_mask)
        l2_med = masked_median(l2_mask)
        l3_med = masked_median(l3_mask)
        fb_med = masked_median(fb_mask)
        
        # Choose median: L1 if available, else L2, else L3, else FB
        med = np.where(~np.isnan(l1_med), l1_med,
               np.where(~np.isnan(l2_med), l2_med,
                np.where(~np.isnan(l3_med), l3_med, fb_med)))
                
        # If target mode_i is NaN, we can only use fallback
        med = np.where(pd.isna(target_mode), fb_med, med)
        
        peer_medians[car_id] = med
        
    return peer_medians

def extract_peer_features(signal_series: pd.Series, peer_median: pd.Series, prefix: str = "peer_") -> Dict[str, float]:
    """
    Extracts features from the residual between a car's signal and its peer median.
    """
    features = {}
    
    residual = (signal_series - peer_median).dropna()
    
    if len(residual) == 0:
        for k in ["residual_median", "residual_abs_median", "residual_abs_p90", "residual_abs_p95", 
                  "residual_abs_max", "residual_mad", "fraction_gt_1", "fraction_gt_2", "longest_persistent_deviation"]:
            features[f"{prefix}{k}"] = float('nan')
        return features
        
    abs_residual = residual.abs()
    
    features[f"{prefix}residual_median"] = float(residual.median())
    features[f"{prefix}residual_abs_median"] = float(abs_residual.median())
    features[f"{prefix}residual_abs_p90"] = float(abs_residual.quantile(0.90))
    features[f"{prefix}residual_abs_p95"] = float(abs_residual.quantile(0.95))
    features[f"{prefix}residual_abs_max"] = float(abs_residual.max())
    
    median_res = features[f"{prefix}residual_median"]
    features[f"{prefix}residual_mad"] = float((abs_residual - median_res).abs().median())
    
    features[f"{prefix}fraction_gt_1"] = float((abs_residual > 1.0).mean())
    features[f"{prefix}fraction_gt_2"] = float((abs_residual > 2.0).mean())
    
    # longest persistent deviation (e.g. > 1 degree)
    is_dev = (abs_residual > 1.0).astype(int)
    runs = is_dev.groupby((is_dev != is_dev.shift()).cumsum()).sum()
    features[f"{prefix}longest_persistent_deviation"] = float(runs.max()) if not runs.empty else 0.0
    
    return features
