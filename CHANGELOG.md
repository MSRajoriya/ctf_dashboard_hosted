# Changelog

All notable changes to the CTF Tracker Dashboard.

## v1.5.0
- Added best-effort category guessing (AI/ML, Robotics, Web, Pwn, Reverse Eng.,
  Crypto, Forensics, OSINT, Web3, Hardware) from title/description keywords.
  Clearly labeled "(guessed)" — CTFtime's API doesn't expose real challenge
  categories, so this is a heuristic, not authoritative data.
- Added version number, shown in the statusbar and footer, plus a `--version`
  CLI flag.

## v1.4.0
- Added organizing team's country flag next to each event name (via a cached
  per-team lookup against CTFtime's team API — not available on the events
  endpoint directly).
- Added live GitHub Actions status badge (pulled straight from GitHub, not
  faked client-side) plus an "auto-updates every 15 min" note.
- Fixed a real bug: a raw socket-read `TimeoutError` during the CTFtime fetch
  wasn't caught by the existing `URLError`/`HTTPError` handlers and crashed
  with a full traceback. Now caught explicitly, with a 2-attempt retry.
- Bumped `actions/checkout` and `actions/setup-python` to v7 (clears the
  Node.js 20 deprecation warning GitHub started surfacing on runs).

## v1.3.0
- Full redesign: "Aurora" theme (teal/coral/violet gradients, stat cards,
  Sora display font) replacing the original amber terminal theme.
- All displayed times forced to IST regardless of viewer's browser timezone
  or the GitHub Actions runner's UTC clock.
- Added author credit link in the header and footer.
- Renamed the on-page title to "CTF Tracker Dashboard".

## v1.2.0
- Set up GitHub Pages + GitHub Actions hosting: a scheduled workflow
  (`*/15 * * * *`) re-runs the fetcher and commits a fresh `index.html`,
  which Pages serves automatically — no server to maintain.

## v1.1.0
- Fixed charts silently failing to render: switched the Chart.js CDN from
  cdnjs (blocked by some browsers' tracking-prevention lists) to jsdelivr,
  dropped the moment.js date-adapter dependency (replaced with plain
  relative-hours math), and added a graceful fallback message if Chart.js
  fails to load for any reason — the event table never depends on it.

## v1.0.0
- Initial release: fetches online, individual-joinable CTF events from
  CTFtime's API server-side (avoids the browser CORS block CTFtime's API has
  no headers for), renders a static dashboard with a timeline chart, format
  breakdown doughnut, and event table with live countdowns.
