"""Structured logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog


def configure_logging(log_dir: Path, level: str = "INFO") -> None:
    """Configure structured console and rotating file logging."""

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "medreport.log"
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=5),
        ],
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
