import re
from typing import Dict, Tuple, List, Optional

def parse_column_name(column_name: str) -> Tuple[Optional[str], str]:
    """
    Parses a column name to extract the car ID and parameter name.
    
    Expected format: 'Car 03 - ACV Running Mode'
    Returns: (car_id, parameter_name) or (None, column_name) if it doesn't match.
    """
    match = re.match(r"Car\s+(\d+)\s*-\s*(.+)", str(column_name).strip())
    if match:
        car_id = match.group(1)
        param_name = match.group(2).strip()
        return car_id, param_name
    return None, str(column_name)

def extract_cars_and_parameters(columns: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Given a list of column names, extracts the cars and their parameters.
    
    Returns a dictionary mapping car_id -> {parameter_name: original_column_name}
    """
    cars: Dict[str, Dict[str, str]] = {}
    for col in columns:
        car_id, param_name = parse_column_name(col)
        if car_id is not None:
            if car_id not in cars:
                cars[car_id] = {}
            if param_name in cars[car_id]:
                raise ValueError(f"Duplicate telemetry mapping for car {car_id}: {param_name}")
            cars[car_id][param_name] = col
    return cars
