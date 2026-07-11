"""
config.py — Configuration loader for BurbleBot.

All runtime configuration is ingested exclusively from environment variables.
No sensitive data is ever hardcoded. Raises EnvironmentError on startup
if any required variable is missing or empty.
"""

import os


class Config:
    """
    Loads and validates all environment variables required by BurbleBot.

    Required:
        TARGET_URL          The URL to navigate to.

    Optional:
        TARGET_SELECTOR     CSS selector to wait for after navigation.
        SLEEP_INTERVAL      Seconds between capture cycles (default: 60).
        OUTPUT_DESTINATION  File path for screenshot output (default: /app/output.png).
    """

    def __init__(self) -> None:
        self.target_url: str = os.getenv("TARGET_URL", "")
        self.target_selector: str = os.getenv("TARGET_SELECTOR", "")
        self.sleep_interval: int = int(os.getenv("SLEEP_INTERVAL", "60"))
        self.output_destination: str = os.getenv(
            "OUTPUT_DESTINATION", "/app/output.png"
        )
        self._validate()

    def _validate(self) -> None:
        """
        Validates required environment variables.
        Fails fast with a descriptive EnvironmentError so the process
        never silently operates on missing configuration.
        """
        if not self.target_url or not self.target_url.strip():
            raise EnvironmentError(
                "Missing required environment variable: TARGET_URL\n"
                "Set it in your .env file or export it before running:\n"
                "  export TARGET_URL=https://example.com"
            )

        if self.sleep_interval < 1:
            raise EnvironmentError(
                f"SLEEP_INTERVAL must be a positive integer, got: {self.sleep_interval}"
            )

    def __repr__(self) -> str:
        return (
            f"Config("
            f"target_url={self.target_url!r}, "
            f"target_selector={self.target_selector!r}, "
            f"sleep_interval={self.sleep_interval}, "
            f"output_destination={self.output_destination!r})"
        )
