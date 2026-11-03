"""screen.py: each rule with a positive and a negative case, duplicates, the sponsor flag, and a DB run."""
from __future__ import annotations

import copy
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import jf_net
import screen
import srcfx
from conftest import run_script

NOW = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
SKILLS = ["SQL", "Power BI", "Python", "Excel"]


def job(**kw) -> dict:
    base = {"id": "j1", "title": "Data Analyst", "company": "Calder Water Services", "location": "Leeds",
            "remote": "hybrid", "salary_min": 36000.0, "salary_max": 40000.0, "salary_period": "year",
            "currency": "GBP", "contract_type": "permanent", "employer_type": "direct", "source": "reed",
            "posted_at": "2026-11-02", "expires_at": None, "first_seen": "2026-11-03T07:00:00Z"}
    base.update(kw)
    return base


def profile(**changes) -> dict:
    p = copy.deepcopy(srcfx.PROFILE)
    for dotted, value in changes.items():
        cur = p
        parts = dotted.split("__")
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
    return p


def run(j=None, prof=None, desc="We use SQL and Power BI daily.", **kw):
    return screen.screen_job(j or job(), prof or profile(), SKILLS, description=desc, now=NOW, **kw)


def rules(res):
    return [e["rule"] for e in res["exclusions"]]


def has_flag(res, prefix):
    return any(f.startswith(prefix) for f in res["flags"])


# ----------------------------------------------------------------- the baseline

def test_clean_match_scores_high_and_is_kept():
    res = run()
    assert res["excluded"] is None and res["exclusions"] == []
    assert res["scores"]["title"] == 40 and res["scores"]["employer"] == 10 and res["scores"]["salary"] == 10
    assert res["fit_pre"] >= 80 and res["ghost_risk"] == "low"
    assert "SQL" in res["matched_terms"] and "Power BI" in res["matched_terms"]


# ----------------------------------------------------------------- exclusions

def test_dealbreaker():
    p = profile(exclusions__dealbreakers=["night shifts", "Java"])
    res = run(prof=p, desc="Rota includes night shifts.")
    assert rules(res) == ["dealbreaker"] and res["excluded"] == "dealbreaker: night shifts"
    assert rules(run(job(title="Java Data Analyst"), p))[0] == "dealbreaker"
    assert rules(run(prof=p, desc="JavaScript and nightly shift reports.")) == []


def test_company():
    assert rules(run(job(company="Brighouse Foods Ltd"))) == ["company"]
    assert rules(run(job(company="Brighouse Foodservice Partners"))) == []


def test_agency_only_when_filter_on():
    agency = job(company="Spectrum Talent Recruitment", employer_type="agency")
    assert rules(run(agency, profile(exclusions__filters__no_agencies=True))) == ["agency"]
    assert rules(run(agency)) == []
    named = job(company="Hays", employer_type="unknown")
    assert rules(run(named, profile(exclusions__filters__no_agencies=True))) == ["agency"]
    assert has_flag(run(agency), "agency:")


def test_unpaid_and_commission_only():
    p = profile(exclusions__dealbreakers=[])
    assert rules(run(prof=p, desc="This is an unpaid internship.")) == ["unpaid"]
    assert rules(run(prof=p, desc="Commission-only sales, self-employed agent.")) == ["commission-only"]
    off = profile(exclusions__dealbreakers=[], exclusions__filters__no_unpaid=False)
    res = run(prof=off, desc="This is an unpaid internship.")
    assert rules(res) == [] and has_flag(res, "unpaid")
    assert rules(run(prof=p, desc="Uncapped commission on top of a £40,000 basic.")) == []


def test_contract_type():
    assert rules(run(job(contract_type="temporary"))) == ["contract-type"]
    assert rules(run(job(contract_type="fixed-term"))) == []
    assert rules(run(job(contract_type="unknown"))) == []
    unclear = run(job(contract_type="contract"), desc="12 month fixed term contract.")
    assert rules(unclear) == [] and has_flag(unclear, "contract-type-unclear")
    assert rules(run(job(contract_type="permanent"), profile(targets__contract_types=[]))) == []


def test_salary_floor_same_period_only():
    res = run(job(salary_min=24000.0, salary_max=28000.0))
    assert rules(res) == ["salary"] and "£28,000 a year is below your floor of £30,000 a year" in res["excluded"]
    assert rules(run(job(salary_min=28000.0, salary_max=32000.0))) == []
    day = run(job(salary_min=400.0, salary_max=450.0, salary_period="day"))
    assert rules(day) == [] and has_flag(day, "day-rate")
    assert rules(run(job(salary_min=None, salary_max=None))) == []


def test_clearance_active_only():
    assert rules(run(desc="Active SC clearance is essential.")) == ["clearance"]
    assert rules(run(desc="Candidates must be DV cleared.")) == ["clearance"]
    eligible = run(desc="You must be eligible for SC clearance and willing to undergo SC.")
    assert rules(eligible) == [] and has_flag(eligible, "clearance")
    held = run(prof=profile(eligibility__security_clearance="SC"), desc="Active SC clearance is essential.")
    assert rules(held) == [] and has_flag(held, "clearance")
    dv = run(prof=profile(eligibility__security_clearance="SC"), desc="Must hold current DV clearance.")
    assert rules(dv) == ["clearance"]
    assert rules(run(desc="BPSS checks apply.")) == []


def test_sponsorship_only_when_needed():
    text = "Unfortunately we are unable to offer visa sponsorship for this role."
    needs = profile(eligibility__sponsorship_needed_ever=True)
    assert rules(run(prof=needs, desc=text)) == ["sponsorship"]
    assert rules(run(desc=text)) == []
    assert rules(run(prof=needs, desc="Visa sponsorship is available.")) == []


def test_every_exclusion_names_rule_and_text():
    res = run(job(contract_type="temporary"), desc="Active SC clearance. Commission only.")
    assert rules(res) == ["dealbreaker", "commission-only", "contract-type", "clearance"]
    for e in res["exclusions"]:
        assert e["rule"] and e["matched"]


# ----------------------------------------------------------------- flags

def test_location_and_work_mode_flags():
    assert has_flag(run(job(location="Manchester")), "location-outside: Manchester")
    assert not has_flag(run(job(location="Manchester", remote="remote")), "location-outside")
    assert not has_flag(run(job(location="Bradford, BD5 0JD")), "location-outside")
    assert has_flag(run(job(remote="office")), "work-mode: office")


def test_salary_and_age_flags():
    res = run(job(salary_min=None, salary_max=None), desc="Competitive salary. SQL.")
    assert has_flag(res, "salary-not-stated: competitive salary")
    assert not has_flag(run(), "salary-not-stated")
    old = run(job(posted_at="2026-09-01"))
    assert has_flag(old, "old-posting") and old["ghost_risk"] == "medium"
    repost = run(extra={"first_published": "2025-02-17T09:00:00Z", "updated_at": "2026-09-25T05:00:00Z"})
    assert has_flag(repost, "reposted")
    assert not has_flag(run(extra={"first_published": "2026-10-01", "updated_at": "2026-10-05"}), "reposted")


def test_employer_and_agency_flags():
    res = run(job(company=None), desc="Our client, a household name, needs an analyst.")
    assert has_flag(res, "no-employer-named") and res["scores"]["employer"] == 0
    agency = run(job(company="Spectrum Talent Recruitment", employer_type="agency", salary_min=None, salary_max=None),
                 desc="Our client is a leading company. Immediate start.")
    assert has_flag(agency, "agency-generic") and has_flag(agency, "immediate-start")
    assert not has_flag(run(), "agency-generic") and not has_flag(run(), "immediate-start")


def test_closing_and_checks_flags():
    assert has_flag(run(job(expires_at="2026-11-05")), "closes-soon")
    assert not has_flag(run(job(expires_at="2026-12-05")), "closes-soon")
    assert has_flag(run(desc="This advert may close early."), "may-close-early")
    assert has_flag(run(desc="Subject to an enhanced DBS check."), "dbs")
    assert not has_flag(run(), "dbs")
    nolicence = profile(eligibility__driving_licence="")
    assert has_flag(run(prof=nolicence, desc="Full UK driving licence essential."), "driving-licence-needed")
    assert not has_flag(run(desc="Full UK driving licence essential."), "driving-licence-needed")


def test_ir35_and_right_to_work_flags():
    res = run(prof=profile(targets__ir35="outside"), desc="Inside IR35, umbrella only.")
    assert has_flag(res, "ir35-inside") and has_flag(res, "ir35-mismatch")
    assert not has_flag(run(desc="Outside IR35."), "ir35-inside")
    needs = profile(eligibility__sponsorship_needed_ever=True)
    assert has_flag(run(prof=needs, desc="You must have the right to work in the UK."), "right-to-work")
    assert not has_flag(run(desc="You must have the right to work in the UK."), "right-to-work")
    assert has_flag(run(desc="This post is open to UK nationals only."), "nationality")


def test_public_sector_ghost_risk_stays_low():
    res = run(job(source="nhs", posted_at="2026-08-01", company=None))
    assert res["ghost_risk"] == "low"


# ----------------------------------------------------------------- duplicates

def test_duplicate_grouping_same_agency_reposts():
    a = job(id="a1", title="Lead Software Developer", company="Redtech Recruitment Ltd", salary_min=70000.0,
            salary_max=80000.0, location="London", posted_at="2026-10-20", first_seen="2026-10-20T07:00:00Z")
    b = dict(a, id="b2", title="Software Developer (Lead)", salary_max=81000.0, posted_at="2026-10-29",
             first_seen="2026-10-29T07:00:00Z")
    c = dict(a, id="c3", company="Other Agency", first_seen="2026-10-30T07:00:00Z", posted_at="2026-10-30")
    d = dict(a, id="d4", posted_at="2026-11-20", first_seen="2026-11-20T07:00:00Z")      # outside 14 days
    e = dict(a, id="e5", location="Manchester", first_seen="2026-10-21T07:00:00Z", posted_at="2026-10-21")
    dupes = screen.find_duplicates([a, b, c, d, e])
    assert dupes == {"b2": "a1"}
    flagged = run(b, duplicate_of=dupes["b2"])
    assert "likely-duplicate-of a1" in flagged["flags"] and flagged["excluded"] is None


def test_duplicate_key_needs_salary_or_advertiser():
    vague = job(company=None, salary_min=None, salary_max=None)
    assert screen.duplicate_key(vague) is None
    assert screen.duplicate_key(job()) is not None


# ----------------------------------------------------------------- sponsor flag

def test_sponsor_flag_only_for_users_who_need_it():
    needs = profile(eligibility__sponsorship_needed_ever=True)
    res = run(prof=needs, sponsor_check=lambda name: "yes")
    assert "sponsor-licence: yes" in res["flags"] and res["sponsor_licence"] == "yes" and res["excluded"] is None
    assert not has_flag(run(sponsor_check=lambda name: "yes"), "sponsor-licence")
    agency = run(job(employer_type="agency", company="Hays"), needs, sponsor_check=lambda name: "yes")
    assert "sponsor-licence: unknown" in agency["flags"]


def test_skill_terms_from_ledger_and_profile():
    ledger = {"facts": [{"kind": "skill", "text": "**Data:** SQL (PostgreSQL, BigQuery), Python (pandas), dbt"},
                        {"kind": "skill", "text": "Tableau and Looker", "superseded_by": "F099"},
                        {"kind": "bullet", "text": "Built a dashboard"}]}
    terms = screen.skill_terms({"history": {"skills": ["Excel", "sql"]}}, ledger)
    assert {"SQL", "PostgreSQL", "BigQuery", "Python", "pandas", "dbt", "Excel"} <= set(terms)
    assert "Tableau" not in terms and len([t for t in terms if t.lower() == "sql"]) == 1


# ----------------------------------------------------------------- end to end on the database

@pytest.fixture
def discovered(jf_home):
    jf_net.set_cache_dir(None)
    prof = copy.deepcopy(srcfx.PROFILE)
    prof["eligibility"]["sponsorship_needed_ever"] = True
    srcfx.write_home(jf_home, profile=prof)
    srcfx.prime_sources()
    srcfx.prime_sponsors()
    r = run_script("discover.py", "run", "--offline", "--since", srcfx.SINCE, "--json", home=jf_home)
    assert r.returncode == 0, r.stderr
    yield jf_home, json.loads(r.stdout)["run_id"]
    jf_net.set_cache_dir(None)


def test_screen_run_writes_results_and_statuses(discovered):
    home, run_id = discovered
    r = run_script("screen.py", "--run", run_id, "--offline", "--json", home=home)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["screened"] >= 17 and out["excluded"] >= 2
    con = sqlite3.connect(str(home / "jobferret.db"))
    con.row_factory = sqlite3.Row
    jobs = [dict(x) for x in con.execute("SELECT * FROM jobs")]
    con.close()
    assert all(j["screen_json"] and j["fit_pre"] is not None for j in jobs)
    excluded = [j for j in jobs if j["status"] == "excluded"]
    assert excluded and all(j["status_reason"] and ": " in j["status_reason"] for j in excluded)
    calder = [j for j in jobs if j["company"] == "Calder Water Services"][0]
    sj = json.loads(calder["screen_json"])
    assert calder["status"] == "screened" and "sponsor-licence: yes" in sj["flags"]       # register cached
    northgate_alert = [j for j in jobs if j["source"] == "alerts" and j["company"] == "Northgate Analytics Ltd"][0]
    assert any(f.startswith("likely-duplicate-of") for f in json.loads(northgate_alert["screen_json"])["flags"])


def test_screen_all_new_skips_already_screened_and_keeps_shortlist(discovered):
    home, run_id = discovered
    run_script("screen.py", "--offline", home=home)
    again = json.loads(run_script("screen.py", "--all-new", "--offline", "--json", home=home).stdout)
    assert again["screened"] == 0
    import db
    con = db.connect(home / "jobferret.db")
    jid = db.list_jobs(con, status="screened")[0]["id"]
    db.set_job_status(con, jid, "shortlisted", "good fit")
    con.close()
    run_script("screen.py", "--run", run_id, "--offline", home=home)
    con = db.connect(home / "jobferret.db")
    assert db.list_jobs(con, status="shortlisted")[0]["id"] == jid
    con.close()


def test_screen_unknown_run_is_usage_error(jf_home):
    srcfx.write_home(jf_home)
    assert run_script("screen.py", "--run", "nope", home=jf_home).returncode == 4
