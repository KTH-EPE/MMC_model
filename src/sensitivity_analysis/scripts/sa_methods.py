import yaml
import chaospy as cp
from sklearn.metrics import r2_score
from SALib.sample.latin import sample

from src.mmc_sim.tests.step_voltage_reference.scripts.svr_methods import *
from src.mmc_sim.core.logger import setup_logger

CONFIG_FILE = Path(".\\SA_config.yaml")

emt_sim_logger = setup_logger(
    "simulation"
)

pce_logger = setup_logger("pce_analysis")


def load_config_file(config_file: Path):
    """
    Load YAML configuration file.
    """
    with open(config_file) as file:
        return yaml.safe_load(file)


# Problem definition
def define_sampling_problem():
    """
    Define uncertain parameters for sensitivity analysis.
    Returns
    -------
    dict
        SALib problem definition.
    """
    return {"num_vars": 5,
            "names": ["L", "C", "R", "SCR", "XR"],
            "bounds": [
                [400.0, 800.0],  # L [mH]
                [800.0, 2100.0],  # C [uF]
                [6.0, 10.0],  # R [Ohm]
                [5.0, 15.0],  # SCR
                [5.0, 20.0]  # X/R ratio
            ]
            }


# Grid parameter calculation
def calculate_grid_parameters(dataframe: pd.DataFrame, nominal_power: float = 1200,
                              voltage: float = 400, frequency: float = 50):
    """
    Calculate equivalent grid impedance.
    Parameters
    ----------
    dataframe:
        Sample dataframe containing SCR and XR.
    Returns
    -------
    DataFrame
        Updated dataframe with Lg and Rg.
    """
    dataframe["Lg"] = (voltage ** 2 / (dataframe["SCR"] * nominal_power * 2 * math.pi * frequency))
    dataframe["Rg"] = (voltage ** 2 / (dataframe["SCR"] * nominal_power * dataframe["XR"]))
    return dataframe


# Sample generation
def generate_samples(number_of_samples: int, random_seed: int = None):
    """
    Generate Latin Hypercube samples.

    Parameters
    ----------
    number_of_samples:
        Number of samples.

    random_seed:
        Reproducibility seed.

    Returns
    -------
    DataFrame
    """

    problem = define_sampling_problem()
    pce_logger.info(f"Generating {number_of_samples} samples")
    samples = sample(problem, number_of_samples, seed=random_seed)
    dataframe = pd.DataFrame(samples, columns=problem["names"])
    dataframe = calculate_grid_parameters(dataframe)
    return dataframe


# Save samples
def save_samples(dataframe: pd.DataFrame, output_directory: Path, filename="sample_data.csv"):
    """
    Save generated samples.
    """

    output_directory.mkdir(parents=True, exist_ok=True)
    output_file = (output_directory / filename)
    dataframe.round(3).to_csv(output_file, index=False)
    return output_file


def load_dataset(sample_file: Path, result_file: Path):
    """
    Load and merge simulation input/output data.

    Parameters
    ----------
    sample_file:
        Generated sensitivity samples.

    result_file:
        PSCAD response summary.

    Returns
    -------
    DataFrame
        Prepared input-output dataset.
    """
    pce_logger.info("Loading sample and simulation data")
    samples = pd.read_csv(sample_file)
    results = pd.read_csv(result_file)

    # Select required simulation outputs
    results = results[["H_mH", "C_uF", "R_ohms", "Xm", "Tcr", "Tcs"]]
    dataset = samples.merge(
        results,
        left_on=["L", "C", "R"],
        right_on=["H_mH", "C_uF", "R_ohms"],
        how="inner"
    )
    dataset.drop(columns=["H_mH", "C_uF", "R_ohms"], inplace=True)

    # Convert mH to H
    dataset["L"] /= 1000
    pce_logger.info(f"Dataset size: {dataset.shape}")
    return dataset


# Polynomial Chaos Model
def create_distribution():
    """
    Define uncertain parameter distributions.
    """
    return cp.J(
        cp.Uniform(0.4, 0.8),  # L
        cp.Uniform(800, 2100),  # C
        cp.Uniform(6, 10),  # R
        cp.Uniform(5, 15),  # SCR
        cp.Uniform(5, 20)  # XR
    )


def train_pce(X_train, Y_train, order, distribution):
    """
    Train polynomial chaos expansion surrogate.
    """
    pce_logger.info(f"Training PCE order={order}")
    expansion = cp.generate_expansion(order, distribution)
    model = cp.fit_regression(expansion, X_train.T, Y_train)
    return model


# Validation
def evaluate_model(model, X_train, X_test, Y_train, Y_test):
    """
    Evaluate surrogate model accuracy.
    """
    Y_train_pred = model(*X_train.T)
    Y_test_pred = model(*X_test.T)
    metrics = {
        "r2_train": r2_score(Y_train, Y_train_pred),
        "r2_test":
            r2_score(Y_test, Y_test_pred),
        "relative_l2_error": np.linalg.norm(Y_test - Y_test_pred) / np.linalg.norm(Y_test)
    }
    return metrics


# Sobol sensitivity
def calculate_sobol_indices(model, distribution):
    """
    Calculate Sobol sensitivity indices.
    """
    pce_logger.info("Calculating Sobol indices")
    return {
        "first_order": cp.Sens_m(model, distribution),
        "second_order": cp.Sens_m2(model, distribution),
        "total": cp.Sens_t(model, distribution)
    }


def sample_data_emt_run(sample_data_path: str, plot_results: bool = False):
    cfg = load_configuration(CONFIG_FILE)

    model = PSCADModel(
        cfg["project_path"],
        cfg["project_name"],
    )

    project = model.get_project()

    project.component(cfg["mmc_id"]).parameters(idmode="0")
    project.parameters(time_step=cfg["time_step"])
    project.parameters(time_duration=cfg["time_duration"])
    project.parameters(sample_step=cfg["sample_step"])

    configure_ac_grid(
        project,
        cfg["ac_grid_id"],
        cfg["scr"],
        cfg["xr"],
        cfg["mva"],
        cfg["fn"],
        cfg["ac_voltage"],
    )

    model.set_output(cfg["output_file"])

    canvas_components = model.canvas_components()

    set_power_and_voltage_values(
        canvas_components,
        cfg["ref_power"],
        cfg["uref"],
        cfg["u_step"],
        cfg["step_time"]
    )

    dc_grid_components = find_dc_components(canvas_components)
    dc_network = ConfigDCGridComponents(dc_grid_components)
    sample_data_df = pd.read_csv(sample_data_path)
    for _, row in sample_data_df.iterrows():
        dc_grid_params = {"R": row["R"], "L": round(row["L"] / 1000, 6), "C": row["C"]}  # inductance in H
        dc_network.set_dc_network(
            **dc_grid_params
        )

        simulation = Simulation(model)

        emt_sim_logger.info(f"Running simulation for {dc_grid_params}")

        result_df = simulation.run(cfg["result_file"])
        new_file_name = format_rlc_filename(**dc_grid_params, file_name=cfg["output_file"])
        move_result_file(result_df, cfg["save_path"] / "sim_timeseries", new_file_name)
        if cfg["u_step"] > cfg["uref"]:
            result_summary = analyse_step_up_voltage_signal_for_sa(cfg["save_path"] / "sim_timeseries" / new_file_name,
                                                                   step_time=cfg["step_time"],
                                                                   voltage_reference=cfg["uref"])
            file_path = cfg["save_path"] / "sim_summary" / new_file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            result_summary.to_csv(file_path)
            if plot_results:
                plot_step_up_voltage_signal(cfg["save_path"] / "sim_timeseries" / new_file_name,
                                            step_time=cfg["step_time"], voltage_reference=cfg["uref"])
        elif cfg["u_step"] < cfg["uref"]:
            result_summary = analyse_step_down_voltage_signal(cfg["save_path"] / "sim_timeseries" / new_file_name,
                                                              step_time=cfg["step_time"], voltage_reference=cfg["uref"])
            file_path = cfg["save_path"] / "sim_summary" / new_file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            result_summary.to_csv(file_path, index=False)
            if plot_results:
                plot_step_down_voltage_signal(cfg["save_path"] / "sim_timeseries" / new_file_name,
                                              step_time=cfg["step_time"], voltage_reference=cfg["uref"])
    return


def analyse_step_up_voltage_signal_for_sa(
        file_path,
        step_time,
        time_col="TIME",
        signal_col="Vdc",
        step_pu=0.02,
        tol_factor=0.05,
        voltage_reference=640.,
        settling_window=200  # default window for smoothing
):
    """
    Analyze a signal from a CSV file.
    Settling time is calculated using a smoothed version of the signal.
    The settling time is calculated with a smaller than specified in InterOPERA tolerance to improve accuracy of
    sensitivity analysis.
    """
    # -----------------------------
    # LOAD DATA
    # -----------------------------
    df = pd.read_csv(file_path)
    steady_state_point = df.index.get_loc(df.index[df['TIME'] >= (step_time - 0.1)][0])
    df = df.iloc[steady_state_point:, :]
    df["R_ohms"] = float(str(file_path).split("\\")[-1].split("_")[-2][1:])  # Creating a column for the resistance.
    df["H_mH"] = float(str(file_path).split("\\")[-1].split("_")[-4][1:])
    df["C_uF"] = float(str(file_path).split("\\")[-1].split("_")[-3][1:])
    t = df[time_col].values
    y = df[signal_col].values

    # -----------------------------
    # TOLERANCE BAND
    # -----------------------------
    target = (1. + step_pu) * voltage_reference
    band_percent = 0.02 * voltage_reference
    tol = tol_factor * band_percent
    lower = target - tol
    upper = target + tol

    # Boolean array for raw signal
    within_band = (y >= lower) & (y <= upper)

    # -----------------------------
    # PEAK
    # -----------------------------
    peak_idx = np.argmax(y)
    peak_value = y[peak_idx]
    peak_time = t[peak_idx]

    # -----------------------------
    # FIRST ENTRY
    # -----------------------------
    first_entry_idx = None
    for i in range(len(y)):
        if within_band[i]:
            first_entry_idx = i
            break
    first_entry_time = t[first_entry_idx] if first_entry_idx is not None else None

    # -----------------------------
    # SETTLING TIME USING SMOOTH SIGNAL
    # -----------------------------
    lower = target - tol * 0.5   # Reducing the tolerance improves the sensitivity analysis
    upper = target + tol * 0.5
    y_smooth = smooth_signal(y, window_size=settling_window)
    within_band_smooth = (y_smooth >= lower) & (y_smooth <= upper)

    settling_idx = None
    for i in range(len(y_smooth)):
        if within_band_smooth[i] and np.all(within_band_smooth[i:]):
            settling_idx = i
            break

    settling_time = t[settling_idx] if settling_idx is not None else None

    # -----------------------------
    # RETURN RESULTS
    # -----------------------------
    result_df = df.iloc[-1:].copy()
    result_df["Tcr"] = round(first_entry_time - step_time, 3)
    result_df["Tcs"] = round(settling_time - step_time, 3)
    result_df["Xm"] = round(peak_value - target, 2)
    result_df["Vdc_ss"] = round(df[signal_col][-10:].mean(), 2)
    result_df = result_df.drop(columns=["TIME", "Vdc"])
    result_df.reset_index(drop=True, inplace=True)

    return result_df
