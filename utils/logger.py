"""Logging setup for the application."""
import logging
import os
from logging.handlers import RotatingFileHandler
import config


def setup_logger(name: str = "docprocessor") -> logging.Logger:
    """Configure root application logger with rotating file + console handlers."""
    os.makedirs(config.LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # Console handler – INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    )

    # Rotating file handler – DEBUG and above
    log_file = os.path.join(config.LOG_DIR, "docprocessor.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Return a named child logger under the root application logger."""
    return logging.getLogger(f"docprocessor.{module_name}")
