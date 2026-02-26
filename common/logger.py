import logging
import logging.handlers
from pathlib import Path
import os
from typing import Optional

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_DIR = os.getenv("LOG_DIR", "/runtime/logs")
_LOG_FILENAME = os.getenv("LOG_FILENAME", "screenshoter.log")
_LOG_FILE_MAX_MB = os.getenv("LOG_FILE_MAX_MB", 10)
_LOG_FILE_BACKUPS = os.getenv("LOG_FILE_BACKUPS", 5)


class _TextFormatter(logging.Formatter):
    _COLORS = {
        logging.DEBUG: "\033[36m",  # cyan
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[35m",  # magenta
    }
    _RESET = "\033[0m"

    FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    DATETIMEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, use_colors: bool = None) -> None:
        super().__init__(fmt=self.FMT, datefmt=self.DATETIMEFMT)
        self._use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        if self._use_colors:
            color = self._COLORS.get(record.levelno, "")
            return f"{color}{formatted}{self._RESET}"
        return formatted


def _build_file_handler() -> logging.handlers.RotatingFileHandler:
    log_dir = Path(_LOG_DIR)

    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{_LOG_FILENAME}.log"

    handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=_LOG_FILE_MAX_MB * 1024 * 1024,
        backupCount=_LOG_FILE_BACKUPS,
        encoding="utf-8",
    )

    handler.setFormatter(_TextFormatter(use_colors=False))
    return handler


def _configure_root_logger() -> None:
    global _configured
    if _configured:
        return

    formatter = _TextFormatter(use_colors=True)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(_LOG_LEVEL)

    try:
        if not root.handlers:
            root.addHandler(handler)
            root.addHandler(_build_file_handler())
    except OSError as e:
        logging.getLogger(__name__).warning(
            "File logging disabled: cannot create log file in '%s': %s",
            _LOG_DIR, e,
        )

    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("aiormq").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    _configure_root_logger()
    return logging.getLogger(name)
