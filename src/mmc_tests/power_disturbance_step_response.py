from methods import *

# =========================
# Load configuration file
# =========================
# Read experiment parameters for the active power disturbance study

with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

# Extract configuration for the power disturbance experiment
PROJECT_PATH = Path(cfg["step_power_disturbance"]["path"])              # PSCAD project file path
PROJECT_NAME = cfg["step_power_disturbance"]["name"]                    # Project name inside PSCAD
OUTPUT_FILE_NAME = cfg["step_power_disturbance"]["output"]["file_name"]  # Base name for PSCAD output file
RESULT_FILE = Path(f'{cfg["step_power_disturbance"]["output"]["result_file"]}/{OUTPUT_FILE_NAME}')  # Temporary file
OUTPUT_DIR = Path(cfg["step_power_disturbance"]["output"]["directory"])     # Directory for storing processed results
REF_POWER = cfg["step_power_disturbance"]["ref_power"]                  # Initial steady-state active power
STEP_POWER = cfg["step_power_disturbance"]["step_power"]          # Power after step-up disturbance


# =========================
# Single simulation run
# =========================
def run_single_test():
    """
    Run a single RLC simulation for a fixed operating point.

    Uses fixed parameters:
        L = 0.4 H
        C = 1300 uF
        R = 6 Ohm
    """

    # Connect to PSCAD model and configure power disturbance scenario
    proj, components = connect_step_power_disturbance_model(
        proj_path=PROJECT_PATH,
        proj_name=PROJECT_NAME,
        output_file_name=OUTPUT_FILE_NAME,
        ref_power=REF_POWER,
        step_P=STEP_POWER
    )

    # Run simulation for a single RLC configuration
    csv_file = run_lcr_simulation(
        proj=proj,
        components=components,
        L=0.4,
        C=1300,
        R=6,
        result_file=RESULT_FILE
    )

    return csv_file


# =========================
# Parameter space definition
# =========================
def generate_parameter_space():
    """
    Define the parameter space for RLC sweep.

    Returns:
        inductors  : List of inductance values [H]
        resistors  : List of resistance values [Ohm]
        capacitors : List of capacitance values [uF]

    Notes:
    - Inductance is swept from 0.4 H to 0.9 H (step = 0.05 H)
    - Resistance is swept from 6 to 10 Ohm
    - Capacitance is swept from 500 to 2400 uF (step = 100 uF)

    This parameter space represents variations in the DC-side equivalent network.
    """
    inductors = [i * 1e-3 for i in range(400, 801, 100)]  # Convert mH → H
    resistors = list(range(6, 11))                       # Integer Ohmic values
    capacitors = list(range(800, 2101, 100))             # Capacitance values in uF

    return inductors, resistors, capacitors


# =========================
# Parameter sweep execution
# =========================
def run_parameter_sweep():
    """
    Run a full RLC parameter sweep for the power disturbance scenario.

    Workflow:
    1. Connect to PSCAD model and configure disturbance
    2. Generate parameter combinations (L, R, C)
    3. Run simulations for all combinations
    4. Save results with structured filenames
    """

    # Step 1: Connect to PSCAD and extract component handles
    proj, components = connect_step_power_disturbance_model(
        proj_path=PROJECT_PATH,
        proj_name=PROJECT_NAME,
        output_file_name=OUTPUT_FILE_NAME,
        ref_power=REF_POWER,
        step_P=STEP_POWER
    )

    # Step 2: Generate sweep values
    L_vals, R_vals, C_vals = generate_parameter_space()

    # Step 3: Execute parameter sweep
    run_rlc_parameter_sweep(
        inductor_values=L_vals,
        resistor_values=R_vals,
        capacitor_values=C_vals,
        output_dir=OUTPUT_DIR,
        result_file=RESULT_FILE,
        proj=proj,
        components=components,
    )


# =========================
# Script entry point
# =========================
if __name__ == "__main__":
    """
    Entry point of the script.

    By default, runs the full RLC parameter sweep.
    Uncomment run_single_test() for quick validation or debugging.
    """
    run_parameter_sweep()
    # run_single_test()  # Optional: quick test run