import os
import glob
import pandas as pd
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
from railpulse.acv.loader import load_acv_case

def main():
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'acv'))
    train_dir = os.path.join(data_dir, 'Train')
    test_dir = os.path.join(data_dir, 'Test')
    
    all_files = glob.glob(os.path.join(train_dir, '*.xlsx')) + glob.glob(os.path.join(test_dir, '*.xlsx'))
    
    for file_path in all_files:
        print(f"Inspecting {os.path.basename(file_path)}...", flush=True)
        t0 = time.time()
        case = load_acv_case(file_path)
        print(f"Loaded {case.filename} in {time.time()-t0:.1f}s. Cars: {case.car_ids}", flush=True)

if __name__ == "__main__":
    main()

