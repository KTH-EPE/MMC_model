from methods import *

# =========================
# Load configuration file
# =========================
# Read experiment parameters for the voltage reference step study

with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

# Extract configuration for the voltage reference step experiment
PROJECT_PATH = Path(cfg["voltage_ref_step"]["path"])              # PSCAD project file path
PROJECT_NAME = cfg["voltage_ref_step"]["name"]                    # Project name inside PSCAD
OUTPUT_FILE_NAME = cfg["voltage_ref_step"]["output"]["file_name"]  # Base name for PSCAD output file
RESULT_FILE = Path(f'{cfg["voltage_ref_step"]["output"]["result_file"]}/{OUTPUT_FILE_NAME}')  # Temporary file
OUTPUT_DIR = Path(cfg["voltage_ref_step"]["output"]["directory"])     # Directory for storing processed results

TEST = cfg["voltage_ref_step"]["test"]                            # Test type ("u_ref_step_up" or "u_ref_step_down")
REF_POWER = cfg["voltage_ref_step"]["ref_power"]                  # Initial steady-state active power


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

    # Connect to PSCAD model and configure voltage reference step test
    proj, components = connect_step_voltage_ref_model(
        proj_path=PROJECT_PATH,
        proj_name=PROJECT_NAME,
        test=TEST,
        output_file_name=OUTPUT_FILE_NAME,
        ref_power=REF_POWER
    )

    # Run simulation for a single RLC configuration
    csv_file = run_lcr_simulation(
        proj=proj,
        components=components,
        L=0.4,
        C=1300,
        R=8,
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

    This parameter space represents variations in the DC-side equivalent
    network influencing voltage control dynamics.
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
    Run a full RLC parameter sweep for the voltage reference step scenario.

    Workflow:
    1. Connect to PSCAD model and configure voltage reference step
    2. Generate parameter combinations (L, R, C)
    3. Run simulations for all combinations
    4. Save results with structured filenames
    """

    # Step 1: Connect to PSCAD and extract component handles
    proj, components = connect_step_voltage_ref_model(
        proj_path=PROJECT_PATH,
        proj_name=PROJECT_NAME,
        test=TEST,
        output_file_name=OUTPUT_FILE_NAME,
        ref_power=REF_POWER
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