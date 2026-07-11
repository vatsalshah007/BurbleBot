"""
browser.py — Playwright browser controller for BurbleBot.

Implements BrowserController as a context manager to guarantee the browser
session is always gracefully terminated — even when exceptions occur —
preventing memory leaks during 24/7 continuous operation.

Configured explicitly for ARM64 (Raspberry Pi 5) headless deployment.
"""

import logging

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

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
            url:        The URL to navigate to.
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
