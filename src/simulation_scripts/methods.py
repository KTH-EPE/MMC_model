import shutil
from pathlib import Path
import itertools
import yaml
import math

import mhi.pscad
from mhi.pscad.utilities.file import OutFile

# =========================
# Load configuration file
# =========================
# Contains system parameters such as SCR, X/R ratio,
# and step magnitudes for voltage reference tests
with open("\\config.yaml") as f:
    cfg = yaml.safe_load(f)

X_R = cfg["ac_grid"]["X_R"]  # Grid X/R ratio
SCR = cfg["ac_grid"]["SCR"]  # Short Circuit Ratio
STEP_UP_VOLTAGE = cfg["voltage_ref_step"]["step_up_voltage"]
STEP_DOWN_VOLTAGE = cfg["voltage_ref_step"]["step_down_voltage"]


# =========================
# File handling utilities
# =========================
def move_result_file(src: Path, dest_dir: Path, new_name: str):
    """
    Move simulation result file to a target directory and rename it.

    Ensures destination directory exists before moving.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / new_name
    shutil.move(str(src), dest_path)


def format_lcr_filename(L, C, R):
    """
    Generate a standardized filename for LCR simulations.

    Inductance is converted to mH for readability.
    """
    return f"step_u_ref_response_L{str(round(L * 1e3, 3))}_C{str(round(C, 3))}_R{str(round(R, 3))}_.csv"


def format_rl_filename(L, R):
    """
    Generate a standardized filename for RL simulations.
    """
    return f"step_u_ref_response_L{int(L * 1e3)}_R{int(R)}_.csv"


# =========================
# Simulation execution
# =========================
def run_lcr_simulation(proj, components, L: float, C: float, R: float, result_file: Path):
    """
    Run a single PSCAD simulation for an RLC DC grid equivalent model.

    Steps:
    1. Update component parameters
    2. Execute simulation
    3. Export results to CSV
    """
    components["L"].parameters(L=L)
    components["C"].parameters(C=C)
    components["R"].parameters(R=R)

    print(f"Running: L={L}, C={C}, R={R}")

    proj.run()

    outfile = OutFile(str(result_file))
    outfile.toCSV()

    return Path(f"{result_file}.csv")


def run_lcr_sensitivity_simulation(proj, components, L: float, C: float, R: float, Lg: float, Rg: float,
                                   result_file: Path):
    """
    Run a single PSCAD simulation for an RLC DC grid equivalent model for sensitivity analysis.

    Steps:
    1. Update component parameters
    2. Execute simulation
    3. Export results to CSV
    """
    components["L"].parameters(L=L)
    components["C"].parameters(C=C)
    components["R"].parameters(R=R)
    components["mmc"].parameters(Lg=Lg)
    components["mmc"].parameters(idmode="0")  # idmode = 0 → DC bus voltage control mode
    components["AC"].parameters(Rg=Rg, Lg=Lg)

    print(f"Running: L={L}, C={C}, R={R}, Rg={Rg}, Lg={Lg}")

    proj.run()

    outfile = OutFile(str(result_file))
    outfile.toCSV()

    return Path(f"{result_file}.csv")


def run_rl_simulation(proj, components, L: float, R: float, result_file: Path):
    """
    Run a single PSCAD simulation for an RL DC grid equivalent model.
    """
    components["L"].parameters(L=L)
    components["R"].parameters(R=R)

    print(f"Running: L={L}, R={R}")

    proj.run()

    outfile = OutFile(str(result_file))
    outfile.toCSV()

    return Path(f"{result_file}.csv")


# =========================
# Parameter sweep routines
# =========================
def run_rlc_parameter_sweep(inductor_values, resistor_values, capacitor_values,
                            output_dir, result_file, proj, components):
    """
    Perform a full parameter sweep over L, R, and C values.

    Uses Cartesian product to explore all combinations.
    Each simulation result is saved with a unique filename.
    """
    for L, R, C in itertools.product(inductor_values, resistor_values, capacitor_values):
        try:
            csv_file = run_lcr_simulation(proj, components, L, C, R, result_file)

            new_name = format_lcr_filename(L, C, R)
            move_result_file(csv_file, output_dir, new_name)

        except Exception as e:
            print(f"Failed for L={L}, C={C}, R={R}: {e}")


def run_rlc_sensitivity_parameter_sweep(input_sample_data, output_dir, result_file, proj, components):
    """
    Perform a full parameter sweep over L, R, and C values for sensitivity analysis.
    Each simulation result is saved with a unique filename.
    """
    for indx, row in input_sample_data.iterrows():
        L = round(row["L"] * 1E-3, 6)  # Convert to H
        R = row["R"]
        C = row["C"]
        Rg = row["Rg"]
        Lg = row["Lg"]
        try:
            csv_file = run_lcr_sensitivity_simulation(proj=proj, components=components, L=L, C=C, R=R, Rg=Rg, Lg=Lg,
                                                      result_file=result_file)
            new_name = format_lcr_filename(L=L, C=C, R=R)
            move_result_file(csv_file, output_dir, new_name)

        except Exception as e:
            print(f"Failed for L={L}, C={C}, R={R}: {e}")


def run_rl_parameter_sweep(inductor_values, resistor_values,
                           output_dir, result_file, proj, components):
    """
    Perform parameter sweep over L and R values.
    """
    for L, R in itertools.product(inductor_values, resistor_values):
        try:
            csv_file = run_rl_simulation(proj, components, L, R, result_file)

            new_name = format_rl_filename(L, R)
            move_result_file(csv_file, output_dir, new_name)

        except Exception as e:
            print(f"Failed for L={L}, R={R}: {e}")


# =========================
# PSCAD model connection
# =========================
def connect_step_voltage_ref_model(proj_path: Path, proj_name: str, test: str,
                                   output_file_name: str, ref_power: float):
    """
    Connect to a PSCAD project configured for voltage reference step tests
    under DC voltage control mode.

    This function:
    - Loads the PSCAD project
    - Configures the MMC in DC voltage control mode
    - Applies grid conditions based on SCR and X/R ratio
    - Sets the voltage reference step input
    - Sets the initial active power reference
    - Extracts required DC-side components (R, L, C)

    Parameters:
        proj_path        : Path to PSCAD project file
        proj_name        : Name of the project inside PSCAD
        test             : Type of voltage step ("u_ref_step_up" or "u_ref_step_down")
        output_file_name : Name for PSCAD output file
        ref_power        : Initial steady-state active power reference

    Returns:
        proj        : Configured PSCAD project object
        components  : Dictionary containing R, L, and C component handles
    """

    # Initialize PSCAD application and load the project
    app = mhi.pscad.application()
    app.settings(fortran_version="GFortran 4.6.2")  # Ensure compatible compiler
    app.load(str(proj_path))

    # Access and focus on the specified project
    proj = app.project(proj_name)
    proj.focus()

    # Configure MMC control mode
    # idmode = 0 → DC bus voltage control mode
    mmc = proj.component(171519397)
    mmc.parameters(idmode="0")

    # Compute equivalent grid impedance from SCR and X/R ratio
    lg, rg = apply_scr_and_xr(scr=SCR, xr=X_R)

    mmc.parameters(Lg=lg)

    # Apply grid impedance to AC grid component
    ac_grid = proj.component(13902648)
    ac_grid.parameters(Rg=rg, Lg=lg)

    # Define output file for simulation results
    proj.parameters(output_filename=f"{output_file_name}.out")

    # Access main simulation canvas
    canvas = proj.canvas("Main")

    # Mapping between PSCAD component names and internal keys
    required = {"R_dc": "R", "L_dc": "L", "C_dc": "C"}
    components = {}

    # Iterate through all components in the model
    for comp in canvas.components():
        try:
            name = comp.parameters().get("Name")  # Retrieve component name
        except Exception:
            continue  # Skip components without accessible parameters

        # Store required DC-side components
        if name in required:
            components[required[name]] = comp

        # Configure voltage reference step input
        elif name == "UC0_step":
            configure_volt_ref_step_response_test(test, comp)

        # Set initial (pre-disturbance) active power reference
        elif name == "Pref0":
            comp.parameters(Value=ref_power)

    # Validate that all required components were found
    missing = set(required.values()) - set(components.keys())
    if missing:
        raise ValueError(f"Missing components in PSCAD model: {missing}")

    return proj, components


def connect_step_voltage_ref_sensitivity_analysis_model(proj_path: Path, proj_name: str, test: str,
                                                        output_file_name: str, ref_power: float):
    """
    Connect to a PSCAD project configured for voltage reference step tests
    under DC voltage control mode.

    This function:
    - Loads the PSCAD project
    - Configures the MMC in DC voltage control mode
    - Applies grid conditions based on SCR and X/R ratio
    - Sets the voltage reference step input
    - Sets the initial active power reference
    - Extracts required DC-side components (R, L, C)

    Parameters:
        proj_path        : Path to PSCAD project file
        proj_name        : Name of the project inside PSCAD
        test             : Type of voltage step ("u_ref_step_up" or "u_ref_step_down")
        output_file_name : Name for PSCAD output file
        ref_power        : Initial steady-state active power reference

    Returns:
        proj        : Configured PSCAD project object
        components  : Dictionary containing R, L, and C component handles
    """

    # Initialize PSCAD application and load the project
    app = mhi.pscad.application()
    app.settings(fortran_version="GFortran 4.6.2")  # Ensure compatible compiler
    app.load(str(proj_path))

    # Access and focus on the specified project
    proj = app.project(proj_name)
    proj.focus()

    # Define output file for simulation results
    proj.parameters(output_filename=f"{output_file_name}.out")

    # Access main simulation canvas
    canvas = proj.canvas("Main")

    # Mapping between PSCAD component names and internal keys
    required = {"R_dc": "R", "L_dc": "L", "C_dc": "C", "AC_Grid": "AC", "ALA MMC": "mmc"}
    components = {}

    # Iterate through all components in the model
    for comp in canvas.components():
        try:
            name = comp.parameters().get("Name")  # Retrieve component name
        except Exception:
            continue  # Skip components without accessible parameters

        # Store required DC-side components
        if name in required:
            components[required[name]] = comp

        # Configure voltage reference step input
        elif name == "UC0_step":
            configure_volt_ref_step_response_test(test, comp)

        # Set initial (pre-disturbance) active power reference
        elif name == "Pref0":
            comp.parameters(Value=ref_power)

    # Validate that all required components were found
    missing = set(required.values()) - set(components.keys())
    if missing:
        raise ValueError(f"Missing components in PSCAD model: {missing}")

    return proj, components


def connect_step_power_disturbance_model(proj_path: Path, proj_name: str, output_file_name: str, ref_power: float,
                                         step_P: float):
    """
    Connect to a PSCAD project configured for active power disturbance tests
    under DC voltage control mode.

    This function:
    - Loads the PSCAD project
    - Configures the MMC in DC voltage control mode
    - Applies grid conditions based on SCR and X/R ratio
    - Introduces an active power disturbance (step-up or step-down)
    - Extracts required DC-side components (R, L, C)

    Parameters:
        proj_path        : Path to PSCAD project file
        proj_name        : Name of the project inside PSCAD
        test             : Type of disturbance ("p_step_up" or "p_step_down")
        output_file_name : Name for PSCAD output file
        ref_power        : Initial steady-state active power reference
        step_P           : Power value after step disturbance

    Returns:
        proj        : Configured PSCAD project object
        components  : Dictionary containing R, L, and C component handles
    """

    # Initialize PSCAD application and load the project
    app = mhi.pscad.application()
    app.settings(fortran_version="GFortran 4.6.2")  # Ensure compatible compiler
    app.load(str(proj_path))

    # Access and focus on the specified project
    proj = app.project(proj_name)
    proj.focus()

    # Configure MMC control mode
    # idmode = 0 → DC bus voltage control mode
    mmc = proj.component(1155983973)
    mmc.parameters(idmode="0")

    # Compute equivalent grid impedance from SCR and X/R ratio
    lg, rg = apply_scr_and_xr(scr=SCR, xr=X_R)

    mmc.parameters(Lg=lg)

    # Apply grid impedance to AC grid component
    ac_grid = proj.component(609475367)
    ac_grid.parameters(Rg=rg, Lg=lg)

    # Define output file for simulation results
    proj.parameters(output_filename=f"{output_file_name}.out")

    # Access main simulation canvas
    canvas = proj.canvas("Main")

    # Mapping between PSCAD component names and internal keys
    # Full RLC equivalent is required for DC grid representation
    required = {"R_dc": "R", "L_dc": "L", "C_dc": "C"}

    components = {}

    # Iterate through all components in the model
    for comp in canvas.components():
        try:
            name = comp.parameters().get("Name")  # Retrieve component name
        except Exception:
            continue  # Skip components without accessible parameters

        # Store required DC-side components
        if name in required:
            components[required[name]] = comp

        # Set initial (pre-disturbance) active power reference
        elif name == "Pref0":
            comp.parameters(Value=ref_power)

        # Apply active power disturbance (step input)
        elif name == "Pref_new":
            comp.parameters(Value=step_P)

    # Validate that all required components were found
    found = set(components.keys())
    expected = set(required.values())
    missing = expected - found

    if missing:
        raise ValueError(f"Missing components in PSCAD model: {missing}")

    return proj, components


def connect_step_voltage_disturbance_model(proj_path: Path, proj_name: str, test: str,
                                           output_file_name: str, ref_power: float,
                                           power_step: float,
                                           step_up_u: float, step_down_u: float):
    """
    Connect to a PSCAD project configured for voltage disturbance tests
    under voltage droop control.

    This function:
    - Loads the PSCAD project
    - Configures the MMC in voltage droop control mode
    - Applies grid conditions based on SCR and X/R ratio
    - Sets both power and voltage disturbances
    - Extracts required DC-side components (R, L)

    Parameters:
        proj_path        : Path to PSCAD project file
        proj_name        : Name of the project inside PSCAD
        test             : Type of voltage test ("u_step_up" or "u_step_down")
        output_file_name : Name for PSCAD output file
        ref_power        : Initial steady-state active power reference
        power_step       : Power disturbance applied during the test
        step_up_u        : Voltage reference after step-up event
        step_down_u      : Voltage reference after step-down event

    Returns:
        proj        : Configured PSCAD project object
        components  : Dictionary containing R and L component handles
    """

    # Initialize PSCAD application and load the project
    app = mhi.pscad.application()
    app.settings(fortran_version="GFortran 4.6.2")  # Ensure compatible compiler
    app.load(str(proj_path))

    # Access and focus on the specified project
    proj = app.project(proj_name)
    proj.focus()

    # Configure MMC control mode
    # idmode = 2 → Voltage droop control mode
    mmc = proj.component(1004889451)
    mmc.parameters(idmode="2")

    # Compute equivalent grid impedance from SCR and X/R ratio
    lg, rg = apply_scr_and_xr(scr=SCR, xr=X_R)

    mmc.parameters(Lg=lg)

    # Apply grid impedance to AC grid component
    ac_grid = proj.component(1350091687)
    ac_grid.parameters(Rg=rg, Lg=lg)

    # Define output file for simulation results
    proj.parameters(output_filename=f"{output_file_name}.out")

    # Access main simulation canvas
    canvas = proj.canvas("Main")

    # Mapping between PSCAD component names and internal keys
    # Only R and L are required (no DC capacitor in this setup)
    required = {"R_dc": "R", "L_dc": "L"}

    components = {}

    # Iterate through all components in the model
    for comp in canvas.components():
        try:
            name = comp.parameters().get("Name")  # Retrieve component name
        except Exception:
            continue  # Skip components that do not expose parameters

        # Store required DC-side components
        if name in required:
            components[required[name]] = comp

        # Apply active power disturbance
        elif name == "Pref_new":
            comp.parameters(Value=power_step)

        # Set initial (pre-disturbance) power reference
        elif name == "Pref0":
            comp.parameters(Value=ref_power)

        # Configure voltage reference disturbance
        elif name == "uref_new":
            if test == "u_step_up":
                comp.parameters(Value=step_up_u)
            else:
                comp.parameters(Value=step_down_u)

    # Validate that all required components were found
    found = set(components.keys())
    expected = set(required.values())
    missing = expected - found

    if missing:
        raise ValueError(f"Missing components in PSCAD model: {missing}")

    return proj, components


def connect_step_power_ref_model(proj_path: Path, proj_name: str, test: str,
                                 output_file_name: str, ref_power: float,
                                 step_up_P: float, step_down_P: float, ramp_rate: float):
    """
    Connect to a PSCAD project configured for active power reference step tests.

    This function:
    - Loads the PSCAD project
    - Configures the MMC in active power control mode
    - Applies grid conditions based on SCR and X/R ratio
    - Sets up power reference step inputs (step-up or step-down)
    - Extracts required DC-side components (R, L)

    Parameters:
        proj_path        : Path to PSCAD project file
        proj_name        : Name of the project inside PSCAD
        test             : Type of test ("p_ref_step_up" or "p_ref_step_down")
        output_file_name : Name for PSCAD output file
        ref_power        : Initial steady-state active power reference
        step_up_P        : Power reference after step-up event
        step_down_P      : Power reference after step-down event

    Returns:
        proj        : Configured PSCAD project object
        components  : Dictionary containing R and L component handles
        :param step_down_P:
        :param ref_power:
        :param output_file_name:
        :param test:
        :param proj_name:
        :param proj_path:
        :param step_up_P:
        :param ramp_rate: Ramp rate of power
    """

    # Initialize PSCAD application and load project
    app = mhi.pscad.application()
    app.settings(fortran_version="GFortran 4.6.2")  # Required compiler version
    app.load(str(proj_path))

    # Access and focus on the specified project
    proj = app.project(proj_name)
    proj.focus()

    # Configure MMC control mode
    # idmode = 1 → Active power control mode
    mmc = proj.component(1382517697)
    mmc.parameters(idmode="1")

    # Set power ramp rate (MW/s)
    ratelimit = proj.component(150450347)
    ratelimit.parameters(IR=f"{ramp_rate} [1/s]", )
    ratelimit.parameters(DR=f"{ramp_rate} [1/s]", )

    # Compute grid equivalent impedance from SCR and X/R ratio
    lg, rg = apply_scr_and_xr(scr=SCR, xr=X_R)

    mmc.parameters(Lg=lg)

    # Apply grid impedance to AC grid component
    ac_grid = proj.component(2126013019)
    ac_grid.parameters(Rg=rg, Lg=lg)

    # Set output file name for simulation results
    proj.parameters(output_filename=f"{output_file_name}.out")

    # Access main canvas where components are placed
    canvas = proj.canvas("Main")

    # Mapping between PSCAD component names and internal keys
    # Only R and L are required for this test (no capacitor)
    required = {"R_dc": "R", "L_dc": "L"}

    components = {}

    # Iterate through all components in the canvas
    for comp in canvas.components():
        try:
            name = comp.parameters().get("Name")  # Retrieve component name
        except Exception:
            continue  # Skip components without accessible parameters

        # Store required DC-side components
        if name in required:
            components[required[name]] = comp

        # Configure new power reference (step input)
        elif name == "Pref_new":
            if test == "p_ref_step_up":
                comp.parameters(Value=step_up_P)
            elif test == "p_ref_step_down":
                comp.parameters(Value=step_down_P)
            else:
                raise Exception("Unknown test")

        # Set initial (pre-disturbance) power reference
        elif name == "Pref0":
            comp.parameters(Value=ref_power)

    # Validate that all required components were found
    found = set(components.keys())
    expected = set(required.values())
    missing = expected - found

    if missing:
        raise ValueError(f"Missing components in PSCAD model: {missing}")

    return proj, components


# =========================
# Step configuration helpers
# =========================
def configure_volt_ref_step_response_test(test: str, component,
                                          step_up: float = STEP_UP_VOLTAGE,
                                          step_down: float = STEP_DOWN_VOLTAGE):
    """
    Configure voltage reference step input based on test type.
    """
    if test == "u_ref_step_up":
        component.parameters(Value=step_up)
    elif test == "u_ref_step_down":
        component.parameters(Value=step_down)


# =========================
# Grid parameter calculation
# =========================
def apply_scr_and_xr(scr: float, xr: float,
                     sn: float = 1200., fn: float = 50.) -> (float, float):
    """
    Compute equivalent grid inductance (Lg) and resistance (Rg)
    from Short Circuit Ratio (SCR) and X/R ratio.

    Assumes:
    - Base voltage = 400 kV
    - Nominal power = sn (MVA)
    - Frequency = fn (Hz)
    """
    lg = 400 ** 2 / (scr * sn * 2 * fn * math.pi)
    rg = 400 ** 2 / (scr * sn * xr)
    return lg, rg
