"""
logger.py — BurbleBotLogger

Sets up a daily rotating log file under the Logs/ directory.
Every time the script runs, it checks today's date and writes all logs
to Logs/YYYY-MM-DD.log — a fresh file is used automatically each day.

For 24/7 long-running containers, call `BurbleBotLogger.rotate_if_needed()`
at the top of each monitoring cycle. When the date rolls over, the old
file handler is closed and a new one is opened for the new day.

Logs are written to BOTH:
  - The daily file in Logs/   (persistent record)
  - stdout                    (visible in Docker / systemd on Pi)

Usage:
    from logger import BurbleBotLogger

    BurbleBotLogger.setup()                    # call once at startup
    log = BurbleBotLogger.get("name")          # get a named child logger
    BurbleBotLogger.rotate_if_needed()         # call at the top of each cycle
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
    Call `BurbleBotLogger.rotate_if_needed()` at the top of each monitoring
    cycle to ensure logs roll over to a new file at midnight.

    All subsequent `logging.getLogger(name)` calls — including those
    inside app/browser.py and app/config.py — will automatically
    inherit the configured handlers.
    """

    _initialised: bool = False
    _current_date: str = ""
    _file_handler: logging.FileHandler | None = None
    _level: int = logging.INFO

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

        cls._level = level

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

        # Track state for daily rotation
        cls._file_handler = file_handler
        cls._current_date = today
        cls._initialised = True

        # Log the first entry so the file is visibly opened
        startup_log = cls.get("burblebot.logger")
        startup_log.info(
            "Logging initialised. Writing to: %s",
            log_file.relative_to(_PROJECT_ROOT),
        )

    @classmethod
    def rotate_if_needed(cls) -> None:
        """
        Checks if the date has rolled over since the last log file was opened.
        If so, closes the old file handler and opens a new one for today.

        Call this at the top of each monitoring cycle in main.py.
        No-op if the date has not changed or if setup() has not been called.
        """
        if not cls._initialised:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        if today == cls._current_date:
            return

        # Date has rolled over — swap file handler
        root = logging.getLogger()

        # Close and remove old file handler
        if cls._file_handler is not None:
            cls._file_handler.close()
            root.removeHandler(cls._file_handler)

        # Create new file handler for today
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOGS_DIR / f"{today}.log"

        formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
        new_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
        new_handler.setLevel(cls._level)
        new_handler.setFormatter(formatter)

        root.addHandler(new_handler)

        cls._file_handler = new_handler
        cls._current_date = today

        rotation_log = cls.get("burblebot.logger")
        rotation_log.info(
            "Log file rotated for new day. Now writing to: %s",
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

