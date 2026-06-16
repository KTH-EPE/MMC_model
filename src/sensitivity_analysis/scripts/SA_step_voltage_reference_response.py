"""
Polynomial Chaos Expansion based sensitivity analysis.
"""

from sklearn.model_selection import train_test_split
from sa_methods import *


# Main analysis pipeline
def run_analysis(config_file):
    cfg = load_config(config_file)
    sample_data = Path(cfg["sensitivity_analysis"]["output"]["sample_data"])
    sim_summary_data = Path(cfg["sensitivity_analysis"]["output"]["sim_data"])
    dataset = load_dataset(sample_data, sim_summary_data)

    # Inputs
    X = dataset[["L", "C", "R", "SCR", "XR"]].values

    # Output response
    Y = dataset["Xm"].values  # or "Tcr", "Tcs"
    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.2, random_state=13)
    distribution = create_distribution()
    model = train_pce(X_train, Y_train, order=3, distribution=distribution)
    metrics = evaluate_model(model, X_train, X_test, Y_train, Y_test)

    sobol = calculate_sobol_indices(model, distribution)
    logger.info(f"Accuracy: {metrics}")
    return {
        "model": model,
        "metrics": metrics,
        "sobol": sobol
    }


if __name__ == "__main__":
    results_summary = run_analysis("SA_config.yaml")
    print(results_summary["metrics"])
    print(results_summary["sobol"])
