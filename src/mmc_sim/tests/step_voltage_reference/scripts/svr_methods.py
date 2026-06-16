import math
from pathlib import Path
from src.mmc_sim.core.config import Config

TEST_STEP_UP = "u_ref_step_up"
TEST_STEP_DOWN = "u_ref_step_down"


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


def configure_ac_grid(project, component_id: str, scr: float, xr: float, mva: float, fn: float):
    lg, rg = apply_scr_and_xr(scr=scr, xr=xr, sn=mva, fn=fn)

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
        "mmc_id": cfg.get(sim_cfg, "components", "mmc_id"),
        "ac_grid_id": cfg.get(sim_cfg, "components", "ac_grid_id"),
    }
