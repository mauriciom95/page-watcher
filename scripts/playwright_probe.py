#!/usr/bin/env python3
"""
One-off diagnostic: renders a Fandango movie-overview page with a real
browser (geolocation granted, so Fandango can resolve local theaters) and
reports whether real showtime/theater content appears, versus the raw-HTTP
fetch which only ever sees the generic pre-sale placeholder.

Not part of the regular watcher - run manually to validate the
headless-browser approach before wiring it into check.py.
"""
from playwright.sync_api import sync_playwright

URL = "https://www.fandango.com/toy-story-5-2026-243393/movie-overview"
NYC = {"latitude": 40.7128, "longitude": -74.0060}


def dump_interactive_elements(page):
    print("--- inputs ---")
    for el in page.locator("input").all():
        try:
            print({
                "name": el.get_attribute("name"),
                "id": el.get_attribute("id"),
                "placeholder": el.get_attribute("placeholder"),
                "aria-label": el.get_attribute("aria-label"),
                "value": el.get_attribute("value"),
            })
        except Exception as e:
            print("input error:", e)

    print("--- buttons/elements with 'zip' or 'location' in attrs ---")
    for el in page.locator("[class*=zip i], [class*=location i], [id*=zip i], [id*=location i], [aria-label*=zip i], [aria-label*=location i]").all():
        try:
            print({
                "tag": el.evaluate("e => e.tagName"),
                "class": el.get_attribute("class"),
                "id": el.get_attribute("id"),
                "aria-label": el.get_attribute("aria-label"),
                "text": el.inner_text()[:80],
            })
        except Exception as e:
            print("element error:", e)

    print("--- element containing the zip text 98848 ---")
    for el in page.get_by_text("98848").all():
        try:
            print({
                "tag": el.evaluate("e => e.tagName"),
                "class": el.get_attribute("class"),
                "outerHTML": el.evaluate("e => e.outerHTML")[:500],
            })
        except Exception as e:
            print("zip element error:", e)


TARGET_ZIP = "10019"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            geolocation=NYC,
            permissions=["geolocation"],
            locale="en-US",
        )
        page = context.new_page()
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(5000)

        print("Location button before:", page.locator(".js-location-overlay").first.inner_text())
        page.locator(".js-location-overlay").first.click()
        page.wait_for_timeout(2000)

        search_input = page.locator("#setLocationSearchInput").first
        search_input.fill(TARGET_ZIP)
        page.wait_for_timeout(2500)
        page.screenshot(path="/tmp/after_typing_zip.png", full_page=True)

        print("--- suggestion/dropdown items visible after typing ---")
        for el in page.locator("li:visible, [role=option]:visible, [class*=suggest i]:visible, [class*=dropdown i]:visible").all():
            try:
                t = el.inner_text().strip()
                if t:
                    print({"class": el.get_attribute("class"), "text": t[:80]})
            except Exception as e:
                pass

        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)
        page.screenshot(path="/tmp/after_enter.png", full_page=True)

        print("Location button after:", page.locator(".js-location-overlay").first.inner_text())
        print("--- body text near THEATERS NEAR ---")
        text = page.inner_text("body")
        idx = text.find("THEATERS NEAR")
        print(text[idx:idx+600] if idx >= 0 else "NOT FOUND")

        browser.close()


if __name__ == "__main__":
    main()
