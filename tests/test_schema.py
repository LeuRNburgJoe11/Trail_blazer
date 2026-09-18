import pytest
from acv.schema import parse_column_name, extract_cars_and_parameters

def test_parse_column_name_valid():
    car_id, param = parse_column_name("Car 03 - ACV Running Mode")
    assert car_id == "03"
    assert param == "ACV Running Mode"

    car_id, param = parse_column_name("Car 1 - Indoor Average Temperature")
    assert car_id == "1"
    assert param == "Indoor Average Temperature"

def test_parse_column_name_invalid():
    car_id, param = parse_column_name("Time")
    assert car_id is None
    assert param == "Time"

def test_extract_cars_and_parameters():
    columns = [
        "Time",
        "Car 03 - ACV Running Mode",
        "Car 03 - Indoor Average Temperature",
        "Car 04 - ACV Running Mode"
    ]
    
    cars = extract_cars_and_parameters(columns)
    
    assert "03" in cars
    assert "04" in cars
    assert cars["03"]["ACV Running Mode"] == "Car 03 - ACV Running Mode"
    assert cars["03"]["Indoor Average Temperature"] == "Car 03 - Indoor Average Temperature"
    assert cars["04"]["ACV Running Mode"] == "Car 04 - ACV Running Mode"
    
    assert "Time" not in cars
