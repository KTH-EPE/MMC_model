import pandas as pd
from pathlib import Path
import chaospy as cp
import yaml
import numpy as np
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

# ---------------------------
# Load configuration
# ---------------------------
with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

SAMPLE_DATA_DIR = Path(cfg["sensitivity_analysis"]["output"]["sample_data"])
TEST_RESULTS = Path("../../result_analysis/summary/step_up_u_ref_response_summary_SA.csv")

# ---------------------------
# Load and merge data
# ---------------------------
sample_data_df = pd.read_csv(f"{SAMPLE_DATA_DIR}/train_input_data.csv")
test_results_df = pd.read_csv(TEST_RESULTS)

train_test_df = pd.merge(
    sample_data_df,
    test_results_df.iloc[:, 5:11],
    left_on=["L", "C", "R"],
    right_on=["H_mH", "C_uF", "R_ohms"],
    how="inner"
)

train_test_df.drop(columns=["H_mH", "C_uF", "R_ohms"], inplace=True)

# Convert inductance to correct scale
train_test_df["L"] = train_test_df["L"] / 1000

# Save processed dataset (optional)
train_test_df.to_csv(f"{SAMPLE_DATA_DIR}/train_io_data.csv", index=False)

print(train_test_df.tail())

# ---------------------------
# Define inputs and output
# ---------------------------
X_raw = train_test_df.iloc[:, 0:5].values   # L, C, R, SCR, XR
Y = train_test_df.iloc[:, 7].values          # output (Xm), Tcr and Tcs should also be tested

# ---------------------------
# Train-test split (IMPORTANT)
# ---------------------------
X_train, X_test, Y_train, Y_test = train_test_split(
    X_raw, Y, test_size=0.2, random_state=13
)

X_train_T = X_train.T
X_test_T = X_test.T

# ---------------------------
# Define input distributions
# ---------------------------
dist = cp.J(
    cp.Uniform(0.4, 0.8),     # L
    cp.Uniform(800, 2100),    # C
    cp.Uniform(6.0, 10.0),    # R
    cp.Uniform(5.0, 15.0),    # SCR
    cp.Uniform(5.0, 20.0)     # XR
)

# ---------------------------
# Polynomial Chaos Expansion
# ---------------------------
order = 3
poly_expansion = cp.generate_expansion(order, dist)

approx_model = cp.fit_regression(poly_expansion, X_train_T, Y_train)

# ---------------------------
# Predictions
# ---------------------------
Y_pred_train = approx_model(*X_train_T)
Y_pred_test = approx_model(*X_test_T)

# ---------------------------
# Accuracy metrics
# ---------------------------

# R² (train & test)
r2_train = r2_score(Y_train, Y_pred_train)
r2_test = r2_score(Y_test, Y_pred_test)

# Relative L2 error (test set)
rel_l2_error = np.linalg.norm(Y_test - Y_pred_test) / np.linalg.norm(Y_test)

print("\n===== PCE ACCURACY =====")
print("Train R2:", r2_train)
print("Test R2:", r2_test)
print("Relative L2 error:", rel_l2_error)

# ---------------------------
# Sobol indices
# ---------------------------
sobol_first = cp.Sens_m(approx_model, dist)
sobol_second = cp.Sens_m2(approx_model, dist)
sobol_total = cp.Sens_t(approx_model, dist)

print("\n===== SOBOL INDICES =====")
print("First-order Sobol:", sobol_first)
print("Second-order Sobol:", sobol_second)
print("Total Sobol:", sobol_total)