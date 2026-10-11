"""
browser.py — Playwright browser controller for BurbleBot.

Implements BrowserController as a context manager to guarantee the browser
session is always gracefully terminated — even when exceptions occur —
preventing memory leaks during 24/7 continuous operation.

Configured explicitly for ARM64 (Raspberry Pi 5) headless deployment.
"""

from datetime import datetime
import logging
from pathlib import Path
import re
import time

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    sync_playwright,
)

from app.config import Config

logger = logging.getLogger(__name__)


# Chromium launch flags required for ARM64 Linux / containerised environments.
# These are mandatory for stable headless operation on Raspberry Pi 5.
ARM64_CHROMIUM_ARGS: list[str] = [
    "--no-sandbox",           # Required: no user namespace isolation in containers
    "--disable-dev-shm-usage",  # Required: /dev/shm is too small on Pi — use /tmp
    "--disable-gpu",          # Required: no GPU available in headless Pi environment
    "--disable-setuid-sandbox",  # Required alongside --no-sandbox for some ARM builds
    "--single-process",       # Reduces memory footprint on resource-constrained hardware
]

# Default navigation timeout in milliseconds.
DEFAULT_TIMEOUT_MS: int = 30_000


class BrowserController:
    """
    Manages the full lifecycle of a Playwright Chromium browser session.

    Usage (always use as a context manager):

        with BrowserController(config) as controller:
            controller.navigate(config.target_url)

    The browser, context, and page are created on __enter__ and are
    guaranteed to be closed on __exit__, regardless of whether an
    exception was raised inside the block.
    """

    def __init__(self, config: Config, playwright: Playwright | None = None) -> None:
        self._config = config
        self._provided_playwright = playwright
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> "BrowserController":
        """
        Starts the Playwright runtime and launches a headless Chromium browser
        configured for ARM64 Linux deployment.
        """
        logger.info("Starting Playwright runtime...")
        if self._provided_playwright is not None:
            self._playwright = self._provided_playwright
        else:
            self._playwright = sync_playwright().start()

        logger.info("Launching headless Chromium (ARM64 mode)...")
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=ARM64_CHROMIUM_ARGS,
        )

        self._context = self._browser.new_context(
            # Viewport matches common dashboard/monitoring display sizes
            viewport={"width": 1920, "height": 1080},
        )

        self._page = self._context.new_page()
        self._page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        self._page.set_default_navigation_timeout(DEFAULT_TIMEOUT_MS)

        logger.info("Browser session initialised successfully.")
        return self

    def navigate(self, url: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
        """
        Navigates to the given URL and waits until the network is idle.

        Args:
            url: The URL to navigate to.
            timeout_ms: Maximum milliseconds to wait for navigation (default 30s).

        Raises:
            RuntimeError: If the browser session has not been started via __enter__.
            TimeoutError: If navigation does not complete within timeout_ms.
        """
        if self._page is None:
            raise RuntimeError(
                "BrowserController must be used as a context manager. "
                "Use: 'with BrowserController(config) as browser:'"
            )

        logger.info("Navigating to: %s", url)
        try:
            self._page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            logger.info("Navigation complete. Current URL: %s", self._page.url)
        except Exception as exc:
            # Re-raise as TimeoutError for network/timeout issues so callers
            # can distinguish transient failures from programming errors.
            raise TimeoutError(
                f"Navigation to '{url}' failed after {timeout_ms}ms: {exc}"
            ) from exc

    @property
    def page(self) -> Page:
        """Returns the active Playwright Page. Raises if session not started."""
        if self._page is None:
            raise RuntimeError(
                "BrowserController must be used as a context manager."
            )
        return self._page

    def _get_load_number(self, target: str | Locator, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> tuple[str, Locator]:
        """
        Extracts load number text and live Locator from the 1st <td> element
        inside the first <table> under target (either a selector str or parent Locator).

        Args:
            target: The parent DOM selector string or parent Locator.
            timeout_ms: Maximum milliseconds to wait for the element text (default 30s).

        Returns:
            Tuple of (cleaned load number text, target Locator object).

        Raises:
            RuntimeError: If extraction fails.
        """
        if self._page is None:
            raise RuntimeError("Browser session not started.")

        try:
            if isinstance(target, str):
                table_loc = self._page.locator(f"{target} table").first
            else:
                table_loc = target.locator("table").first

            load_locator = table_loc.locator("td").nth(0)
            load_text = load_locator.inner_text(timeout=timeout_ms).strip().replace("\n", " ")
            return load_text, load_locator
        except Exception as exc:
            logger.debug("Failed to extract load number from '%s': %s", target, exc)
            raise RuntimeError(f"Failed to extract load number: {exc}") from exc

    def _get_eta(self, target: str | Locator, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> tuple[str, Locator]:
        """
        Extracts ETA text and live Locator from the 2nd <td> element
        inside the first <table> under target (either a selector str or parent Locator).

        Args:
            target: The parent DOM selector string or parent Locator.
            timeout_ms: Maximum milliseconds to wait for the element text (default 30s).

        Returns:
            Tuple of (cleaned ETA text, target Locator object).

        Raises:
            RuntimeError: If extraction fails.
        """
        if self._page is None:
            raise RuntimeError("Browser session not started.")

        try:
            if isinstance(target, str):
                table_loc = self._page.locator(f"{target} table").first
            else:
                table_loc = target.locator("table").first

            eta_locator = table_loc.locator("td").nth(1)
            eta_text = eta_locator.inner_text(timeout=timeout_ms).strip()
            return eta_text, eta_locator
        except Exception as exc:
            logger.debug("Failed to extract ETA from '%s': %s", target, exc)
            raise RuntimeError(f"Failed to extract ETA: {exc}") from exc

    def get_flight_status(self, selector: str) -> dict[str, any]:
        """
        Coordinates extraction of flight load number and ETA from the DOM.

        Args:
            selector: Base CSS selector for the manifest body.

        Returns:
            Dictionary containing cleaned text data and live Playwright Locators:
            {
                "load_number": load_num,
                "load_locator": load_locator,
                "eta": eta,
                "eta_locator": eta_locator
            }

        Raises:
            RuntimeError: If base selector is not visible or extraction fails.
        """
        if self._page is None:
            raise RuntimeError("Browser session not started.")

        if not selector:
            raise RuntimeError("No selector provided for flight status extraction.")

        base_path = f"{selector} div[id^='{self._config.jumper_manifest_load}']"
        logger.info("Waiting for base row path: '%s'...", base_path)

        try:
            self._page.wait_for_selector(base_path, state="visible", timeout=5000)
        except Exception:
            logger.info("Base selector '%s' not visible (no active loads found).", base_path)
            return {
                "has_loads": False,
                "load_number": None,
                "load_locator": None,
                "eta": None,
                "eta_locator": None,
                "flight_manifest_locator": None,
            }

        load_num, load_locator = self._get_load_number(base_path)
        eta, eta_locator = self._get_eta(base_path)

        logger.info("Flight status extracted — Load Number: %s, ETA: %s", load_num, eta)

        return {
            "has_loads": True,
            "load_number": load_num.split(" ")[-1],
            "load_locator": load_locator,
            "eta": eta,
            "eta_locator": eta_locator,
            "flight_manifest_locator": self._page.locator(base_path).first,
        }

    def take_manifest_screenshot(self, status_dict: dict[str, any], output_path: str) -> None:
        """
        Captures a screenshot of the flight manifest row/table using status_dict["flight_manifest_locator"].

        Args:
            status_dict: Dictionary containing 'flight_manifest_locator' or 'load_locator'.
            output_path: File path where the PNG screenshot will be saved.
        """
        target_locator = status_dict.get("flight_manifest_locator") or status_dict.get("load_locator")
        if target_locator is None:
            raise RuntimeError(
                "Cannot take manifest screenshot: neither 'flight_manifest_locator' nor 'load_locator' found in status_dict."
            )

        parent_dir = Path(output_path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Capturing manifest screenshot using flight_manifest_locator -> %s", output_path)
        target_locator.screenshot(
            path=output_path,
            type="png",
            animations="disabled",
            timeout=10000,
        )
        logger.info("Screenshot successfully captured and saved: %s", output_path)

    def _is_date_rolled_over(self, start_date: str) -> bool:
        """Returns True if the current calendar date has rolled over past start_date."""
        return datetime.now().strftime("%Y-%m-%d") != start_date

    def _parse_eta_minutes(self, eta_text: str) -> int | None:
        """
        Extracts signed integer minutes from ETA text (e.g., '10 Mins' -> 10, '-2 Mins' -> -2).
        Returns None if text cannot be parsed into an integer (e.g. 'Closed').
        """
        if not eta_text:
            return None
        match = re.search(r"(-?\d+)", eta_text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _get_poll_interval(self, eta_minutes: int | None, default_poll_interval_sec: int = 30) -> int:
        """
        Dynamic polling helper:
        - 5s if eta_minutes is defined and <= 1 (fast polling near closure).
        - default_poll_interval_sec otherwise (standard polling).
        """
        if eta_minutes is not None and eta_minutes <= 1:
            return 5
        return default_poll_interval_sec

    def _should_recycle_session(self, elapsed_seconds: float, eta_minutes: int | None, max_duration_sec: int = 2700) -> bool:
        """
        Weather hold / session recycling helper:
        Determines if browser session should be recycled to prevent memory bloat on Pi.
        Enforces Rule 1: Never recycle if eta_minutes <= 5 (finish monitoring imminent flight).
        """
        if elapsed_seconds < max_duration_sec:
            return False
        # Rule 1: Never recycle if ETA <= 5 (finish monitoring imminent flight)
        if eta_minutes is not None and eta_minutes <= 5:
            return False
        return True

    def _check_active_section(self, target_load_number: str) -> dict[str, any]:
        """
        Inspects the first visible load section on the board and verifies if it
        still matches target_load_number.

        Returns a dictionary:
        {
            "is_active": bool,
            "load_number": str | None,
            "eta": str | None,
            "flight_manifest_locator": Locator | None,
            "reason": str,  # 'ok', 'no_loads', 'not_visible', 'load_mismatch', 'error'
        }
        """
        if self._page is None:
            return {
                "is_active": False,
                "load_number": None,
                "eta": None,
                "flight_manifest_locator": None,
                "reason": "no_page",
            }

        base_path = f"{self._config.jumper_manifest_body} div[id^='{self._config.jumper_manifest_load}']"
        try:
            rows = self._page.locator(base_path)
            if rows.count() == 0:
                time.sleep(1)
                if rows.count() == 0:
                    return {
                        "is_active": False,
                        "load_number": None,
                        "eta": None,
                        "flight_manifest_locator": None,
                        "reason": "no_loads",
                    }

            first_row = rows.first
            if not first_row.is_visible():
                time.sleep(1)
                if not first_row.is_visible():
                    return {
                        "is_active": False,
                        "load_number": None,
                        "eta": None,
                        "flight_manifest_locator": None,
                        "reason": "not_visible",
                    }

            load_text, load_locator = self._get_load_number(first_row, timeout_ms=3000)
            current_load_num = load_text.split(" ")[-1]

            if current_load_num != str(target_load_number):
                return {
                    "is_active": False,
                    "load_number": current_load_num,
                    "eta": None,
                    "flight_manifest_locator": None,
                    "reason": "load_mismatch",
                }

            eta_text, eta_locator = self._get_eta(first_row, timeout_ms=3000)

            return {
                "is_active": True,
                "load_number": current_load_num,
                "eta": eta_text,
                "flight_manifest_locator": first_row,
                "reason": "ok",
            }
        except Exception as exc:
            logger.debug("Error checking active section for Load %s: %s", target_load_number, exc)
            return {
                "is_active": False,
                "load_number": None,
                "eta": None,
                "flight_manifest_locator": None,
                "reason": f"error: {exc}",
            }

    def wait_for_flight_closed(self, status_dict: dict[str, any], output_path: str, poll_interval_sec: int = 30, max_duration_sec: int = 2700) -> bool:
        """
        Polls the active flight manifest section until closure, date rollover, or cycle timeout.

        - Verifies that the top section still matches status_dict['load_number'].
        - Aborts if date rolls over past midnight.
        - Dynamically polls every 5s when ETA <= 1, otherwise every 30s.
        - Caches in-memory screenshot bytes when ETA <= 1; if load vanishes before
          'Closed' is detected, saves the in-memory fallback screenshot to output_path.
        - Enforces Rule 1: Never recycles the session if ETA <= 5.
        - Once 'Closed' is detected, immediately invokes self.take_manifest_screenshot(status_dict, output_path).

        Args:
            status_dict: Dictionary containing 'load_number' and initial locators.
            output_path: File path where screenshot will be saved.
            poll_interval_sec: Default fallback polling interval in seconds.
            max_duration_sec: Maximum duration in seconds before recycling session (default 45 min).

        Returns:
            bool: True if a screenshot was saved (closed or fallback), False if cycled or aborted.
        """
        load_num = status_dict.get("load_number", "unknown")
        start_date = datetime.now().strftime("%Y-%m-%d")
        start_time = time.monotonic()
        last_screenshot_bytes: bytes | None = None

        logger.info(
            "Starting closure monitoring for Load %s (date: %s)...",
            load_num,
            start_date,
        )

        while True:
            # 1. Date rollover check: avoid cross-midnight misattribution
            if self._is_date_rolled_over(start_date):
                logger.warning(
                    "Date rolled over past midnight while waiting for Load %s on %s. Aborting wait.",
                    load_num,
                    start_date,
                )
                return False

            # 2. Section check: verify target load is still active in the first section
            section_status = self._check_active_section(load_num)
            if not section_status["is_active"]:
                reason = section_status.get("reason", "unknown")
                logger.warning(
                    "Load %s is no longer active in the first section (reason: %s).",
                    load_num,
                    reason,
                )
                # If we have a cached in-memory screenshot from when ETA <= 1, save as fallback!
                if last_screenshot_bytes is not None:
                    parent_dir = Path(output_path).parent
                    parent_dir.mkdir(parents=True, exist_ok=True)
                    Path(output_path).write_bytes(last_screenshot_bytes)
                    logger.warning(
                        "Board cleared before 'Closed' ETA detected for Load %s. Saved last available in-memory screenshot: %s",
                        load_num,
                        output_path,
                    )
                    return True
                return False

            current_text = section_status["eta"] or ""
            logger.debug("Load %s status poll text: '%s'", load_num, current_text)

            # 3. Check for "Closed"
            if current_text.lower() == "closed":
                logger.info("Flight for Load %s is CLOSED. Invoking manifest screenshot...", load_num)
                if section_status.get("flight_manifest_locator"):
                    status_dict["flight_manifest_locator"] = section_status["flight_manifest_locator"]
                self.take_manifest_screenshot(status_dict, output_path)
                return True

            # 4. Parse ETA minutes
            eta_mins = self._parse_eta_minutes(current_text)

            # 5. Check weather hold / cycle ceiling (Rule 1: Never recycle if ETA <= 5)
            elapsed = time.monotonic() - start_time
            if self._should_recycle_session(elapsed, eta_mins, max_duration_sec=max_duration_sec):
                logger.info(
                    "Load %s still pending after %ds (ETA: %s). Cycling browser session to prevent memory bloat...",
                    load_num,
                    int(elapsed),
                    current_text,
                )
                return False

            # 6. Cache in-memory screenshot when ETA <= 1 (including 0, -1, -2, etc.)
            if eta_mins is not None and eta_mins <= 1:
                try:
                    manifest_loc = section_status.get("flight_manifest_locator") or status_dict.get("flight_manifest_locator")
                    if manifest_loc:
                        last_screenshot_bytes = manifest_loc.screenshot(
                            type="png", animations="disabled", timeout=5000
                        )
                        logger.debug(
                            "Cached in-memory fallback screenshot for Load %s (ETA: %s)",
                            load_num,
                            current_text,
                        )
                except Exception as exc:
                    logger.debug("Could not cache in-memory screenshot for Load %s: %s", load_num, exc)

            # 7. Sleep dynamic poll interval (5s when ETA <= 1, 30s otherwise)
            interval = self._get_poll_interval(eta_mins, default_poll_interval_sec= poll_interval_sec)
            time.sleep(interval)

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Gracefully tears down the entire browser session in reverse order:
        page → context → browser → playwright runtime.

        Always runs — even if an exception was raised inside the 'with' block.
        Returns False to allow exceptions to propagate normally.
        """
        logger.info("Closing browser session...")

        if self._page is not None:
            try:
                self._page.close()
                logger.debug("Page closed.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error closing page: %s", exc)
            finally:
                self._page = None

        if self._context is not None:
            try:
                self._context.close()
                logger.debug("Browser context closed.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error closing browser context: %s", exc)
            finally:
                self._context = None

        if self._browser is not None:
            try:
                self._browser.close()
                logger.debug("Browser closed.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error closing browser: %s", exc)
            finally:
                self._browser = None

        # Only stop the Playwright runtime if we started it ourselves.
        # When an external runtime is provided, the caller owns its lifecycle.
        if self._playwright is not None and self._provided_playwright is None:
            try:
                self._playwright.stop()
                logger.debug("Playwright runtime stopped.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error stopping Playwright: %s", exc)
            finally:
                self._playwright = None

        logger.info("Browser session terminated cleanly.")
        # Return False: do not suppress exceptions raised inside the with-block
        return False
