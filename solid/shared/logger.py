import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "solid",
    level: str = "INFO",
    log_dir: Optional[str] = None,
    fmt: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt: str = "%Y-%m-%d %H:%M:%S",
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(fmt, datefmt=datefmt)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(
            filename=Path(log_dir) / f"{name}.log",
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger
