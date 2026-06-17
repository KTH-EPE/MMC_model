from src.mmc_sim.core.config import Config
from sa_methods import sample_data_emt_run, CONFIG_FILE


if __name__ == "__main__":
    """
    This script performs EMT simulations from sampled data for sensitivity analysis. The sampled data should be in a
    csv file with columns for "R" in ohms, "L" in mH, "C" in uF, "SCR" and "XR". The config.yaml file should be 
    updated accordingly.
    """
    sa_cfg = Config(CONFIG_FILE)
    sample_data = sa_cfg.get("sensitivity_analysis", "output", "sample_data")
    sample_data_emt_run(sample_data)
