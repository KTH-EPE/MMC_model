from methods import *

# =========================
# Configuration parameters
# =========================
# Extract experiment settings for the voltage disturbance study
# from the global configuration dictionary (cfg)

PROJECT_PATH = Path(cfg["step_voltage_disturbance"]["path"])              # PSCAD project file path
PROJECT_NAME = cfg["step_voltage_disturbance"]["name"]                    # Project name inside PSCAD
OUTPUT_FILE_NAME = cfg["step_voltage_disturbance"]["output"]["file_name"]  # Base name for PSCAD output file
RESULT_FILE = Path(f'{cfg["step_voltage_disturbance"]["output"]["result_file"]}/{OUTPUT_FILE_NAME}')  # Temporary file
OUTPUT_DIR = Path(cfg["step_voltage_disturbance"]["output"]["directory"])     # Directory for storing processed results

INITIAL_POWER = cfg["step_voltage_disturbance"]["initial_power"]                  # Initial steady-state active power
POWER_STEP = cfg["step_voltage_disturbance"]["step_power"]                # Power disturbance magnitude
STEP_UP_VOLTAGE = cfg["step_voltage_disturbance"]["step_up_voltage"]      # Voltage step-up value
STEP_DOWN_VOLTAGE = cfg["step_voltage_disturbance"]["step_down_voltage"]  # Voltage step-down value

TEST = cfg["step_voltage_disturbance"]["test"]                            # Test type ("u_step_up" or "u_step_down")


# =========================
# Single simulation run
# =========================
def run_single_test():
    """
    Run a single RL simulation for a fixed operating point.
    Uses fixed values:
        L = 0.4 H
        R = 6 Ohm
    """

    # Connect to PSCAD model and configure disturbance scenario
    proj, components = connect_step_voltage_disturbance_model(
        proj_path=PROJECT_PATH,
        proj_name=PROJECT_NAME,
        test=TEST,
        output_file_name=OUTPUT_FILE_NAME,
        ref_power=INITIAL_POWER,
        power_step=POWER_STEP,
        step_up_u=STEP_UP_VOLTAGE,
        step_down_u=STEP_DOWN_VOLTAGE
    )

    # Run simulation for a single RL configuration
    csv_file = run_rl_simulation(
        proj=proj,
        components=components,
        L=0.4,
        R=6,
        result_file=RESULT_FILE
    )

    return csv_file


# =========================
# Parameter space definition
# =========================
def generate_parameter_space():
    """
    Define the parameter space for RL sweep.

    Returns:
        inductors : List of inductance values [H]
        resistors : List of resistance values [Ohm]

    Notes:
    - Inductance is swept from 0.4 H to 0.9 H (step = 0.05 H)
    - Resistance is swept from 6 to 10 Ohm
    """
    inductors = [i * 1e-3 for i in range(400, 801, 50)]  # Convert mH → H
    resistors = list(range(6, 11))                       # Integer Ohmic values

    return inductors, resistors


# =========================
# Parameter sweep execution
# =========================
def run_parameter_sweep():
    """
    Run a full RL parameter sweep for the voltage disturbance scenario.

    Workflow:
    1. Connect to PSCAD model and configure disturbance
    2. Generate parameter combinations
    3. Run simulations for all (L, R) pairs
    4. Save results with structured filenames
    """

    # Step 1: Connect to PSCAD and extract component handles
    proj, components = connect_step_voltage_disturbance_model(
        proj_path=PROJECT_PATH,
        proj_name=PROJECT_NAME,
        test=TEST,
        output_file_name=OUTPUT_FILE_NAME,
        ref_power=INITIAL_POWER,
        power_step=POWER_STEP,
        step_up_u=STEP_UP_VOLTAGE,
        step_down_u=STEP_DOWN_VOLTAGE
    )

    # Step 2: Generate sweep values
    L_vals, R_vals = generate_parameter_space()

    # Step 3: Execute parameter sweep
    run_rl_parameter_sweep(
        inductor_values=L_vals,
        resistor_values=R_vals,
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

    By default, runs the full parameter sweep.
    Uncomment run_single_test() for quick validation runs.
    """
    run_parameter_sweep()
    # run_single_test()  # Useful for debugging