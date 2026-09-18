import pandas as pd
from typing import Dict, Any, List
from .loader import ACVCase
from .preprocessing import standardize_car_telemetry
from .data_quality import extract_data_quality_features
from .thermal_features import extract_thermal_features
from .control_features import extract_control_features
from .peer_features import get_simple_peer_median, get_context_matched_peer_median, extract_peer_features

def build_features_for_case(case: ACVCase) -> pd.DataFrame:
    """
    Builds the complete feature table for a single ACV case.
    Returns a DataFrame with one row per car.
    """
    if not case.car_ids:
        return pd.DataFrame()
        
    # 1. Standardize all cars
    std_cars = {}
    for car_id, car_df in case.cars.items():
        std_cars[car_id] = standardize_car_telemetry(car_df)
        
    # 2. Compute case-level peer references
    # We'll use 'Indoor Average Temperature' as the primary peer signal
    simple_peer_medians = get_simple_peer_median(std_cars, "Indoor Average Temperature")
    context_peer_medians = get_context_matched_peer_median(std_cars, "Indoor Average Temperature")
    
    # We might also want peer error instead of peer temperature. 
    # But sticking to peer temp is good.
    
    records = []
    
    for car_id in case.car_ids:
        std_df = std_cars[car_id]
        raw_df = case.cars[car_id]
        
        car_features = {
            "case_id": case.filename,
            "car_id": car_id
        }
        
        # Data Quality
        dq_feats = extract_data_quality_features(std_df, case.timestamps)
        car_features.update(dq_feats)
        
        # Thermal
        th_feats = extract_thermal_features(std_df)
        car_features.update(th_feats)
        
        # Control
        ctrl_feats = extract_control_features(std_df, case.timestamps)
        car_features.update(ctrl_feats)
        
        # Peer - Simple
        indoor = std_df.get("Indoor Average Temperature", pd.Series(dtype=float))
        simple_peer = simple_peer_medians.get(car_id, pd.Series(dtype=float))
        peer_simple_feats = extract_peer_features(indoor, simple_peer, prefix="peer_simple_")
        car_features.update(peer_simple_feats)
        
        # Peer - Context
        context_peer = context_peer_medians.get(car_id, pd.Series(dtype=float))
        peer_context_feats = extract_peer_features(indoor, context_peer, prefix="peer_context_")
        car_features.update(peer_context_feats)
        
        records.append(car_features)
        
    return pd.DataFrame(records)
