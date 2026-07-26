---
trigger: always_on
---

Task: Refactor DOM Scraping Logic to Return Data and Live Playwright Locators

**Context & Objective:**
We need to refactor the data extraction logic in `app/browser.py` and its invocation in `main.py`. The system targets a specific table inside `#jumpermanifest-body > div:nth-child(2) > div > div:nth-child(1)` to extract flight load information. 

To prepare for an upcoming feature that will take DOM-specific screenshots, our extraction methods must return both the cleaned text data AND the live Playwright `Locator` object for each respective element. We must use clean OOP design, Playwright's native locator chaining, and the Single Responsibility Principle.

**Step 1: Update `app/browser.py` (`BrowserController` class)**
Import `Locator` from `playwright.sync_api` for strict type hinting. Implement two granular helper methods and one public coordinating method:

1. `_get_load_number(self, base_selector: str) -> tuple[str, Locator]`:
   * Use Playwright locator chaining to find the first `<table>` inside `base_selector`.
   * Target the 1st `<td>` (`.nth(0)`) or specifically the `.load-info-big` span.
   * Extract and clean (strip whitespace/newlines) the inner text representing the load number (e.g., "10").
   * Store the target `Locator` object pointing to this DOM section.
   * Implement robust try/except error handling that logs warnings and raises a descriptive `RuntimeError` if extraction fails.
   * Return a tuple containing both: `(load_text, target_locator)`.

2. `_get_eta(self, base_selector: str) -> tuple[str, Locator]`:
   * Use Playwright locator chaining to find the first `<table>` inside `base_selector`.
   * Target the 2nd `<td>` (`.nth(1)`) or specifically the `.load-info-mins` span.
   * Extract and clean (strip whitespace/newlines) the inner text representing the ETA (e.g., "30 Mins").
   * Store the target `Locator` object pointing to this DOM section.
   * Implement robust try/except error handling that logs warnings and raises a descriptive `RuntimeError` if extraction fails.
   * Return a tuple containing both: `(eta_text, target_locator)`.

3. `get_flight_status(self, selector: str) -> dict[str, any]`:
   * Acts as the single public coordinator method called by `main.py`.
   * Construct the full row path: `f"{selector} > div:nth-child(2) > div > div:nth-child(1)"`.
   * Explicitly wait for this base selector to be visible using `self._page.wait_for_selector()`.
   * Call `self._get_load_number(base_path)` and unpack the resulting tuple into `load_num` and `load_locator`.
   * Call `self._get_eta(base_path)` and unpack the resulting tuple into `eta` and `eta_locator`.
   * Log the text results cleanly (do not attempt to log the raw Locator object as a string).
   * Return a structured Python dictionary ready for future screenshot operations:
     `{"load_number": load_num, "load_locator": load_locator, "eta": eta, "eta_locator": eta_locator}`.

**Step 2: Update `main.py` (The Orchestrator)**
* Remove any legacy calls to `list_child_elements()` or standalone `get_eta()` functions inside the execution block.
* Inside the `with BrowserController(config) as browser:` context manager, call:
  `status = browser.get_flight_status(config.target_selector)`
* Log the extracted text values (`status["load_number"]` and `status["eta"]`) to confirm successful execution before the cycle terminates or sleeps.
* Note: The `status["load_locator"]` and `status["eta_locator"]` objects are now preserved in the dictionary and ready to be passed into future screenshot methods.

**Strict Constraints:**
* Rely purely on Playwright locator chaining (`.locator().first.locator().nth()`) rather than Python `for` loops for DOM traversal.
* Maintain strict type hinting (using `tuple[str, Locator]` and `dict[str, any]`) and docstrings for all new methods.
* Do not hardcode any CSS selectors or URLs outside of the dynamic `selector` variable passed from `Config`.