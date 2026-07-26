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

from datetime import datetime
from pathlib import Path
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
         d. Construct dynamic output path and check duplicate prevention
         e. Wait for flight closure and capture manifest screenshot if not already taken
         f. Gracefully close the browser session (guaranteed via context manager)
         g. Sleep for config.sleep_interval seconds before next cycle
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

                # Dynamic path construction using current date and load number
                today = datetime.now().strftime("%Y-%m-%d")
                load_num = status["load_number"]

                dest_dir = Path(config.output_destination)
                if dest_dir.suffix.lower() == ".png":
                    dest_dir = dest_dir.parent

                output_file = dest_dir / f"{today}_load_num_{load_num}.png"
                output_path_str = str(output_file)

                # Duplicate-prevention check: skip wait/screenshot if file already exists
                if output_file.exists():
                    logger.info(
                        "Manifest screenshot for Load %s on %s already exists (%s). Skipping closure wait.",
                        load_num,
                        today,
                        output_file.name,
                    )
                else:
                    browser.wait_for_flight_closed(status, output_path_str)

        
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
