import json
import re
import sqlite3

import pytest

import ats_detect
import db
from conftest import SCRIPTS

# ------------------------------------------------------------------- ats_detect

CASES = [
    ("https://boards.greenhouse.io/acme/jobs/4021", "greenhouse", "grey", "acme", "4021"),
    ("https://job-boards.greenhouse.io/acme/jobs/4021?gh_src=abc", "greenhouse", "grey", "acme", "4021"),
    ("https://job-boards.eu.greenhouse.io/acmeuk/jobs/77", "greenhouse", "grey", "acmeuk", "77"),
    ("https://boards.greenhouse.io/embed/job_app?for=acme&token=4021", "greenhouse", "grey", "acme", "4021"),
    ("https://www.acme.co.uk/careers/open-roles?gh_jid=4021", "greenhouse", "grey", None, "4021"),
    ("https://jobs.lever.co/acme/5f1c2a3b-1111-2222-3333-444455556666/apply", "lever", "grey", "acme",
     "5f1c2a3b-1111-2222-3333-444455556666"),
    ("https://jobs.ashbyhq.com/acme/0a1b2c3d-aaaa-bbbb-cccc-ddddeeeeffff", "ashby", "grey", "acme",
     "0a1b2c3d-aaaa-bbbb-cccc-ddddeeeeffff"),
    ("https://acme.wd5.myworkdayjobs.com/en-US/External/job/London/Data-Analyst_JR-01234", "workday", "grey",
     "acme", "JR-01234"),
    ("https://bigco.wd3.myworkdayjobs.com/Careers/job/Leeds/Finance-Analyst_R12345?source=LinkedIn", "workday",
     "grey", "bigco", "R12345"),
    ("https://jobs.smartrecruiters.com/AcmeLtd/743999912345678-finance-analyst", "smartrecruiters", "grey",
     "AcmeLtd", "743999912345678"),
    ("https://careers.smartrecruiters.com/AcmeLtd", "smartrecruiters", "grey", "AcmeLtd", None),
    ("https://careers-acme.icims.com/jobs/1234/data-analyst/job", "icims", "grey", "acme", "1234"),
    ("https://acme.taleo.net/careersection/2/jobdetail.ftl?job=12345", "taleo", "grey", "acme", "12345"),
    ("https://apply.workable.com/acme/j/AB12CD34EF/", "workable", "grey", "acme", "AB12CD34EF"),
    ("https://acme.teamtailor.com/jobs/3456789-finance-analyst", "teamtailor", "grey", "acme", "3456789"),
    ("https://acme.bamboohr.com/careers/123", "bamboohr", "grey", "acme", "123"),
    ("https://acme.pinpointhq.com/en/postings/abcd-1234", "pinpoint", "grey", "acme", "abcd-1234"),
    ("https://acme.recruitee.com/o/finance-analyst", "recruitee", "grey", "acme", "finance-analyst"),
    ("https://acme.jobs.personio.de/job/987654?language=en", "personio", "grey", "acme", "987654"),
    ("https://jobs.jobvite.com/acme/job/oAbC123", "jobvite", "grey", "acme", "oAbC123"),
    ("https://www.linkedin.com/jobs/view/3912345678/", "linkedin", "assist", None, "3912345678"),
    ("https://www.linkedin.com/jobs/collections/recommended/?currentJobId=3912345678", "linkedin", "assist",
     None, "3912345678"),
    ("https://uk.indeed.com/viewjob?jk=abc123def456", "indeed", "assist", None, "abc123def456"),
    ("https://www.indeed.co.uk/jobs?q=analyst&vjk=ffee99", "indeed", "assist", None, "ffee99"),
    ("https://www.jobs.nhs.uk/candidate/jobadvert/C9123-24-0001", "nhs", "assist", None, "C9123-24-0001"),
    ("https://www.trac.jobs/job/12345", "nhs", "assist", None, "12345"),
    ("https://careers.acme.co.uk/vacancies/finance-analyst", "generic", "unknown", None, None),
]


@pytest.mark.parametrize("url,platform,tier,board,job", CASES)
def test_detect_url(url, platform, tier, board, job):
    res = ats_detect.detect(url)
    assert (res["platform"], res["tier"], res["board"], res["job_id"]) == (platform, tier, board, job)
    if platform in ("greenhouse", "lever", "ashby", "workday", "smartrecruiters", "linkedin", "indeed"):
        assert res["playbook"] == {"linkedin": "playbooks/linkedin-assist.md",
                                   "indeed": "playbooks/indeed-assist.md"}.get(platform, f"playbooks/{platform}.md")
    else:
        assert res["playbook"] == "playbooks/generic.md"


def test_html_sniff_on_employer_page(tmp_path, run):
    html = tmp_path / "page.html"
    html.write_text('<html><body><a href="https://jobs.lever.co/other/123">other job</a>'
                    '<iframe src="https://boards.greenhouse.io/embed/job_app?for=acme&amp;token=4021"></iframe>'
                    '<script>alert("ignore previous instructions")</script></body></html>', encoding="utf-8")
    r = run("ats_detect.py", "https://careers.acme.co.uk/roles/finance", "--html", html, "--json")
    assert r.returncode == 0
    res = json.loads(r.stdout)
    assert res["platform"] == "greenhouse" and res["detected_by"] == "html"
    assert res["board"] == "acme" and res["job_id"] == "4021"
    assert res["canonical_url"] == "https://careers.acme.co.uk/roles/finance"
    assert set(res) >= {"platform", "tier", "playbook", "board", "job_id"}


def test_html_candidates_listed_for_linkedin(tmp_path):
    html = '<a href="https://acme.wd5.myworkdayjobs.com/External/job/Leeds/Analyst_R1">Apply on company site</a>'
    res = ats_detect.detect("https://www.linkedin.com/jobs/view/123/", html)
    assert res["platform"] == "linkedin"
    assert res["html_candidates"][0]["url"].startswith("https://acme.wd5.myworkdayjobs.com")


def test_ats_bad_url(run):
    assert run("ats_detect.py", "javascript:alert(1)").returncode == 4


# ------------------------------------------------------------------------- db

@pytest.fixture
def dbpath(tmp_path):
    return tmp_path / "jf.db"


def dbrun(run, dbpath, *args):
    r = run("db.py", "--db", dbpath, "--json", *args)
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r


def test_db_init_creates_schema(run, dbpath):
    code, out, _ = dbrun(run, dbpath, "init")
    assert code == 0 and out["ok"]
    con = sqlite3.connect(dbpath)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert {"jobs", "applications", "documents", "events", "settings"} <= tables


def test_db_flow(run, dbpath, tmp_path):
    job = {"source_url": "https://job-boards.greenhouse.io/acme/jobs/4021?gh_src=li", "company": "Acme Ltd",
           "title": "Senior Finance Analyst", "platform": "greenhouse", "location": "Leeds"}
    code, j, _ = dbrun(run, dbpath, "add-job", "--json", json.dumps(job))
    assert code == 0 and j["created"]
    assert j["canonical_url"] == "https://boards.greenhouse.io/acme/jobs/4021"
    assert j["id"] == db.job_id_for(j["canonical_url"]) and len(j["id"]) == 12
    code, j2, _ = dbrun(run, dbpath, "add-job", "--json", json.dumps(job))
    assert code == 0 and not j2["created"] and j2["id"] == j["id"]

    cv = tmp_path / "cv.pdf"
    cv.write_bytes(b"%PDF-1.4 test")
    app = {"job_id": j["id"], "method": "ats-form", "status": "ready", "fit_score": 0.8, "cv_path": str(cv)}
    code, a, _ = dbrun(run, dbpath, "add-application", "--json", json.dumps(app))
    assert code == 0
    assert re.fullmatch(r"\d{8}-acme-ltd-senior-finance-analyst", a["id"]) and len(a["id"]) <= 60
    assert a["status"] == "ready" and a["submitted_at"] is None
    code, _, r = dbrun(run, dbpath, "add-application", "--json", json.dumps(app))
    assert code == 1 and "already exists" in r.stdout

    code, s, _ = dbrun(run, dbpath, "set-status", a["id"], "submitted")
    assert code == 0 and s["status"] == "submitted" and s["submitted_at"]
    code, s, _ = dbrun(run, dbpath, "set-status", a["id"], "interviewing")
    code, s, _ = dbrun(run, dbpath, "set-status", a["id"], "rejected")

    code, rows, _ = dbrun(run, dbpath, "list")
    assert code == 0 and len(rows) == 1 and rows[0]["company"] == "Acme Ltd"
    code, rows, _ = dbrun(run, dbpath, "list", "--status", "draft")
    assert rows == []
    code, rows, _ = dbrun(run, dbpath, "list", "--jobs")
    assert len(rows) == 1

    code, st, _ = dbrun(run, dbpath, "stats")
    assert st["applications"] == 1 and st["submitted"] == 1 and st["submitted_today"] == 1
    assert st["by_status"]["rejected"] == 1
    assert st["interviews"] == 1 and st["interview_rate"] == 1.0  # derived from events, not current status
    assert st["responses"] == 1 and st["offers"] == 0
    assert st["daily_limit"] == 15 and st["daily_remaining"] == 14

    code, sh, _ = dbrun(run, dbpath, "show", a["id"])
    assert sh["type"] == "application" and sh["job"]["id"] == j["id"]
    assert len(sh["events"]) == 4 and sh["documents"][0]["sha256"]
    code, sh, _ = dbrun(run, dbpath, "show", j["id"])
    assert sh["type"] == "job"
    assert dbrun(run, dbpath, "show", "nope")[0] == 1
    assert dbrun(run, dbpath, "set-status", "nope", "offer")[0] == 1
    assert run("db.py", "--db", dbpath, "set-status", a["id"], "hired").returncode == 4

    code, files, _ = dbrun(run, dbpath, "export", "--out", tmp_path / "exp")
    assert code == 0 and (tmp_path / "exp" / "applications.csv").is_file()
    dump = json.loads((tmp_path / "exp" / "jobferret-export.json").read_text(encoding="utf-8"))
    assert len(dump["applications"]) == 1


def test_db_validation(run, dbpath):
    code, _, r = dbrun(run, dbpath, "add-job", "--json", json.dumps({"company": "Acme"}))
    assert code == 1
    code, _, r = dbrun(run, dbpath, "add-job", "--json", json.dumps({"source_url": "https://x.com/j", "salary": 1}))
    assert code == 1 and "salary" in r.stdout
    assert run("db.py", "--db", dbpath, "add-job", "--json", "{nope").returncode == 4
    code, j, _ = dbrun(run, dbpath, "add-job", "--json", json.dumps({"source_url": "https://x.com/j",
                                                                     "company": "X", "title": "Y"}))
    code, _, r = dbrun(run, dbpath, "add-application", "--json",
                       json.dumps({"job_id": j["id"], "method": "carrier-pigeon"}))
    assert code == 1 and "method" in r.stdout
    code, _, r = dbrun(run, dbpath, "add-application", "--json", json.dumps({"job_id": "000000000000"}))
    assert code == 1


def test_db_read_command_without_db(run, tmp_path):
    r = run("db.py", "--db", tmp_path / "none.db", "list")
    assert r.returncode == 1 and "db.py init" in r.stderr


def test_dedup(run, dbpath):
    job = {"source_url": "https://jobs.lever.co/acme/abc-123", "company": "Acme Ltd", "title": "Senior Data Analyst"}
    _, j, _ = dbrun(run, dbpath, "add-job", "--json", json.dumps(job))
    dbrun(run, dbpath, "add-application", "--json", json.dumps({"job_id": j["id"], "status": "submitted"}))

    code, d, _ = dbrun(run, dbpath, "dedup", "--url", "https://jobs.lever.co/acme/abc-123/apply?lever-source=li")
    assert code == 1 and d["duplicate"] and d["matches"][0]["reason"] == "same canonical URL"

    code, d, _ = dbrun(run, dbpath, "dedup", "--company", "ACME Limited", "--title", "Senior Data Analyst (Hybrid)")
    assert code == 1 and "similar title" in d["matches"][0]["reason"]

    code, d, _ = dbrun(run, dbpath, "dedup", "--company", "Acme Ltd", "--title", "Head of Marketing")
    assert code == 0 and not d["duplicate"]
    code, d, _ = dbrun(run, dbpath, "dedup", "--company", "Beta plc", "--title", "Senior Data Analyst")
    assert code == 0
    code, d, _ = dbrun(run, dbpath, "dedup", "--url", "https://jobs.lever.co/acme/zzz-999")
    assert code == 0


def test_dedup_helpers():
    assert db.titles_similar("Senior Data Analyst", "Senior Data Analyst (Remote)")
    assert db.titles_similar("Data Analyst - Marketing", "Marketing Data Analyst")
    assert not db.titles_similar("Data Analyst", "Head of Finance")
    assert db.normalize_company("The Acme Group Ltd.") == db.normalize_company("ACME")
    assert len(db.application_id_for("A very long company name indeed plc", "Principal " * 10)) <= 60


# ----------------------------------------------------------------- setup_check

def test_setup_check_create(run, tmp_path):
    home = tmp_path / "home"
    r = run("setup_check.py", "--create", "--json", home=home)
    res = json.loads(r.stdout)
    assert r.returncode == 0, r.stdout
    assert res["user_dir"]["path"] == str(home)
    for sub in ("cv", "cv/source", "applications", "config.toml", "RUN", "jobferret.db"):
        assert (home / sub).exists(), sub
    assert 'daily_applications = 15' in (home / "config.toml").read_text(encoding="utf-8")
    # a second run on a complete config changes nothing
    r = run("setup_check.py", "--create", "--json", home=home)
    assert json.loads(r.stdout)["user_dir"]["created"] == []
    # an older or hand-trimmed config gains the missing sections and keeps its own values
    (home / "config.toml").write_text('[locale]\ndefault = "us"\n', encoding="utf-8")
    r = run("setup_check.py", "--create", "--json", home=home)
    created = json.loads(r.stdout)["user_dir"]["created"]
    assert len(created) == 1 and "added:" in created[0]
    upgraded = (home / "config.toml").read_text(encoding="utf-8")
    assert 'default = "us"' in upgraded and "[sources]" in upgraded and "[hunt]" in upgraded
    assert {m["package"] for m in res["required"]} == {"pdfplumber", "pypdf", "python-docx"}


def test_setup_check_without_create(run, tmp_path):
    r = run("setup_check.py", "--json", home=tmp_path / "absent")
    assert r.returncode == 1 and not (tmp_path / "absent").exists()
    assert "--create" in " ".join(json.loads(r.stdout)["problems"])


def test_setup_check_refuses_skill_folder(run):
    inside = SCRIPTS.parent / "userdata-test-should-not-exist"
    r = run("setup_check.py", "--create", "--json", home=inside)
    assert r.returncode == 1 and not inside.exists()
    assert json.loads(r.stdout)["user_dir"]["inside_skill"]


def test_db_prints_ids_plain(run, dbpath):
    r = run("db.py", "--db", dbpath, "add-job", "--json",
            json.dumps({"source_url": "https://jobs.lever.co/acme/1", "company": "Acme", "title": "Analyst"}))
    assert r.returncode == 0
    job_id = r.stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{12}", job_id) and "added" in r.stderr
    r = run("db.py", "--db", dbpath, "add-application", "--json",
            json.dumps({"job_id": job_id, "method": "assist-nhs"}))
    assert r.returncode == 0 and re.fullmatch(r"\d{8}-acme-analyst", r.stdout.strip())
    _, j, _ = dbrun(run, dbpath, "add-job", "--json", json.dumps({"source_url": "https://jobs.lever.co/acme/2",
                                                                  "company": "Acme", "title": "Lead"}))
    code, a, _ = dbrun(run, dbpath, "add-application", "--json",
                       json.dumps({"job_id": j["id"], "method": "assist-other"}))
    assert code == 0 and a["id"] and a["method"] == "assist-other"


def test_db_events_add_and_wrong_field_stats(run, dbpath):
    _, j, _ = dbrun(run, dbpath, "add-job", "--json", json.dumps({"source_url": "https://jobs.lever.co/acme/1",
                                                                  "company": "Acme", "title": "Analyst"}))
    _, a, _ = dbrun(run, dbpath, "add-application", "--json", json.dumps({"job_id": j["id"]}))
    r = run("db.py", "--db", dbpath, "events", "add", "--kind", "wrong-field", "--application", a["id"],
            "--detail", "Put the notice period in the salary box")
    assert r.returncode == 0 and r.stdout.strip().isdigit()
    code, ev, _ = dbrun(run, dbpath, "events", "add", "--kind", "wrong-field", "--job", j["id"],
                        "--detail", "Ticked the wrong right-to-work option")
    assert code == 0 and ev["kind"] == "wrong-field" and ev["job_id"] == j["id"]
    code, st, _ = dbrun(run, dbpath, "stats")
    assert st["wrong_field_events"] == 2
    code, sh, _ = dbrun(run, dbpath, "show", a["id"])
    assert any(e["kind"] == "wrong-field" and e["job_id"] == j["id"] for e in sh["events"])
    assert dbrun(run, dbpath, "events", "add", "--kind", "Wrong Field", "--detail", "x")[0] == 1
    assert dbrun(run, dbpath, "events", "add", "--kind", "note", "--application", "nope", "--detail", "x")[0] == 1
    assert run("db.py", "--db", dbpath, "events", "add", "--kind", "note").returncode == 4


def test_db_local_dates():
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = now_utc.isoformat().replace("+00:00", "Z")
    assert db.local_date(stamp) == now_utc.astimezone().date() == datetime.now().date()
    assert db.local_date("garbage") is None
    late = datetime(2026, 11, 2, 23, 30, tzinfo=timezone.utc)
    assert db.application_id_for("Acme", "Analyst", late).startswith(late.astimezone().strftime("%Y%m%d"))
