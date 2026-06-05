import pandas as pd
from pathlib import Path
import chaospy as cp
import yaml
from sklearn.metrics import r2_score


with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

SAMPLE_DATA_DIR = Path(cfg["sensitivity_analysis"]["output"]["sample_data"])
TEST_RESULTS = Path("../../result_analysis/summary/step_up_u_ref_response_summary_SA.csv")

# Load data
sample_data_df = pd.read_csv(f"{SAMPLE_DATA_DIR}/train_input_data.csv")
test_results_df = pd.read_csv(TEST_RESULTS)
train_test_df = pd.merge(sample_data_df,
                         test_results_df.iloc[:, 5:11],
                         left_on=["L", "C", "R"],
                         right_on=["H_mH", "C_uF", "R_ohms"],
                         how="inner"
                         )
train_test_df.drop(columns=["H_mH", "C_uF", "R_ohms"], inplace=True)
train_test_df.to_csv(f"{SAMPLE_DATA_DIR}/train_io_data.csv")
train_test_df['L'] = round(train_test_df['L']/1000, 6)

print(train_test_df.tail())

X_raw = train_test_df.iloc[:, 0:5].values   # (samples: L, C, R, SCR, XR)
Y = train_test_df.iloc[:, 7].values         # Xm (should be performed for Tcs and Tcr too)
X = X_raw.T

# Define distributions
dist = cp.J(
    cp.Uniform(0.4, 0.8),
    cp.Uniform(800, 2100),
    cp.Uniform(6.0, 10.0),
    cp.Uniform(5.0, 15.0),
    cp.Uniform(5.0, 20.0)
)

# Polynomial order
order = 3

# Generate polynomial basis
poly_expansion = cp.generate_expansion(order, dist)

# Fit PCE using regression
approx_model = cp.fit_regression(poly_expansion, X, Y)

# ---- Validation ----
Y_pred = approx_model(*X)   # vectorized prediction

print("R2:", r2_score(Y, Y_pred))

# ---- Sobol indices ----
sobol_first = cp.Sens_m(approx_model, dist)
sobol_second = cp.Sens_m2(approx_model, dist)
sobol_total = cp.Sens_t(approx_model, dist)

print("First-order Sobol:", sobol_first)
print("Second-order Sobol:", sobol_second)
print("Total Sobol:", sobol_total)
