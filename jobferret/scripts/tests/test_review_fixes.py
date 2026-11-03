"""Tests for the fresh-eyes review fixes: dedup, ats_detect, the never-fetch guard in jf_net,
submitted counts by method, jf_common's redacted config, track.py due, qa.py answer, setup_ui."""
import http.client
import json
import urllib.request
from datetime import date

import pytest

import ats_detect
import db
import jf_net
import outreach
import setup_ui
import sources
import track
from conftest import run_script
from test_onboarding import start_ui


@pytest.fixture
def con(tmp_path, jf_home):
    c = db.connect(tmp_path / "rf.db")
    yield c
    c.close()


def dbrun(home, dbp, *args):
    r = run_script("db.py", "--db", dbp, "--json", *args, home=home)
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r


# ------------------------------------------------------------------ 1. dedup

def test_dedup_known_job_without_application_exits_0(tmp_path):
    home, dbp = tmp_path / "h", tmp_path / "d.db"
    url = "https://jobs.lever.co/acme/abc-123"
    _, j, _ = dbrun(home, dbp, "add-job", "--json", json.dumps(
        {"source_url": url, "company": "Acme Ltd", "title": "Senior Data Analyst"}))
    code, d, _ = dbrun(home, dbp, "dedup", "--url", url)
    assert code == 0 and d["ok"] is True and d["duplicate"] is False and d["matches"] == []
    assert d["known_job"]["job_id"] == j["id"] and d["known_job"]["applications"] == 0
    # nothing has been applied for, so the same company and title is clear too
    code, d, _ = dbrun(home, dbp, "dedup", "--company", "Acme Ltd", "--title", "Senior Data Analyst")
    assert code == 0 and d["known_job"] is None
    dbrun(home, dbp, "add-application", "--json", json.dumps({"job_id": j["id"], "status": "submitted"}))
    code, d, _ = dbrun(home, dbp, "dedup", "--url", url)
    assert code == 1 and d["duplicate"] and d["matches"][0]["reason"] == "same canonical URL"
    assert d["known_job"]["applications"] == 1
    code, d, _ = dbrun(home, dbp, "dedup", "--url", "https://jobs.lever.co/acme/never-seen")
    assert code == 0 and d["known_job"] is None


# --------------------------------------------------------------- 2. ats_detect

@pytest.mark.parametrize("url,name", [
    ("https://www.totaljobs.com/job/data-analyst/acme-ltd-job105123456", "totaljobs"),
    ("https://www.cwjobs.co.uk/job/developer/x-job9", "cwjobs"),
    ("https://www.jobsite.co.uk/job/x", "jobsite"),
    ("https://www.caterer.com/job/chef/x", "caterer"),
    ("https://www.milkround.com/jobs/x", "milkround"),
    ("https://www.glassdoor.co.uk/job-listing/analyst-acme-JV_IC2671300_KO0,7.htm?jl=1", "glassdoor"),
    ("https://www.glassdoor.com/Job/x.htm", "glassdoor"),
])
def test_ats_detect_never_fetch_hosts_are_prohibited_automation(url, name):
    res = ats_detect.detect(url)
    assert (res["platform"], res["tier"]) == (name, "prohibited-automation")
    assert res["playbook"] == "playbooks/indeed-assist.md"
    assert "prohibits automated access and applying (05 §2)" in res["note"]
    assert res["note"].startswith(sources._host(url))


def test_ats_detect_covers_every_never_fetch_rule():
    for rule in sources.NEVER_FETCH_DOMAINS:
        base = rule[:-2] + ".co.uk" if rule.endswith(".*") else rule
        res = ats_detect.detect(f"https://www.{base}/jobs/1")
        assert res["tier"] in ("prohibited-automation", "assist"), rule
        assert res["note"]


def test_ats_detect_linkedin_indeed_keep_assist_and_get_a_note():
    li = ats_detect.detect("https://www.linkedin.com/jobs/view/3912345678/")
    assert (li["platform"], li["tier"], li["playbook"]) == ("linkedin", "assist", "playbooks/linkedin-assist.md")
    assert li["note"]
    assert ats_detect.detect("https://boards.greenhouse.io/acme/jobs/1")["note"] is None


# ------------------------------------------------------------ 3. jf_net guard

def test_fetch_refuses_never_fetch_before_cache_or_socket(monkeypatch, tmp_path):
    jf_net.set_cache_dir(tmp_path / "c")
    jf_net.set_offline(False)
    monkeypatch.setattr(jf_net, "_do_request", lambda *a, **k: pytest.fail("a request was made"))
    try:
        for url in ("https://www.linkedin.com/jobs/view/1", "https://uk.indeed.com/viewjob?jk=1",
                    "https://www.totaljobs.com/job/x", "https://glassdoor.co.uk/x"):
            with pytest.raises(jf_net.NeverFetch):
                jf_net.fetch(url)
    finally:
        jf_net.set_offline(None)
        jf_net.set_cache_dir(None)
    assert sources.NeverFetch is jf_net.NeverFetch and sources.is_never_fetch is jf_net.is_never_fetch


def test_redirect_to_never_fetch_host_raises():
    handler = jf_net._NeverFetchRedirect()
    req = urllib.request.Request("https://short.example/abc")
    with pytest.raises(jf_net.NeverFetch):
        handler.redirect_request(req, None, 302, "Found", {}, "https://www.linkedin.com/jobs/view/9")
    ok = handler.redirect_request(req, None, 302, "Found", {}, "https://careers.example.com/job/9")
    assert ok.full_url == "https://careers.example.com/job/9"


def test_do_request_installs_the_redirect_handler(monkeypatch):
    seen = []

    class Stop(Exception):
        pass

    def fake_build_opener(*handlers):
        seen.extend(handlers)
        raise Stop

    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)
    with pytest.raises(Stop):
        jf_net._do_request("https://example.com/", {}, "GET", None, 5)
    assert any(isinstance(h, jf_net._NeverFetchRedirect) for h in seen)


def test_verify_check_domain_never_fetches_linkedin(con, monkeypatch):
    jf_net.set_offline(False)
    monkeypatch.setattr(jf_net, "_do_request", lambda *a, **k: pytest.fail("a request was made"))
    try:
        res = outreach.verify(con, "x@linkedin.com", check_domain=True)
    finally:
        jf_net.set_offline(None)
    assert res["syntax_ok"] and res["result"] == "syntax" and res["domain_checked"] is False
    assert "prohibits automated access" in res["detail"]


# ---------------------------------------------------- 4. submitted counts by method

def _app(con, n, **kw):
    j = db.add_job(con, {"source_url": f"https://jobs.lever.co/acme/{n}", "company": f"Co{n}", "title": "Analyst"})
    return db.add_application(con, {"job_id": j["id"], **kw})


def test_manual_application_does_not_count_today_or_toward_auto(con):
    before = db.stats(con, {})["auto_eligible_progress"]
    a = _app(con, 1, status="interviewing", method="manual")
    assert a["submitted_at"] is None                      # the user supplies the real date
    st = db.stats(con, {"limits": {"daily_applications": 15, "hard_cap": 25}})
    assert st["submitted_today"] == 0 and st["submitted_today_manual"] == 0
    assert st["auto_eligible_progress"] == before
    assert st["daily_remaining"] == 15
    # a manual application with a real date today is listed as manual, still not counted
    _app(con, 2, status="submitted", method="manual", submitted_at=db.now_iso())
    st = db.stats(con, {})
    assert st["submitted_today"] == 0 and st["submitted_today_manual"] == 1 and st["submitted"] == 2
    # set_status keeps manual null too
    c = _app(con, 3, status="draft", method="manual")
    db.set_status(con, c["id"], "submitted")
    assert db.show(con, c["id"])["application"]["submitted_at"] is None


def test_assisted_counts_toward_daily_limit_but_not_auto(con):
    _app(con, 1, status="submitted", method="assist-linkedin")
    _app(con, 2, status="submitted", method="assist-nhs")
    st = db.stats(con, {})
    assert st["submitted_today"] == 2 and st["submitted_today_assisted"] == 2  # assist-* counts toward G7
    assert st["auto_eligible_progress"].startswith("0 of")                    # but not toward auto mode
    a = _app(con, 3, status="draft", method="ats-form")
    db.set_status(con, a["id"], "submitted")
    st = db.stats(con, {})
    assert st["submitted_today"] == 3 and st["auto_eligible_progress"].startswith("1 of")
    assert db.show(con, a["id"])["application"]["submitted_at"]


def test_twenty_assisted_applications_never_unlock_auto(con):
    for i in range(20):
        _app(con, i, status="submitted", method="assist-indeed")
    assert db.stats(con, {})["auto_eligible"] is False


# --------------------------------------------------- 5. jf_common prints no keys

def test_jf_common_main_redacts_config_keys(tmp_path):
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.toml").write_text('[sources.reed]\napi_key = "REEDKEYVALUE999"\n'
                                      '[sources.adzuna]\napp_id = "ADZID123"\napp_key = "ADZKEY456"\n',
                                      encoding="utf-8")
    for args in ((), ("--json",)):
        r = run_script("jf_common.py", *args, home=home)
        assert r.returncode == 0, r.stderr
        for secret in ("REEDKEYVALUE999", "ADZID123", "ADZKEY456"):
            assert secret not in r.stdout
        assert "***" in r.stdout


# ------------------------------------------------------ 6. track due and closing date

def test_due_waits_for_closing_date(con):
    today = date(2026, 11, 3)

    def mk(n, expires):
        j = db.add_job(con, {"source_url": f"https://jobs.lever.co/acme/{n}", "company": f"Co{n}",
                             "title": f"Analyst {n}", "expires_at": expires})
        return db.add_application(con, {"job_id": j["id"], "status": "submitted",
                                        "submitted_at": "2026-10-14T10:00:00Z",
                                        "created_at": "2026-10-01T09:00:00Z"})["id"]

    closing = mk(1, "2026-11-10")
    closed = mk(2, "2026-11-01")
    unknown = mk(3, None)
    res = track.due(con, today)
    owed = {r["application_id"] for r in res["follow_ups"]}
    assert closing not in owed and {closed, unknown} <= owed
    assert res["waiting_for_close"] == [{"application_id": closing, "company": "Co1", "title": "Analyst 1",
                                         "status": "submitted", "closes": "2026-11-10", "days_to_close": 7}]
    # an explicit follow-up date waits for the closing date as well
    db.add_application(con, {"id": closing, "follow_up_due": "2026-11-02"}, update=True)
    res = track.due(con, today)
    assert closing not in {r["application_id"] for r in res["follow_ups"]}
    assert res["waiting_for_close"][0]["application_id"] == closing
    later = track.due(con, date(2026, 11, 11))
    assert closing in {r["application_id"] for r in later["follow_ups"]} and not later["waiting_for_close"]


# ------------------------------------------------------------- 7. qa answer

def qa(home, *args):
    return run_script("qa.py", *args, home=home)


def test_qa_answer_keeps_comma_item_and_force(tmp_path):
    home = tmp_path / "h"
    assert qa(home, "add", "--key", "targets.titles", "--question", "Titles?").returncode == 0
    assert qa(home, "add", "--key", "targets.role_families", "--question", "Families?").returncode == 0
    r = qa(home, "answer", "1", "Data analyst, public sector", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["value"] == ["Data analyst, public sector"]
    prof = json.loads((home / "profile.json").read_text(encoding="utf-8"))
    assert prof["targets"]["titles"] == ["Data analyst, public sector"]
    r = qa(home, "answer", "2", "Finance; Data, BI\nOperations", "--json")
    assert json.loads(r.stdout)["value"] == ["Finance", "Data, BI", "Operations"]
    # re-answering needs --force
    r = qa(home, "answer", "1", "Analyst; Manager")
    assert r.returncode == 1 and "--force" in r.stderr
    r = qa(home, "answer", "1", "Analyst; Manager", "--force", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["value"] == ["Analyst", "Manager"]
    prof = json.loads((home / "profile.json").read_text(encoding="utf-8"))
    assert prof["targets"]["titles"] == ["Analyst", "Manager"]


# ------------------------------------------------- 8. setup_ui employers, 9. 413

@pytest.mark.parametrize("url,platform,token", [
    ("https://apply.workable.com/acme-ltd/", "workable", "acme-ltd"),
    ("https://acme.teamtailor.com/jobs", "teamtailor", "acme"),
    ("https://acme.recruitee.com/", "recruitee", "acme"),
    ("https://acme.jobs.personio.de/", "personio", "acme"),
    ("https://acme.pinpointhq.com/", "pinpoint", "acme"),
    ("https://jobs.smartrecruiters.com/AcmeLtd", "smartrecruiters", "AcmeLtd"),
    ("https://jobs.lever.co/acme", "lever", "acme"),
])
def test_parse_employer_recognises_every_board_platform(url, platform, token):
    assert setup_ui.parse_employer(url, []) == {"name": token, "platform": platform, "token": token}


def test_parse_employer_unknown_url_and_plain_name_are_kept():
    assert setup_ui.parse_employer("https://careers.acme.co.uk/", []) == \
        {"name": "https://careers.acme.co.uk/", "platform": "", "token": ""}
    assert setup_ui.parse_employer("Beta plc", []) == {"name": "Beta plc", "platform": "", "token": ""}


def test_setup_ui_post_over_64kb_gets_413(tmp_path):
    home = tmp_path / "uih"
    assert run_script("setup_check.py", "--create", home=home).returncode in (0, 3)
    proc, port, token = start_ui(home, "--timeout", "30")
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.putrequest("POST", f"/save?t={token}")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(setup_ui.MAX_BODY + 1))
        conn.endheaders()
        resp = conn.getresponse()
        assert resp.status == 413
        assert "too large" in resp.read().decode("utf-8")
        conn.close()
    finally:
        proc.kill()
        proc.communicate()


def test_methods_include_assist_nhs_and_other(con):
    assert {"ats-form", "assist-linkedin", "assist-indeed", "assist-nhs", "assist-other", "email",
            "manual"} <= set(db.METHODS)
    for i, m in enumerate(("assist-nhs", "assist-other")):
        assert _app(con, 40 + i, status="submitted", method=m)["method"] == m
    assert db.stats(con, {})["submitted_today"] == 2
