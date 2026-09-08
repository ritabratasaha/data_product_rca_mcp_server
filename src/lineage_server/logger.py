"""Centralized logging configuration for the MCP server."""

import logging
from pathlib import Path

# Log directory and file paths (relative to project root)
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "lineage_server.log"

# Log format
LOG_FORMAT = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "lineage_server") -> logging.Logger:
    """
    Set up and return a logger with file-based output.

    Args:
        name: The logger name (used for module identification).

    Returns:
        Configured logger instance.
    """
    LOG_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers
    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger for a specific module.

    Args:
        name: Module name (will be prefixed with 'lineage_server.').

    Returns:
        Logger instance for the module.
    """
    setup_logger()
    return logging.getLogger(f"lineage_server.{name}")
