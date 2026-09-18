import pytest
from railpulse.acv.metrics import rank_decay_score

def test_rank_decay_score():
    ranked_cars = ["03", "01", "05", "02", "04", "06", "07", "08"]
    
    # rank 1
    assert rank_decay_score("03", ranked_cars) == 1.000
    
    # rank 2
    assert rank_decay_score("01", ranked_cars) == 8/8 - 1/8
    
    # rank 8
    assert rank_decay_score("08", ranked_cars) == 1/8
    
    # missing
    assert rank_decay_score("09", ranked_cars) == 0.0

