import os
import glob
import pandas as pd
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from acv.loader import load_acv_case
from acv.feature_pipeline import build_features_for_case

def main():
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    train_dir = os.path.join(data_dir, 'Train')
    test_dir = os.path.join(data_dir, 'Test')
    
    train_files = glob.glob(os.path.join(train_dir, '*.xlsx'))
    test_files = glob.glob(os.path.join(test_dir, '*.xlsx'))
    
    labels_path = os.path.join(data_dir, 'Train_Labels.csv')
    labels = {}
    if os.path.exists(labels_path):
        labels_df = pd.read_csv(labels_path)
        labels = dict(zip(labels_df['filename'], labels_df['faulty_car'].astype(str).str.zfill(2)))
        
    all_features = []
    
    for file_path in train_files:
        print(f"Building features for {os.path.basename(file_path)}...")
        case = load_acv_case(file_path)
        df_feats = build_features_for_case(case)
        
        if not df_feats.empty:
            # Add target variable
            faulty_car = labels.get(case.filename)
            if faulty_car:
                df_feats['faulty'] = (df_feats['car_id'] == faulty_car).astype(int)
            else:
                df_feats['faulty'] = -1
                
            all_features.append(df_feats)
            
    if all_features:
        final_df = pd.concat(all_features, ignore_index=True)
        
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs'))
        os.makedirs(output_dir, exist_ok=True)
        
        out_path = os.path.join(output_dir, 'train_features.csv')
        final_df.to_csv(out_path, index=False)
        print(f"Features saved to {out_path}")
        print(f"Shape: {final_df.shape}")
    else:
        print("No features generated.")

if __name__ == "__main__":
    main()
