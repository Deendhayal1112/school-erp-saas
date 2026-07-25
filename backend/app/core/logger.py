import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

# Define backend root and log storage directory
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BACKEND_ROOT / "logs"

# Ensure the logs directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Define exact log file paths
APP_LOG_PATH = LOG_DIR / "application.log"
ERROR_LOG_PATH = LOG_DIR / "error.log"


def setup_logging() -> None:
    """
    Initializes and configures the centralized logging system.
    Sets up Console output, Rotating Application Log, and Rotating Error Log.
    Overlays configuration onto third-party loggers (e.g., Uvicorn, FastAPI).
    """
    log_level = settings.LOG_LEVEL
    log_format = settings.LOG_FORMAT

    # Create central formatter specifying timestamp, thread, process, level, module, and message
    formatter = logging.Formatter(log_format)

    # Resolve the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear pre-existing handlers to prevent duplicated logs
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # ==========================================
    # 1. Console Log Handler (Standard Output)
    # ==========================================
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # ==========================================
    # 2. General Application Log Handler (Rotating)
    # ==========================================
    # Captures all logs from the configured LOG_LEVEL and above
    app_file_handler = RotatingFileHandler(
        filename=str(APP_LOG_PATH),
        maxBytes=10 * 1024 * 1024,  # 10 Megabytes per file
        backupCount=5,             # Retains up to 5 rotation backups
        encoding="utf-8"
    )
    app_file_handler.setFormatter(formatter)
    app_file_handler.setLevel(log_level)
    root_logger.addHandler(app_file_handler)

    # ==========================================
    # 3. Error-Specific Log Handler (Rotating)
    # ==========================================
    # Captures ONLY ERROR and CRITICAL logs for rapid debugging and operations alerts
    error_file_handler = RotatingFileHandler(
        filename=str(ERROR_LOG_PATH),
        maxBytes=10 * 1024 * 1024,  # 10 Megabytes per file
        backupCount=5,             # Retains up to 5 rotation backups
        encoding="utf-8"
    )
    error_file_handler.setFormatter(formatter)
    error_file_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_file_handler)

    # ==========================================
    # 4. Integrate Third-Party Loggers
    # ==========================================
    # Redirect logs from FastAPI and Uvicorn server processes to use our handlers and formats
    third_party_loggers = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "sqlalchemy.engine",  # Can be activated for query debugging
        "celery"
    ]
    for logger_name in third_party_loggers:
        third_party_logger = logging.getLogger(logger_name)
        third_party_logger.handlers.clear()
        # Propagating logs up to the root logger lets our handlers parse and format them
        third_party_logger.propagate = True

    logging.info(
        f"Centralized logging initialized successfully. Log level: {logging.getLevelName(log_level)}"
    )
