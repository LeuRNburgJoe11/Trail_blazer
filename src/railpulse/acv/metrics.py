import pandas as pd
from typing import List

def rank_decay_score(true_car: str, ranked_cars: List[str]) -> float:
    """
    Calculates the ACV linear rank-decay metric.
    n = number of cars
    r = rank of the true faulty car (1-based)
    score = (n - (r - 1)) / n
    If true car is missing: score = 0
    """
    n = len(ranked_cars)
    if n == 0:
        return 0.0
        
    try:
        r = ranked_cars.index(true_car) + 1
        return (n - (r - 1)) / n
    except ValueError:
        return 0.0

