"""
test_browser_helpers.py — Unit tests for BrowserController helper functions.

Tests logic for:
- Date rollover detection
- ETA parsing (positive and negative minutes)
- Dynamic polling intervals (5s vs 30s)
- Weather hold session recycling (Rule 1 enforcement: never recycle when ETA <= 5)
"""

from unittest.mock import MagicMock
from app.browser import BrowserController
from app.config import Config


def _get_mock_controller() -> BrowserController:
    mock_config = MagicMock(spec=Config)
    mock_config.jumper_manifest_body = "#jumpermanifest-body"
    mock_config.jumper_manifest_load = "jumpermanifest-load"
    return BrowserController(mock_config)


class TestBrowserHelpers:
    def test_is_date_rolled_over(self):
        controller = _get_mock_controller()
        from datetime import datetime, timedelta

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        assert controller._is_date_rolled_over(today) is False
        assert controller._is_date_rolled_over(yesterday) is True

    def test_parse_eta_minutes_positive(self):
        controller = _get_mock_controller()
        assert controller._parse_eta_minutes("15 Mins") == 15
        assert controller._parse_eta_minutes("1 Min") == 1
        assert controller._parse_eta_minutes("0 Mins") == 0

    def test_parse_eta_minutes_negative(self):
        controller = _get_mock_controller()
        assert controller._parse_eta_minutes("-1 Min") == -1
        assert controller._parse_eta_minutes("-2 Mins") == -2
        assert controller._parse_eta_minutes(" -5 mins ") == -5

    def test_parse_eta_minutes_non_numeric(self):
        controller = _get_mock_controller()
        assert controller._parse_eta_minutes("Closed") is None
        assert controller._parse_eta_minutes("Hold") is None
        assert controller._parse_eta_minutes("") is None
        assert controller._parse_eta_minutes(None) is None

    def test_get_poll_interval(self):
        controller = _get_mock_controller()
        # Normal polling (30s) when ETA > 1 or non-numeric
        assert controller._get_poll_interval(15) == 30
        assert controller._get_poll_interval(2) == 30
        assert controller._get_poll_interval(None) == 30

        # Fast polling (5s) when ETA <= 1
        assert controller._get_poll_interval(1) == 5
        assert controller._get_poll_interval(0) == 5
        assert controller._get_poll_interval(-1) == 5
        assert controller._get_poll_interval(-3) == 5

    def test_should_recycle_session_rule_1_enforcement(self):
        controller = _get_mock_controller()
        max_duration = 2700  # 45 minutes

        # Within cycle duration -> never recycle
        assert controller._should_recycle_session(1000, 20, max_duration_s=max_duration) is False

        # Over cycle duration and ETA > 5 -> recycle allowed (weather hold / long delay)
        assert controller._should_recycle_session(2800, 20, max_duration_s=max_duration) is True
        assert controller._should_recycle_session(2800, 6, max_duration_s=max_duration) is True
        assert controller._should_recycle_session(2800, None, max_duration_s=max_duration) is True

        # Over cycle duration but Rule 1 applies (ETA <= 5) -> NEVER recycle
        assert controller._should_recycle_session(2800, 5, max_duration_s=max_duration) is False
        assert controller._should_recycle_session(2800, 3, max_duration_s=max_duration) is False
        assert controller._should_recycle_session(2800, 1, max_duration_s=max_duration) is False
        assert controller._should_recycle_session(2800, 0, max_duration_s=max_duration) is False
        assert controller._should_recycle_session(2800, -1, max_duration_s=max_duration) is False

    def test_get_load_number_and_eta_with_locator(self):
        controller = _get_mock_controller()
        controller._page = MagicMock()

        # Mock parent locator hierarchy: locator.locator("table").first.locator("td").nth(0/1)
        mock_parent = MagicMock()
        mock_table = MagicMock()
        mock_td_0 = MagicMock()
        mock_td_0.inner_text.return_value = "Supervan 21\n"
        mock_td_1 = MagicMock()
        mock_td_1.inner_text.return_value = " 10 Mins "

        mock_parent.locator.return_value.first = mock_table
        mock_table.locator.return_value.nth.side_effect = lambda idx: mock_td_0 if idx == 0 else mock_td_1

        load_text, load_loc = controller._get_load_number(mock_parent, timeout_ms=3000)
        assert load_text == "Supervan 21"
        assert load_loc == mock_td_0
        mock_td_0.inner_text.assert_called_once_with(timeout=3000)

        eta_text, eta_loc = controller._get_eta(mock_parent, timeout_ms=3000)
        assert eta_text == "10 Mins"
        assert eta_loc == mock_td_1
        mock_td_1.inner_text.assert_called_once_with(timeout=3000)

    def test_get_load_number_and_eta_with_str(self):
        controller = _get_mock_controller()
        mock_page = MagicMock()
        controller._page = mock_page

        mock_table = MagicMock()
        mock_td_0 = MagicMock()
        mock_td_0.inner_text.return_value = "Otter 5"
        mock_td_1 = MagicMock()
        mock_td_1.inner_text.return_value = "Closed"

        mock_page.locator.return_value.first = mock_table
        mock_table.locator.return_value.nth.side_effect = lambda idx: mock_td_0 if idx == 0 else mock_td_1

        load_text, load_loc = controller._get_load_number("#row-selector", timeout_ms=5000)
        assert load_text == "Otter 5"
        assert load_loc == mock_td_0

        eta_text, eta_loc = controller._get_eta("#row-selector", timeout_ms=5000)
        assert eta_text == "Closed"
        assert eta_loc == mock_td_1

