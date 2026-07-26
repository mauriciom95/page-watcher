#!/usr/bin/env python3
"""
Fetches each enabled watcher's target, evaluates its condition, and diffs
against the last known state. Prints one JSON line per watcher to stdout,
rewrites state/state.json with the latest results, and — for any watcher
that just transitioned to matched (TRIGGERED) — pushes a notification via
ntfy.sh if NTFY_TOPIC is set in the environment.

Two evaluation backends, chosen per-watcher via the "render" field:
  - (default) "http": plain HTTP fetch, substring checks against the raw
    HTML (require_present / require_absent). Fast, no browser, but blind
    to anything JavaScript renders client-side.
  - "playwright": renders the page in a real headless browser, optionally
    runs a scripted sequence of UI interactions ("actions" - needed e.g.
    to set a delivery location on sites that require it), then checks for
    a specific element (success_selector) rather than raw text. Slower,
    but sees real client-rendered content and is far more precise since it
    can scope the check to a specific element instead of the whole page.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
WATCHERS_DIR = os.path.join(ROOT, "watchers")
STATE_PATH = os.path.join(ROOT, "state", "state.json")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")


def send_ntfy(title, message, url):
    if not NTFY_TOPIC:
        return
    req = urllib.request.Request(
        f"{NTFY_SERVER}/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Click": url,
            "Priority": "high",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"ntfy send failed: {e}", file=sys.stderr)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def load_watchers():
    watchers = []
    if not os.path.isdir(WATCHERS_DIR):
        return watchers
    for fname in sorted(os.listdir(WATCHERS_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(WATCHERS_DIR, fname)) as f:
            cfg = json.load(f)
        cfg.setdefault("id", os.path.splitext(fname)[0])
        cfg.setdefault("enabled", True)
        cfg.setdefault("render", "http")
        watchers.append(cfg)
    return watchers


def fetch_http(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def evaluate_http(cfg):
    html = fetch_http(cfg["url"])
    for needle in cfg.get("require_present", []):
        if needle not in html:
            return False
    for needle in cfg.get("require_absent", []):
        if needle in html:
            return False
    return True


def run_actions(page, actions):
    for action in actions:
        if "click" in action:
            page.locator(action["click"]).first.click()
        elif "fill" in action:
            page.locator(action["fill"]["selector"]).first.fill(action["fill"]["value"])
        elif "press" in action:
            page.keyboard.press(action["press"])
        elif "wait_ms" in action:
            page.wait_for_timeout(action["wait_ms"])
        else:
            raise ValueError(f"Unknown action: {action}")


def evaluate_playwright(page, cfg):
    page.goto(cfg["url"], wait_until="load", timeout=60000)
    page.wait_for_timeout(cfg.get("initial_wait_ms", 5000))
    run_actions(page, cfg.get("actions", []))

    sel = cfg["success_selector"]
    locator = page.locator(sel["selector"])
    if sel.get("has_text"):
        locator = locator.filter(has_text=sel["has_text"])
    return locator.count() > 0


def main():
    state = load_state()
    watchers = load_watchers()
    now = datetime.now(timezone.utc).isoformat()
    results = []

    needs_browser = any(w.get("enabled", True) and w.get("render") == "playwright" for w in watchers)
    browser = page = None
    playwright_ctx = None
    if needs_browser:
        from playwright.sync_api import sync_playwright
        playwright_ctx = sync_playwright().start()
        browser = playwright_ctx.chromium.launch()
        page = browser.new_context(locale="en-US").new_page()

    for cfg in watchers:
        wid = cfg["id"]
        prev = state.get(wid, {})

        if not cfg.get("enabled", True):
            results.append({"id": wid, "status": "SKIPPED_DISABLED"})
            continue

        try:
            if cfg["render"] == "playwright":
                matched = evaluate_playwright(page, cfg)
            else:
                matched = evaluate_http(cfg)
            error = None
        except Exception as e:
            matched = prev.get("last_result", False)
            error = str(e)

        was_true = prev.get("last_result", False)
        status = "ERROR" if error else ("TRIGGERED" if matched and not was_true else "OK")

        state[wid] = {
            "last_result": matched,
            "last_checked": now,
            "last_error": error,
            "last_notified": now if status == "TRIGGERED" else prev.get("last_notified"),
        }

        notify_subject = cfg.get("notify_subject") or cfg.get("name", wid)
        notify_body = (cfg.get("notify_body") or "").format(url=cfg["url"])

        results.append({
            "id": wid,
            "name": cfg.get("name", wid),
            "url": cfg["url"],
            "status": status,
            "matched": matched,
            "error": error,
            "notify_subject": notify_subject,
            "notify_body": notify_body,
        })

        if status == "TRIGGERED":
            send_ntfy(notify_subject, notify_body, cfg["url"])

    if browser:
        browser.close()
        playwright_ctx.stop()

    save_state(state)

    for r in results:
        print(json.dumps(r))


if __name__ == "__main__":
    main()
