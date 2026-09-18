import pytest
import pandas as pd
import numpy as np
from acv.peer_features import get_simple_peer_median, get_context_matched_peer_median, extract_peer_features
from acv.loader import ACVCase
from acv.feature_pipeline import build_features_for_case

def test_peer_medians():
    cars_data = {
        "01": pd.DataFrame({"Indoor Average Temperature": [20, 21, 22], "ACV Running Mode": ["Cooling", "Cooling", "Cooling"], "Load Halved": [0, 0, 0], "Cooling Setpoint": [20, 20, 20]}),
        "02": pd.DataFrame({"Indoor Average Temperature": [22, 23, 24], "ACV Running Mode": ["Cooling", "Cooling", "Cooling"], "Load Halved": [0, 0, 0], "Cooling Setpoint": [20, 20, 20]}),
        "03": pd.DataFrame({"Indoor Average Temperature": [24, 25, 26], "ACV Running Mode": ["Heating", "Cooling", "Cooling"], "Load Halved": [0, 0, 0], "Cooling Setpoint": [20, 20, 20]})
    }
    
    simple = get_simple_peer_median(cars_data, "Indoor Average Temperature")
    
    # For car 01: peers are 02 (22), 03 (24) -> median is 23
    assert simple["01"].iloc[0] == 23.0
    
    context = get_context_matched_peer_median(cars_data, "Indoor Average Temperature")
    
    # For car 01 at idx 0: mode is Cooling. Peers: 02 (Cooling), 03 (Heating). 
    # Context match should pick 02 only for level 1.
    assert context["01"].iloc[0] == 22.0
    
def test_build_features_for_case():
    cars_data = {
        "01": pd.DataFrame({"Indoor Average Temperature": [20, 21, 22], "ACV Running Mode": ["Cooling", "Cooling", "Cooling"], "Load Halved": [0, 0, 0], "Cooling Setpoint": [20, 20, 20]}),
        "02": pd.DataFrame({"Indoor Average Temperature": [22, 23, 24], "ACV Running Mode": ["Cooling", "Cooling", "Cooling"], "Load Halved": [0, 0, 0], "Cooling Setpoint": [20, 20, 20]})
    }
    
    case = ACVCase(
        filename="test.xlsx",
        timestamps=pd.Series(pd.date_range("2023-01-01", periods=3, freq="30s")),
        metadata={},
        car_ids=["01", "02"],
        cars=cars_data,
        available_parameters={},
        warnings=[]
    )
    
    df_features = build_features_for_case(case)
    
    assert len(df_features) == 2
    assert "car_id" in df_features.columns
    assert "peer_simple_residual_median" in df_features.columns
    assert "temp_error_median" in df_features.columns
    assert df_features.loc[0, "car_id"] == "01"
    assert df_features.loc[1, "car_id"] == "02"
