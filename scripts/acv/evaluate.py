import os
import pandas as pd
import sys

def main():
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'outputs', 'acv'))
    results_path = os.path.join(output_dir, 'validation_results_baseline.csv')
    
    if not os.path.exists(results_path):
        print("Validation results not found. Run train.py first.")
        return
        
    df = pd.read_csv(results_path)
    
    print("Per-case ranking results (Baseline)\n")
    for _, row in df.iterrows():
        print(f"Case {row['case_id']}")
        print(f"True faulty car: {row['true_faulty_car']}")
        print(f"Rank: {row['true_car_rank']}")
        print(f"Score: {row['rank_decay_score']:.3f}\n")
        
    print("Overall")
    print(f"Mean rank-decay score: {df['rank_decay_score'].mean():.3f}")
    print(f"Top-1 cases: {(df['true_car_rank'] == 1).sum()}")
    print(f"Top-2 cases: {(df['true_car_rank'] <= 2).sum()}")
    print(f"Worst-case rank: {df['true_car_rank'].max()}")

if __name__ == "__main__":
    main()
