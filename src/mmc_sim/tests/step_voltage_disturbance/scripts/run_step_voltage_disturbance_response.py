from src.mmc_sim.core.pscad import PSCADModel
from src.mmc_sim.core.config_components import ConfigDCGridComponents
from src.mmc_sim.core.simulation import Simulation
from src.mmc_sim.core.parameter_sweep import ParameterSweep
from src.mmc_sim.core.misc import *
from svd_methods import *
from src.mmc_sim.core.logger import setup_logger


CONFIG_FILE = Path("config.yaml")

logger = setup_logger(
    "simulation"
)


def single_run():
    cfg = load_configuration(CONFIG_FILE)

    model = PSCADModel(
        cfg["project_path"],
        cfg["project_name"],
    )

    project = model.get_project()

    project.component(cfg["mmc_id"]).parameters(idmode="2")

    configure_ac_grid(
        project,
        cfg["ac_grid_id"],
        cfg["scr"],
        cfg["xr"],
        cfg["mva"],
        cfg["fn"],
    )

    model.set_output(cfg["output_file"])

    canvas_components = model.canvas_components()

    configure_power_and_voltage_values(
        canvas_components,
        cfg["initial_power"],
        cfg["step_power"],
        cfg["uref"],
        cfg["u_step"]
    )

    dc_grid_components = find_dc_components(canvas_components)

    dc_network = ConfigDCGridComponents(dc_grid_components)
    dc_grid_params = {"R": 7, "L": 0.4}
    dc_network.set_dc_network(**dc_grid_params)
    logger.info(f"Running simulation for {dc_grid_params}")
    simulation = Simulation(model)
    result_df = simulation.run(cfg["result_file"])
    new_file_name = format_rl_filename(**dc_grid_params)
    move_result_file(result_df, cfg["save_path"], new_file_name)
    return


def parameter_sweep_run():
    cfg = load_configuration(CONFIG_FILE)

    model = PSCADModel(
        cfg["project_path"],
        cfg["project_name"],
    )

    project = model.get_project()

    project.component(cfg["mmc_id"]).parameters(idmode="2")

    configure_ac_grid(
        project,
        cfg["ac_grid_id"],
        cfg["scr"],
        cfg["xr"],
        cfg["mva"],
        cfg["fn"],
    )

    model.set_output(cfg["output_file"])

    canvas_components = model.canvas_components()

    configure_power_and_voltage_values(
        canvas_components,
        cfg["initial_power"],
        cfg["step_power"],
        cfg["uref"],
        cfg["u_step"]
    )

    dc_grid_components = find_dc_components(canvas_components)

    dc_grid_parameters = ParameterSweep(
        {
            "R": [6, 8, 10],
            "L": [0.4, 0.5, 0.6],
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
        new_file_name = format_rl_filename(**params)
        move_result_file(result_df, cfg["save_path"], new_file_name)
    return


if __name__ == "__main__":
    parameter_sweep_run()
    # single_run()
