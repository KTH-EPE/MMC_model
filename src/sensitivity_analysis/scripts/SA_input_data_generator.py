"""
Sensitivity analysis sample generation.
"""

from sa_methods import *


# Main execution
def run_sampling(config_file=Path("SA_config.yaml"), samples=300):
    cfg = load_config(config_file)
    output_directory = Path(cfg["sensitivity_analysis"]["output"]["sample_data"])
    dataframe = generate_samples(number_of_samples=samples, random_seed=13)
    save_samples(dataframe, output_directory)
    return dataframe


if __name__ == "__main__":
    data_samples = run_sampling()
    print(data_samples.head())
