#!/usr/bin/env python3
"""
Final validation: navigate to the actual Odyssey watcher URL (with the real
target date), force the zip to 10019 via the location-overlay UI (the only
mechanism that actually works - query params are ignored), then check for
an "IMAX" format-filter chip, which only appears when that format has real
bookable inventory for the selected date/location.
"""
from playwright.sync_api import sync_playwright

URL = "https://www.fandango.com/the-odyssey-2026-241283/movie-overview?date=2026-08-21"
TARGET_ZIP = "10019"
NYC = {"latitude": 40.7128, "longitude": -74.0060}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(geolocation=NYC, permissions=["geolocation"], locale="en-US")
        page = context.new_page()
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(5000)

        page.locator(".js-location-overlay").first.click()
        page.wait_for_timeout(1500)
        page.locator("#setLocationSearchInput").first.fill(TARGET_ZIP)
        page.wait_for_timeout(1000)
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)

        print("Location button after:", page.locator(".js-location-overlay").first.inner_text())

        text = page.inner_text("body")
        idx = text.find("THEATERS NEAR")
        print("--- THEATERS NEAR section ---")
        print(text[idx:idx + 800] if idx >= 0 else "NOT FOUND")

        imax_chips = page.locator(".format-filter__list-item", has_text="IMAX")
        print("\nIMAX format-filter chip count:", imax_chips.count())

        any_showtime = page.locator(".showtimes-btn-list__item")
        print("Any bookable showtime slots:", any_showtime.count())

        page.screenshot(path="/tmp/odyssey_final.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
