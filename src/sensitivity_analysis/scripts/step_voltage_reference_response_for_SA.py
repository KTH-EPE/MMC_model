import pandas as pd

from src.mmc_sim.core.pscad import PSCADModel
from src.mmc_sim.core.config_components import ConfigDCGridComponents
from src.mmc_sim.core.simulation import Simulation
from src.mmc_sim.core.misc import *
from src.mmc_sim.tests.step_voltage_reference.scripts.svr_methods import *
from src.mmc_sim.core.logger import setup_logger
from src.mmc_sim.core.config import Config


CONFIG_FILE = Path(".\\SA_config.yaml")

logger = setup_logger(
    "simulation"
)


def sample_data_run(sample_data_path: str):
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
    )

    model.set_output(cfg["output_file"])

    canvas_components = model.canvas_components()

    set_power_and_voltage_values(
        canvas_components,
        cfg["ref_power"],
    )

    dc_grid_components = find_dc_components(canvas_components)
    dc_network = ConfigDCGridComponents(dc_grid_components)
    sample_data_df = pd.read_csv(sample_data_path)
    for _, row in sample_data_df.iterrows():
        dc_grid_params = {"R": row["R"], "L": row["L"], "C": row["C"]}
        dc_network.set_dc_network(
            **dc_grid_params
        )

        simulation = Simulation(model)
        logger.info(f"Running simulation for {dc_grid_params}")
        result_df = simulation.run(cfg["result_file"])
        new_file_name = format_rlc_filename(**dc_grid_params)
        move_result_file(result_df, cfg["save_path"], new_file_name)
    return


if __name__ == "__main__":
    sa_cfg = Config(CONFIG_FILE)
    sample_data = f'{sa_cfg.get("sensitivity_analysis", "output", "sample_data")}/sample_data.csv'
    sample_data_run(sample_data)
