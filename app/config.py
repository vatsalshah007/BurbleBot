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
        JUMPER_MANIFEST_BODY CSS selector for the Jumper Manifest Body.
        JUMPER_MANIFEST_LOAD CSS selector for the Jumper Manifest Load element.

    Optional:
        SLEEP_INTERVAL      Seconds between capture cycles (default: 60).
        OUTPUT_DESTINATION  File path for screenshot output (default: /app/output.png).
    """

    def __init__(self) -> None:
        self.target_url: str = os.getenv("TARGET_URL", "").strip('"\'')
        self.jumper_manifest_body: str = os.getenv(
            "JUMPER_MANIFEST_BODY", ""
        ).strip('"\'')
        self.jumper_manifest_load: str = os.getenv(
            "JUMPER_MANIFEST_LOAD", ""
        ).strip('"\'')
        self.sleep_interval: int = int(os.getenv("SLEEP_INTERVAL", "60"))
        self.output_destination: str = os.getenv(
            "OUTPUT_DESTINATION", "/app/output.png"
        ).strip('"\'')
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

        if not self.jumper_manifest_body or not self.jumper_manifest_body.strip():
            raise EnvironmentError(
                "Missing required environment variable: JUMPER_MANIFEST_BODY\n"
                "Set it in your .env file or export it before running:\n"
                "  export JUMPER_MANIFEST_BODY=#jumpermanifest-body"
            )

        if not self.jumper_manifest_load or not self.jumper_manifest_load.strip():
            raise EnvironmentError(
                "Missing required environment variable: JUMPER_MANIFEST_LOAD\n"
                "Set it in your .env file or export it before running:\n"
                "  export JUMPER_MANIFEST_LOAD=.load-row"
            )

        if self.sleep_interval < 1:
            raise EnvironmentError(
                f"SLEEP_INTERVAL must be a positive integer, got: {self.sleep_interval}"
            )

    def __repr__(self) -> str:
        return (
            f"Config("
            f"target_url={self.target_url!r}, "
            f"jumper_manifest_body={self.jumper_manifest_body!r}, "
            f"jumper_manifest_load={self.jumper_manifest_load!r}, "
            f"sleep_interval={self.sleep_interval}, "
            f"output_destination={self.output_destination!r})"
        )
