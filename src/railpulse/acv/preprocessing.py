from typing import Dict, List
import pandas as pd

# Mapping of canonical names to known variations found across the dataset
PARAMETER_ALIASES = {
    "Indoor Average Temperature": [
        "Indoor Average Temperature",
        "Passenger Cabin Temperature Detected Value"
    ],
    "Outdoor Average Temperature": [
        "Outdoor Average Temperature",
        "Outside Temperature Sensor Reading",
        # We assume Fresh Air Temperature might be the closest proxy if outdoor isn't available,
        # but for now we won't strictly map it unless necessary.
    ],
    "Cooling Setpoint": [
        "ACV Control Temperature (Cooling)",
        "Target Temperature Value"
    ],
    "Heating Setpoint": [
        "ACV Control Temperature (Heating)",
        "Target Temperature Value"
    ],
    "Load Halved": [
        "Load Halved",
        "Load Shedding"
    ],
    "ACV Running Mode": [
        "ACV Running Mode",
        "ACV Operating Mode"
    ],
    "ACV Setting Mode": [
        "ACV Setting Mode",
        "ACV Control Mode"
    ],
    "ACV Information Valid": [
        "ACV Information Valid",
        "ACV Grounding Detection Status"  # Roughly analogous if true data valid isn't there, or None
    ]
}

def resolve_parameter(car_df: pd.DataFrame, canonical_name: str) -> pd.Series:
    """
    Attempts to extract a canonical parameter from the car dataframe by checking known aliases.
    Returns the series if found, otherwise returns a series of NaNs.
    """
    if canonical_name in PARAMETER_ALIASES:
        aliases = PARAMETER_ALIASES[canonical_name]
    else:
        aliases = [canonical_name]
        
    for alias in aliases:
        if alias in car_df.columns:
            return car_df[alias]
            
    # Return empty series if not found
    return pd.Series(float('nan'), index=car_df.index, name=canonical_name)

def standardize_car_telemetry(car_df: pd.DataFrame) -> pd.DataFrame:
    """
    Creates a standardized dataframe for a car with canonical column names.
    """
    standardized = pd.DataFrame(index=car_df.index)
    
    for canonical_name in PARAMETER_ALIASES.keys():
        standardized[canonical_name] = resolve_parameter(car_df, canonical_name)
        
    return standardized

