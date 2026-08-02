# ctf-dashboard (hosted)

Live CTF tracker, auto-refreshed every 15 min via GitHub Actions, served free
via GitHub Pages.

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

## Deploy steps (from WSL)

```bash
# 1. From this folder, init git and make the first commit
cd ctf_dashboard_hosted
git init
git add .
git commit -m "init: ctf dashboard"

# 2. Create the repo on GitHub (via web UI, or gh cli if you have it)
gh repo create ctf-dashboard --public --source=. --push
# — or manually: create an empty repo on github.com, then:
git remote add origin https://github.com/<you>/ctf-dashboard.git
git branch -M main
git push -u origin main

# 3. Generate a first index.html so Pages has something to serve
python3 fetch_and_render.py --out index.html
git add index.html
git commit -m "chore: initial dashboard render"
git push
```

## Enable GitHub Pages

1. On the repo page: **Settings → Pages**
2. Under "Build and deployment", set **Source: Deploy from a branch**
3. Branch: `main`, folder: `/ (root)` → **Save**
4. Your dashboard is live at `https://<you>.github.io/ctf-dashboard/`
   (takes a minute or two on first deploy)

## Verify the automation

- Go to the repo's **Actions** tab — you should see "Update CTF Dashboard"
  runs appear every 15 min.
- You can trigger one immediately: Actions tab → Update CTF Dashboard →
  **Run workflow**.
- If a run fails, click into it — most likely cause is CTFtime rate-limiting
  or a transient network error; the script exits non-zero rather than
  writing a broken page, so a failed run just means Pages keeps serving the
  last good version.

## Notes carried over from the local version

- Onsite-only events are excluded (online is the closest proxy CTFtime
  offers for "individually joinable").
- HackTheBox isn't included — no open public feed, only session-authenticated.
- `restrictions` column (Open / Invitation only / Academic) is shown but not
  filtered — check it per event.
