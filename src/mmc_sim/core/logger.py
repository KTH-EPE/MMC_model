"""
Logging utilities for MMC simulation framework.

Provides centralized logging configuration for:
- PSCAD simulation execution
- parameter sweeps
- sensitivity analysis
- result processing
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(
        name: str = "mmc_sim",
        log_dir: Path = Path("logs"),
        level: int = logging.INFO
):
    """
    Configure application logger.

    Parameters
    ----------
    name:
        Logger name.

    log_dir:
        Directory where log files are stored.

    level:
        Logging level.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """

    # Create log directory
    log_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    logger = logging.getLogger(name)

    logger.setLevel(level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # =========================
    # Log format
    # =========================

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # =========================
    # Console handler
    # =========================

    console_handler = logging.StreamHandler(
        sys.stdout
    )

    console_handler.setLevel(level)

    console_handler.setFormatter(
        formatter
    )

    # =========================
    # File handler
    # =========================

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    log_file = (
            log_dir /
            f"simulation_{timestamp}.log"
    )

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8"
    )

    file_handler.setLevel(
        level
    )

    file_handler.setFormatter(
        formatter
    )

    # Register handlers

    logger.addHandler(
        console_handler
    )

    logger.addHandler(
        file_handler
    )

    logger.info(
        "Logging initialized"
    )

    logger.info(
        f"Log file: {log_file}"
    )

    return logger
