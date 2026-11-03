"""discover.py: offline runs against primed fixtures write jobs and a run; keys, never-fetch, boards add."""
from __future__ import annotations

import json
import sqlite3
import tomllib

import pytest

import jf_net
import srcfx
from conftest import run_script


@pytest.fixture
def home(jf_home):
    jf_net.set_cache_dir(None)
    jf_net.set_offline(None)
    srcfx.write_home(jf_home)
    srcfx.prime_sources()
    yield jf_home
    jf_net.set_cache_dir(None)


def rows(home, q, *args):
    con = sqlite3.connect(str(home / "jobferret.db"))
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(q, args)]
    finally:
        con.close()


def test_offline_run_writes_jobs_files_and_a_run(home):
    r = run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, "--json", home=home)
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] and out["offline"] and out["run_id"]
    srcs = out["sources"]
    assert srcs["adzuna"]["found"] == 3 and srcs["reed"]["found"] == 3 and srcs["nhs"]["found"] == 3
    assert srcs["boards"]["found"] == 4                           # Monzo 2 + SmartRecruiters 2
    assert srcs["rss"]["status"] == "partial" and "cwjobs.co.uk" in srcs["rss"]["errors"][0]
    assert srcs["alerts"]["found"] == 4 and any("not a known job-alert sender" in e for e in srcs["alerts"]["errors"])
    jobs = rows(home, "SELECT * FROM jobs")
    assert len(jobs) == out["new"] >= 17
    for j in jobs:
        assert j["jd_path"] and (home / "jobs" / f"{j['id']}.json").is_file()
        assert j["run_id"] == out["run_id"] and j["status"] == "seen"
    run = rows(home, "SELECT * FROM runs")[0]
    info = json.loads(run["errors_json"])
    assert info["counts"]["reed"]["status"] == "ok" and info["counts"]["reed"]["found"] == 3
    assert run["found"] == out["found"] and run["new"] == out["new"]


def test_adzuna_jobs_keep_no_canonical_and_lose_tracking(home):
    run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, home=home)
    adz = rows(home, "SELECT * FROM jobs WHERE source = 'adzuna'")
    assert adz and all(j["canonical_url"] is None for j in adz)
    assert all("utm_" not in j["source_url"] and "se=" not in j["source_url"] for j in adz)
    reed = rows(home, "SELECT * FROM jobs WHERE source = 'reed' AND company = 'Calder Water Services'")[0]
    assert reed["canonical_url"] == "https://boards.greenhouse.io/calderwater/jobs/4021"   # externalUrl, gh_src gone
    assert reed["employer_type"] == "direct"


def test_login_tokens_never_reach_disk(home):
    run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, home=home)
    blobs = [p.read_text(encoding="utf-8") for p in (home / "jobs").glob("*.json")]
    db_dump = json.dumps(rows(home, "SELECT * FROM jobs"))
    for text in blobs + [db_dump]:
        assert "FAKE-LOGIN-TOKEN" not in text and "autologin" not in text
    tj = rows(home, "SELECT * FROM jobs WHERE source_url LIKE 'https://alerts.jobferret.invalid/%'")
    assert len(tj) == 1 and tj[0]["source_url"].endswith("/totaljobs/108272777")


def test_alert_does_not_overwrite_better_source(home):
    run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, home=home)
    calder = rows(home, "SELECT * FROM jobs WHERE source_url LIKE '%55501234%'")
    assert len(calder) == 1 and calder[0]["source"] == "reed"
    doc = json.loads((home / "jobs" / f"{calder[0]['id']}.json").read_text(encoding="utf-8"))
    assert "visa sponsorship is available" in doc["description"] and set(doc["seen_in"]) == {"alerts", "reed"}


def test_second_run_finds_nothing_new_and_since_is_per_source(home):
    run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, home=home)
    r = run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, "--json", home=home)
    out = json.loads(r.stdout)
    assert out["new"] == 0 and out["found"] > 0
    import db
    import discover
    from jf_common import load_config
    con = db.connect(home / "jobferret.db")
    try:
        assert discover.since_for(con, "reed", load_config(), None) == 1
        assert discover.since_for(con, "teaching", load_config(), None) in (1, 7)
    finally:
        con.close()


def test_missing_keys_skip_with_help_and_others_run(jf_home):
    srcfx.write_home(jf_home, keys=False)
    srcfx.prime_sources()
    r = run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, "--json", home=jf_home)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["sources"]["adzuna"]["status"] == "skipped"
    assert "developer.adzuna.com" in out["sources"]["adzuna"]["note"]
    assert "reed.co.uk/developers" in out["sources"]["reed"]["note"]
    assert out["sources"]["nhs"]["status"] == "ok"
    text = run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, home=jf_home).stdout
    assert "need a key" in text and "skipped: needs a key" in text


def test_nothing_could_run_exits_1(jf_home):
    profile = dict(srcfx.PROFILE, targets=dict(srcfx.PROFILE["targets"], titles=[]))
    srcfx.write_home(jf_home, keys=False, profile=profile, boards=[], feeds=[], alerts=())
    r = run_script("discover.py", "run", "--offline", "--json", home=jf_home)
    assert r.returncode == 1
    assert json.loads(r.stdout)["nothing_ran"] is True


def test_offline_with_empty_cache_reports_source_errors(jf_home):
    srcfx.write_home(jf_home, alerts=())
    r = run_script("discover.py", "run", "--offline", "--source", "nhs,reed", "--json", home=jf_home)
    out = json.loads(r.stdout)
    assert r.returncode == 1
    assert "offline" in out["sources"]["nhs"]["errors"][0]


def test_kill_switch(jf_home):
    srcfx.write_home(jf_home, run_file=False)
    r = run_script("discover.py", "run", "--offline", home=jf_home)
    assert r.returncode == 1 and "kill switch" in r.stdout


def test_dry_run_fetches_and_stores_nothing(jf_home):
    srcfx.write_home(jf_home)
    r = run_script("discover.py", "run", "--dry-run", "--json", home=jf_home)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["dry_run"] and out["run_id"] is None
    q = out["sources"]["adzuna"]["queries"][0]
    assert q["title"] == "Data Analyst" and q["location"] == "Leeds"
    assert "test-key" not in r.stdout
    assert not rows(jf_home, "SELECT * FROM jobs") if (jf_home / "jobferret.db").exists() else True


def test_unknown_source_is_usage_error(jf_home):
    srcfx.write_home(jf_home)
    assert run_script("discover.py", "run", "--source", "findajob", home=jf_home).returncode == 4


def test_sources_lists_keys_and_never_fetch(jf_home):
    srcfx.write_home(jf_home, keys=False)
    r = run_script("discover.py", "sources", "--json", home=jf_home)
    out = json.loads(r.stdout)
    by = {s["name"]: s for s in out["sources"]}
    assert by["adzuna"]["key"] == "missing" and by["nhs"]["key"] == "not needed"
    assert "totaljobs.com" in out["never_fetch"]


def test_boards_add_writes_config_and_refuses_never_fetch(jf_home):
    srcfx.write_home(jf_home, boards=[])
    r = run_script("discover.py", "boards", "add", "Octopus Energy", "https://jobs.lever.co/octoenergy", home=jf_home)
    assert r.returncode == 0, r.stderr
    cfg = tomllib.loads((jf_home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["sources"]["boards"]["employers"] == [{"name": "Octopus Energy", "platform": "lever", "token": "octoenergy"}]
    again = run_script("discover.py", "boards", "add", "Octopus", "https://jobs.lever.co/octoenergy/", home=jf_home)
    assert "Already listed" in again.stdout
    bad = run_script("discover.py", "boards", "add", "TJ", "https://www.totaljobs.com/jobs/data-analyst", home=jf_home)
    assert bad.returncode == 1 and "terms" in bad.stdout
    unknown = run_script("discover.py", "boards", "add", "Acme", "https://careers.acme.example/jobs", home=jf_home)
    assert unknown.returncode == 1 and "--platform teamtailor" in unknown.stdout
    custom = run_script("discover.py", "boards", "add", "Acme", "https://careers.acme.example/jobs",
                        "--platform", "teamtailor", "--json", home=jf_home)
    assert json.loads(custom.stdout)["employer"]["token"] == "careers.acme.example"


def test_guarded_fetch_refuses_never_fetch_boards(jf_home):
    srcfx.write_home(jf_home, boards=[{"name": "Bad", "platform": "teamtailor", "token": "jobs.totaljobs.com"}],
                     feeds=[], alerts=())
    r = run_script("discover.py", "run", "--offline", "--source", "boards", "--json", home=jf_home)
    out = json.loads(r.stdout)
    assert "Totaljobs' terms" in " ".join(out["sources"]["boards"]["errors"])
