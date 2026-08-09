"""
browser.py — Playwright browser controller for BurbleBot.

Implements BrowserController as a context manager to guarantee the browser
session is always gracefully terminated — even when exceptions occur —
preventing memory leaks during 24/7 continuous operation.

Configured explicitly for ARM64 (Raspberry Pi 5) headless deployment.
"""

import logging
import time
from pathlib import Path

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

    def __init__(self, config: Config) -> None:
        self._config = config
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

    def _get_load_number(self, base_selector: str) -> tuple[str, Locator]:
        """
        Extracts load number text and live Locator from the 1st <td> element
        inside the first <table> under base_selector.

        Args:
            base_selector: The parent DOM selector.

        Returns:
            Tuple of (cleaned load number text, target Locator object).

        Raises:
            RuntimeError: If extraction fails.
        """
        if self._page is None:
            raise RuntimeError("Browser session not started.")

        try:
            table_loc = self._page.locator(f"{base_selector} table").first
            load_locator = table_loc.locator("td").nth(0)
            load_text = load_locator.inner_text().strip().replace("\n", " ")
            return load_text, load_locator
        except Exception as exc:
            logger.warning("Failed to extract load number from '%s': %s", base_selector, exc)
            raise RuntimeError(f"Failed to extract load number from '{base_selector}': {exc}") from exc

    def _get_eta(self, base_selector: str) -> tuple[str, Locator]:
        """
        Extracts ETA text and live Locator from the 2nd <td> element
        inside the first <table> under base_selector.

        Args:
            base_selector: The parent DOM selector.

        Returns:
            Tuple of (cleaned ETA text, target Locator object).

        Raises:
            RuntimeError: If extraction fails.
        """
        if self._page is None:
            raise RuntimeError("Browser session not started.")

        try:
            table_loc = self._page.locator(f"{base_selector} table").first
            eta_locator = table_loc.locator("td").nth(1)
            eta_text = eta_locator.inner_text().strip()
            return eta_text, eta_locator
        except Exception as exc:
            logger.warning("Failed to extract ETA from '%s': %s", base_selector, exc)
            raise RuntimeError(f"Failed to extract ETA from '{base_selector}': {exc}") from exc

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

    def wait_for_flight_closed(
        self, status_dict: dict[str, any], output_path: str, poll_interval_s: int = 30
    ) -> None:
        """
        Polls the live Playwright Locator (eta_locator or load_locator) in status_dict using time.sleep().
        Continuously evaluates if the text content reads "Closed" (case-insensitive).
        Once "Closed" is detected, immediately invokes self.take_manifest_screenshot(status_dict, output_path).

        Args:
            status_dict: Dictionary containing status locators and 'load_number'.
            output_path: File path where screenshot will be saved.
            poll_interval_s: Sleep duration between polls in seconds (default: 30s).
        """
        poll_locator = status_dict.get("eta_locator") or status_dict.get("load_locator")
        if poll_locator is None:
            raise RuntimeError("Cannot wait for flight closed: missing locator in status_dict.")

        load_num = status_dict.get("load_number", "unknown")
        logger.info("Starting closure monitoring for Load %s (polling every %ds)...", load_num, poll_interval_s)

        while True:
            try:
                current_text = poll_locator.inner_text().strip()
                logger.debug("Load %s status poll text: '%s'", load_num, current_text)

                if current_text.lower() == "closed":
                    logger.info("Flight for Load %s is CLOSED. Invoking manifest screenshot...", load_num)
                    self.take_manifest_screenshot(status_dict, output_path)
                    break
            except Exception as exc:
                logger.warning("Error reading status text for Load %s during poll: %s", load_num, exc)

            time.sleep(poll_interval_s)

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

        if self._playwright is not None:
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
