# page-watcher

Watches web pages for a condition (text that should appear or disappear) and
reports state transitions so a caller can notify on them. Built to run as a
scheduled cloud agent, but `check.py` works standalone anywhere Python 3 is
installed.

## How it works

- Each file in `watchers/*.json` describes one thing to watch: a URL, a list
  of substrings that must be **present**, and a list that must be **absent**
  for the watcher to be considered "matched" (i.e. the condition you care
  about is true).
- `check.py` fetches every enabled watcher's URL, evaluates the condition,
  and compares it to the last known result stored in `state/state.json`.
- A watcher is reported as `TRIGGERED` only on the transition from
  not-matched to matched (so you're notified once, not on every run).
- The script never sends notifications itself. It prints one JSON line per
  watcher to stdout. The scheduled agent that runs it is responsible for
  emailing on `TRIGGERED` watchers and committing the updated
  `state/state.json` back to the repo (so state persists across runs in a
  fresh sandbox).

## Running it manually

```
python3 check.py
```

Output is one JSON object per line, e.g.:

```json
{"id": "odyssey_imax_aug20", "name": "...", "url": "...", "status": "TRIGGERED", "matched": true, "error": null, "notify_subject": "...", "notify_body": "..."}
```

`status` is one of:
- `OK` — checked, condition not newly true (either still false, or already
  true last run and already notified)
- `TRIGGERED` — condition just became true; notify the user
- `ERROR` — fetch failed; `matched` falls back to the last known value
- `SKIPPED_DISABLED` — watcher has `"enabled": false`

## Adding a new watcher

Copy `watchers/example_lululemon.json`, fill in a real URL, and set
`"enabled": true`. Pick `require_present` / `require_absent` strings that
reliably distinguish the "before" and "after" states of the page — view
source (not just the rendered page) to confirm the text is actually present
in the raw HTML, since this script does a plain HTTP fetch and does not
execute JavaScript.

## Current watchers

- `odyssey_imax_aug20` — The Odyssey (2026) on Fandango. Watches for the
  "notify me, tickets aren't on sale yet" placeholder to disappear from the
  2026-08-21 showtimes view (i.e. tickets on sale for dates after Aug 20),
  while confirming the page mentions IMAX.
- `example_lululemon` — disabled template showing the pattern for a
  restock/availability watch on a product page.

## Caveats

Fandango (and many retail sites) render some content client-side via
JavaScript. This script only fetches raw HTML — it doesn't run a browser. If
a watcher's target content turns out to be JS-only, `require_present` /
`require_absent` checks against the raw HTML won't see it, and the watcher
will need a different strategy (e.g. finding the underlying API, or adding a
headless-browser fetch step).
