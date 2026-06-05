from SALib.sample.latin import sample
import pandas as pd
import math
from pathlib import Path
import yaml


with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

OUTPUT_DIR = Path(cfg["sensitivity_analysis"]["output"]["sample_data"])     # Store random sample data here

problem = {
    'num_vars': 5,
    'names': ['L', 'C', 'R', 'SCR', 'XR'],
    'bounds': [[400., 800.], [800., 2100.], [6.0, 10.0], [5.0, 15.0], [5.0, 20.0]]
}

X = sample(problem, 300)
xcols = ['L', 'C', 'R', 'SCR', 'XR']
df = pd.DataFrame(X)
df.columns = xcols

Sn = 1200
Vtrms = 400
fn = 50

df['Lg'] = 400**2 / (df['SCR'] * Sn * 2 * fn * math.pi)
df['Rg'] = 400**2 / (df['SCR'] * Sn * df['XR'])
df = df.round(3)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
df.to_csv(f"{OUTPUT_DIR}/train_input_data.csv", index=False)
