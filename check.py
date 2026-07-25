#!/usr/bin/env python3
"""
Fetches each enabled watcher's URL, evaluates its condition, and diffs
against the last known state. Prints one JSON line per watcher to stdout
so a calling agent can decide what to notify about, and rewrites
state/state.json with the latest results.

This script never sends notifications itself — it only detects state
transitions. The calling routine (a Claude Code agent with a Gmail MCP
connection) is responsible for emailing on TRIGGERED watchers and
committing the updated state file back to git.
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
        watchers.append(cfg)
    return watchers


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def evaluate(html, cfg):
    for needle in cfg.get("require_present", []):
        if needle not in html:
            return False
    for needle in cfg.get("require_absent", []):
        if needle in html:
            return False
    return True


def main():
    state = load_state()
    watchers = load_watchers()
    now = datetime.now(timezone.utc).isoformat()
    results = []

    for cfg in watchers:
        wid = cfg["id"]
        prev = state.get(wid, {})

        if not cfg.get("enabled", True):
            results.append({"id": wid, "status": "SKIPPED_DISABLED"})
            continue

        try:
            html = fetch(cfg["url"])
            matched = evaluate(html, cfg)
            error = None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
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

        results.append({
            "id": wid,
            "name": cfg.get("name", wid),
            "url": cfg["url"],
            "status": status,
            "matched": matched,
            "error": error,
            "notify_subject": cfg.get("notify_subject"),
            "notify_body": (cfg.get("notify_body") or "").format(url=cfg["url"]),
        })

    save_state(state)

    for r in results:
        print(json.dumps(r))

    if any(r.get("status") == "TRIGGERED" for r in results):
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
