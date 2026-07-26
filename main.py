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

import sys
import time

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
    Main execution flow (24/7 continuous monitoring loop):
      1. Load .env into os.environ (no-op if already set by the container runtime)
      2. Validate all required environment variables via Config
      3. Enter continuous monitoring loop:
         a. Open a headless Chromium session via BrowserController
         b. Navigate to TARGET_URL
         c. Extract flight status (load number and ETA) and live Playwright Locators
         d. Gracefully close the browser session (guaranteed via context manager)
         e. Sleep for config.sleep_interval seconds before next cycle
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

    logger.info(
        "Starting 24/7 continuous monitoring loop (interval: %ds)...",
        config.sleep_interval,
    )

    # Step 3 — Continuous loop
    while True:
        try:
            with BrowserController(config) as browser:
                browser.navigate(config.target_url)
                logger.info("Successfully reached: %s", config.target_url)

                status = browser.get_flight_status(config.jumper_manifest_body)
                logger.info("Extracted Load Number: %s", status["load_number"])
                logger.info("Extracted ETA: %s", status["eta"])

        except TimeoutError as exc:
            logger.error("Navigation failed (timeout or network error):\n%s", exc)

        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error during capture cycle:\n%s", exc, exc_info=True)

        logger.info(
            "Cycle complete. Sleeping for %d seconds before next cycle...",
            config.sleep_interval,
        )
        time.sleep(config.sleep_interval)


if __name__ == "__main__":
    main()
