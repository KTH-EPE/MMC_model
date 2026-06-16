import math
from pathlib import Path
import yaml
import numpy as np
import pandas as pd
import chaospy as cp
from sklearn.metrics import r2_score
from SALib.sample.latin import sample

from src.mmc_sim.core.logger import setup_logger

logger = setup_logger("pce_analysis")


def load_config(config_file: Path):
    """
    Load YAML configuration file.
    """
    with open(config_file) as file:
        return yaml.safe_load(file)


# Problem definition
def define_sampling_problem():
    """
    Define uncertain parameters for sensitivity analysis.
    Returns
    -------
    dict
        SALib problem definition.
    """
    return {"num_vars": 5,
            "names": ["L", "C", "R", "SCR", "XR"],
            "bounds": [
                [400.0, 800.0],  # L [mH]
                [800.0, 2100.0],  # C [uF]
                [6.0, 10.0],  # R [Ohm]
                [5.0, 15.0],  # SCR
                [5.0, 20.0]  # X/R ratio
            ]
            }


# Grid parameter calculation
def calculate_grid_parameters(dataframe: pd.DataFrame, nominal_power: float = 1200,
                              voltage: float = 400, frequency: float = 50):
    """
    Calculate equivalent grid impedance.
    Parameters
    ----------
    dataframe:
        Sample dataframe containing SCR and XR.
    Returns
    -------
    DataFrame
        Updated dataframe with Lg and Rg.
    """
    dataframe["Lg"] = (voltage ** 2 / (dataframe["SCR"] * nominal_power * 2 * math.pi * frequency))
    dataframe["Rg"] = (voltage ** 2 / (dataframe["SCR"] * nominal_power * dataframe["XR"]))
    return dataframe


# Sample generation
def generate_samples(number_of_samples: int, random_seed: int = None):
    """
    Generate Latin Hypercube samples.

    Parameters
    ----------
    number_of_samples:
        Number of samples.

    random_seed:
        Reproducibility seed.

    Returns
    -------
    DataFrame
    """

    problem = define_sampling_problem()
    logger.info(f"Generating {number_of_samples} samples")
    samples = sample(problem, number_of_samples, seed=random_seed)
    dataframe = pd.DataFrame(samples, columns=problem["names"])
    dataframe = calculate_grid_parameters(dataframe)
    return dataframe


# Save samples
def save_samples(dataframe: pd.DataFrame, output_directory: Path, filename="sample_data.csv"):
    """
    Save generated samples.
    """

    output_directory.mkdir(parents=True, exist_ok=True)
    output_file = (output_directory / filename)
    dataframe.round(6).to_csv(output_file, index=False)
    return output_file


def load_dataset(sample_file: Path, result_file: Path):
    """
    Load and merge simulation input/output data.

    Parameters
    ----------
    sample_file:
        Generated sensitivity samples.

    result_file:
        PSCAD response summary.

    Returns
    -------
    DataFrame
        Prepared input-output dataset.
    """
    logger.info("Loading sample and simulation data")
    samples = pd.read_csv(sample_file)
    results = pd.read_csv(result_file)

    # Select required simulation outputs
    results = results[["H_mH", "C_uF", "R_ohms", "Xm"]]
    dataset = samples.merge(
        results,
        left_on=["L", "C", "R"],
        right_on=["H_mH", "C_uF", "R_ohms"],
        how="inner"
    )
    dataset.drop(columns=["H_mH", "C_uF", "R_ohms"], inplace=True)

    # Convert mH to H
    dataset["L"] /= 1000
    logger.info(f"Dataset size: {dataset.shape}")
    return dataset


# Polynomial Chaos Model
def create_distribution():
    """
    Define uncertain parameter distributions.
    """
    return cp.J(
        cp.Uniform(0.4, 0.8),   # L
        cp.Uniform(800, 2100),  # C
        cp.Uniform(6, 10),      # R
        cp.Uniform(5, 15),      # SCR
        cp.Uniform(5, 20)       # XR
    )


def train_pce(X_train, Y_train, order, distribution):
    """
    Train polynomial chaos expansion surrogate.
    """
    logger.info(f"Training PCE order={order}")
    expansion = cp.generate_expansion(order, distribution)
    model = cp.fit_regression(expansion, X_train.T, Y_train)
    return model


# Validation
def evaluate_model(model, X_train, X_test, Y_train, Y_test):
    """
    Evaluate surrogate model accuracy.
    """
    Y_train_pred = model(*X_train.T)
    Y_test_pred = model(*X_test.T)
    metrics = {
        "r2_train": r2_score(Y_train, Y_train_pred),
        "r2_test":
            r2_score(Y_test, Y_test_pred),
        "relative_l2_error": np.linalg.norm(Y_test - Y_test_pred) / np.linalg.norm(Y_test)
    }
    return metrics


# Sobol sensitivity
def calculate_sobol_indices(model, distribution):
    """
    Calculate Sobol sensitivity indices.
    """
    logger.info("Calculating Sobol indices")
    return {
        "first_order": cp.Sens_m(model, distribution),
        "second_order": cp.Sens_m2(model, distribution),
        "total": cp.Sens_t(model, distribution)
    }
