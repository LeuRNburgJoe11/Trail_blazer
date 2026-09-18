import pytest
import pandas as pd
import numpy as np
from acv.preprocessing import standardize_car_telemetry, resolve_parameter
from acv.thermal_features import extract_thermal_features
from acv.control_features import extract_control_features
from acv.data_quality import extract_data_quality_features

def test_resolve_parameter():
    df = pd.DataFrame({
        "Outside Temperature Sensor Reading": [20.0, 21.0],
        "Passenger Cabin Temperature Detected Value": [25.0, 26.0]
    })
    
    outdoor = resolve_parameter(df, "Outdoor Average Temperature")
    assert list(outdoor) == [20.0, 21.0]
    
    indoor = resolve_parameter(df, "Indoor Average Temperature")
    assert list(indoor) == [25.0, 26.0]
    
    missing = resolve_parameter(df, "ACV Running Mode")
    assert missing.isna().all()

def test_extract_thermal_features():
    df = pd.DataFrame({
        "Indoor Average Temperature": [25.0, 25.5, 26.0, np.nan],
        "Outdoor Average Temperature": [20.0, 20.0, 21.0, 21.0],
        "Cooling Setpoint": [24.0, 24.0, 24.0, 24.0],
        "ACV Running Mode": ["Cooling", "Cooling", "Ventilation", "Off"]
    })
    
    feats = extract_thermal_features(df)
    assert not np.isnan(feats["temp_error_median"])
    assert feats["temp_error_median"] == 1.5 # (25.5 - 24.0) median of [1.0, 1.5, 2.0]
    
def test_extract_control_features():
    df = pd.DataFrame({
        "ACV Running Mode": ["Off", "Cooling", "Cooling", "Ventilation", "Cooling"],
        "Load Halved": [0, 1, 1, 0, 0]
    })
    timestamps = pd.Series(pd.date_range("2023-01-01", periods=5, freq="30s"))
    
    feats = extract_control_features(df, timestamps)
    assert feats["active_cooling_duty_cycle"] == 3 / 5.0
    assert feats["number_of_state_changes"] == 3 # Off -> Cooling -> Ventilation -> Cooling
    assert feats["load_halved_fraction"] == 2 / 5.0

def test_extract_data_quality_features():
    df = pd.DataFrame({
        "Indoor Average Temperature": [25.0, np.nan, np.nan, 26.0, 27.0],
        "ACV Information Valid": [1, np.nan, np.nan, 1, 1]
    })
    timestamps = pd.Series(pd.date_range("2023-01-01", periods=5, freq="30s"))
    
    feats = extract_data_quality_features(df, timestamps)
    assert feats["valid_data_fraction"] == 0.6
    assert feats["longest_missing_data_segment"] == 2
    assert feats["information_valid_fraction"] == 0.6
