from __future__ import annotations

import time
from typing import Callable, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.config import DEFAULT_TIMEOUT, IRCTC_URL


class IRCTCAssistant:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.driver = None
        self.log_callback = log_callback or (lambda message: None)

    def log(self, message: str) -> None:
        self.log_callback(message)

    def _wait(self, locator, timeout: int = DEFAULT_TIMEOUT):
        return WebDriverWait(self.driver, timeout).until(locator)

    def start_browser(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass

        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(IRCTC_URL)
        self.log("Browser opened and IRCTC page loaded.")

    def close(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.log("Browser closed.")

    def login(self, username: str, password: str) -> None:
        if self.driver is None:
            raise RuntimeError("Browser is not running. Start browser first.")

        username_candidates = [
            (By.ID, "userId"),
            (By.NAME, "userid"),
            (By.NAME, "userName"),
            (By.XPATH, "//input[contains(@placeholder, 'User') or contains(@placeholder, 'Username')]"),
            (By.XPATH, "//input[@type='text']"),
        ]

        password_candidates = [
            (By.ID, "pwd"),
            (By.NAME, "password"),
            (By.XPATH, "//input[@type='password']"),
        ]

        user_input = None
        for by, value in username_candidates:
            try:
                user_input = self.driver.find_element(by, value)
                break
            except Exception:
                continue

        pass_input = None
        for by, value in password_candidates:
            try:
                pass_input = self.driver.find_element(by, value)
                break
            except Exception:
                continue

        if user_input is None or pass_input is None:
            raise RuntimeError("Could not find login fields. IRCTC page layout may have changed.")

        user_input.clear()
        user_input.send_keys(username)

        pass_input.clear()
        pass_input.send_keys(password)

        try:
            login_button = self.driver.find_element(By.XPATH, "//button[contains(text(),'LOGIN') or contains(text(),'Log In')]")
            login_button.click()
        except Exception:
            self.log("Login button not found. Please complete the authentication manually if OTP/captcha is shown.")

        self.log("Login form submitted. If OTP or CAPTCHA is required, complete it manually before continuing.")

    def search_trains(self, from_station: str, to_station: str, journey_date: str, travel_class: str) -> List[str]:
        if self.driver is None:
            raise RuntimeError("Browser is not running. Start browser first.")

        self.log(f"Searching for trains from {from_station} to {to_station} on {journey_date}.")

        source_input = self._find_field_by_candidates([
            (By.XPATH, "//input[contains(@placeholder, 'From*') or @placeholder='From*' or @name='fromStation']"),
            (By.XPATH, "//input[contains(@placeholder, 'FROM') or @name='from']"),
            (By.ID, "fromStation"),
        ])

        destination_input = self._find_field_by_candidates([
            (By.XPATH, "//input[contains(@placeholder, 'To*') or @placeholder='To*' or @name='toStation']"),
            (By.XPATH, "//input[contains(@placeholder, 'TO') or @name='to']"),
            (By.ID, "toStation"),
        ])

        source_input.clear()
        source_input.send_keys(from_station)
        time.sleep(1)
        source_input.send_keys(Keys.ENTER)

        destination_input.clear()
        destination_input.send_keys(to_station)
        time.sleep(1)
        destination_input.send_keys(Keys.ENTER)

        date_input = self._find_field_by_candidates([
            (By.XPATH, "//input[contains(@placeholder, 'Journey Date') or @name='journeyDate']"),
            (By.XPATH, "//input[contains(@placeholder, 'Date') or @name='date']"),
        ])
        date_input.clear()
        date_input.send_keys(journey_date)

        try:
            class_dropdown = self.driver.find_element(By.XPATH, "//select[contains(@name, 'class') or contains(@id, 'class')]" )
            class_dropdown.send_keys(travel_class)
        except Exception:
            self.log("Class selector not found. Continuing without changing class.")

        try:
            search_button = self.driver.find_element(By.XPATH, "//button[contains(text(),'Search') or contains(text(),'Find Trains')]" )
            search_button.click()
        except Exception:
            self.log("Search button not found. Please click search manually in browser.")

        self.log("Search submitted. Waiting for train results...")
        time.sleep(5)

        result_rows = self._fetch_search_results()
        if not result_rows:
            self.log("No search results found yet. Please verify the station or page state.")
        else:
            self.log(f"Found {len(result_rows)} candidate result(s).")
        return result_rows

    def _fetch_search_results(self) -> List[str]:
        candidate_selectors = [
            "//div[contains(@class,'train') or contains(@class,'ng-star-inserted')]",
            "//tr[contains(@class,'trainRow') or contains(@class,'table-row')]",
            "//div[contains(@class,'result')]",
        ]

        found: List[str] = []
        for selector in candidate_selectors:
            try:
                rows = self.driver.find_elements(By.XPATH, selector)
                for row in rows:
                    text = (row.text or "").strip()
                    if text and len(text) > 10:
                        found.append(text)
            except Exception:
                continue

        unique: List[str] = []
        seen = set()
        for item in found:
            normalized = item.replace("\n", " | ")
            if normalized not in seen:
                seen.add(normalized)
                unique.append(normalized)

        return unique[:20]

    def _find_field_by_candidates(self, candidates):
        for by, value in candidates:
            try:
                return self.driver.find_element(by, value)
            except Exception:
                continue
        raise RuntimeError(f"Could not find a matching input field. Candidates: {candidates}")

