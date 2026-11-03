"""Indeed in the user's browser: URL planning, parsing what the snippet returns, the page-text
fallback, caps and the ledger, and discover.py browse end to end. Nothing here opens a socket;
the fixtures were captured from uk.indeed.com in the desktop browser pane on 2026-11-03."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

import jf_net
import sources
from sources import _browser, indeed
from sources._common import validate_record

HERE = Path(__file__).parent
FIX = HERE / "fixtures" / "sources" / "browse"
SCRIPTS = HERE.parent


def cards():
    return json.loads((FIX / "indeed-cards.json").read_text(encoding="utf-8"))


# ----------------------------------------------------------------- registry and policy

def test_indeed_is_a_browser_source_with_no_search():
    mod = sources.SOURCES["indeed"]
    assert mod.SOURCE["kind"] == "browser" and mod.SOURCE["tier"] == "assist" and mod.SOURCE["needs_key"] is False
    assert sources.is_browser_source("indeed") and not sources.is_browser_source("reed")
    assert not hasattr(mod, "search")
    assert callable(mod.plan_urls) and callable(mod.parse_payload)
    for key in ("search", "job"):
        path = SCRIPTS / mod.SOURCE["snippets"][key]
        text = path.read_text(encoding="utf-8")
        assert path.is_file() and "fetch(" not in text and "XMLHttpRequest" not in text and ".click(" not in text


def test_indeed_http_is_still_refused():
    assert jf_net.is_never_fetch("https://uk.indeed.com/jobs?q=finance+analyst")
    assert "browser" in jf_net.never_fetch_message("https://uk.indeed.com/viewjob?jk=abc")
    calls = []
    guarded = sources.guard(lambda url, **kw: calls.append(url) or "ok")
    with pytest.raises(sources.NeverFetch):
        guarded("https://uk.indeed.com/jobs?q=x")
    assert calls == []


# ----------------------------------------------------------------- URLs

def q(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_search_url_parameters():
    u = indeed.search_url("Finance Analyst", "Manchester", 25, since_days=5, contract_types=["permanent"],
                          salary_min=40000, period="year")
    p = q(u)
    assert u.startswith("https://uk.indeed.com/jobs?")
    assert p["q"] == "Finance Analyst £40,000" and p["l"] == "Manchester" and p["radius"] == "25"
    assert p["fromage"] == "7" and p["jt"] == "permanent" and p["sort"] == "date" and "start" not in p


@pytest.mark.parametrize("since,expected", [(None, None), (1, 1), (2, 3), (3, 3), (7, 7), (10, 14), (14, 14), (30, None)])
def test_fromage_buckets(since, expected):
    assert indeed.fromage_for(since) == expected


def test_job_type_only_when_one_kind():
    assert indeed.job_type_for(["permanent"]) == "permanent"
    assert indeed.job_type_for(["contract", "fixed-term"]) == "contract"
    assert indeed.job_type_for(["permanent", "contract"]) is None
    assert indeed.job_type_for([]) is None


def test_search_url_remote_day_rate_and_paging():
    u = indeed.search_url("Data Analyst", "Leeds", 10, salary_min=450, period="day", remote=True, start=20)
    p = q(u)
    assert p["l"] == "Remote" and "radius" not in p and p["q"] == "Data Analyst" and p["start"] == "20"


def test_plan_urls_variants_and_pages():
    base = {"title": "Finance Analyst", "location": "Manchester", "radius_miles": 25, "since_days": 7,
            "contract_types": ["permanent"], "salary_min": 40000, "period": "year"}
    both = indeed.plan_urls(dict(base, work_modes=["hybrid", "remote"]), {"max_pages_per_query": 2})
    assert [u["label"] for u in both] == ["Finance Analyst · Manchester", "Finance Analyst · Remote",
                                          "Finance Analyst · Manchester · page 2", "Finance Analyst · Remote · page 2"]
    assert q(both[2]["url"])["start"] == "10" and both[2]["page"] == 2
    office = indeed.plan_urls(dict(base, work_modes=["office"]), {})
    assert [u["remote"] for u in office] == [False]
    remote_only = indeed.plan_urls(dict(base, work_modes=["remote"]), {})
    assert [u["remote"] for u in remote_only] == [True]
    nowhere = indeed.plan_urls(dict(base, location=None, work_modes=[]), {})
    assert [u["remote"] for u in nowhere] == [True]
    assert indeed.plan_urls({"title": ""}, {}) == []


# ----------------------------------------------------------------- parsing the snippet's output

def test_fixture_cards_parse_to_valid_records():
    recs = indeed.parse_search({"kind": "search", "cards": cards(), "url": "https://uk.indeed.com/jobs?q=x",
                                "page": 1, "captured_at": "2026-11-03T10:30:00Z"})
    assert len(recs) == 15
    assert all(validate_record(r) == [] for r in recs)
    assert all(r["source"] == "indeed" and r["platform"] == "indeed" for r in recs)
    assert all(r["source_url"].startswith("https://uk.indeed.com/viewjob?jk=") for r in recs)
    assert all(r["canonical_url"] is None and r["extra"]["description_is_snippet"] for r in recs)
    by_company = {r["company"]: r for r in recs}
    pets = by_company["Pets at Home"]
    assert pets["title"] == "Commercial Finance Accountant" and pets["location"] == "Cheadle"
    assert pets["remote"] == "hybrid" and (pets["salary_min"], pets["salary_max"], pets["salary_period"]) == (38000, 43000, "year")
    assert pets["currency"] == "GBP" and pets["extra"]["apply"] == "company-site" and pets["posted_at"].startswith("2026-11-02")
    assert "financial analysis" in pets["description"] and "<" not in pets["description"]
    assert pets["raw"]["jobkey"] == "37bba43d44c57777" and "snippet" not in pets["raw"]
    iff = by_company["Ingham Frankland Fide - IFF Talent"]
    assert (iff["salary_min"], iff["salary_max"], iff["salary_period"]) == (500, 600, "day")
    assert iff["contract_type"] == "temporary" and iff["extra"]["apply"] == "indeed-apply"
    axa = [r for r in recs if r["company"] == "AXA"][0]
    assert axa["salary_min"] is None and axa["salary_max"] == 35000 and axa["contract_type"] == "permanent"
    assert sum(1 for r in recs if r["extra"]["sponsored"]) == 3
    assert sum(1 for r in recs if r["extra"]["apply"] == "indeed-apply") == 5


def test_compact_snippet_capture_parses_the_same():
    """indeed_cards.js returns a compact card (about 0.5 KB each); captured live on 2026-11-03 from the
    same search as indeed-cards.json (the page's raw data), so the two must agree."""
    payload = json.loads((FIX / "indeed-cards-compact.json").read_text(encoding="utf-8"))
    assert payload["how"] == "mosaic" and payload["challenge"] is False and payload["logged_in"] is False
    recs = indeed.parse_payload(payload)
    assert len(recs) == 15 and all(validate_record(r) == [] for r in recs)
    raw = {r["source_url"]: r for r in indeed.parse_search({"cards": cards()})}
    shared = [r for r in recs if r["source_url"] in raw]
    assert len(shared) >= 10
    for r in shared:
        o = raw[r["source_url"]]
        for k in ("title", "company", "location", "remote", "salary_min", "salary_max", "salary_period", "contract_type", "posted_at"):
            assert r[k] == o[k], (k, r["title"])
        assert r["extra"]["apply"] == o["extra"]["apply"] and r["extra"]["sponsored"] == o["extra"]["sponsored"]
    pets = [r for r in recs if r["company"] == "Pets at Home"][0]
    assert pets["description"].startswith("Skilled at explaining") and "\n" in pets["description"]
    assert pets["extra"]["search_url"].startswith("https://uk.indeed.com/jobs?") and pets["extra"]["page"] == 1
    njr = [r for r in recs if r["company"] == "NJR Recruitment"][0]
    assert "Life insurance" in njr["extra"]["benefits"] and njr["extra"]["apply"] == "indeed-apply"
    assert len(json.dumps(payload["cards"])) < 1200 * 15          # the point of the compact shape


def test_search_url_tracking_params_are_known():
    # The card links carry Indeed's tracking; discover.store strips these names.
    for name in ("bb", "xkcb", "fccid", "vjs", "tk", "from"):
        assert name in indeed.TRACKING_PARAMS


def test_expired_untitled_and_duplicate_cards_are_dropped():
    c = cards()[:3]
    c[0] = dict(c[0], expired=True)
    c[1] = dict(c[1], title="", displayTitle="")
    c.append(dict(c[2]))                                   # same jobkey twice on one page
    recs = indeed.parse_search({"cards": c})
    assert len(recs) == 1 and recs[0]["company"] == cards()[2]["company"]


def test_estimated_salary_is_shown_not_used():
    card = {"jobkey": "abcdef1234567890", "title": "Analyst", "company": "Acme", "formattedLocation": "Leeds",
            "estimatedSalary": {"formattedRange": "£30K - £35K a year"}, "pubDate": 1793599200000}
    rec = indeed.card_to_record(card)
    assert rec["salary_min"] is None and rec["salary_max"] is None and rec["salary_period"] == "unknown"
    assert rec["extra"]["salary_estimated"] is True and rec["extra"]["salary_text"] == "£30K - £35K a year"


def test_monthly_and_weekly_salaries_become_yearly():
    rec = indeed.card_to_record({"jobkey": "abcdef1234567890", "title": "A", "extractedSalary": {"min": 2000, "max": 2500, "type": "MONTHLY"},
                                 "salarySnippet": {"text": "£2,000 - £2,500 a month"}})
    assert (rec["salary_min"], rec["salary_max"], rec["salary_period"]) == (24000, 30000, "year")


def test_zero_minimum_means_unknown_minimum():
    rec = indeed.card_to_record({"jobkey": "abcdef1234567890", "title": "A", "extractedSalary": {"min": 0, "max": 60000, "type": "YEARLY"}})
    assert rec["salary_min"] is None and rec["salary_max"] == 60000


@pytest.mark.parametrize("text,days", [("Just posted", 0), ("Today", 0), ("3 days ago", 3), ("Posted 12 days ago", 12),
                                       ("Active 5 days ago", 5), ("30+ days ago", None), ("Posted 30+ days ago", None),
                                       ("", None), ("yesterday-ish", None)])
def test_days_from_relative(text, days):
    assert _browser.days_from_relative(text) == days


def test_relative_time_dates_a_card_without_pub_date():
    when = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    rec = indeed.card_to_record({"jobkey": "abcdef1234567890", "title": "A", "formattedRelativeTime": "3 days ago"}, captured_at=when)
    assert rec["posted_at"] == "2026-10-31" and rec["extra"]["relative_time"] == "3 days ago"
    old = indeed.card_to_record({"jobkey": "abcdef1234567890", "title": "A", "formattedRelativeTime": "30+ days ago"}, captured_at=when)
    assert old["posted_at"] is None


def test_remote_mapping():
    assert indeed.card_to_record({"jobkey": "abcdef1234567890", "title": "A", "remoteWorkModel": {"type": "REMOTE_ALWAYS"}})["remote"] == "remote"
    rec = indeed.card_to_record({"jobkey": "abcdef1234567890", "title": "A", "formattedLocation": "Remote", "remoteWorkModel": None})
    assert rec["remote"] == "remote" and rec["location"] == "Remote"
    rec = indeed.card_to_record({"jobkey": "abcdef1234567890", "title": "A", "formattedLocation": "Hybrid work in Leeds"})
    assert rec["remote"] == "hybrid" and rec["location"] == "Leeds"
    assert indeed.card_to_record({"jobkey": "abcdef1234567890", "title": "A", "formattedLocation": "Leeds"})["remote"] == "unknown"


def test_dom_fallback_shape_parses_too():
    card = {"jobkey": "0123456789abcdef", "title": "Data Analyst", "company": "Acme", "formattedLocation": "Leeds LS1",
            "salary_text": "£35,000 - £40,000 a year", "job_types": ["Full-time", "Permanent"], "snippet": "SQL and Power BI.",
            "link": "/rc/clk?jk=0123456789abcdef&bb=x", "sponsored": False}
    rec = indeed.card_to_record(card)
    assert rec["source_url"].endswith("jk=0123456789abcdef") and rec["contract_type"] == "permanent"
    assert (rec["salary_min"], rec["salary_max"]) == (35000, 40000) and rec["extra"]["hours"] == "full-time"
    assert rec["extra"]["apply"] == "unknown"


# ----------------------------------------------------------------- page text fallback

def test_page_text_fallback_reads_every_card():
    text = (FIX / "indeed-page.txt").read_text(encoding="utf-8")
    recs = indeed.parse_page_text(text, "https://uk.indeed.com/jobs?q=finance+analyst&l=Manchester")
    assert len(recs) == 15 and all(validate_record(r) == [] for r in recs)
    titles = [r["title"] for r in recs]
    assert titles[0] == "Commercial Finance Accountant" and titles[-1] == "Senior Finance Business Partner"
    assert [r["company"] for r in recs][:4] == ["Pets at Home", "Stagecoach", "AXA", "Aptia Group"]
    assert all(r["source_url"] is None and r["extra"]["no_public_link"] and r["extra"]["from_page_text"] for r in recs)
    rw = [r for r in recs if r["company"] == "Robert Walters Outsourcing"][0]
    assert rw["location"] == "Manchester" and rw["remote"] == "hybrid" and rw["extra"]["apply"] == "indeed-apply"
    njr = [r for r in recs if r["company"] == "NJR Recruitment"][0]
    assert "Liability portfolio" in njr["description"]          # benefit lines did not start a new card


def test_page_text_without_results_block_is_empty():
    assert indeed.parse_page_text("Sign in\nNothing here\n") == []


# ----------------------------------------------------------------- one job page

def test_job_capture_gives_full_description_and_apply_route():
    payload = {"kind": "job", "url": "https://uk.indeed.com/viewjob?jk=37bba43d44c57777&from=serp", "jobkey": "37bba43d44c57777",
               "title": "Commercial Finance Accountant", "company": "Pets at Home", "location": "Cheadle",
               "salary": {"min": 38000, "max": 43000, "type": "YEARLY"}, "salary_text": "£38,000 - £43,000 a year",
               "job_types": ["Full-time", "Fixed term contract"],
               "description_html": "<div><p>Join us as a <b>Commercial Finance Accountant</b> on a 12 months fixed-term contract.</p><ul><li>Budgets</li></ul></div>",
               "apply": {"kind": "company-site", "url": "https://uk.indeed.com/applystart?jk=37bba43d44c57777&from=vj", "label": "Apply on company site"},
               "expired": False, "logged_in": False}
    rec = indeed.parse_job(payload)
    assert validate_record(rec) == []
    assert rec["source_url"] == "https://uk.indeed.com/viewjob?jk=37bba43d44c57777"
    assert rec["extra"]["description_is_snippet"] is False and "- Budgets" in rec["description"]
    assert rec["extra"]["apply"] == "company-site" and rec["extra"]["apply_url"].startswith("https://uk.indeed.com/applystart")
    assert rec["contract_type"] == "fixed-term" and rec["salary_max"] == 43000
    assert indeed.parse_payload(payload)[0]["title"] == rec["title"]
    assert indeed.parse_job({"kind": "job", "url": "https://uk.indeed.com/viewjob?jk=abc"}) is None


# ----------------------------------------------------------------- payload files, caps, ledger

def test_load_payload_shapes(tmp_path):
    data = {"kind": "search", "cards": cards()[:2]}
    (tmp_path / "obj.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "list.json").write_text(json.dumps(data["cards"]), encoding="utf-8")
    (tmp_path / "quoted.json").write_text(json.dumps(json.dumps(data)), encoding="utf-8")
    (tmp_path / "page.txt").write_text("Sort by:\nrelevance - date\n", encoding="utf-8")
    (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
    (tmp_path / "empty.json").write_text("", encoding="utf-8")
    assert _browser.load_payload(tmp_path / "obj.json")["kind"] == "search"
    assert len(_browser.load_payload(tmp_path / "list.json")["cards"]) == 2
    assert _browser.load_payload(tmp_path / "quoted.json")["cards"][0]["jobkey"] == cards()[0]["jobkey"]
    assert _browser.load_payload(tmp_path / "page.txt")["kind"] == "text"
    assert _browser.load_payload(tmp_path / "obj.json", text=True)["kind"] == "text"
    for bad in ("bad.json", "empty.json", "missing.json"):
        with pytest.raises(_browser.PayloadError):
            _browser.load_payload(tmp_path / bad)


def test_caps_floor_and_defaults():
    assert _browser.caps(None) == {"max_queries": 4, "max_pages_per_query": 1, "daily_page_cap": 20}
    assert _browser.caps({"max_queries": 0, "daily_page_cap": 3, "max_pages_per_query": True})["max_queries"] == 4
    assert _browser.caps({"daily_page_cap": 3})["daily_page_cap"] == 3


def test_ledger_counts_pages_per_day(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBFERRET_HOME", str(tmp_path))
    today = date(2026, 11, 3)
    assert _browser.pages_today("indeed", today) == 0
    assert _browser.note_pages("indeed", 2, today) == 2
    assert _browser.note_pages("indeed", 1, today) == 3
    assert _browser.pages_today("indeed", today) == 3 and _browser.pages_today("indeed", date(2026, 11, 4)) == 0
    assert _browser.remaining_today("indeed", {"daily_page_cap": 5}, today) == 2
    assert _browser.remaining_today("indeed", {"daily_page_cap": 2}, today) == 0
    ledger = json.loads(_browser.ledger_path().read_text(encoding="utf-8"))
    assert ledger == {"indeed": {"2026-11-03": 3}}


# ----------------------------------------------------------------- discover.py browse end to end

def run(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "JOBFERRET_HOME": str(home), "PYTHONIOENCODING": "utf-8", "JOBFERRET_OFFLINE": "1"}
    return subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:]], capture_output=True, text=True,
                          encoding="utf-8", env=env, cwd=str(SCRIPTS))


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    r = run(h, "setup_check.py", "--create")
    assert r.returncode == 0, r.stdout + r.stderr
    profile = json.loads(run(h, "jf_common.py").stdout) if False else None  # noqa: F841 (kept simple below)
    from jf_common import empty_profile
    p = empty_profile()
    p["personal"].update(name="Test User", location="Manchester")
    p["targets"].update(titles=["Finance Analyst", "Finance Business Partner", "Commercial Finance Manager"],
                        locations=["Manchester"], radius_miles=25, work_modes=["hybrid", "remote"],
                        contract_types=["permanent"], salary_floor={"amount": 40000, "currency": "GBP", "period": "year"})
    (h / "profile.json").write_text(json.dumps(p), encoding="utf-8")
    (h / "RUN").touch()
    return h


def test_browse_plan_ingest_and_the_rest_of_the_pipeline(home):
    r = run(home, "discover.py", "browse", "plan", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    plan = json.loads(r.stdout)["plans"][0]
    assert plan["ok"] and plan["board"] == "indeed" and plan["pages_today"] == 0
    assert len(plan["urls"]) == 4                      # max_queries 4: three titles at Manchester, then one Remote
    assert [u["remote"] for u in plan["urls"]] == [False, False, False, True]
    assert all(u["page"] == 1 for u in plan["urls"]) and all("uk.indeed.com/jobs?" in u["url"] for u in plan["urls"])
    assert plan["snippet"].endswith("indeed_cards.js") and Path(plan["snippet"]).is_file()
    assert Path(plan["inbox"]) == home / "inbox" / "browse" and Path(plan["inbox"]).is_dir()
    folder = Path(plan["folder"])
    assert folder.parent == home / "inbox" / "browse" and folder.name.startswith("indeed-") and folder.is_dir()
    assert plan["urls"][0]["save_as"] == str(folder / "indeed-01.json")
    assert plan["job_save_as"] == str(folder / "job-<jk>.json")

    # A stale capture from an earlier hunt must not be swept up by this hunt's glob.
    stale = home / "inbox" / "browse" / "indeed-20260101-000000"
    stale.mkdir()
    (stale / "indeed-01.json").write_text(json.dumps({"kind": "search", "cards": cards()[:1]}), encoding="utf-8")

    capture = Path(plan["urls"][0]["save_as"])
    capture.write_text(json.dumps({"board": "indeed", "kind": "search", "url": plan["urls"][0]["url"], "page": 1,
                                   "captured_at": "2026-11-03T10:30:00Z", "logged_in": False, "challenge": False,
                                   "cards": cards()}), encoding="utf-8")
    r = run(home, "discover.py", "browse", "ingest", str(folder / "indeed-*.json"), "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    s = json.loads(r.stdout)
    assert (s["found"], s["new"], s["pages"], s["pages_today"]) == (15, 15, 1, 1) and s["run_id"] and not s["challenge"]
    job_files = list((home / "jobs").glob("*.json"))
    assert len(job_files) == 15
    doc = json.loads(job_files[0].read_text(encoding="utf-8"))
    assert doc["source"] == "indeed" and doc["extra"]["read_in"] == "browser" and doc["record"]["source_url"].count("?") == 1

    # The same page again: nothing new, another page on the ledger.
    s2 = json.loads(run(home, "discover.py", "browse", "ingest", str(capture), "--json").stdout)
    assert (s2["found"], s2["new"], s2["pages_today"]) == (15, 0, 2)

    # A challenge capture is reported and stores nothing.
    bad = home / "inbox" / "browse" / "indeed-09.json"
    bad.write_text(json.dumps({"kind": "search", "url": "x", "challenge": True, "cards": []}), encoding="utf-8")
    r = run(home, "discover.py", "browse", "ingest", str(bad), "--json")
    s3 = json.loads(r.stdout)
    assert r.returncode == 1 and s3["challenge"] and s3["found"] == 0 and "stop browsing" in s3["errors"][0]

    # Page text works through --text and through the .txt suffix.
    txt = home / "inbox" / "browse" / "indeed-02.txt"
    txt.write_text((FIX / "indeed-page.txt").read_text(encoding="utf-8"), encoding="utf-8")
    s4 = json.loads(run(home, "discover.py", "browse", "ingest", str(txt), "--json").stdout)
    assert s4["found"] == 15 and s4["pages"] == 1
    assert s4["new"] == 0 and len(list((home / "jobs").glob("*.json"))) == 15   # linkless sightings merge by title and employer

    # The ordinary run skips the browser source with a pointer, and the sources table shows the day's pages.
    r = run(home, "discover.py", "run", "--dry-run", "--source", "indeed", "--json")
    assert json.loads(r.stdout)["sources"]["indeed"]["note"].startswith("read in your browser")
    rows = {s["name"]: s for s in json.loads(run(home, "discover.py", "sources", "--json").stdout)["sources"]}
    assert rows["indeed"]["kind"] == "browser" and rows["indeed"]["has"].startswith("4 of 20 pages read today")

    # Screening and the digest take the browsed jobs like any other.
    r = run(home, "screen.py", "--all-new", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    sc = json.loads(r.stdout)
    assert sc["kept"] + sc["excluded"] >= 15
    r = run(home, "digest.py", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    digest_text = Path(json.loads(r.stdout)["path"]).read_text(encoding="utf-8")
    assert "Indeed (browser)" in digest_text

    # The daily cap stops the plan once it is used up.
    assert run(home, "setup_check.py", "--set", "sources.indeed.daily_page_cap=3").returncode == 0
    r = run(home, "discover.py", "browse", "plan", "--json")
    plan2 = json.loads(r.stdout)["plans"][0]
    assert r.returncode == 1 and not plan2["ok"] and "daily page cap reached" in plan2["skip"] and plan2["urls"] == []

    # hunt_cron never browses: it runs the other sources and reports Indeed as skipped.
    r = run(home, "hunt_cron.py", "--offline", "--json")
    assert "indeed" in json.loads(r.stdout)["discover"]["sources"]
    assert json.loads(r.stdout)["discover"]["sources"]["indeed"]["status"] == "skipped"


def test_browse_job_stores_the_full_description(home):
    f = home / "job.json"
    f.write_text(json.dumps({"kind": "job", "url": "https://uk.indeed.com/viewjob?jk=37bba43d44c57777", "jobkey": "37bba43d44c57777",
                             "title": "Commercial Finance Accountant", "company": "Pets at Home", "location": "Cheadle",
                             "description_html": "<p>" + "Long advert text. " * 40 + "</p>",
                             "apply": {"kind": "company-site", "url": "https://uk.indeed.com/applystart?jk=37bba43d44c57777"}}),
                 encoding="utf-8")
    r = run(home, "discover.py", "browse", "job", str(f), "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["job"]["apply"] == "company-site" and out["job"]["next"].startswith("Click 'Apply on company site'")
    assert out["job"]["apply_url"].startswith("https://uk.indeed.com/applystart")
    assert out["pages_today"] == 1 and out["daily_page_cap"] == 20 and out["cap_reached"] is False
    doc = json.loads((home / "jobs" / f"{out['job']['id']}.json").read_text(encoding="utf-8"))
    assert doc["extra"]["description_is_snippet"] is False and len(doc["description"]) > 500
    assert doc["record"]["source_url"] == "https://uk.indeed.com/viewjob?jk=37bba43d44c57777"

    # The job page counts toward the cap, and the output says when the cap is reached.
    assert run(home, "setup_check.py", "--set", "sources.indeed.daily_page_cap=2").returncode == 0
    r = run(home, "discover.py", "browse", "job", str(f))
    assert r.returncode == 0 and "Daily cap reached (2 of 2 Indeed pages)" in r.stdout


def test_browse_plan_needs_a_browser_source_enabled(home):
    assert run(home, "setup_check.py", "--set", "sources.enabled=adzuna,reed").returncode == 0
    r = run(home, "discover.py", "browse", "plan", "--json")
    assert r.returncode == 1 and json.loads(r.stdout)["plans"] == []
    r = run(home, "discover.py", "browse", "plan", "--source", "reed")
    assert r.returncode == 4 and "not a browser source" in (r.stderr + r.stdout)


def test_kill_switch_stops_ingest(home):
    (home / "RUN").unlink()
    r = run(home, "discover.py", "browse", "ingest", str(FIX / "indeed-cards.json"), "--json")
    assert r.returncode == 1 and "kill switch" in json.loads(r.stdout)["error"]
