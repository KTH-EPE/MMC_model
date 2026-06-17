
from svr_methods import single_run, parameter_sweep_run


if __name__ == "__main__":
    """
        Run this section of the code for a single set of RLC parameters. Update the RLC parameters and the `config.yaml` 
        file accordingly.
    """
    dc_grid_params = {"R": 7, "L": 0.4, "C": 800.}
    single_run(dc_grid_params)

    """
        Run this section of the code for parameter sweeps. Update the RLC parameter lists and `config.yaml` 
        file accordingly.
    """
    dc_grid_param_list = {
        "R": [6, 8, 10],
        "L": [0.4, 0.5, 0.6],
        "C": [800., 900., 1000.]
    }
    parameter_sweep_run(dc_grid_param_list)
