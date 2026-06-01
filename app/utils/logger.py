"""Centralized logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import get_settings

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_LOG_FILE_PATH = Path("logs/app.log")
_LOG_CONFIGURED = False


def _configure_logging() -> None:
    """Configure root logging once for both file and console handlers."""

    global _LOG_CONFIGURED

    if _LOG_CONFIGURED:
        return

    settings = get_settings()
    log_level_name = settings.log_level.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    _LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = logging.FileHandler(_LOG_FILE_PATH)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _LOG_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance for a module."""

    _configure_logging()
    return logging.getLogger(name)
