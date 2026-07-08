from spr_methods import single_run, parameter_sweep_run

if __name__ == "__main__":
    """
        Run this section of the code for a single set of RLC parameters. Update the RLC parameters and the `config.yaml` 
        file accordingly.
    """
    dc_grid_params = {"R": 7, "L": 0.4}
    single_run(dc_grid_params)

    """
        Run this section of the code for parameter sweeps. Update the RLC parameter lists and `config.yaml` 
        file accordingly.
    """
    dc_grid_param_list = {
        "R": list(range(6, 11)),
        "L": [i * 1e-3 for i in range(400, 801, 100)],
    }
    parameter_sweep_run(dc_grid_param_list)
