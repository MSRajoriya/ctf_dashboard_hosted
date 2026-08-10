# CTF Tracker Dashboard

**Live: [msrajoriya.github.io/ctf_dashboard_hosted](https://msrajoriya.github.io/ctf_dashboard_hosted/)**

Live CTF tracker, auto-refreshed every 15 min via GitHub Actions, served free
via GitHub Pages. Current version: see the footer on the live site, or run
`python3 fetch_and_render.py --version`.

## How it works

- `fetch_and_render.py` pulls online events from CTFtime server-side (dodges
  the browser CORS block CTFtime's API has) and writes a static `index.html`
  with the data embedded.
- `.github/workflows/update.yml` runs that script on a schedule inside
  GitHub's own servers, then commits the regenerated `index.html` back to
  the repo.
- GitHub Pages serves whatever's in the repo as a website. Every commit from
  the workflow = a fresh deploy, automatically.

"Real-time" here means "as fresh as the last 15-min tick," not live-on-load —
worth knowing going in. If you want true live-on-load later, that's the
Cloudflare Worker route from before; this repo doesn't block you from adding
that on top.

## What's on the dashboard

- Live/upcoming CTF events, online-only (onsite events excluded)
- Timeline chart + format breakdown doughnut (Chart.js, with a graceful
  text fallback if the CDN script fails to load)
- Organizer's country flag next to each event name (best-effort, via a
  cached per-team lookup — CTFtime doesn't expose this on the events list
  directly)
- Best-effort challenge category guess (AI/ML, Web, Pwn, Reverse Eng.,
  Crypto, Forensics, OSINT, Web3, Hardware, Robotics) from keywords in the
  title/description — clearly labeled "(guessed)" since CTFtime doesn't
  publish real category data for most events ahead of time
- All times shown in IST, regardless of viewer's browser timezone
- Live GitHub Actions status badge (pulled from GitHub itself, not faked)
- Version number in the statusbar/footer

## Repo layout

```
ctf_dashboard_hosted/
├── fetch_and_render.py       # fetch CTFtime + render the HTML
├── assets/
│   └── hero-bg.jpg           # dashboard background image
├── .github/workflows/
│   └── update.yml            # scheduled Action, runs every 15 min
├── index.html                # generated — do not hand-edit, it gets
│                              # overwritten on every run
├── CHANGELOG.md
└── README.md
```

## Deploy steps (from scratch, if you're forking this)

```bash
# 1. From this folder, init git and make the first commit
cd ctf_dashboard_hosted
git init
git add .
git commit -m "init: ctf dashboard"

# 2. Create the repo on GitHub (via web UI, or gh cli if you have it)
gh repo create ctf_dashboard_hosted --public --source=. --push

# 3. Generate a first index.html so Pages has something to serve
python3 fetch_and_render.py --out index.html
git add index.html
git commit -m "chore: initial dashboard render"
git push
```

**Note on branch name:** `gh repo create` and VSCode's "Publish to GitHub"
both default to `master`, not `main` — check `git branch` and make sure the
Pages branch setting (next step) matches whichever one your repo actually
uses.

## Enable GitHub Pages

1. On the repo page: **Settings → Pages**
2. Under "Build and deployment", set **Source: Deploy from a branch**
3. Branch: `master` (or `main`, whichever yours is), folder: `/ (root)` → **Save**
4. Your dashboard is live at `https://<you>.github.io/<repo-name>/`
   (takes a minute or two on first deploy)

## Verify the automation

- Go to the repo's **Actions** tab — you should see "Update CTF Dashboard"
  runs appear every 15 min.
- You can trigger one immediately: Actions tab → Update CTF Dashboard →
  **Run workflow**.
- If a run fails, click into it — most likely cause is CTFtime rate-limiting
  or a transient network error (the fetcher retries once automatically
  before giving up); the script exits non-zero rather than writing a broken
  page, so a failed run just means Pages keeps serving the last good version.

## Working locally without conflicts

The Actions workflow commits `index.html` on its own schedule. If you also
regenerate and commit it locally, you'll hit merge conflicts on that file.
Before making local changes:

```bash
git pull origin master   # always pull first, not just when push fails
```

If you do hit a conflict on `index.html` specifically, don't hand-resolve it
— just take your local version and regenerate:

```bash
git checkout --ours index.html
git add index.html
git commit -m "merge: resolve index.html conflict"
python3 fetch_and_render.py --out index.html
git add . && git commit -m "chore: regenerate" && git push
```

## Running tests / lint locally

```bash
pip install pytest ruff mypy --break-system-packages
pytest tests/ -v
ruff check .
mypy fetch_and_render.py
```

Same checks run automatically on every push via `.github/workflows/ci.yml`
(separate from the scheduled `update.yml` — CI checks code quality, the
other one just fetches fresh data).

## Notes / known limitations

- Onsite-only events are excluded (online is the closest proxy CTFtime
  offers for "individually joinable").
- HackTheBox isn't included — no open public feed, only session-authenticated.
- `restrictions` column (Open / Invitation only / Academic) is shown but not
  filtered — check it per event.
- Country flag = the *organizing team's* country, not "where the CTF is
  held" (most tracked events are online-only anyway).
- Categories are a keyword-based guess, not real CTFtime data — most events
  will show "General" since most titles don't hint at challenge type.

See `CHANGELOG.md` for the version history.
