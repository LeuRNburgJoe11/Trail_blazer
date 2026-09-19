import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import os
from .schema import extract_cars_and_parameters

@dataclass
class ACVCase:
    filename: str
    timestamps: pd.Series
    metadata: Dict[str, Any]
    car_ids: List[str]
    cars: Dict[str, pd.DataFrame]
    available_parameters: Dict[str, List[str]]
    warnings: List[str]

def load_acv_case(path: str) -> ACVCase:
    """
    Loads an ACV case from an Excel file, extracts per-car telemetry, and normalizes it.
    """
    df = pd.read_excel(path)
    
    filename = os.path.basename(path)
    warnings = []
    
    # Identify timestamp column
    timestamp_col = None
    # Look for obvious time column
    time_columns = [col for col in df.columns if str(col).strip().lower() in ("time", "timestamp", "datetime")]
    if len(time_columns) != 1:
        raise ValueError("ACV requires exactly one explicit Time/Timestamp/Datetime column")
    timestamp_col = time_columns[0]
        
    if df.empty:
        raise ValueError("ACV case contains no telemetry rows")
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="raise")
    if df[timestamp_col].isna().any():
        raise ValueError("ACV timestamps contain missing values")
    if not df[timestamp_col].is_monotonic_increasing:
        warnings.append("Input timestamps reordered chronologically")
    df = df.sort_values(by=timestamp_col, kind="stable").reset_index(drop=True)
        
    timestamps = df[timestamp_col]
    
    # Check for duplicates
    num_duplicates = timestamps.duplicated().sum()
    if num_duplicates > 0:
        warnings.append(f"Found {num_duplicates} duplicate timestamps")
        
    # Extract car parameters
    car_map = extract_cars_and_parameters(df.columns.tolist())
    car_ids = sorted(list(car_map.keys()))
    if not car_ids:
        raise ValueError("No native car telemetry columns found")
    
    cars = {}
    available_parameters = {}
    
    for car_id in car_ids:
        params = car_map[car_id]
        car_df = pd.DataFrame(index=df.index)
        available_parameters[car_id] = list(params.keys())
        
        for param_name, orig_col in params.items():
            try:
                car_df[param_name] = pd.to_numeric(df[orig_col])
            except (ValueError, TypeError):
                car_df[param_name] = df[orig_col]
            
        cars[car_id] = car_df
        
    return ACVCase(
        filename=filename,
        timestamps=timestamps,
        metadata={"original_columns": df.columns.tolist()},
        car_ids=car_ids,
        cars=cars,
        available_parameters=available_parameters,
        warnings=warnings
    )
