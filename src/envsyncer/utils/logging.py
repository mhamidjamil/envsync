"""File logging for EnvSyncer.

Human-facing output goes through :mod:`envsyncer.ui.console` (colored, concise).
This module records a durable audit trail — uploads, downloads, profile
switches, conflicts and errors — to ``~/.envsyncer/logs/envsyncer.log`` so the
tool can be diagnosed after the fact without cluttering the terminal.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from envsyncer.utils import paths

_LOGGER_NAME = "envsyncer"
_configured = False


def get_logger() -> logging.Logger:
    """Return the shared EnvSyncer logger, configuring it on first use."""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    paths.ensure_dirs()
    handler = RotatingFileHandler(
        paths.LOGS_DIR / "envsyncer.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _configured = True
    return logger
