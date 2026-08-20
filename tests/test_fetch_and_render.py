"""
Test suite for fetch_and_render.py.

Run locally with:  pip install pytest --break-system-packages && pytest -v
Run in CI via .github/workflows/ci.yml on every push.

These tests deliberately avoid hitting the real network (CTFtime's API) —
everything is tested against mock data or mocked urllib calls, so the suite
runs fast and doesn't depend on CTFtime being reachable.
"""
import sys
import unittest.mock as mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import fetch_and_render as far


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


# --- country_to_flag --------------------------------------------------------

def test_country_to_flag_valid():
    assert far.country_to_flag("IN") == "🇮🇳"
    assert far.country_to_flag("US") == "🇺🇸"


def test_country_to_flag_lowercase():
    assert far.country_to_flag("in") == "🇮🇳"


def test_country_to_flag_invalid():
    assert far.country_to_flag(None) == ""
    assert far.country_to_flag("") == ""
    assert far.country_to_flag("USA") == ""  # wrong length
    assert far.country_to_flag("12") == ""   # non-alpha


# --- guess_categories --------------------------------------------------------

def test_guess_categories_general_fallback():
    assert far.guess_categories("DEF CON CTF Quals 2026", None) == ["General"]


def test_guess_categories_single_match():
    assert far.guess_categories("AI Security CTF 2026", None) == ["AI / ML"]
    assert far.guess_categories("RoboHack Robotics Challenge", None) == ["Robotics"]
    assert far.guess_categories("Reverse Engineering Marathon", None) == ["Reverse Eng."]
    assert far.guess_categories("OSINT Hunters", None) == ["OSINT"]


def test_guess_categories_compound_ctf_names():
    """Common CTF naming pattern glues the category word directly to 'CTF'
    with no space (CryptoCTF, WebCTF, PwnCTF) — must still match."""
    assert far.guess_categories("CryptoCTF 2026", None) == ["Crypto"]
    assert far.guess_categories("WebCTF", None) == ["Web"]
    assert far.guess_categories("PwnCTF Finals", None) == ["Pwn / Binary"]


def test_guess_categories_multiple_matches():
    result = far.guess_categories("AI + Web Combined CTF", None)
    assert result == ["AI / ML", "Web"]


def test_guess_categories_false_positive_guard():
    """'Webinar' should NOT match 'Web' — word-boundary regex should prevent
    partial-word false positives."""
    assert far.guess_categories("Webinar CTF 2026", None) == ["General"]


def test_guess_categories_uses_description():
    assert far.guess_categories("Mystery CTF", "an AI/ML focused challenge set") == ["AI / ML"]


# --- normalize() -------------------------------------------------------------

def test_normalize_excludes_onsite():
    now = datetime.now(timezone.utc)
    mock_events = [
        {"id": 1, "title": "Online Event", "onsite": False, "format": "Jeopardy",
         "restrictions": "Open", "weight": 10, "organizers": [{"id": 1, "name": "X"}],
         "start": iso(now - timedelta(hours=1)), "finish": iso(now + timedelta(hours=5))},
        {"id": 2, "title": "Onsite Event", "onsite": True, "format": "Jeopardy",
         "restrictions": "Open", "weight": 10, "organizers": [{"id": 2, "name": "Y"}],
         "start": iso(now - timedelta(hours=1)), "finish": iso(now + timedelta(hours=5))},
    ]
    result = far.normalize(mock_events, fetch_countries=False)
    assert len(result) == 1
    assert result[0]["title"] == "Online Event"


def test_normalize_skips_malformed_entries():
    now = datetime.now(timezone.utc)
    mock_events = [
        {"id": 1, "title": "Good Event", "onsite": False, "format": "Jeopardy",
         "restrictions": "Open", "weight": 10, "organizers": [{"id": 1, "name": "X"}],
         "start": iso(now), "finish": iso(now + timedelta(hours=5))},
        {"id": 2, "title": "Malformed Event", "onsite": False},  # missing start/finish
    ]
    result = far.normalize(mock_events, fetch_countries=False)
    assert len(result) == 1
    assert result[0]["title"] == "Good Event"


def test_normalize_live_vs_upcoming_status():
    now = datetime.now(timezone.utc)
    mock_events = [
        {"id": 1, "title": "Live Now", "onsite": False, "format": "Jeopardy",
         "restrictions": "Open", "weight": 10, "organizers": [{"id": 1, "name": "X"}],
         "start": iso(now - timedelta(hours=1)), "finish": iso(now + timedelta(hours=5))},
        {"id": 2, "title": "Future Event", "onsite": False, "format": "Jeopardy",
         "restrictions": "Open", "weight": 10, "organizers": [{"id": 2, "name": "Y"}],
         "start": iso(now + timedelta(days=2)), "finish": iso(now + timedelta(days=3))},
    ]
    result = far.normalize(mock_events, fetch_countries=False)
    statuses = {e["title"]: e["status"] for e in result}
    assert statuses["Live Now"] == "LIVE"
    assert statuses["Future Event"] == "UPCOMING"


def test_normalize_sorts_live_first():
    now = datetime.now(timezone.utc)
    mock_events = [
        {"id": 1, "title": "Upcoming", "onsite": False, "format": "Jeopardy",
         "restrictions": "Open", "weight": 10, "organizers": [{"id": 1, "name": "X"}],
         "start": iso(now + timedelta(days=1)), "finish": iso(now + timedelta(days=2))},
        {"id": 2, "title": "Live", "onsite": False, "format": "Jeopardy",
         "restrictions": "Open", "weight": 10, "organizers": [{"id": 2, "name": "Y"}],
         "start": iso(now - timedelta(hours=1)), "finish": iso(now + timedelta(hours=5))},
    ]
    result = far.normalize(mock_events, fetch_countries=False)
    assert result[0]["title"] == "Live"
    assert result[1]["title"] == "Upcoming"


# --- fetch_events: timeout retry --------------------------------------------

def test_fetch_events_recovers_from_transient_timeout():
    call_count = {"n": 0}

    class FakeResp:
        status = 200
        def read(self):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise TimeoutError("simulated read timeout")
            return b"[]"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    with mock.patch("urllib.request.urlopen", lambda req, timeout: FakeResp()):
        with mock.patch("time.sleep", lambda s: None):
            result = far.fetch_events(limit=10, window_days=30, retries=2)
    assert result == []
    assert call_count["n"] == 2


def test_fetch_events_raises_clean_error_after_all_retries_fail():
    class AlwaysFailResp:
        status = 200
        def read(self):
            raise TimeoutError("always times out")
        def __enter__(self): return self
        def __exit__(self, *a): return False

    with mock.patch("urllib.request.urlopen", lambda req, timeout: AlwaysFailResp()):
        with mock.patch("time.sleep", lambda s: None):
            try:
                far.fetch_events(limit=10, window_days=30, retries=2)
                raise AssertionError("should have raised RuntimeError")
            except RuntimeError as e:
                assert "attempt 2/2" in str(e)


# --- fetch_team_country: graceful failure -----------------------------------

def test_fetch_team_country_fails_gracefully():
    with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("fail")):
        cache = {}
        result = far.fetch_team_country(999, cache)
        assert result is None
        assert cache[999] is None  # failure is cached to avoid retry storms


# --- generate_ics -------------------------------------------------------------

def test_generate_ics_structure():
    events = [{
        "id": 1, "title": "Test CTF", "start": "2026-08-09T10:00:00+00:00",
        "finish": "2026-08-09T15:00:00+00:00", "ctftime_url": "https://ctftime.org/event/1",
        "format": "Jeopardy", "restrictions": "Open", "weight": 10, "organizers": "X",
    }]
    ics = far.generate_ics(events)
    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.strip().endswith("END:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == ics.count("END:VEVENT") == 1
    assert "SUMMARY:Test CTF" in ics


def test_generate_ics_escapes_special_chars():
    text = far._ics_escape("Event; with, comma\nand newline")
    assert text == "Event\\; with\\, comma\\nand newline"


def test_generate_ics_skips_malformed_events():
    events = [{"id": 1, "title": "Bad Event", "start": "not-a-date", "finish": "also-bad"}]
    ics = far.generate_ics(events)
    assert "BEGIN:VEVENT" not in ics  # malformed entry skipped, not crashed
    assert "BEGIN:VCALENDAR" in ics and "END:VCALENDAR" in ics


def test_generate_ics_empty_list():
    ics = far.generate_ics([])
    assert ics.strip() == "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//CTF Tracker Dashboard//EN\r\nCALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\nX-WR-CALNAME:CTF Tracker Dashboard\r\nX-WR-CALDESC:Online CTF events pulled from CTFtime\r\nREFRESH-INTERVAL;VALUE=DURATION:PT15M\r\nEND:VCALENDAR"


# --- render_html: no leftover placeholders ----------------------------------

def test_render_html_no_leftover_placeholders():
    now = datetime.now(timezone.utc)
    mock_events = far.normalize([{
        "id": 1, "title": "Test CTF", "onsite": False, "format": "Jeopardy",
        "restrictions": "Open", "weight": 10, "organizers": [{"id": 1, "name": "X"}],
        "start": iso(now - timedelta(hours=1)), "finish": iso(now + timedelta(hours=5)),
    }], fetch_countries=False)
    html = far.render_html(mock_events, 30, "MSRajoriya", "ctf_dashboard_hosted", "https://manishsaini-protfolio.netlify.app/")
    for placeholder in ["__AUTHOR__", "__AUTHOR_LOWER__", "__REPO__", "__PORTFOLIO__", "__VERSION__",
                         "__SCAN_TIME__", "__WINDOW_DAYS__", "__EVENTS_JSON__"]:
        assert placeholder not in html, f"leftover placeholder: {placeholder}"


def test_render_html_uses_jsdelivr_not_cdnjs():
    events = far.normalize([], fetch_countries=False)
    html = far.render_html(events, 30, "MSRajoriya", "ctf_dashboard_hosted", "https://manishsaini-protfolio.netlify.app/")
    assert 'src="https://cdnjs' not in html
    assert 'src="https://cdn.jsdelivr.net' in html
