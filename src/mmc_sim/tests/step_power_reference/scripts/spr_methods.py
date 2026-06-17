import math
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


def configure_rate_limiter(project, component_id: str, ramp_rate: float):
    limiter = project.component(component_id)

    params = {
        "IR": f"{ramp_rate} [1/s]",
        "DR": f"{ramp_rate} [1/s]",
    }

    limiter.parameters(**params)


def configure_ac_grid(project, component_id: str, scr: float, xr: float, mva: float, fn: float, u_ac: float):
    lg, rg = apply_scr_and_xr(scr=scr, xr=xr, ac_voltage=u_ac, sn=mva, fn=fn)

    grid = project.component(component_id)
    grid.parameters(Rg=rg, Lg=lg)


def configure_power_references(components, initial_power, final_power):
    for comp in components:
        try:
            name = comp.parameters().get("Name")
        except Exception:
            continue

        if name == "Pref_init":
            comp.parameters(Value=initial_power)

        elif name == "Pref_step":
            comp.parameters(Value=final_power)


def find_dc_components(components):
    required = {
        "R_dc": "R",
        "L_dc": "L",
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

    sim_cfg = "step_power_ref"

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
        "initial_power": cfg.get(sim_cfg, "initial_power"),
        "final_power": cfg.get(sim_cfg, "final_power"),
        "ramp_rate": cfg.get(sim_cfg, "ramp_rate"),
        "scr": cfg.get(sim_cfg, "SCR"),
        "xr": cfg.get(sim_cfg, "XR"),
        "ac_voltage": cfg.get(sim_cfg, "ac_voltage"),
        "mmc_id": cfg.get(sim_cfg, "components", "mmc_id"),
        "rate_limiter_id": cfg.get(sim_cfg, "components", "rate_limiter_id"),
        "ac_grid_id": cfg.get(sim_cfg, "components", "ac_grid_id"),
    }


def single_run(rl_params: Dict[str, float]):
    cfg = load_configuration(CONFIG_FILE)

    model = PSCADModel(
        cfg["project_path"],
        cfg["project_name"],
    )

    project = model.get_project()

    project.component(cfg["mmc_id"]).parameters(idmode="1")

    configure_rate_limiter(
        project,
        cfg["rate_limiter_id"],
        cfg["ramp_rate"],
    )

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

    configure_power_references(
        canvas_components,
        cfg["initial_power"],
        cfg["final_power"]
    )

    dc_grid_components = find_dc_components(canvas_components)
    dc_network = ConfigDCGridComponents(dc_grid_components)
    dc_network.set_dc_network(**rl_params)

    logger.info(f"Running simulation for {rl_params}")

    simulation = Simulation(model)
    result_df = simulation.run(cfg["result_file"])
    new_file_name = format_rl_filename(**rl_params)
    move_result_file(result_df, cfg["save_path"], new_file_name)
    return


def parameter_sweep_run(rl_params: Dict[str, List[float]]):
    cfg = load_configuration(CONFIG_FILE)

    model = PSCADModel(
        cfg["project_path"],
        cfg["project_name"],
    )

    project = model.get_project()

    project.component(cfg["mmc_id"]).parameters(idmode="1")

    configure_rate_limiter(
        project,
        cfg["rate_limiter_id"],
        cfg["ramp_rate"],
    )

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

    configure_power_references(
        canvas_components,
        cfg["initial_power"],
        cfg["final_power"]
    )

    dc_grid_components = find_dc_components(canvas_components)
    dc_grid_parameters = ParameterSweep(rl_params)
    dc_network = ConfigDCGridComponents(dc_grid_components)

    for params in dc_grid_parameters.combinations():
        dc_network.set_dc_network(
            **params
        )

        simulation = Simulation(model)
        logger.info(f"Running simulation for {params}")
        result_df = simulation.run(cfg["result_file"])
        new_file_name = format_rl_filename(**params)
        move_result_file(result_df, cfg["save_path"], new_file_name)
    return
