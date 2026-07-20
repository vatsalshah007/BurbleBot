"""
main.py — BurbleBot entry point.

Loads environment variables from .env (local dev), validates configuration,
initialises a headless Chromium browser session, navigates to the target URL,
and ensures the browser is always cleanly terminated.

Exit codes:
    0 — Success
    1 — Configuration error (missing/invalid environment variable)
    2 — Navigation error (network timeout or unreachable URL)
    3 — Unexpected runtime error
"""

import os
import sys

from dotenv import load_dotenv

from app.browser import BrowserController
from app.config import Config
from logger import BurbleBotLogger

# ---------------------------------------------------------------------------
# Logging — daily file in Logs/YYYY-MM-DD.log + stdout mirror
# Must be the very first thing set up so all module loggers inherit it.
# ---------------------------------------------------------------------------
BurbleBotLogger.setup()
logger = BurbleBotLogger.get("burblebot")


def main() -> None:
    """
    Main execution flow:
      1. Load .env into os.environ (no-op if already set by the container runtime)
      2. Validate all required environment variables via Config
      3. Open a headless Chromium session via BrowserController
      4. Navigate to TARGET_URL
      5. Gracefully close the browser session (guaranteed via context manager)
    """

    # Step 1 — Load .env for local development.
    # In production (Docker / systemd on Pi), env vars are injected by the runtime
    # and load_dotenv() will simply find nothing to override — safe to call always.
    load_dotenv()
    logger.info("Environment loaded.")

    # Step 2 — Validate configuration. Exits here if TARGET_URL is missing.
    try:
        config = Config()
        logger.info("Configuration validated: %r", config)
    except EnvironmentError as exc:
        logger.error("Configuration error:\n%s", exc)
        sys.exit(1)

    # Step 3 & 4 — Launch browser and navigate.
    # The 'with' block guarantees __exit__ is always called, closing the browser
    # cleanly whether navigation succeeds, times out, or raises unexpectedly.
    try:
        with BrowserController(config) as browser:
            browser.navigate(config.target_url)
            logger.info("Successfully reached: %s", config.target_url)
            eta = browser.get_eta(os.getenv("JUMPER_MANIFEST_BODY", ""))
            logger.info("ETA: %s", eta)

    except TimeoutError as exc:
        logger.error("Navigation failed (timeout or network error):\n%s", exc)
        sys.exit(2)

    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error during browser session:\n%s", exc, exc_info=True)
        sys.exit(3)

    logger.info("Task 1 complete. Browser session closed cleanly.")


if __name__ == "__main__":
    main()
