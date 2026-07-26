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

# A definitely-on-sale-right-now movie (control) and the actual target.
PAGES = {
    "toy_story_5_control": "https://www.fandango.com/toy-story-5-2026-243393/movie-overview",
    "odyssey_target": "https://www.fandango.com/the-odyssey-2026-241283/movie-overview?date=2026-08-21",
}

NYC = {"latitude": 40.7128, "longitude": -74.0060}


def probe(page, label, url):
    print(f"\n===== {label}: {url} =====")
    page.goto(url, wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(3000)
    text = page.inner_text("body")

    print("notify-me placeholder present:", "notify you when tickets go on sale" in text)
    print("IMAX mentions:", text.count("IMAX"))
    for chain in ["AMC", "Regal", "Cinemark", "Marcus"]:
        print(f"{chain} mentions:", text.count(chain))
    print("BUY TICKETS occurrences:", text.count("BUY TICKETS"))
    print("--- first 400 chars of body text ---")
    print(text[:400].replace("\n", " | "))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            geolocation=NYC,
            permissions=["geolocation"],
            locale="en-US",
        )
        page = context.new_page()
        for label, url in PAGES.items():
            try:
                probe(page, label, url)
            except Exception as e:
                print(f"ERROR probing {label}: {e}")
        browser.close()


if __name__ == "__main__":
    main()
