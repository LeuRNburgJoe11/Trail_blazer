import nbformat as nbf
import os

nb = nbf.v4.new_notebook()

text = """\
# Phase 1: Data Exploration

This notebook explores the six labelled training ACV cases.
The goal is to visually inspect the telemetry to identify patterns distinguishing the known faulty car from its peers.
"""

code_imports = """\
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys

# Add src to python path
sys.path.insert(0, os.path.abspath('../src'))
from acv.loader import load_acv_case

sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (14, 6)
"""

code_load_labels = """\
labels_path = '../data/Train_Labels.csv'
if os.path.exists(labels_path):
    labels_df = pd.read_csv(labels_path)
    labels_map = dict(zip(labels_df['filename'], labels_df['faulty_car'].astype(str).str.zfill(2)))
else:
    labels_map = {}
    print("Labels not found at", labels_path)
"""

code_explore = """\
train_dir = '../data/Train'
case_files = [f for f in os.listdir(train_dir) if f.endswith('.xlsx')]

for filename in case_files:
    path = os.path.join(train_dir, filename)
    case = load_acv_case(path)
    faulty_car = labels_map.get(filename, None)
    
    print(f"\\n{'='*50}")
    print(f"Case: {filename} | Faulty Car: {faulty_car}")
    print(f"{'='*50}")
    
    if not case.car_ids:
        print("No cars detected.")
        continue
        
    # Pick a common thermal parameter
    # usually 'Indoor Average Temperature' or 'Outdoor Average Temperature'
    param_indoor = 'Indoor Average Temperature'
    
    # Check if param exists for all cars
    all_have_indoor = all(param_indoor in case.available_parameters[c] for c in case.car_ids)
    
    if all_have_indoor:
        plt.figure()
        for car_id in case.car_ids:
            car_df = case.cars[car_id]
            color = 'red' if car_id == faulty_car else 'grey'
            alpha = 1.0 if car_id == faulty_car else 0.4
            linewidth = 2.0 if car_id == faulty_car else 1.0
            
            plt.plot(case.timestamps, car_df[param_indoor], 
                     label=f"Car {car_id}{' (Faulty)' if car_id == faulty_car else ''}", 
                     color=color, alpha=alpha, linewidth=linewidth)
                     
        plt.title(f"{filename} - {param_indoor}")
        plt.xlabel("Time")
        plt.ylabel("Temperature (°C)")
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.show()
    else:
        print(f"Parameter '{param_indoor}' not available for all cars in {filename}.")
"""

nb['cells'] = [
    nbf.v4.new_markdown_cell(text),
    nbf.v4.new_code_cell(code_imports),
    nbf.v4.new_code_cell(code_load_labels),
    nbf.v4.new_code_cell(code_explore)
]

output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'notebooks', '01_data_exploration.ipynb'))
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w') as f:
    nbf.write(nb, f)
print(f"Notebook generated at {output_path}")

