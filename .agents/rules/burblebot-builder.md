---
trigger: always_on
---

## Task: Implement Split Closure Monitoring, Dynamic Pathing Manifest Screenshots, and Duplicate Prevention

### 1. Update `app/browser.py`
Refactor the closure monitoring and screenshot logic into two distinct, modular methods inside the `BrowserController` class:

- **Method 1: `wait_for_flight_closed(self, status_dict, output_path, poll_interval_s=30, max_duration_s=2700)`**
  - Monitors the first manifest card for load closure using modular internal helpers (`_check_active_section`, `_parse_eta_minutes`, `_get_poll_interval`, `_should_recycle_session`, `_is_date_rolled_over`).
  - Implements dynamic polling: polls every 5s when `ETA <= 1` (including 0, -1, -2), otherwise every 30s.
  - Caches rolling in-memory screenshot bytes during the fast-polling window.
  - If `"Closed"` is detected, immediately invokes `self.take_manifest_screenshot(status_dict, output_path)`.
  - If the section vanishes before `"Closed"` is detected, writes the in-memory fallback screenshot to disk and logs a `WARNING`.
  - Enforces Rule 1: Never recycles the session on a weather hold if `ETA <= 5`.

- **Method 2: `take_manifest_screenshot(self, status_dict, output_path)`**
  - Dedicated entirely to capturing the screenshot.
  - Executes `.screenshot()` directly on the target manifest locator.

### 2. Update `main.py`
Modify the main orchestrator loop to call the waiting function: `browser.wait_for_flight_closed(status_dict, output_path_str)`.
- Ensure duplicate-prevention logic (`output_file.exists()`) is maintained in the main loop to prevent re-triggering after a flight is closed.
- Modify the orchestrator loop to construct the output file path dynamically using the configured destination, current date, and load number:
  ```python
  output_file = dest_dir / today / f"load_num_{load_num}.png"
  ```