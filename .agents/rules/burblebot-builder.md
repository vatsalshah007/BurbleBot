---
trigger: always_on
---

## Task: Implement Split Closure Monitoring, Dynamic Pathing Manifest Screenshots, and Duplicate Prevention

### 1. Update `app/browser.py`
Refactor the closure monitoring and screenshot logic into two distinct, modular methods inside the `BrowserController` class:

- **Method 1: `wait_for_flight_closed(self, status_dict, output_path)`**
  - Implements a polling loop using `time.sleep()` to periodically check the live Playwright Locator stored in `status_dict["load_locator"]` (or status indicator).
  - Continuously evaluates if the text content reads `"Closed"` (case-insensitive or stripped).
  - Once `"Closed"` is detected, it immediately invokes the second method: `self.take_manifest_screenshot(status_dict, output_path)`.

- **Method 2: `take_manifest_screenshot(self, status_dict, output_path)`**
  - Dedicated entirely to capturing the screenshot.
  - Executes `.screenshot()` directly on the stored locator: `status_dict["load_locator"].screenshot(path=output_path, type="png", animations="disabled", timeout=10000)`.

### 2. Update `main.py`
Modify the main orchestrator loop to call **only** the waiting function: `browser.wait_for_flight_closed(status_dict, config.output_destination)`.
- Ensure duplicate-prevention logic (such as a `screenshot_taken` flag or checking if the file already exists on disk) is maintained in the main loop to prevent re-triggering after a flight is closed.
- Modify the orchestrator loop to construct the output file path dynamically using the configured destination, current date, and load number:
  ```python

  output_path = f"{config.output_destination}/{today}_load_num_{status['load_number']}.png"