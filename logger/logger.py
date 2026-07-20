"""
logger.py — BurbleBotLogger

Sets up a daily rotating log file under the Logs/ directory.
Every time the script runs, it checks today's date and writes all logs
to Logs/YYYY-MM-DD.log — a fresh file is used automatically each day.

Logs are written to BOTH:
  - The daily file in Logs/   (persistent record)
  - stdout                    (visible in Docker / systemd on Pi)

Usage:
    from logger import BurbleBotLogger

    BurbleBotLogger.setup()          # call once at startup in main.py
    log = BurbleBotLogger.get("name") # get a named child logger anywhere
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Root directory of the project (one level up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Logs directory — sibling of logger/
LOGS_DIR = _PROJECT_ROOT / "Logs"

# Log format — ISO timestamp, level, logger name, message
_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class BurbleBotLogger:
    """
    Configures and manages the application-wide logging setup.

    Call `BurbleBotLogger.setup()` once at the very start of main.py.
    All subsequent `logging.getLogger(name)` calls — including those
    inside app/browser.py and app/config.py — will automatically
    inherit the configured handlers.
    """

    _initialised: bool = False

    @classmethod
    def setup(cls, level: int = logging.INFO) -> None:
        """
        Initialises the root logger with a daily file handler and a
        stdout stream handler.

        Creates Logs/YYYY-MM-DD.log for today if it doesn't already exist.
        Safe to call multiple times — subsequent calls after the first are no-ops.

        Args:
            level: Logging level for all handlers (default: logging.INFO).
        """
        if cls._initialised:
            return

        # Ensure Logs/ directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # Build today's log file path: Logs/2026-07-20.log
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"{today}.log"

        formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

        # --- File handler (daily log file) ---
        file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)

        # --- Stream handler (stdout for Docker / systemd visibility) ---
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)

        # --- Configure root logger ---
        root = logging.getLogger()
        root.setLevel(level)
        root.addHandler(file_handler)
        root.addHandler(stream_handler)

        cls._initialised = True

        # Log the first entry so the file is visibly opened
        startup_log = cls.get("burblebot.logger")
        startup_log.info(
            "Logging initialised. Writing to: %s",
            log_file.relative_to(_PROJECT_ROOT),
        )

    @classmethod
    def get(cls, name: str) -> logging.Logger:
        """
        Returns a named child logger.

        Should only be called after `BurbleBotLogger.setup()` has run.
        Will still work before setup (Python logging is always available),
        but the output will not be directed to the daily log file.

        Args:
            name: Logger name, typically __name__ of the calling module.

        Returns:
            A standard logging.Logger instance.
        """
        return logging.getLogger(name)

    @classmethod
    def today_log_path(cls) -> Path:
        """
        Returns the absolute path to today's log file.

        Useful for surfacing the log location in startup messages or health checks.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return LOGS_DIR / f"{today}.log"
