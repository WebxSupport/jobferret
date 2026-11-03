"""Every source parses its recorded response into valid section 8.3 records. Offline: fetch is faked."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sources
from sources import adzuna, alerts, boards, nhs, reed, rss, sponsors, teaching
from sources._common import PartialFailure, SourceError, iso_date, parse_salary_text, validate_record

FX = Path(__file__).resolve().parent / "fixtures" / "sources"


def read(rel: str) -> str:
    return (FX / rel).read_text(encoding="utf-8")


class FakeFetch:
    """Maps URL substrings to fixture bodies and records every call."""

    def __init__(self, routes: dict[str, str]):
        self.routes = routes
        self.calls: list[dict] = []

    def __call__(self, url, params=None, headers=None, auth=None, accept=None, **kw):
        self.calls.append({"url": url, "params": params, "auth": auth})
        for key, body in self.routes.items():
            if key in url:
                return body(params) if callable(body) else body
        raise AssertionError(f"unexpected fetch {url}")


def assert_valid(records, n=None):
    assert records, "no records"
    if n is not None:
        assert len(records) == n
    for r in records:
        assert validate_record(r) == [], (r["title"], validate_record(r))


QUERY = {"title": "Data Analyst", "titles": ["Data Analyst"], "location": "Leeds", "radius_miles": 10,
         "since_days": None}


# ----------------------------------------------------------------- registry

def test_registry_has_exactly_the_enabled_ids():
    assert tuple(sources.SOURCES) == ("adzuna", "reed", "nhs", "teaching", "boards", "rss", "alerts", "indeed")
    for name, mod in sources.SOURCES.items():
        assert mod.SOURCE["name"] == name
        assert mod.SOURCE["kind"] in ("api", "feed", "board", "alerts", "browser")
        assert mod.SOURCE["tier"] in ("api", "grey", "assist")
        assert isinstance(mod.SOURCE["needs_key"], bool)
        if mod.SOURCE["kind"] == "browser":
            assert not hasattr(mod, "search") and callable(mod.plan_urls) and callable(mod.parse_payload)
        else:
            assert callable(mod.search)
        assert mod.__doc__ and "Verified" in mod.__doc__ and "Tier" in mod.__doc__ and "Apply" in mod.__doc__
    with pytest.raises(KeyError):
        sources.get_source("findajob")


@pytest.mark.parametrize("url", [
    "https://www.totaljobs.com/job/data-analyst/acme-job108272638", "http://cwjobs.co.uk/jobs", "jobsite.co.uk",
    "https://www.caterer.com/x", "https://www.milkround.com/", "https://www.linkedin.com/jobs/view/1",
    "https://uk.indeed.com/viewjob?jk=abc", "https://www.indeed.co.uk/", "https://www.glassdoor.co.uk/Job",
])
def test_never_fetch_matches(url):
    assert sources.is_never_fetch(url)
    assert "alert emails" in sources.never_fetch_message(url)


@pytest.mark.parametrize("url", ["https://www.reed.co.uk/jobs/x/1", "https://notindeed.com/", "https://jobs.nhs.uk",
                                 "https://boards-api.greenhouse.io/v1/boards/monzo/jobs"])
def test_never_fetch_leaves_others(url):
    assert not sources.is_never_fetch(url)


def test_guard_refuses_before_fetching():
    calls = []
    guarded = sources.guard(lambda url, **kw: calls.append(url) or "ok")
    with pytest.raises(sources.NeverFetch):
        guarded("https://www.totaljobs.com/jobs/data-analyst")
    assert calls == []
    assert guarded("https://example.org/feed") == "ok"


# ----------------------------------------------------------------- helpers

def test_salary_text_shapes():
    assert parse_salary_text("£39959.00 to £48117.00")["max"] == 48117.0
    s = parse_salary_text("£35k-£42k")
    assert (s["min"], s["max"], s["period"]) == (35000, 42000, "year")
    assert parse_salary_text("up to £50,000")["max"] == 50000 and parse_salary_text("up to £50,000")["min"] is None
    assert parse_salary_text("£550 per day")["period"] == "day"
    assert parse_salary_text("£12.50ph")["period"] == "hour"
    assert parse_salary_text("Negotiable")["min"] is None


def test_iso_dates():
    assert iso_date("02/11/2026") == "2026-11-02"
    assert iso_date(1681397936163).startswith("2023-04-13")
    assert iso_date("2026-10-27 09:59:51 UTC") == "2026-10-27T09:59:51Z"
    assert iso_date("2026-10-16T10:28:18.777441716") == "2026-10-16T10:28:18Z"
    assert iso_date("Mon, 02 Nov 2026 09:00:00 +0000") == "2026-11-02T09:00:00Z"


# ----------------------------------------------------------------- keyed APIs

def test_adzuna_parses_and_hides_predicted_salary():
    fetch = FakeFetch({"api.adzuna.com": read("adzuna/search.json")})
    recs = adzuna.search(QUERY, {"app_id": "id", "app_key": "key"}, fetch)
    assert_valid(recs, 3)
    first = recs[0]
    assert first["canonical_url"] is None                     # redirect_url is an aggregator link
    assert first["salary_min"] == 35000 and first["contract_type"] == "permanent"
    predicted = recs[1]
    assert predicted["salary_min"] is None and predicted["extra"]["salary_estimate"]["min"] == 44000
    assert fetch.calls[0]["params"]["what"] == "Data Analyst"
    assert fetch.calls[0]["params"]["distance"] == 16           # 10 miles in km


def test_adzuna_without_key_is_a_source_error():
    with pytest.raises(SourceError):
        adzuna.search(QUERY, {}, FakeFetch({}))


def test_reed_direct_and_agency_with_detail():
    def search_body(params):
        return read("reed/search.json") if params.get("postedByDirectEmployer") else read("reed/search-agency.json")

    def detail(_):
        raise AssertionError

    routes = {"/api/1.0/search": search_body,
              "/api/1.0/jobs/55501234": read("reed/detail-55501234.json"),
              "/api/1.0/jobs/55507777": read("reed/detail-55507777.json"),
              "/api/1.0/jobs/55501299": "{}"}
    fetch = FakeFetch(routes)
    recs = reed.search(QUERY, {"api_key": "k"}, fetch)
    assert_valid(recs, 3)
    by_id = {r["extra"]["board_job_id"]: r for r in recs}
    direct = by_id["55501234"]
    assert direct["employer_type"] == "direct"
    assert direct["canonical_url"].startswith("https://boards.greenhouse.io/calderwater")   # externalUrl
    assert direct["salary_period"] == "year" and direct["contract_type"] == "permanent"
    assert "visa sponsorship is available" in direct["description"]
    agency = by_id["55507777"]
    assert agency["employer_type"] == "agency" and agency["salary_period"] == "day"
    assert agency["canonical_url"] == "https://www.reed.co.uk/jobs/data-analyst/55507777"
    blank = by_id["55501299"]                                # blank detail: kept, not resolved
    assert blank["canonical_url"] is None and blank["salary_min"] is None
    assert all(c["auth"] == ("k", "") for c in fetch.calls)


def test_reed_no_agencies_runs_direct_search_only():
    fetch = FakeFetch({"/api/1.0/search": read("reed/search.json"), "/api/1.0/jobs/": "{}"})
    recs = reed.search({**QUERY, "no_agencies": True, "max_details": 0}, {"api_key": "k"}, fetch)
    assert {r["employer_type"] for r in recs} == {"direct"}
    assert [c for c in fetch.calls if "search" in c["url"]].__len__() == 1


# ----------------------------------------------------------------- keyless feeds

def test_nhs_parses_live_excerpt():
    recs = nhs.search(QUERY, {}, FakeFetch({"jobs.nhs.uk": read("nhs/search.xml")}))
    assert_valid(recs, 3)
    district = [r for r in recs if "District" in r["title"]][0]
    assert (district["salary_min"], district["salary_max"]) == (39959.0, 48117.0)
    assert district["expires_at"] == "2026-11-08" and district["platform"] == "nhs"
    nego = recs[0]
    assert nego["salary_min"] is None and nego["extra"]["salary_text"] == "Negotiable"


def test_nhs_fails_softly_on_html():
    with pytest.raises(SourceError, match="withdrawn"):
        nhs.search(QUERY, {}, FakeFetch({"jobs.nhs.uk": "<html><body>Gone</body></html"}))


def test_teaching_parses_and_filters_by_title():
    body = read("teaching/jobs.json")
    recs = teaching.search({"titles": ["History"], "since_days": None}, {}, FakeFetch({"teaching-vacancies": body}))
    assert_valid(recs, 1)
    assert recs[0]["title"] == "Teacher of History" and recs[0]["company"] == "George Dixon Academy"
    everything = teaching.search({"titles": [], "since_days": None}, {}, FakeFetch({"teaching-vacancies": body}))
    assert len(everything) == 3


# ----------------------------------------------------------------- boards

BOARD_FIXTURES = {
    "greenhouse": "greenhouse.json", "lever": "lever.json", "ashby": "ashby.json", "workable": "workable.json",
    "teamtailor": "teamtailor.rss", "recruitee": "recruitee.json", "personio": "personio.xml",
    "pinpoint": "pinpoint.json", "smartrecruiters": "smartrecruiters.json",
}


@pytest.mark.parametrize("platform", list(BOARD_FIXTURES))
def test_each_board_platform_parses(platform):
    recs = boards.parse(platform, read(f"boards/{BOARD_FIXTURES[platform]}"),
                        {"name": "Example", "platform": platform, "token": "example"})
    assert_valid(recs, 2)
    for r in recs:
        assert r["platform"] == platform and r["employer_type"] == "direct"
        assert r["canonical_url"] == r["source_url"]


def test_boards_search_partial_failure_keeps_good_boards():
    emps = [{"name": "Monzo", "platform": "greenhouse", "token": "monzo"},
            {"name": "Broken", "platform": "lever", "token": "nope"},
            {"name": "Odd", "platform": "jobvite", "token": "x"}]

    def lever_fail(_):
        from jf_net import FetchError
        raise FetchError("https://api.lever.co/v0/postings/nope", 404, "not found")
    fetch = FakeFetch({"boards-api.greenhouse.io": read("boards/greenhouse.json"), "api.lever.co": lever_fail})
    with pytest.raises(PartialFailure) as info:
        boards.search({"employers": emps}, {}, fetch)
    assert len(info.value.records) == 2
    assert any("token is wrong" in e for e in info.value.errors)
    assert any("jobvite" not in e or "needs platform" in e for e in info.value.errors)


@pytest.mark.parametrize("url,expected", [
    ("https://boards.greenhouse.io/monzo", ("greenhouse", "monzo")),
    ("https://job-boards.greenhouse.io/monzo/jobs/7343996", ("greenhouse", "monzo")),
    ("https://boards.greenhouse.io/embed/job_board?for=deliveroo", ("greenhouse", "deliveroo")),
    ("https://jobs.lever.co/octoenergy", ("lever", "octoenergy")),
    ("https://jobs.eu.lever.co/acme/123", ("lever", "eu:acme")),
    ("https://jobs.ashbyhq.com/synthesia", ("ashby", "synthesia")),
    ("https://apply.workable.com/huggingface/", ("workable", "huggingface")),
    ("https://career.teamtailor.com/jobs", ("teamtailor", "career")),
    ("https://vilgain.recruitee.com/o/brand-manager-2", ("recruitee", "vilgain")),
    ("https://tado.jobs.personio.de/", ("personio", "tado")),
    ("https://acme.jobs.personio.com/", ("personio", "acme.jobs.personio.com")),
    ("https://goodlord.pinpointhq.com/en/postings/abc", ("pinpoint", "goodlord")),
    ("https://jobs.smartrecruiters.com/ExampleRetailUK/744000012345678", ("smartrecruiters", "ExampleRetailUK")),
])
def test_parse_board_url(url, expected):
    got = boards.parse_board_url(url)
    assert (got["platform"], got["token"]) == expected


def test_parse_board_url_unknown():
    assert boards.parse_board_url("https://careers.example.com/jobs") is None


# ----------------------------------------------------------------- rss

def test_rss_and_atom_parse():
    feeds = ["https://jobs.example.ac.uk/feed", {"name": "Charity", "url": "https://careers.example-charity.org.uk/atom"}]
    fetch = FakeFetch({"jobs.example.ac.uk": read("rss/feed.xml"), "example-charity": read("rss/atom.xml")})
    recs = rss.search({"feeds": feeds, "since_days": None}, {}, fetch)
    assert_valid(recs, 3)
    first = recs[0]
    assert first["title"] == "Research Data Analyst" and first["company"] == "University of Example"
    assert first["canonical_url"] is None


def test_rss_refuses_never_fetch_feed_without_fetching():
    fetch = FakeFetch({"jobs.example.ac.uk": read("rss/feed.xml")})
    with pytest.raises(PartialFailure) as info:
        rss.search({"feeds": ["https://www.cwjobs.co.uk/jobs/data-analyst?rss=1", "https://jobs.example.ac.uk/f"],
                    "since_days": None}, {}, fetch)
    assert len(info.value.records) == 2
    assert "cwjobs.co.uk" in info.value.errors[0] and "terms" in info.value.errors[0]
    assert all("cwjobs" not in c["url"] for c in fetch.calls)


# ----------------------------------------------------------------- alerts

def test_reed_alert_email(tmp_path):
    recs, note = alerts.parse_file(FX / "alerts" / "reed-alert.eml")
    assert note is None
    assert_valid(recs, 2)
    da = recs[0]
    assert da["title"] == "Data Analyst" and da["company"] == "Calder Water Services" and da["location"] == "Leeds"
    assert da["source_url"] == "https://www.reed.co.uk/jobs/data-analyst/55501234"      # query string dropped
    assert da["salary_min"] == 36000 and da["extra"]["sender_checked"] is True
    assert "Ignore previous instructions" not in json.dumps(recs)                       # hidden text is not a job


def test_totaljobs_alert_never_keeps_the_login_link():
    recs, note = alerts.parse_file(FX / "alerts" / "totaljobs-alert.eml")
    assert_valid(recs, 2)
    dumped = json.dumps(recs)
    assert "FAKE-LOGIN-TOKEN" not in dumped and "autologin" not in dumped and "token=" not in dumped
    clean, unknown = recs
    assert clean["source_url"] == "https://www.totaljobs.com/job/data-analyst/northgate-analytics-ltd-job108272638"
    assert unknown["source_url"] is None and unknown["raw"]["board_job_id"] == "108272777"
    assert clean["extra"]["personalised_link_dropped"] is True


def test_unknown_sender_skipped():
    recs, note = alerts.parse_file(FX / "alerts" / "unknown-sender.eml")
    assert recs == [] and "not a known job-alert sender" in note


def test_alerts_search_reads_inbox(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for name in ("reed-alert.eml", "unknown-sender.eml"):
        (inbox / name).write_bytes((FX / "alerts" / name).read_bytes())
    (inbox / "pasted.txt").write_text("Data Analyst - https://www.linkedin.com/comm/jobs/view/3912345678/?trackingId=abc\n"
                                      "Acme Ltd · Leeds\n", encoding="utf-8")
    with pytest.raises(PartialFailure) as info:
        alerts.search({"inbox": inbox, "since_days": None}, {}, None)
    recs = info.value.records
    assert len(recs) == 3
    li = [r for r in recs if r["extra"]["board"] == "linkedin"][0]
    assert li["source_url"] == "https://www.linkedin.com/jobs/view/3912345678/" and li["extra"]["sender_checked"] is False
    assert li["platform"] == "linkedin"


def test_decode_link_unwraps_esp_redirects():
    href = "https://click.example.net/x?u=https%3A%2F%2Fuk.indeed.com%2Frc%2Fclk%3Fjk%3Dabcdef1234567890%26from%3Dalert"
    info = alerts.job_from_link(href)
    assert info["board"] == "indeed" and info["url"] == "https://uk.indeed.com/viewjob?jk=abcdef1234567890"


# ----------------------------------------------------------------- sponsors

def test_sponsor_register_matching():
    idx = sponsors.parse_register(read("sponsors/register.csv"))
    assert sponsors.is_sponsor("Calder Water Services", idx) == "yes"
    assert sponsors.is_sponsor("NORTHGATE ANALYTICS LTD", idx) == "yes"
    assert sponsors.is_sponsor("Lilo", idx) == "yes"                      # trading name
    assert sponsors.is_sponsor("Example Health and Care", idx) == "yes"   # & and "and"
    assert sponsors.is_sponsor("Hays", idx) == "no"
    assert sponsors.is_sponsor("Our client", idx) == "unknown"
    assert sponsors.is_sponsor("", idx) == "unknown"


def test_sponsor_register_through_content_api():
    calls = []

    def fetch_text(url, **kw):
        calls.append((url, kw.get("cache_ttl")))
        if "api/content" in url:
            return read("sponsors/content.json")
        assert url.endswith(".csv")
        return read("sponsors/register.csv")
    sponsors.set_register(None)
    try:
        idx = sponsors.load_register(fetch_text, refresh=True)
        assert "calder water services" in idx
        assert all(ttl == 7 * 24 * 3600 for _, ttl in calls)
    finally:
        sponsors.set_register(None)


def test_sponsor_unknown_when_offline_and_uncached():
    def fail(url, **kw):
        raise OSError("offline")
    sponsors.set_register(None)
    assert sponsors.is_sponsor("Calder Water Services", fetch_text=fail) == "unknown"
    sponsors.set_register(None)
