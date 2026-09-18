import os
import glob
import pandas as pd
import json
import sys

# Add src to path so we can import acv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from railpulse.acv.loader import load_acv_case

def main():
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    train_dir = os.path.join(data_dir, 'Train')
    test_dir = os.path.join(data_dir, 'Test')
    
    all_files = glob.glob(os.path.join(train_dir, '*.xlsx')) + glob.glob(os.path.join(test_dir, '*.xlsx'))
    
    manifest_records = []
    
    for file_path in all_files:
        print(f"Inspecting {os.path.basename(file_path)}...")
        
        # Load raw df just to get simple stats quickly
        df = pd.read_excel(file_path)
        
        # Load via acv to get normalized data
        case = load_acv_case(file_path)
        
        # Calculate start and end timestamps
        start_ts = case.timestamps.min()
        end_ts = case.timestamps.max()
        
        # Estimate sampling interval
        if len(case.timestamps) > 1:
            if pd.api.types.is_datetime64_any_dtype(case.timestamps):
                diffs = case.timestamps.diff().dropna()
                estimated_interval = str(diffs.mode().iloc[0]) if not diffs.empty else "N/A"
            else:
                try:
                    ts_dt = pd.to_datetime(case.timestamps)
                    diffs = ts_dt.diff().dropna()
                    estimated_interval = str(diffs.mode().iloc[0]) if not diffs.empty else "N/A"
                except Exception:
                    estimated_interval = "Unknown"
        else:
            estimated_interval = "N/A"
            
        missing_fraction = df.isna().mean().mean()
        duplicate_ts = case.timestamps.duplicated().sum()
        
        # Get parameter sets
        car_params = case.available_parameters
        
        manifest_records.append({
            "filename": case.filename,
            "number_of_rows": len(df),
            "number_of_columns": len(df.columns),
            "detected_car_ids": "|".join(case.car_ids),
            "number_of_cars": len(case.car_ids),
            "timestamp_column": case.timestamps.name,
            "start_timestamp": str(start_ts),
            "end_timestamp": str(end_ts),
            "estimated_sampling_interval": estimated_interval,
            "available_parameters_per_car": json.dumps(car_params),
            "missing_value_fraction": round(missing_fraction, 4),
            "duplicate_timestamps": int(duplicate_ts)
        })
        
    if not manifest_records:
        print("No Excel files found.")
        return
        
    manifest_df = pd.DataFrame(manifest_records)
    
    # Calculate global parameter overlaps
    all_params_per_file = {}
    for r in manifest_records:
        car_params = json.loads(r["available_parameters_per_car"])
        # aggregate parameters for this file
        file_params = set()
        for params in car_params.values():
            file_params.update(params)
        all_params_per_file[r["filename"]] = file_params
        
    common_params = set.intersection(*all_params_per_file.values()) if all_params_per_file else set()
    
    print("\nParameters common to all cars/files:")
    for p in sorted(list(common_params)):
        print(f" - {p}")
        
    # Unique params per file
    for r in manifest_records:
        file_params = all_params_per_file[r["filename"]]
        unique_params = file_params - common_params
        r["parameters_unique_to_file"] = "|".join(sorted(list(unique_params)))
        r["parameters_common_to_all"] = "|".join(sorted(list(common_params)))
        
    manifest_df = pd.DataFrame(manifest_records)
    
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs'))
    os.makedirs(output_dir, exist_ok=True)
    
    csv_path = os.path.join(output_dir, 'dataset_manifest.csv')
    json_path = os.path.join(output_dir, 'dataset_manifest.json')
    
    manifest_df.to_csv(csv_path, index=False)
    manifest_df.to_json(json_path, orient="records", indent=2)
    
    print(f"\nManifest saved to {csv_path}")
    print(f"Manifest saved to {json_path}")
    
    print("\nOverview:")
    print(manifest_df[['filename', 'number_of_rows', 'number_of_cars', 'missing_value_fraction']].to_string())

if __name__ == "__main__":
    main()

