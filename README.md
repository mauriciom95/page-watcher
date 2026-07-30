# page-watcher

Watches web pages for a condition and pushes a phone notification via
[ntfy.sh](https://ntfy.sh) the moment it happens. Runs on a schedule via
GitHub Actions — no server to maintain.

## How it works

- Each file in `watchers/*.json` describes one thing to watch and how to
  evaluate it (see "Two check modes" below).
- `check.py` runs every enabled watcher, evaluates its condition, and
  compares it to the last known result stored in `state/state.json`.
- A watcher is reported as `TRIGGERED` only on the transition from
  not-matched to matched (so you're notified once, not on every run), and
  `check.py` posts to the `NTFY_TOPIC` ntfy topic when that happens.
- `.github/workflows/check.yml` runs `check.py` every 10 minutes, then
  commits the updated `state/state.json` back to the repo so state persists
  across runs (each run is a fresh checkout). The repo is public so this
  runs on GitHub's free, unlimited Actions minutes for public repos.

## Two check modes

Set per-watcher via the `"render"` field:

- **`"http"` (default)** — plain HTTP fetch, no browser. Checks
  `require_present` / `require_absent` substrings against the raw HTML.
  Fast, but blind to anything JavaScript renders client-side.
- **`"playwright"`** — renders the page in a real headless browser
  (installed in CI via `requirements.txt` + `playwright install`), runs an
  optional scripted `"actions"` sequence (click/fill/press/wait — e.g. to
  set a delivery location the site requires before it'll show real data),
  then checks for a specific element via `"success_selector"` instead of
  raw text.

## Two evaluation modes

Set per-watcher via the `"mode"` field:

- **`"match"` (default)** — the render backend returns true/false, and the
  watcher is `TRIGGERED` on the transition from not-matched to matched.
  This is what both check modes above describe.
- **`"diff"`** — instead of a boolean, each run captures a text snapshot
  of the page and compares it to the previous run's snapshot. `TRIGGERED`
  fires on *any* change at all, not just a specific condition. The first
  run only establishes a baseline (no notification). Useful when you don't
  know in advance what the meaningful change will look like (e.g. "alert
  me if anything on this product page changes, especially stock").
  - For `"render": "playwright"`, the snapshot is the inner text of the
    CSS selectors in `"diff_selectors"` (default `["body"]` — the whole
    visible page). Scope it tighter (e.g. a specific product-info
    container) once you know the DOM, to cut noise from things like
    rotating recommendation carousels.
  - For `"render": "http"`, the snapshot is the raw HTML response.
  - The changed lines (from a unified diff, capped at 25 lines) are
    available to `notify_body` as `{diff}`, alongside `{url}`.

**Use `"playwright"` whenever the target content is JS-rendered or
personalized by location** — verify this by comparing `curl`'s raw output
against what a real browser shows before picking a mode. See the Odyssey
watcher below for a worked example of why this matters: a plain-text check
against that page would have silently never worked, and a naive "does the
page contain the word IMAX" check would have been a false positive from
day one (that word already appears in marketing article titles on the page
regardless of ticket availability). Scoping the check to a specific
element (`.format-filter__list-item` with text "IMAX") avoids both traps.

## Notifications (ntfy.sh)

1. Install the ntfy app ([iOS](https://apps.apple.com/app/ntfy/id1625396347)/
   [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
   or use https://ntfy.sh/app, and subscribe to your topic.
2. Store that topic name as a repo secret so the workflow can use it without
   it appearing in code or logs:
   ```
   gh secret set NTFY_TOPIC --repo <owner>/page-watcher
   ```
3. Treat the topic name like a password — anyone who knows it can publish to
   (and read) that ntfy.sh topic, since the public server has no auth. It's
   stored only as an encrypted Actions secret (never in code, and masked in
   logs), which is why it's safe to keep even though this repo is public.
   Pick a long random string (e.g.
   `python3 -c "import secrets; print(secrets.token_hex(8))"`) — self-host
   ntfy or use a paid ntfy.sh account for stronger access control if wanted.

## Running it manually

```
pip install -r requirements.txt
playwright install chromium   # only needed for "playwright" watchers
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
- `ERROR` — fetch/render failed; `matched` falls back to the last known value
- `SKIPPED_DISABLED` — watcher has `"enabled": false`

## Adding a new watcher

Start with `watchers/example_lululemon.json` (a simple `"http"`-mode
template) or `watchers/odyssey_imax_aug20.json` (a `"playwright"`-mode
example with scripted actions), fill in a real URL, and set
`"enabled": true`.

Before writing the condition: fetch the page both ways and compare.

```
curl -sL -A "Mozilla/5.0 ..." "<url>" | less   # what check.py's http mode sees
```

If the content you care about isn't in that raw output, use `"playwright"`
mode instead — and scope `success_selector` to the specific element that
changes, not a page-wide text search, to avoid false positives from
unrelated text elsewhere on the page (headlines, ads, nav links, etc. all
count as "the page" if you just grep the whole body).

## Current watchers

- `odyssey_imax_aug20` — The Odyssey (2026) on Fandango. Uses `"playwright"`
  mode: forces the delivery location to zip 90028 (Hollywood/LA) via the site's
  location-picker UI (the `?zipcode=` query param is silently ignored —
  confirmed by testing), navigates to the 2026-08-21 showtimes view, and
  checks for an "IMAX" format-filter chip, which only renders when that
  format actually has bookable inventory for the selected date/location.
- `example_lululemon` — disabled template showing the pattern for a
  simple `"http"`-mode restock/availability watch on a product page.
- `lululemon_zeroed_in_shirt_0284` — Zeroed In Short Sleeve Shirt, color
  0284, on Lululemon. Uses `"playwright"` + `"diff"` mode: snapshots the
  whole visible page body on every run and notifies on any change (price,
  size/stock availability, etc.), rather than a single boolean condition.
  Deliberately broad (`diff_selectors: ["body"]`) since the goal is
  catching any change, not just one predicted condition — this means it
  may also fire on unrelated page churn (e.g. rotating recommendation
  carousels). Check the `{diff}` lines in the first few notifications and
  narrow `diff_selectors` to a specific product-info container if it's
  too noisy.

## Caveats

Many retail/ticketing sites render content client-side via JavaScript and
personalize it by inferred location. `"http"` mode is blind to both. Verify
your condition actually appears in `check.py`'s fetch (raw HTTP, no
browser) before relying on `"http"` mode — see "Adding a new watcher" above.

GitHub disables scheduled workflows on a repo after 60 days with no commits
at all. Since the workflow only commits when state actually changes, a
watcher that never flips could in theory go quiet after 60 days — if that
happens, any commit (or opening the Actions tab and re-enabling) restarts it.

Playwright browser binaries are cached between runs (`actions/cache`,
keyed on `requirements.txt`) to keep the 10-minute schedule fast; bumping
the pinned version in `requirements.txt` will trigger one slower run to
repopulate the cache.
