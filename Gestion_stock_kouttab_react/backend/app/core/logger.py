"""Centralised logger configuration."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


_LOG_DIR = Path("logs")
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def _configure_root_logger() -> logging.Logger:
    logger = logging.getLogger("kouttab")
    if logger.handlers:
        return logger

    level = logging.DEBUG if settings.app_debug else logging.INFO
    logger.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT)

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File (rotating)
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            _LOG_DIR / "app.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Filesystem may be read-only on some hosts; ignore.
        pass

    logger.propagate = False
    return logger


logger = _configure_root_logger()


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger sharing the root configuration."""
    if name:
        return logger.getChild(name)
    return logger
