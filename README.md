# page-watcher

Watches web pages for a condition (text that should appear or disappear) and
pushes a phone notification via [ntfy.sh](https://ntfy.sh) the moment it
happens. Runs on a schedule via GitHub Actions — no server to maintain.

## How it works

- Each file in `watchers/*.json` describes one thing to watch: a URL, a list
  of substrings that must be **present**, and a list that must be **absent**
  for the watcher to be considered "matched" (i.e. the condition you care
  about is true).
- `check.py` fetches every enabled watcher's URL, evaluates the condition,
  and compares it to the last known result stored in `state/state.json`.
- A watcher is reported as `TRIGGERED` only on the transition from
  not-matched to matched (so you're notified once, not on every run), and
  `check.py` posts to the `NTFY_TOPIC` ntfy topic when that happens.
- `.github/workflows/check.yml` runs `check.py` every 10 minutes, then
  commits the updated `state/state.json` back to the repo so state persists
  across runs (each run is a fresh checkout). The repo is public so this
  runs on GitHub's free, unlimited Actions minutes for public repos.

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

GitHub disables scheduled workflows on a repo after 60 days with no commits
at all. Since the workflow only commits when state actually changes, a
watcher that never flips could in theory go quiet after 60 days — if that
happens, any commit (or opening the Actions tab and re-enabling) restarts it.
