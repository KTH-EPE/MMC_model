import math
from pathlib import Path
from src.mmc_sim.core.config import Config

TEST_STEP_UP = "p_ref_step_up"
TEST_STEP_DOWN = "p_ref_step_down"


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


def configure_rate_limiter(project, component_id: str, ramp_rate: float):
    limiter = project.component(component_id)

    params = {
        "IR": f"{ramp_rate} [1/s]",
        "DR": f"{ramp_rate} [1/s]",
    }

    limiter.parameters(**params)


def configure_ac_grid(project, component_id: str, scr: float, xr: float, mva: float, fn: float):
    lg, rg = apply_scr_and_xr(scr=scr, xr=xr, sn=mva, fn=fn)

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

    power_cfg = "step_power_ref"

    return {
        "project_path": Path(cfg.get(power_cfg, "model")),
        "project_name": cfg.get(power_cfg, "name"),
        "mva": cfg.get(power_cfg, "mva"),
        "fn": cfg.get(power_cfg, "fn"),
        "output_file": cfg.get(power_cfg, "results", "file_name"),
        "save_path": Path(cfg.get(power_cfg, "results", "save_path")),
        "result_file": Path(
            f"{cfg.get(power_cfg, 'results', 'result_file')}/"
            f"{cfg.get(power_cfg, 'results', 'file_name')}"
        ),
        "initial_power": cfg.get(power_cfg, "initial_power"),
        "final_power": cfg.get(power_cfg, "final_power"),
        "ramp_rate": cfg.get(power_cfg, "ramp_rate"),
        "scr": cfg.get(power_cfg, "SCR"),
        "xr": cfg.get(power_cfg, "XR"),
        "mmc_id": cfg.get(power_cfg, "components", "mmc_id"),
        "rate_limiter_id": cfg.get(power_cfg, "components", "rate_limiter_id"),
        "ac_grid_id": cfg.get(power_cfg, "components", "ac_grid_id"),
    }
