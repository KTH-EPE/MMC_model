# PSCAD Automated Simulation Framework

This repository provides an automated Python-based workflow for running and managing PSCAD simulations to assess the dynamic performance compliance of modular multi-level converters (MMCs) to the functional requirements stipulated in InterOPERA D2.1. The framework supports parameter sweeps with systematic data export and post-processing.

---

## 1. Overview

The scripts in this project automate:

- Connection to PSCAD projects via the Python API
- Configuration of MMC control modes (active power, voltage control, droop control)
- Execution of different test scenarios:
  - Step changes in voltage reference
  - Step changes in active power reference
  - Power disturbances
  - Voltage disturbances
- Parameter sweeps over RLC grid equivalents
- Automatic extraction and storage of simulation results

The goal is to enable **reproducible, large-scale simulation studies** for HVDC and MMC-based grid-connected systems.

---

## 2. Project Structure
```text
MMC_model/
│
├── output/                        # All simulation outputs
│
├── pscad_model/                   # PSCAD project files
│
├── result_analysis/               # Post-processing & plotting scripts
│
│── src/                           # (Optional) reusable source modules
│   simulation_scripts/                     # Main simulation scripts
│   ├── config.yaml                # Experiment configuration file
│   ├── methods.py                 # Core PSCAD interface & utilities
│   │
│   ├── power_disturbance_step_response.py
│   ├── power_reference_step_response.py
│   ├── voltage_disturbance_step_response.py
    ├── voltage_reference_step_response.py
    ├── sensitivity_analysis_input_data_generator.py
    ├── sensitivity_analysis_voltage_step_ref_response.py
│   └── voltage_reference_step_response_fpr_sensitivity_analysis.py
│
├── poetry.lock                    # Locked dependencies (Poetry)
├── pyproject.toml                 # Project configuration & dependencies
└── README.md                      # Project documentation
```

---
## 3. Experiment Types
- N.B: Manually launch PSCAD before initiating any test
### 3.1 Voltage Disturbance Response
- File: `voltage_disturbance_step_response.py`
- Purpose: To assess the open-loop quasi-static behavior of active power response to changes in DC voltage
- Control mode: Voltage droop control (`idmode = 2`)
- In the `config.py` file, set `test: u_step_up` or `test: u_step_down`
---

### 3.2 Power Disturbance Response
- File: `power_disturbance_step_response.py`
- Purpose: 
  - To evaluate the closed-loop dynamics of the device under test (DUT) under various possible operational conditions. 
  - To assess whether the DUT possesses sufficient disturbance rejection capability to handle worst- case disturbances.
- Model includes full RLC equivalent of DC grid
- In the `config.py` file, set `test: p_step_up` or `test: p_step_down`
---

### 3.3 Voltage Reference Step Response
- File: `voltage_reference_step_response.py`
- Purpose: To ensure the capability of the AC/DC converter unit to adhere to the DC voltage set-point at its DC-PoC at steady state
- Control mode: DC voltage control (`idmode = 0`)
- In the `config.py` file, set `test: u_ref_step_up` or `test: u_ref_step_down`
---

### 3.4 Power Reference Step Response
- File: `power_reference_step_response.py`
- Purpose: Analyze active power tracking performance under reference changes
- Control mode: Active power control (`idmode = 1`)
- In the `config.py` file, set `test: p_ref_step_up` or `test: p_ref_step_down`
---

### 3.5 Sensitivity analysis
- Sensitivity analysis assess the impact of the DC and AC grid parameters on control response.
- File: `sensitivity_analysis_input_data_generator.py` generates sample data
- File: `voltage_reference_step_response_for_sensitivity_analysis.py` performs EMT simulations in PSCAD using the sample data.
- The KPI's from the EMT simulations are processed using file: `step_voltage_ref_response_result_analysis.ipynb` in the result analysis directory.
- Sobol sensitivity analysis is then performed using a surrogate PCE model with file: `sensitivity_analysis_voltage_step_ref_response.py`.
---

## 4. Parameter Sweeps

All experiments support automated parameter sweeps over:

### Electrical parameters
- Inductance (L)
- Resistance (R)
- Capacitance (C)

### Sweep structure
- Full Cartesian product of selected parameter ranges
- Each simulation is executed independently
- Results are stored with structured filenames

Example:
```
x_L400_C1300_R6_.csv
```
---

## 5. Configuration (config.yaml)

All simulation settings are centralized in config.yaml.
This ensures:

Reproducibility
Easy modification of test cases
Separation of code and experiment setup
---

## 6. Core Workflow

Each script follows the same structure:
- Step 1 — Connect to PSCAD
  - Load project
  - Set control mode
  - Configure grid impedance (SCR, X/R)
- Step 2 — Configure scenario
  - Set reference values (power or voltage)
  - Define disturbance type (step up/down)
- Step 3 — Run simulation
  - Execute PSCAD simulation
  - Export .out file
- Step 4 — Post-process
  - Convert results to CSV
  - Rename and store systematically
- Step 5 — Parameter sweep (optional)
  - Iterate over L, R, C combinations
  - Store results in structured dataset

---

## 7. Requirements & Installation
### 7.1 Python environment management (Poetry)

This project uses Poetry for dependency management and environment isolation.
Clone the project using

`git clone <repo-url>`

Change the directory to the "MMC_model"

 `cd MMC_model`

Install Poetry (if not already installed):

`pip install poetry`

Then install all dependencies:

`poetry install`

Activate the environment:

`poetry env activate`

Run the tests in "mmc_tests" as desired

---

## 8. Result analyses
- Notebooks for the processing of the results are included in the result_analysis directory
---

## 9. License

For academic and research use only (update as needed).