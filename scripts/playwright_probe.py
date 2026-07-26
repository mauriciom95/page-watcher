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
        page.wait_for_timeout(8000)
        dump_interactive_elements(page)
        page.screenshot(path="/tmp/toy_story_5.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
