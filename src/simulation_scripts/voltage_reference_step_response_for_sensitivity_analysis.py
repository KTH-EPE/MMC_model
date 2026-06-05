from pathlib import Path
import pandas as pd
import yaml

from methods import (
    connect_step_voltage_ref_sensitivity_analysis_model,
    run_rlc_sensitivity_parameter_sweep,
)


def load_config(config_path: Path) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config(Path("config.yaml"))

    voltage_cfg = cfg["voltage_ref_step"]
    sensitivity_cfg = cfg["sensitivity_analysis"]

    project_path = Path(voltage_cfg["path"])
    project_name = voltage_cfg["name"]

    output_file_name = voltage_cfg["output"]["file_name"]
    result_file = (
        Path(voltage_cfg["output"]["result_file"]) / output_file_name
    )

    output_dir = Path(
        sensitivity_cfg["output"]["step_voltage_reference"]
    )

    input_sample_data = Path(
        sensitivity_cfg["output"]["sample_data"]
    )

    test = voltage_cfg["test"]
    ref_power = voltage_cfg["ref_power"]

    input_df = pd.read_csv(
        input_sample_data / "train_input_data.csv"
    )

    print("Simulation started")

    proj, components = (
        connect_step_voltage_ref_sensitivity_analysis_model(
            proj_path=project_path,
            proj_name=project_name,
            test=test,
            output_file_name=output_file_name,
            ref_power=ref_power,
        )
    )

    run_rlc_sensitivity_parameter_sweep(
        input_sample_data=input_df,
        output_dir=output_dir,
        result_file=result_file,
        proj=proj,
        components=components,
    )

    print("Simulation completed")


if __name__ == "__main__":
    main()
