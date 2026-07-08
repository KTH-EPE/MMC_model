from spd_methods import single_run, parameter_sweep_run


if __name__ == "__main__":
    """
        Run this section of the code for a single set of RLC parameters. Update the RLC parameters and the `config.yaml` 
        file accordingly.
    """
    rlc_grid_params = {"R": 7, "L": 0.4, "C": 1000.}
    single_run(rlc_grid_params)  # Requires a single set of values

    """
        Run this section of the code for parameter sweeps. Update the RLC parameter lists and `config.yaml` 
        file accordingly.
    """
    rlc_param_list = {  # List of parameters for the RLC grid equivalent model
        "R": list(range(6, 11)),
        "L": [i * 1e-3 for i in range(400, 801, 100)],
        "C": list(range(800, 2101, 100))
    }
    parameter_sweep_run(rlc_param_list)  # Requires a list for parameter sweeps
