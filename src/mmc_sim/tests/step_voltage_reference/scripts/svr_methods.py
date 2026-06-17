import math
from src.mmc_sim.core.config import Config
from typing import Dict, List
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


def set_power_and_voltage_values(components, ref_power, uref, u_step):
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
        "output_file": cfg.get(sim_cfg, "results", "file_name"),
        "save_path": Path(cfg.get(sim_cfg, "results", "save_path")),
        "result_file": Path(
            f"{cfg.get(sim_cfg, 'results', 'result_file')}/"
            f"{cfg.get(sim_cfg, 'results', 'file_name')}"
        ),
        "ref_power": cfg.get(sim_cfg, "ref_power"),
        "uref": cfg.get(sim_cfg, "voltage_reference"),
        "u_step": cfg.get(sim_cfg, "voltage_step"),
        "scr": cfg.get(sim_cfg, "SCR"),
        "xr": cfg.get(sim_cfg, "XR"),
        "ac_voltage": cfg.get(sim_cfg, "ac_voltage"),
        "mmc_id": cfg.get(sim_cfg, "components", "mmc_id"),
        "ac_grid_id": cfg.get(sim_cfg, "components", "ac_grid_id"),
    }


def single_run(rlc_params: Dict[str, float]):
    cfg = load_configuration(CONFIG_FILE)

    model = PSCADModel(
        cfg["project_path"],
        cfg["project_name"],
    )

    project = model.get_project()

    project.component(cfg["mmc_id"]).parameters(idmode="0")

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
        cfg["u_step"]
    )

    dc_grid_components = find_dc_components(canvas_components)

    dc_network = ConfigDCGridComponents(dc_grid_components)
    dc_grid_params = {"R": 7, "L": 0.4, "C": 1000.}
    dc_network.set_dc_network(**dc_grid_params)
    logger.info(f"Running simulation for {dc_grid_params}")
    simulation = Simulation(model)
    result_df = simulation.run(cfg["result_file"])
    new_file_name = format_rlc_filename(**dc_grid_params)
    move_result_file(result_df, cfg["save_path"], new_file_name)
    return


def parameter_sweep_run(rlc_params: Dict[str, List[float]]):
    cfg = load_configuration(CONFIG_FILE)

    model = PSCADModel(
        cfg["project_path"],
        cfg["project_name"],
    )

    project = model.get_project()

    project.component(cfg["mmc_id"]).parameters(idmode="0")

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
        cfg["u_step"]
    )

    dc_grid_components = find_dc_components(canvas_components)

    dc_grid_parameters = ParameterSweep(
        {
            "R": [6, 8, 10],
            "L": [0.4, 0.5, 0.6],
            "C": [800., 900., 1000.],
        }
    )

    dc_network = ConfigDCGridComponents(dc_grid_components)
    for params in dc_grid_parameters.combinations():
        dc_network.set_dc_network(
            **params
        )

        simulation = Simulation(model)
        logger.info(f"Running simulation for {params}")
        result_df = simulation.run(cfg["result_file"])
        new_file_name = format_rlc_filename(**params)
        move_result_file(result_df, cfg["save_path"], new_file_name)
    return
