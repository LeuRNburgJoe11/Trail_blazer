import pytest
import pandas as pd
import tempfile
import os
from railpulse.acv.loader import load_acv_case, ACVCase

def test_load_acv_case():
    # Create dummy data
    data = {
        "Time": ["2023-01-01 10:00:00", "2023-01-01 10:00:30"],
        "Car 01 - ACV Running Mode": ["Cooling", "Heating"],
        "Car 01 - Indoor Average Temperature": [22.5, 23.1],
        "Car 02 - ACV Running Mode": ["Ventilation", "Cooling"]
    }
    df = pd.DataFrame(data)
    
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        tmp_path = tmp.name
        
    try:
        case = load_acv_case(tmp_path)
        
        assert isinstance(case, ACVCase)
        assert case.car_ids == ["01", "02"]
        assert len(case.timestamps) == 2
        
        assert "ACV Running Mode" in case.cars["01"].columns
        assert "Indoor Average Temperature" in case.cars["01"].columns
        assert "ACV Running Mode" in case.cars["02"].columns
        
        # Check numeric conversion
        assert pd.api.types.is_numeric_dtype(case.cars["01"]["Indoor Average Temperature"])
        
    finally:
        os.remove(tmp_path)

