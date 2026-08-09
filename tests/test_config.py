"""
test_config.py — Unit tests for the Config class.

These tests run without a live browser or network connection.
Environment variables are patched per-test using monkeypatch to keep
tests isolated and side-effect free.
"""

import pytest

from app.config import Config


# ---------------------------------------------------------------------------
# Helper: sets all three required env vars so tests for optional fields
# don't accidentally fail on a missing required variable.
# ---------------------------------------------------------------------------
def _set_required(monkeypatch):
    monkeypatch.setenv("TARGET_URL", "https://example.com")
    monkeypatch.setenv("JUMPER_MANIFEST_BODY", "#jumpermanifest-body")
    monkeypatch.setenv("JUMPER_MANIFEST_LOAD", ".load-row")


class TestConfigSuccess:
    """Tests for valid configuration scenarios."""

    def test_loads_target_url(self, monkeypatch):
        """Config correctly reads TARGET_URL from the environment."""
        _set_required(monkeypatch)
        config = Config()
        assert config.target_url == "https://example.com"

    def test_loads_jumper_manifest_body(self, monkeypatch):
        """Config correctly reads JUMPER_MANIFEST_BODY from the environment."""
        _set_required(monkeypatch)
        config = Config()
        assert config.jumper_manifest_body == "#jumpermanifest-body"

    def test_loads_jumper_manifest_load(self, monkeypatch):
        """Config correctly reads JUMPER_MANIFEST_LOAD from the environment."""
        _set_required(monkeypatch)
        config = Config()
        assert config.jumper_manifest_load == ".load-row"

    def test_strips_quotes_from_jumper_manifest_body(self, monkeypatch):
        """Surrounding quotes are stripped from JUMPER_MANIFEST_BODY."""
        _set_required(monkeypatch)
        monkeypatch.setenv("JUMPER_MANIFEST_BODY", '"#jumpermanifest-body"')
        config = Config()
        assert config.jumper_manifest_body == "#jumpermanifest-body"

    def test_strips_quotes_from_jumper_manifest_load(self, monkeypatch):
        """Surrounding quotes are stripped from JUMPER_MANIFEST_LOAD."""
        _set_required(monkeypatch)
        monkeypatch.setenv("JUMPER_MANIFEST_LOAD", '".load-row"')
        config = Config()
        assert config.jumper_manifest_load == ".load-row"

    def test_default_sleep_interval(self, monkeypatch):
        """SLEEP_INTERVAL defaults to 60 when not set."""
        _set_required(monkeypatch)
        monkeypatch.delenv("SLEEP_INTERVAL", raising=False)
        config = Config()
        assert config.sleep_interval == 60

    def test_custom_sleep_interval(self, monkeypatch):
        """SLEEP_INTERVAL is correctly parsed as an integer."""
        _set_required(monkeypatch)
        monkeypatch.setenv("SLEEP_INTERVAL", "120")
        config = Config()
        assert config.sleep_interval == 120

    def test_default_output_destination(self, monkeypatch):
        """OUTPUT_DESTINATION defaults to /app/output.png when not set."""
        _set_required(monkeypatch)
        monkeypatch.delenv("OUTPUT_DESTINATION", raising=False)
        config = Config()
        assert config.output_destination == "/app/output.png"

    def test_custom_output_destination(self, monkeypatch):
        """OUTPUT_DESTINATION is correctly read from the environment."""
        _set_required(monkeypatch)
        monkeypatch.setenv("OUTPUT_DESTINATION", "/data/screenshots/output.png")
        config = Config()
        assert config.output_destination == "/data/screenshots/output.png"


class TestConfigValidationFailures:
    """Tests that Config raises EnvironmentError for invalid/missing required vars."""

    def test_raises_when_target_url_missing(self, monkeypatch):
        """EnvironmentError is raised when TARGET_URL is not set at all."""
        monkeypatch.delenv("TARGET_URL", raising=False)
        monkeypatch.setenv("JUMPER_MANIFEST_BODY", "#jumpermanifest-body")
        monkeypatch.setenv("JUMPER_MANIFEST_LOAD", ".load-row")
        with pytest.raises(EnvironmentError, match="TARGET_URL"):
            Config()

    def test_raises_when_target_url_is_empty_string(self, monkeypatch):
        """EnvironmentError is raised when TARGET_URL is set but empty."""
        monkeypatch.setenv("TARGET_URL", "")
        monkeypatch.setenv("JUMPER_MANIFEST_BODY", "#jumpermanifest-body")
        monkeypatch.setenv("JUMPER_MANIFEST_LOAD", ".load-row")
        with pytest.raises(EnvironmentError, match="TARGET_URL"):
            Config()

    def test_raises_when_target_url_is_whitespace_only(self, monkeypatch):
        """EnvironmentError is raised when TARGET_URL is only whitespace."""
        monkeypatch.setenv("TARGET_URL", "   ")
        monkeypatch.setenv("JUMPER_MANIFEST_BODY", "#jumpermanifest-body")
        monkeypatch.setenv("JUMPER_MANIFEST_LOAD", ".load-row")
        with pytest.raises(EnvironmentError, match="TARGET_URL"):
            Config()

    def test_raises_when_jumper_manifest_body_missing(self, monkeypatch):
        """EnvironmentError is raised when JUMPER_MANIFEST_BODY is not set."""
        monkeypatch.setenv("TARGET_URL", "https://example.com")
        monkeypatch.delenv("JUMPER_MANIFEST_BODY", raising=False)
        monkeypatch.setenv("JUMPER_MANIFEST_LOAD", ".load-row")
        with pytest.raises(EnvironmentError, match="JUMPER_MANIFEST_BODY"):
            Config()

    def test_raises_when_jumper_manifest_body_is_empty(self, monkeypatch):
        """EnvironmentError is raised when JUMPER_MANIFEST_BODY is empty."""
        monkeypatch.setenv("TARGET_URL", "https://example.com")
        monkeypatch.setenv("JUMPER_MANIFEST_BODY", "")
        monkeypatch.setenv("JUMPER_MANIFEST_LOAD", ".load-row")
        with pytest.raises(EnvironmentError, match="JUMPER_MANIFEST_BODY"):
            Config()

    def test_raises_when_jumper_manifest_load_missing(self, monkeypatch):
        """EnvironmentError is raised when JUMPER_MANIFEST_LOAD is not set."""
        monkeypatch.setenv("TARGET_URL", "https://example.com")
        monkeypatch.setenv("JUMPER_MANIFEST_BODY", "#jumpermanifest-body")
        monkeypatch.delenv("JUMPER_MANIFEST_LOAD", raising=False)
        with pytest.raises(EnvironmentError, match="JUMPER_MANIFEST_LOAD"):
            Config()

    def test_raises_when_jumper_manifest_load_is_empty(self, monkeypatch):
        """EnvironmentError is raised when JUMPER_MANIFEST_LOAD is empty."""
        monkeypatch.setenv("TARGET_URL", "https://example.com")
        monkeypatch.setenv("JUMPER_MANIFEST_BODY", "#jumpermanifest-body")
        monkeypatch.setenv("JUMPER_MANIFEST_LOAD", "")
        with pytest.raises(EnvironmentError, match="JUMPER_MANIFEST_LOAD"):
            Config()

    def test_raises_when_sleep_interval_is_zero(self, monkeypatch):
        """EnvironmentError is raised when SLEEP_INTERVAL is 0 (not positive)."""
        _set_required(monkeypatch)
        monkeypatch.setenv("SLEEP_INTERVAL", "0")
        with pytest.raises(EnvironmentError, match="SLEEP_INTERVAL"):
            Config()

    def test_raises_when_sleep_interval_is_negative(self, monkeypatch):
        """EnvironmentError is raised when SLEEP_INTERVAL is negative."""
        _set_required(monkeypatch)
        monkeypatch.setenv("SLEEP_INTERVAL", "-5")
        with pytest.raises(EnvironmentError, match="SLEEP_INTERVAL"):
            Config()
