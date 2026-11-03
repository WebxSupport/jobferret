"""Shared set-up for the discovery tests: a temp user dir, a profile, config, and the jf_net cache
primed with the recorded source responses so `--offline` runs see them. Never opens a socket."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

FX = Path(__file__).resolve().parent / "fixtures" / "sources"
SINCE = "3650"          # fixtures are dated November 2026; look back far enough that they always count

PROFILE = {
    "personal": {"name": "Test User", "location": "Leeds"},
    "targets": {"titles": ["Data Analyst"], "locations": ["Leeds", "Bradford"], "radius_miles": 10,
                "work_modes": ["hybrid", "remote"], "salary_floor": {"amount": 30000, "currency": "GBP", "period": "year"},
                "contract_types": ["permanent", "fixed-term"], "ir35": ""},
    "exclusions": {"dealbreakers": ["commission only"], "companies": ["Brighouse Foods"],
                   "filters": {"no_agencies": False, "no_unpaid": True, "no_commission_only": True}},
    "eligibility": {"right_to_work": "yes", "sponsorship_needed_ever": False, "security_clearance": "",
                    "driving_licence": "full UK"},
    "history": {"skills": ["SQL", "Power BI", "Python", "Excel"]},
}

BOARDS = [{"name": "Monzo", "platform": "greenhouse", "token": "monzo"},
          {"name": "Example Retail", "platform": "smartrecruiters", "token": "ExampleRetailUK"}]
FEEDS = ["https://jobs.example.ac.uk/feed", "https://www.cwjobs.co.uk/jobs/data-analyst?rss=1"]


def read(rel: str) -> str:
    return (FX / rel).read_text(encoding="utf-8")


def route(url: str, params: dict | None = None) -> str:
    params = params or {}
    if "api.adzuna.com" in url:
        return read("adzuna/search.json")
    if "/api/1.0/search" in url:
        return read("reed/search.json") if params.get("postedByDirectEmployer") else read("reed/search-agency.json")
    m = re.search(r"/api/1\.0/jobs/(\d+)", url)
    if m:
        f = FX / "reed" / f"detail-{m.group(1)}.json"
        return f.read_text(encoding="utf-8") if f.exists() else "{}"
    table = {"jobs.nhs.uk": "nhs/search.xml", "teaching-vacancies": "teaching/jobs.json",
             "boards-api.greenhouse.io": "boards/greenhouse.json", "api.lever.co": "boards/lever.json",
             "api.ashbyhq.com": "boards/ashby.json", "apply.workable.com": "boards/workable.json",
             "teamtailor.com": "boards/teamtailor.rss", "recruitee.com": "boards/recruitee.json",
             "personio": "boards/personio.xml", "pinpointhq.com": "boards/pinpoint.json",
             "api.smartrecruiters.com": "boards/smartrecruiters.json", "jobs.example.ac.uk": "rss/feed.xml",
             "example-charity": "rss/atom.xml", "gov.uk/api/content": "sponsors/content.json",
             "assets.publishing.service.gov.uk": "sponsors/register.csv"}
    for key, rel in table.items():
        if key in url:
            return read(rel)
    raise AssertionError(f"no fixture for {url}")


def write_home(home: Path, *, keys: bool = True, profile: dict | None = None, boards=None, feeds=None,
               alerts=("reed-alert.eml", "totaljobs-alert.eml", "unknown-sender.eml"), run_file: bool = True) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    from jf_common import update_config
    update_config({"sources": {
        "enabled": ["adzuna", "reed", "nhs", "teaching", "boards", "rss", "alerts"],
        "adzuna": {"app_id": "test-id" if keys else "", "app_key": "test-key" if keys else ""},
        "reed": {"api_key": "test-reed-key" if keys else ""},
        "rss": {"feeds": FEEDS if feeds is None else feeds},
        "boards": {"employers": BOARDS if boards is None else boards},
    }}, home / "config.toml")
    (home / "profile.json").write_text(json.dumps(profile or PROFILE), encoding="utf-8")
    if run_file:
        (home / "RUN").write_text("", encoding="utf-8")
    inbox = home / "inbox"
    inbox.mkdir(exist_ok=True)
    for name in alerts:
        shutil.copy(FX / "alerts" / name, inbox / name)
    return home


def prime_sources(since: int | None = int(SINCE)) -> int:
    """Prime the jf_net cache with every request discover.py would make. Returns the count."""
    import db
    import discover
    import jf_net
    import sources
    from jf_common import load_config, load_profile
    n = 0

    def recorder(url, params=None, **kw):
        nonlocal n
        if sources.is_never_fetch(url):
            raise sources.NeverFetch(sources.never_fetch_message(url))
        body = route(url, params)
        jf_net.prime_cache(url, body, params=params)
        n += 1
        return body

    config, profile = load_config(), load_profile()
    con = db.connect(db.default_db_path())
    try:
        for e in discover.plan(None, config, profile, con, since):
            if e["skip"]:
                continue
            discover.run_source(e, config, recorder)
    finally:
        con.close()
    return n


def prime_sponsors() -> None:
    import jf_net
    from sources import sponsors
    content = json.loads(read("sponsors/content.json"))
    jf_net.prime_cache(sponsors.CONTENT_API, read("sponsors/content.json"))
    jf_net.prime_cache(sponsors.csv_url(content), read("sponsors/register.csv"))
