import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
from typing import Dict, List

from src.mmc_sim.core.config import Config
from src.mmc_sim.core.pscad import PSCADModel
from src.mmc_sim.core.config_components import ConfigDCGridComponents
from src.mmc_sim.core.simulation import Simulation
from src.mmc_sim.core.parameter_sweep import ParameterSweep
from src.mmc_sim.core.misc import *
from src.mmc_sim.core.logger import setup_logger

CONFIG_FILE = Path("config.yaml")

logger = setup_logger(
    "simulation"
)


def apply_scr_and_xr(scr: float, xr: float, ac_voltage: float = 400.,
                     sn: float = 1200., fn: float = 50.) -> (float, float):
    """
    Compute equivalent grid inductance (Lg) and resistance (Rg)
    from Short Circuit Ratio (SCR) and X/R ratio.

    Assumes:
    - Base voltage = 400 kV
    - Nominal power = sn (MVA)
    - Frequency = fn (Hz)
    """
    lg = ac_voltage ** 2 / (scr * sn * 2 * fn * math.pi)
    rg = ac_voltage ** 2 / (scr * sn * xr)
    return lg, rg


def configure_ac_grid(project, component_id: str, scr: float, xr: float, mva: float, fn: float, u_ac: float):
    lg, rg = apply_scr_and_xr(scr=scr, xr=xr, sn=mva, fn=fn, ac_voltage=u_ac)

    grid = project.component(component_id)
    grid.parameters(Rg=rg, Lg=lg)


def set_power_and_voltage_values(components, ref_power, uref, u_step, step_time):
    for comp in components:
        try:
            name = comp.parameters().get("Name")
        except Exception:
            continue

        if name == "Pref":
            comp.parameters(Value=ref_power)
        elif name == "uref":
            comp.parameters(Value=uref)
        elif name == "u_step":
            comp.parameters(Value=u_step)
        elif name == "step_obj":
            comp.parameters(X=step_time)


def find_dc_components(components):
    required = {
        "R_dc": "R",
        "L_dc": "L",
        "C_dc": "C",
    }

    dc_components = {}

    for comp in components:
        try:
            name = comp.parameters().get("Name")
        except Exception:
            continue

        if name in required:
            dc_components[required[name]] = comp

    missing = set(required.values()) - set(dc_components)

    if missing:
        raise ValueError(
            f"Missing DC components in PSCAD model: {sorted(missing)}"
        )

    return dc_components


def load_configuration(config_file):
    cfg = Config(config_file)

    sim_cfg = "step_voltage_ref"

    return {
        "project_path": Path(cfg.get(sim_cfg, "model")),
        "project_name": cfg.get(sim_cfg, "name"),
        "mva": cfg.get(sim_cfg, "mva"),
        "fn": cfg.get(sim_cfg, "fn"),
        "step_time": cfg.get(sim_cfg, "step_time"),
        "sample_step": cfg.get(sim_cfg, "sample_step"),
        "time_step": cfg.get(sim_cfg, "time_step"),
        "time_duration": cfg.get(sim_cfg, "time_duration"),
        "output_file": cfg.get(sim_cfg, "results", "file_name"),
        "save_path": Path(cfg.get(sim_cfg, "results", "save_path")),
        "result_file": Path(
            f"{cfg.get(sim_cfg, 'results', 'result_file')}/"
            f"{cfg.get(sim_cfg, 'results', 'file_name')}"
        ),
        "ref_power": cfg.get(sim_cfg, "ref_power"),
        "uref": cfg.get(sim_cfg, "reference_voltage"),
        "u_step": cfg.get(sim_cfg, "step_voltage"),
        "scr": cfg.get(sim_cfg, "SCR"),
        "xr": cfg.get(sim_cfg, "XR"),
        "ac_voltage": cfg.get(sim_cfg, "ac_voltage"),
        "mmc_id": cfg.get(sim_cfg, "components", "mmc_id"),
        "ac_grid_id": cfg.get(sim_cfg, "components", "ac_grid_id"),
    }


def single_run(rlc_params: Dict[str, float], plot_results: bool = True):
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
    dc_network.set_dc_network(**rlc_params)
    logger.info(f"Running simulation for {rlc_params}")
    simulation = Simulation(model)
    result_df = simulation.run(cfg["result_file"])
    new_file_name = format_rlc_filename(**rlc_params, file_name=cfg["output_file"])
    move_result_file(result_df, cfg["save_path"] / "sim_timeseries", new_file_name)
    if cfg["u_step"] > cfg["uref"]:
        result_summary = analyse_step_up_voltage_signal(cfg["save_path"] / "sim_timeseries" / new_file_name,
                                                        step_time=cfg["step_time"], voltage_reference=cfg["uref"])
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
        result_summary.to_csv(file_path)
        if plot_results:
            plot_step_down_voltage_signal(cfg["save_path"] / "sim_timeseries" / new_file_name,
                                          step_time=cfg["step_time"], voltage_reference=cfg["uref"])
    return


def parameter_sweep_run(rlc_params: Dict[str, List[float]], plot_results: bool = True):
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

    dc_grid_parameters = ParameterSweep(rlc_params)

    dc_network = ConfigDCGridComponents(dc_grid_components)
    for params in dc_grid_parameters.combinations():
        dc_network.set_dc_network(
            **params
        )

        simulation = Simulation(model)
        logger.info(f"Running simulation for {params}")
        result_df = simulation.run(cfg["result_file"])
        new_file_name = format_rlc_filename(**params, file_name=cfg["output_file"])
        move_result_file(result_df, cfg["save_path"] / "sim_timeseries", new_file_name)
        if cfg["u_step"] > cfg["uref"]:
            result_summary = analyse_step_up_voltage_signal(cfg["save_path"] / "sim_timeseries" / new_file_name,
                                                            step_time=cfg["step_time"], voltage_reference=cfg["uref"])
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


def analyse_step_up_voltage_signal(
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


def smooth_signal(y, window_size=50):
    """
    Apply moving average (running average) to smooth signal.

    Parameters:
    - y: input signal (numpy array)
    - window_size: number of samples in averaging window

    Returns:
    - smoothed signal (same length as input)
    """
    return pd.Series(y).rolling(window=window_size, center=True, min_periods=1).mean().values


def plot_step_up_voltage_signal(
        file_path,
        step_time=3,
        time_col="TIME",
        signal_col="Vdc",
        step_pu=0.02,
        voltage_reference=640,
        tol_factor=0.05,
        settling_window=100
):
    # -----------------------------
    # LOAD DATA
    # -----------------------------
    df = pd.read_csv(file_path)
    steady_state_point = df.index.get_loc(df.index[df['TIME'] >= (step_time - 0.5)][0])
    df = df.iloc[steady_state_point:, :]
    t = df[time_col].values
    y = df[signal_col].values

    # -----------------------------
    # TOLERANCE BAND
    # -----------------------------
    target = 1.02 * voltage_reference
    band_percent = step_pu * voltage_reference
    tol = tol_factor * band_percent
    lower = target - tol
    upper = target + tol

    # -----------------------------
    # SMOOTHING (for settling)
    # -----------------------------
    y_smooth = pd.Series(y).rolling(window=settling_window, center=True, min_periods=1).mean().values

    within_band = (y >= lower) & (y <= upper)
    within_band_smooth = (y_smooth >= lower) & (y_smooth <= upper)

    # -----------------------------
    # RISE TIME (first entry)
    # -----------------------------
    rise_idx = None
    for i in range(len(y)):
        if within_band[i]:
            rise_idx = i
            break

    rise_time = t[rise_idx] if rise_idx is not None else None

    # -----------------------------
    # PEAK
    # -----------------------------
    peak_idx = np.argmax(y)
    peak_value = y[peak_idx]
    peak_time = t[peak_idx]

    # -----------------------------
    # SETTLING TIME (smoothed)
    # -----------------------------
    settling_idx = None
    for i in range(len(y_smooth)):
        if within_band_smooth[i] and np.all(within_band_smooth[i:]):
            settling_idx = i
            break

    settling_time = t[settling_idx] if settling_idx is not None else None

    # -----------------------------
    # PLOTTING
    # -----------------------------
    plt.figure(figsize=(7, 4))
    ax = plt.gca()

    # Signal
    plt.plot(t, y / voltage_reference, label="Udc", color="blue")

    # Smoothed (optional for visualization)
    plt.plot(t, y_smooth / voltage_reference, linestyle="--", label="Udc average")

    # Target line
    plt.axhline(target / voltage_reference, linestyle="--", color="red", label="Reference")

    # Tolerance band
    plt.axhline(lower / voltage_reference, linestyle=":", color="brown", linewidth=1.5, label="Lower tolerance")
    plt.axhline(upper / voltage_reference, linestyle="-", color="brown", linewidth=1.5, label="Upper tolerance")

    # Rise time marker
    if rise_time is not None:
        plt.scatter(rise_time, y[rise_idx] / voltage_reference, color="indigo")
        plt.annotate(
            "Tcr",
            (rise_time, y[rise_idx] / voltage_reference),
            xytext=(rise_time - 0.01, y[rise_idx] / voltage_reference - 0.008),
            arrowprops=dict(arrowstyle="->")
        )

    # Peak marker
    plt.scatter(peak_time, peak_value / voltage_reference, color="green")
    plt.annotate(
        "Xm",
        (peak_time, peak_value / voltage_reference),
        xytext=(peak_time + 0.005, peak_value / voltage_reference + 0.005),
        arrowprops=dict(arrowstyle="->")
    )

    # Settling time marker
    if settling_time is not None:
        plt.scatter(settling_time, y[settling_idx] / voltage_reference, color="violet")
        plt.annotate(
            "Tcs",
            (settling_time, y[settling_idx] / voltage_reference),
            xytext=(settling_time + 0.01, y[settling_idx] / voltage_reference + 0.007),
            arrowprops=dict(arrowstyle="->")
        )

    # Labels
    plt.xlabel("Time (s)")
    plt.ylabel("Udc [p.u]")
    plt.title("Voltage reference step response")

    plt.legend(loc=4)
    plt.grid()
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    plt.ylim([0.99, 1.03])
    plt.xlim([step_time - 0.2, step_time + 0.5])
    plt.tight_layout()

    fig_path = "\\".join(str(file_path).split("\\")[0:-2]) + "\\sim_figures"
    fig_name = str(file_path).split("\\")[-1][0:-4]
    file_path = Path(f"{fig_path}\\{fig_name}.pdf")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(file_path)


def analyse_step_down_voltage_signal(
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
    Analyze a step-down signal from a CSV file.
    Settling time is calculated using a smoothed version of the signal.
    """
    # -----------------------------
    # LOAD DATA
    # -----------------------------
    df = pd.read_csv(file_path)
    steady_state_point = df.index.get_loc(df.index[df[time_col] >= (step_time - 0.1)][0])
    df = df.iloc[steady_state_point:, :]
    df["R_ohms"] = float(str(file_path).split("\\")[-1].split("_")[-2][1:])
    df["H_mH"] = float(str(file_path).split("\\")[-1].split("_")[-4][1:])
    df["C_uF"] = float(str(file_path).split("\\")[-1].split("_")[-3][1:])

    t = df[time_col].values
    y = df[signal_col].values

    # -----------------------------
    # TOLERANCE BAND
    # -----------------------------
    target = (1. - step_pu) * voltage_reference
    band_percent = 0.02 * voltage_reference
    tol = tol_factor * band_percent
    lower = target - tol
    upper = target + tol

    within_band = (y >= lower) & (y <= upper)

    # -----------------------------
    # MIN VALUE
    # -----------------------------
    min_idx = np.argmin(y)
    min_value = y[min_idx]
    min_time = t[min_idx]

    # -----------------------------
    # TIME TO FALL INTO TOLERANCE BAND
    # -----------------------------
    fall_idx = None
    for i in range(len(y)):
        if within_band[i]:
            fall_idx = i
            break
    fall_time = t[fall_idx] if fall_idx is not None else None

    # -----------------------------
    # SETTLING TIME USING SMOOTH SIGNAL
    # -----------------------------
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
    result_df["Tcr"] = round(fall_time - step_time, 3)
    result_df["Tcs"] = round(settling_time - step_time, 3)
    result_df["Xm"] = round(target - min_value, 2)
    result_df["Vdc_ss"] = round(df[signal_col][-10:].mean(), 2)
    result_df = result_df.drop(columns=["TIME", "Vdc"])
    result_df.reset_index(drop=True, inplace=True)

    return result_df


def plot_step_down_voltage_signal(
        file_path,
        time_col="TIME",
        signal_col="Vdc",
        step_time=3,
        step_pu=0.02,
        voltage_reference=640,
        tol_factor=0.05,
        settling_window=200
):
    # -----------------------------
    # LOAD DATA
    # -----------------------------
    df = pd.read_csv(file_path)
    steady_state_point = df.index.get_loc(df.index[df[time_col] >= (step_time - 0.5)][0])
    df = df.iloc[steady_state_point:, :]
    t = df[time_col].values
    y = df[signal_col].values

    # -----------------------------
    # TOLERANCE BAND
    # -----------------------------
    target = (1. - step_pu) * voltage_reference
    band_percent = step_pu * voltage_reference
    tol = tol_factor * band_percent
    lower = target - tol
    upper = target + tol

    # -----------------------------
    # SMOOTH SIGNAL FOR SETTLING
    # -----------------------------
    y_smooth = smooth_signal(y, window_size=settling_window)
    within_band = (y >= lower) & (y <= upper)
    within_band_smooth = (y_smooth >= lower) & (y_smooth <= upper)

    # -----------------------------
    # TIME TO FALL INTO BAND
    # -----------------------------
    fall_idx = None
    for i in range(len(y)):
        if within_band[i]:
            fall_idx = i
            break
    fall_time = t[fall_idx] if fall_idx is not None else None

    # -----------------------------
    # MIN VALUE
    # -----------------------------
    min_idx = np.argmin(y)
    min_value = y[min_idx]
    min_time = t[min_idx]

    # -----------------------------
    # SETTLING TIME
    # -----------------------------
    settling_idx = None
    for i in range(len(y_smooth)):
        if within_band_smooth[i] and np.all(within_band_smooth[i:]):
            settling_idx = i
            break
    settling_time = t[settling_idx] if settling_idx is not None else None

    # -----------------------------
    # PLOTTING
    # -----------------------------
    plt.figure(figsize=(7, 4))
    ax = plt.gca()
    plt.plot(t, y / voltage_reference, color="blue", label="Udc")
    plt.plot(t, y_smooth / voltage_reference, linestyle="--", label="Udc average")
    plt.axhline(target / voltage_reference, linestyle="--", color="red", linewidth=1.5, label="Reference")
    plt.axhline(lower / voltage_reference, linestyle=":", color="brown", linewidth=1.5, label="Lower tolerance")
    plt.axhline(upper / voltage_reference, linestyle="-", color="brown", linewidth=1.5, label="Upper tolerance")

    if fall_time is not None:
        plt.scatter(fall_time, y[fall_idx] / voltage_reference)
        plt.annotate(
            "Tcr",
            (fall_time, y[fall_idx] / voltage_reference),
            xytext=(fall_time - 0.09, y[fall_idx] / voltage_reference + 0.008),
            arrowprops=dict(arrowstyle="->")
        )

    plt.scatter(min_time, min_value / voltage_reference)
    plt.annotate(
        "Xm",
        (min_time, min_value / voltage_reference),
        xytext=(min_time + 0.005, min_value / voltage_reference + 0.006),
        arrowprops=dict(arrowstyle="->")
    )

    if settling_time is not None:
        plt.scatter(settling_time, y[settling_idx] / voltage_reference)
        plt.annotate(
            "Tcs",
            (settling_time, y[settling_idx] / voltage_reference),
            xytext=(settling_time + 0.01, y[settling_idx] / voltage_reference + 0.007),
            arrowprops=dict(arrowstyle="->")
        )

    plt.xlabel("Time (s)")
    plt.ylabel("Udc [p.u]")
    plt.title("Voltage reference step response")
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
    plt.legend(loc=1)
    plt.ylim([0.97, 1.005])
    plt.xlim([step_time - 0.2, step_time + 0.5])
    plt.grid()

    fig_path = "\\".join(str(file_path).split("\\")[0:-2]) + "\\sim_figures"
    fig_name = str(file_path).split("\\")[-1][0:-4]
    file_path = Path(f"{fig_path}\\{fig_name}.pdf")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(file_path)
