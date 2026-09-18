import pytest
import pandas as pd
from acv.ranking import calculate_robust_z_scores, baseline_ranking

def test_calculate_robust_z_scores():
    df = pd.DataFrame({
        "car_id": ["01", "02", "03", "04", "05"],
        "temp_error_median": [1.0, 1.1, 1.05, 5.0, 0.95] # 04 is an outlier
    })
    
    scored = calculate_robust_z_scores(df, ["temp_error_median"])
    
    assert "z_temp_error_median" in scored.columns
    # Outlier should have highest score
    assert scored.loc[3, "z_temp_error_median"] > scored.loc[0, "z_temp_error_median"]
    assert scored.loc[3, "z_temp_error_median"] > 10.0 # It should be quite large
    
def test_baseline_ranking():
    df = pd.DataFrame({
        "car_id": ["01", "02", "03", "04"],
        "temp_error_median": [1.0, 1.0, 1.0, 5.0],
        "peer_context_residual_median": [0.1, 0.1, 0.1, 3.0],
        "peer_context_longest_persistent_deviation": [0, 0, 0, 100],
        "active_cooling_duty_cycle": [0.5, 0.5, 0.5, 0.9]
    })
    
    ranked = baseline_ranking(df)
    
    assert len(ranked) == 4
    assert ranked.iloc[0]["car_id"] == "04"
    assert ranked.iloc[0]["rank"] == 1
    
    assert ranked.iloc[1]["rank"] == 2
