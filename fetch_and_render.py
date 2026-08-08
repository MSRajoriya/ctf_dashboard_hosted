#!/usr/bin/env python3
"""
CTF Tracker — fetches live/upcoming CTF events from CTFtime and renders
a static HTML dashboard with embedded data (Chart.js for visuals).

Why server-side: ctftime.org/api does not send Access-Control-Allow-Origin,
so a browser-side fetch() from the dashboard itself is blocked by CORS.
Fetching here (no browser involved) sidesteps that entirely. Run this on
a cron interval; the HTML it produces is what you keep open in a browser.

Usage:
    python3 fetch_and_render.py [--limit N] [--window-days N] [--out PATH]

No third-party deps — stdlib only (urllib), so it runs anywhere Python 3
is available in your WSL environment without a venv.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CTFTIME_API = "https://ctftime.org/api/v1/events/"
# CTFtime blocks generic/empty User-Agents — identify honestly.
HEADERS = {"User-Agent": "ctf-dashboard/1.0 (personal tracker; +local use)"}
TIMEOUT = 15


def fetch_events(limit: int, window_days: int, retries: int = 2) -> list[dict]:
    now = datetime.now(timezone.utc)
    start_ts = int((now - timedelta(days=2)).timestamp())   # small lookback to catch already-live events
    finish_ts = int((now + timedelta(days=window_days)).timestamp())

    params = f"?limit={limit}&start={start_ts}&finish={finish_ts}"
    url = CTFTIME_API + params
    req = urllib.request.Request(url, headers=HEADERS)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"CTFtime API returned HTTP {resp.status}")
                data = json.loads(resp.read().decode("utf-8"))
            last_error = None
            break  # success — stop retrying
        except urllib.error.HTTPError as e:
            last_error = RuntimeError(f"CTFtime API HTTP error: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            last_error = RuntimeError(f"Network error reaching CTFtime API: {e.reason}")
        except TimeoutError as e:
            # A raw socket-read timeout (e.g. CTFtime slow to send the response body)
            # is NOT wrapped as URLError by urllib — it slips past the handlers above
            # and crashes with a full traceback if left uncaught. Catch it explicitly.
            last_error = RuntimeError(f"Timed out reading CTFtime API response (attempt {attempt}/{retries})")
        except json.JSONDecodeError as e:
            last_error = RuntimeError(f"CTFtime API returned invalid JSON: {e}")
        except OSError as e:
            # Covers other low-level network failures (DNS, connection reset, etc.)
            last_error = RuntimeError(f"Network error reaching CTFtime API: {e}")

        if attempt < retries:
            time.sleep(2)  # brief pause before retrying — CTFtime can be transiently slow

    if last_error is not None:
        raise last_error


    if not isinstance(data, list):
        raise RuntimeError("Unexpected CTFtime API response shape (expected a list)")
    return data


def normalize(events: list[dict]) -> list[dict]:
    """Keep only online events (solo-joinable in principle) and shape fields
    the template needs. CTFtime has no explicit 'solo' flag — 'onsite: false'
    is the closest proxy, per your filtering choice."""
    now = datetime.now(timezone.utc)
    out = []
    for e in events:
        if e.get("onsite") is True:
            continue  # exclude physical/onsite-only events

        try:
            start = datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
            finish = datetime.fromisoformat(e["finish"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue  # skip malformed entries rather than crash the whole run

        status = "LIVE" if start <= now <= finish else "UPCOMING"

        organizers = ", ".join(o.get("name", "?") for o in e.get("organizers", [])) or "Unknown"

        out.append({
            "id": e.get("id"),
            "title": e.get("title", "Untitled"),
            "url": e.get("url") or e.get("ctftime_url", ""),
            "ctftime_url": e.get("ctftime_url", ""),
            "format": e.get("format", "Unknown"),
            "restrictions": e.get("restrictions", "Unknown"),
            "weight": e.get("weight", 0),
            "organizers": organizers,
            "start": start.isoformat(),
            "finish": finish.isoformat(),
            "status": status,
        })

    # LIVE first (soonest-ending first), then UPCOMING (soonest-starting first)
    out.sort(key=lambda x: (x["status"] != "LIVE", x["finish"] if x["status"] == "LIVE" else x["start"]))
    return out


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CTF Tracker Dashboard :: live scan</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<!-- jsdelivr instead of cdnjs: some browsers' tracking-prevention lists flag cdnjs and silently
     drop the script, which breaks charts with no visible cause. jsdelivr avoids that in practice.
     No date-library dependency (moment/date-fns) — the timeline chart uses plain hours-from-now math. -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#0d1117; --panel:#151b26; --panel-border:#232b3a;
    --text:#e8ecf3; --muted:#7b8794;
    --teal:#2dd4bf; --violet:#a78bfa; --coral:#fb7185; --gold:#fbbf24; --sky:#38bdf8;
  }
  *{box-sizing:border-box;}
  body{
    margin:0; min-height:100vh; color:var(--text); background:var(--bg);
    font-family:'JetBrains Mono', monospace; font-size:14px; position:relative;
  }
  body::before{
    content:''; position:fixed; inset:0; z-index:0; pointer-events:none;
    background:
      radial-gradient(ellipse 700px 400px at 10% -10%, rgba(45,212,191,0.18), transparent 60%),
      radial-gradient(ellipse 700px 400px at 100% 0%, rgba(167,139,250,0.16), transparent 60%),
      radial-gradient(ellipse 800px 500px at 50% 100%, rgba(56,189,248,0.10), transparent 60%);
  }
  .wrap{max-width:1180px; margin:0 auto; padding:32px 24px 60px; position:relative; z-index:1;}
  .statusbar{
    display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;
    border:1px solid var(--panel-border); background:var(--panel);
    padding:14px 20px; border-radius:10px; margin-bottom:28px;
  }
  .segs{display:flex; gap:22px; flex-wrap:wrap; font-size:12.5px; color:var(--muted);}
  .segs b{color:var(--text); font-weight:600;}
  .live-badge{display:inline-flex; align-items:center; gap:6px; color:var(--coral); font-weight:600;}
  .pulse-dot{width:8px; height:8px; border-radius:50%; background:var(--coral); animation:pulse 1.5s infinite;}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(251,113,133,0.5);}70%{box-shadow:0 0 0 7px rgba(251,113,133,0);}100%{box-shadow:0 0 0 0 rgba(251,113,133,0);}}
  .titlerow{display:flex; align-items:baseline; justify-content:space-between; flex-wrap:wrap; gap:8px;}
  h1{
    font-family:'Sora', sans-serif; font-weight:800; font-size:34px; margin:4px 0 6px; letter-spacing:-0.8px;
  }
  h1 span{background:linear-gradient(120deg, var(--teal), var(--sky)); -webkit-background-clip:text; background-clip:text; color:transparent;}
  .author{
    font-family:'Sora', sans-serif; font-size:12.5px; color:var(--muted); font-weight:600;
  }
  .author a{color:var(--teal); text-decoration:none;}
  .author a:hover{text-decoration:underline;}
  .subhead{color:var(--muted); font-size:13.5px; margin-bottom:30px; font-family:'Sora',sans-serif; font-weight:500;}
  .autoupdate{
    display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin:8px 0 18px;
    font-size:12px; color:var(--muted);
  }
  .autoupdate img{height:20px; border-radius:4px;}
  .autoupdate a{color:var(--teal);}
  .stat-row{display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:24px;}
  .stat{border:1px solid var(--panel-border); background:var(--panel); border-radius:12px; padding:16px 18px;}
  .stat .num{font-family:'Sora',sans-serif; font-weight:800; font-size:26px;}
  .stat .lbl{color:var(--muted); font-size:11.5px; margin-top:2px; text-transform:uppercase; letter-spacing:0.5px;}
  .stat.n1 .num{color:var(--coral);} .stat.n2 .num{color:var(--teal);} .stat.n3 .num{color:var(--gold);} .stat.n4 .num{color:var(--violet);}
  @media (max-width:800px){.stat-row{grid-template-columns:repeat(2,1fr);}}
  .panel{border:1px solid var(--panel-border); background:var(--panel); border-radius:14px; margin-bottom:24px; overflow:hidden;}
  .panel-title{font-family:'Sora',sans-serif; font-weight:700; font-size:13px; letter-spacing:0.3px; color:var(--text); padding:16px 20px; border-bottom:1px solid var(--panel-border);}
  .panel-body{padding:20px;}
  .charts{display:grid; grid-template-columns:1.6fr 1fr; gap:0;}
  .charts .panel-body{height:280px;}
  @media (max-width:800px){.charts{grid-template-columns:1fr;}}
  table{width:100%; border-collapse:collapse; font-size:13px;}
  th{text-align:left; color:var(--muted); font-weight:600; font-size:10.5px; text-transform:uppercase; letter-spacing:0.5px; padding:8px 10px; border-bottom:1px solid var(--panel-border); font-family:'Sora',sans-serif;}
  td{padding:12px 10px; border-bottom:1px solid rgba(35,43,58,0.6); vertical-align:middle;}
  tr:hover td{background:rgba(45,212,191,0.03);}
  a{color:var(--teal); text-decoration:none;}
  a:hover{text-decoration:underline;}
  .tag{display:inline-block; padding:3px 10px; border-radius:6px; font-size:10.5px; font-weight:700; letter-spacing:0.3px;}
  .tag-live{background:rgba(251,113,133,0.14); color:var(--coral);}
  .tag-upcoming{background:rgba(45,212,191,0.12); color:var(--teal);}
  .fmt-chip{background:rgba(167,139,250,0.14); color:var(--violet); padding:2px 8px; border-radius:6px; font-size:11.5px;}
  .countdown{color:var(--gold); font-size:11.5px; font-weight:600;}
  .empty{color:var(--muted); padding:20px; text-align:center; font-size:12.5px;}
  footer{color:var(--muted); font-size:11px; text-align:center; margin-top:30px;}
  footer a{color:var(--teal); text-decoration:none;}
</style>
</head>
<body>
<div class="wrap">
  <div class="statusbar">
    <div class="live-badge"><span class="pulse-dot"></span>LIVE SCAN ACTIVE</div>
    <div class="segs">
      <span><b id="stat-live-s">0</b> live now</span>
      <span><b id="stat-upcoming-s">0</b> upcoming</span>
      <span>last scan: <b>__SCAN_TIME__</b></span>
      <span>window: <b>__WINDOW_DAYS__d</b></span>
    </div>
  </div>

  <div class="titlerow">
    <h1>CTF Tracker <span>Dashboard</span></h1>
    <div class="author">built by <a href="https://github.com/__AUTHOR__" target="_blank">__AUTHOR__</a></div>
  </div>
  <div class="autoupdate">
    <img src="https://github.com/__AUTHOR__/__REPO__/actions/workflows/update.yml/badge.svg" alt="workflow status" />
    <span>auto-updates every 15 min via <a href="https://github.com/__AUTHOR__/__REPO__/actions" target="_blank">GitHub Actions</a> — badge reflects the actual last run, live from GitHub</span>
  </div>
  <div class="subhead">Online, individual-joinable CTF events — pulled from CTFtime, onsite excluded — all times shown in IST</div>

  <div class="stat-row">
    <div class="stat n1"><div class="num" id="s-live">0</div><div class="lbl">live now</div></div>
    <div class="stat n2"><div class="num" id="s-upcoming">0</div><div class="lbl">upcoming (__WINDOW_DAYS__d)</div></div>
    <div class="stat n3"><div class="num" id="s-weight">0</div><div class="lbl">avg. weight</div></div>
    <div class="stat n4"><div class="num" id="s-formats">0</div><div class="lbl">formats tracked</div></div>
  </div>

  <div class="panel charts">
    <div><div class="panel-title">Timeline — next events</div><div class="panel-body"><canvas id="timelineChart"></canvas></div></div>
    <div><div class="panel-title">Format breakdown</div><div class="panel-body"><canvas id="formatChart"></canvas></div></div>
  </div>

  <div class="panel">
    <div class="panel-title">Event feed</div>
    <div class="panel-body" style="padding:0;">
      <table>
        <thead><tr><th>Status</th><th>Event</th><th>Format</th><th>Restrictions</th><th>Weight</th><th>Window (IST)</th><th>T-minus</th></tr></thead>
        <tbody id="eventBody"></tbody>
      </table>
      <div class="empty" id="emptyMsg" style="display:none;">no online events in this window — widen --window-days on the next run</div>
    </div>
  </div>

  <footer>data: <a href="https://ctftime.org" target="_blank">ctftime.org/api</a> · fetched server-side to avoid browser CORS block · auto-refreshed via <a href="https://github.com/__AUTHOR__/__REPO__/actions" target="_blank">GitHub Actions</a> · built by <a href="https://github.com/__AUTHOR__" target="_blank">__AUTHOR__</a></footer>
</div>

<script id="event-data" type="application/json">__EVENTS_JSON__</script>
<script>
const events = JSON.parse(document.getElementById('event-data').textContent);

// All displayed times are forced to IST (Asia/Kolkata) regardless of the viewer's
// own timezone, since this is a personal dashboard meant to be read in IST.
const IST_TZ = 'Asia/Kolkata';
function fmtDate(iso){
  const d = new Date(iso);
  const s = d.toLocaleString('en-IN', {timeZone: IST_TZ, month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', hour12:true});
  return s + ' IST';
}
function tMinus(iso, status){
  const diff = new Date(iso).getTime() - Date.now();
  const abs = Math.abs(diff);
  const d = Math.floor(abs/86400000), h = Math.floor((abs%86400000)/3600000), m = Math.floor((abs%3600000)/60000);
  const label = d>0 ? `${d}d ${h}h` : (h>0 ? `${h}h ${m}m` : `${m}m`);
  return status==='LIVE' ? `ends in ${label}` : (diff>0 ? `starts in ${label}` : `started ${label} ago`);
}

function render(){
  const tbody = document.getElementById('eventBody');
  tbody.innerHTML = '';
  let live=0, upcoming=0, totalWeight=0;

  if (events.length === 0){
    document.getElementById('emptyMsg').style.display = 'block';
  }

  events.forEach(e=>{
    if(e.status==='LIVE') live++; else upcoming++;
    totalWeight += (e.weight || 0);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="tag ${e.status==='LIVE'?'tag-live':'tag-upcoming'}">${e.status}</span></td>
      <td><a href="${e.ctftime_url || e.url}" target="_blank" rel="noopener">${e.title}</a><br><span style="color:var(--muted); font-size:11px;">${e.organizers}</span></td>
      <td><span class="fmt-chip">${e.format}</span></td>
      <td>${e.restrictions}</td>
      <td>${e.weight}</td>
      <td>${fmtDate(e.start)} → ${fmtDate(e.finish)}</td>
      <td class="countdown" data-target="${e.status==='LIVE'?e.finish:e.start}" data-status="${e.status}"></td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById('stat-live-s').textContent = live;
  document.getElementById('stat-upcoming-s').textContent = upcoming;
  document.getElementById('s-live').textContent = live;
  document.getElementById('s-upcoming').textContent = upcoming;
  document.getElementById('s-weight').textContent = events.length ? (totalWeight/events.length).toFixed(1) : '0';
  document.getElementById('s-formats').textContent = new Set(events.map(e=>e.format)).size;
  tickCountdowns();
}

function tickCountdowns(){
  document.querySelectorAll('.countdown[data-target]').forEach(el=>{
    el.textContent = tMinus(el.dataset.target, el.dataset.status);
  });
}
setInterval(tickCountdowns, 30000);

render();

// Charts are optional enhancement — if the CDN script didn't load (blocked by
// tracking prevention, offline, etc.), degrade quietly instead of throwing.
// The event table above has zero external dependencies and always works.
if (typeof Chart === 'undefined') {
  ['timelineChart', 'formatChart'].forEach(id => {
    const canvas = document.getElementById(id);
    const msg = document.createElement('div');
    msg.style.cssText = 'color:var(--muted); font-size:12px; padding:20px; text-align:center;';
    msg.textContent = 'charts unavailable — Chart.js failed to load (blocked by browser or offline). table below is unaffected.';
    canvas.replaceWith(msg);
  });
} else {
  const now = Date.now();
  const toHours = iso => (new Date(iso).getTime() - now) / 3600000;
  const upcoming8 = events.slice(0, 8);

  new Chart(document.getElementById('timelineChart'), {
    type: 'bar',
    data: {
      labels: upcoming8.map(e => e.title.length>26 ? e.title.slice(0,24)+'…' : e.title),
      datasets: [{
        data: upcoming8.map(e => [toHours(e.start), toHours(e.finish)]),
        backgroundColor: upcoming8.map(e => e.status==='LIVE' ? '#fb7185' : '#2dd4bf'),
        borderRadius: 4, barThickness: 13,
      }]
    },
    options: {
      indexAxis:'y', responsive:true, maintainAspectRatio:false,
      scales: {
        x:{grid:{color:'#1c2431'}, ticks:{color:'#7b8794', font:{family:'JetBrains Mono', size:10}, callback:v=>v===0?'now':(Math.abs(v)<24?`${v>0?'+':''}${Math.round(v)}h`:`${v>0?'+':''}${Math.round(v/24)}d`)}},
        y:{grid:{display:false}, ticks:{color:'#e8ecf3', font:{family:'JetBrains Mono', size:10}}}
      },
      plugins:{legend:{display:false}}
    }
  });

  const counts = {};
  events.forEach(e=>counts[e.format]=(counts[e.format]||0)+1);
  new Chart(document.getElementById('formatChart'), {
    type:'doughnut',
    data:{labels:Object.keys(counts), datasets:[{data:Object.values(counts), backgroundColor:['#2dd4bf','#fb7185','#a78bfa','#fbbf24','#38bdf8'], borderColor:'#151b26', borderWidth:3}]},
    options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'bottom', labels:{color:'#e8ecf3', font:{family:'JetBrains Mono', size:10}, boxWidth:10}}}}
  });
}
</script>
</body>
</html>
"""


IST = timezone(timedelta(hours=5, minutes=30))


def render_html(events: list[dict], window_days: int, author: str, repo: str) -> str:
    # Scan time shown in IST (not the viewer's or server's local time) since this
    # is a personal dashboard meant to be read in IST regardless of where the
    # GitHub Actions runner (which defaults to UTC) actually executed.
    scan_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    html = HTML_TEMPLATE
    html = html.replace("__EVENTS_JSON__", json.dumps(events))
    html = html.replace("__SCAN_TIME__", scan_time)
    html = html.replace("__WINDOW_DAYS__", str(window_days))
    html = html.replace("__AUTHOR__", author)
    html = html.replace("__REPO__", repo)
    return html


def main():
    ap = argparse.ArgumentParser(description="Fetch CTFtime events and render a live dashboard")
    ap.add_argument("--limit", type=int, default=100, help="max events to request from CTFtime")
    ap.add_argument("--window-days", type=int, default=30, help="how far ahead to look")
    ap.add_argument("--out", type=str, default=str(Path(__file__).parent / "dashboard.html"))
    ap.add_argument("--author", type=str, default="MSRajoriya", help="GitHub username shown as author credit")
    ap.add_argument("--repo", type=str, default="ctf_dashboard_hosted", help="GitHub repo name, used for the Actions status badge and links")
    args = ap.parse_args()

    try:
        raw = fetch_events(args.limit, args.window_days)
    except RuntimeError as e:
        print(f"[fetch_and_render] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    events = normalize(raw)
    html = render_html(events, args.window_days, args.author, args.repo)

    out_path = Path(args.out)
    out_path.write_text(html, encoding="utf-8")
    live = sum(1 for e in events if e["status"] == "LIVE")
    print(f"[fetch_and_render] wrote {out_path} — {len(events)} events ({live} live) at {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
