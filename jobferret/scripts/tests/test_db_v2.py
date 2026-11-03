"""Tests for schema v2: migration, job fields, runs, applications, contacts, messages, stats, secrets."""
import hashlib
import json
import sqlite3
from datetime import date, timedelta

import pytest

import db
from jf_common import canonicalize_url

V1_SCHEMA = """
CREATE TABLE jobs (id TEXT PRIMARY KEY, canonical_url TEXT UNIQUE, source_url TEXT, source TEXT, platform TEXT,
  company TEXT, title TEXT, location TEXT, remote TEXT, salary_min REAL, salary_max REAL, currency TEXT,
  posted_at TEXT, first_seen TEXT, last_seen TEXT, content_hash TEXT, jd_path TEXT, status TEXT);
CREATE TABLE applications (id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id), created_at TEXT, submitted_at TEXT,
  method TEXT, status TEXT, fit_score REAL, ats_score REAL, ghost_risk TEXT, cv_path TEXT, cover_letter_path TEXT,
  answers_path TEXT, review_screenshot TEXT, confirmation_screenshot TEXT, notes TEXT);
CREATE TABLE documents (id INTEGER PRIMARY KEY, application_id TEXT, kind TEXT, path TEXT, sha256 TEXT, created_at TEXT);
CREATE TABLE events (id INTEGER PRIMARY KEY, ts TEXT, application_id TEXT, job_id TEXT, kind TEXT, detail TEXT);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
"""


def make_v1(path, user_version=0):
    con = sqlite3.connect(path)
    con.executescript(V1_SCHEMA)
    con.execute("INSERT INTO settings VALUES ('schema_version', '1')")
    con.execute("INSERT INTO jobs (id, canonical_url, source_url, company, title, first_seen, last_seen, status) "
                "VALUES ('aaaaaaaaaaaa', 'https://boards.greenhouse.io/acme/jobs/1', 'https://x/1', 'Acme', "
                "'Analyst', '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z', 'seen')")
    con.execute("INSERT INTO applications (id, job_id, created_at, status, notes) "
                "VALUES ('20261001-acme-analyst', 'aaaaaaaaaaaa', '2026-10-01T10:00:00Z', 'draft', 'old note')")
    con.execute("INSERT INTO events (ts, application_id, job_id, kind, detail) "
                "VALUES ('2026-10-01T10:00:00Z', '20261001-acme-analyst', 'aaaaaaaaaaaa', 'status', '-> draft')")
    con.execute(f"PRAGMA user_version = {user_version}")
    con.commit()
    con.close()


def cols(con, table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


@pytest.fixture
def con(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


def job(con, n=1, **kw):
    data = {"source_url": f"https://jobs.lever.co/acme/{n}", "company": f"Co{n}", "title": f"Role {n}"}
    data.update(kw)
    return db.add_job(con, data)


def sha(text):
    return hashlib.sha1(text.encode()).hexdigest()


# ------------------------------------------------------------------- migration

@pytest.mark.parametrize("version", [0, 1])
def test_v1_database_migrates_without_losing_rows(tmp_path, version):
    path = tmp_path / "old.db"
    make_v1(path, version)
    c = db.connect(path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 2
    assert c.migrated_from == version and c.migrated
    j = c.execute("SELECT * FROM jobs").fetchone()
    assert j["id"] == "aaaaaaaaaaaa" and j["company"] == "Acme" and j["status"] == "seen"
    assert j["fit_pre"] is None and j["run_id"] is None
    a = c.execute("SELECT * FROM applications").fetchone()
    assert a["notes"] == "old note" and a["follow_up_due"] is None
    assert c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    assert {"salary_period", "contract_type", "employer_type", "expires_at", "fit_pre", "screen_json", "run_id",
            "status_reason"} <= cols(c, "jobs")
    assert {"follow_up_due", "last_contact", "found_via", "cv_variant", "role_family",
            "outcome_reason"} <= cols(c, "applications")
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"runs", "contacts", "messages", "questions_log"} <= tables
    # the old rows work with the new code
    got = db.add_application(c, {"job_id": "aaaaaaaaaaaa", "created_at": "2026-10-01T10:00:00Z", "follow_up_due":
                                 "2026-10-10"}, update=True)
    assert got["follow_up_due"] == "2026-10-10" and got["notes"] == "old note"
    c.close()
    c = db.connect(path)  # second open: nothing left to do
    assert c.migrated == () and db.migrate(c) == []
    c.close()


def test_migrate_command_is_idempotent(run, tmp_path):
    path = tmp_path / "old.db"
    make_v1(path)
    r = run("db.py", "--db", path, "--json", "migrate")
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["from_version"] == 0 and out["to_version"] == 2
    assert "added column jobs.fit_pre" in out["actions"] and "created table contacts" in out["actions"]
    out2 = json.loads(run("db.py", "--db", path, "--json", "migrate").stdout)
    assert out2["actions"] == [] and out2["from_version"] == 2
    assert "nothing to do" in run("db.py", "--db", path, "migrate").stdout


def test_init_creates_version_2(run, tmp_path):
    path = tmp_path / "new.db"
    assert run("db.py", "--db", path, "init").returncode == 0
    c = sqlite3.connect(path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 2
    assert c.execute("SELECT value FROM settings WHERE key = 'schema_version'").fetchone()[0] == "2"
    c.close()


def test_newer_database_is_refused(tmp_path):
    path = tmp_path / "future.db"
    c = sqlite3.connect(path)
    c.execute("PRAGMA user_version = 9")
    c.commit()
    c.close()
    with pytest.raises(db.DBError, match="newer"):
        db.connect(path)


# ------------------------------------------------------------------------ jobs

def test_add_job_new_fields_and_defaults(con):
    j = job(con, 1, salary_period="year", contract_type="permanent", employer_type="direct", remote="hybrid",
            expires_at="2026-12-01", fit_pre=61, screen_json={"excluded": None, "flags": []}, run_id="20261103-090000",
            status="screened", status_reason="ok", description="ignored text", raw={"a": 1})
    assert j["salary_period"] == "year" and j["contract_type"] == "permanent" and j["employer_type"] == "direct"
    assert j["fit_pre"] == 61 and json.loads(j["screen_json"]) == {"excluded": None, "flags": []}
    assert j["run_id"] == "20261103-090000" and j["status"] == "screened" and j["created"]
    assert "description" not in j and "raw" not in j
    bare = job(con, 2)
    assert (bare["remote"], bare["salary_period"], bare["contract_type"], bare["employer_type"]) == ("unknown",) * 4
    assert bare["status"] == "seen" and bare["fit_pre"] is None


@pytest.mark.parametrize("field,bad", [("remote", "hybrid-ish"), ("salary_period", "week"),
                                       ("contract_type", "zero-hours"), ("employer_type", "recruiter"),
                                       ("status", "maybe")])
def test_job_enum_validation_names_allowed_values(con, field, bad):
    with pytest.raises(db.DBError) as exc:
        job(con, 1, **{field: bad})
    assert field in str(exc.value) and "not one of" in str(exc.value)
    assert all(v in str(exc.value) for v in db.JOB_ENUMS[field])
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_job_enum_values_are_case_insensitive(con):
    assert job(con, 1, remote="Hybrid", contract_type="Fixed-Term")["contract_type"] == "fixed-term"


def test_reseen_job_keeps_screening_and_status(con):
    first = job(con, 1, source="adzuna", run_id="r1")
    db.set_screening(con, first["id"], 72, {"flags": ["no salary"]}, "screened")
    db.set_job_status(con, first["id"], "shortlisted", "good fit")
    again = db.add_job(con, {"source_url": "https://jobs.lever.co/acme/1", "company": "Co1", "title": "Role 1",
                             "location": "Leeds", "source": "reed", "run_id": "r2", "status": "seen",
                             "fit_pre": 5, "screen_json": {"flags": []}, "status_reason": "reset?",
                             "contract_type": "permanent", "employer_type": "unknown"})
    assert not again["created"] and again["id"] == first["id"]
    assert again["status"] == "shortlisted" and again["status_reason"] == "good fit"
    assert again["fit_pre"] == 72 and json.loads(again["screen_json"]) == {"flags": ["no salary"]}
    assert again["location"] == "Leeds" and again["contract_type"] == "permanent"  # newly known field filled
    assert again["source"] == "adzuna" and again["run_id"] == "r1"  # first source and run kept
    assert again["first_seen"] == first["first_seen"] and again["last_seen"] >= first["last_seen"]
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_reseen_job_does_not_blank_known_fields_with_unknown(con):
    j = job(con, 1, remote="remote", employer_type="direct")
    again = db.add_job(con, {"source_url": j["source_url"], "remote": "unknown", "employer_type": "unknown"})
    assert again["remote"] == "remote" and again["employer_type"] == "direct"


def test_job_id_uses_canonical_then_source_url(con):
    j = job(con, 1)
    assert j["id"] == sha(j["canonical_url"])[:12] and j["canonical_url"] == canonicalize_url(j["source_url"])
    agg = db.add_job(con, {"source": "adzuna", "source_url": "https://www.adzuna.co.uk/jobs/land/ad/123?utm_x=1",
                           "canonical_url": None, "company": "Beta", "title": "Analyst"})
    assert agg["canonical_url"] is None
    assert agg["id"] == sha(canonicalize_url("https://www.adzuna.co.uk/jobs/land/ad/123?utm_x=1"))[:12]


def test_canonical_url_learned_later_keeps_id(con):
    src = "https://www.adzuna.co.uk/jobs/land/ad/999"
    agg = db.add_job(con, {"source": "adzuna", "source_url": src, "canonical_url": None, "company": "Beta",
                           "title": "Analyst", "fit_pre": 55})
    again = db.add_job(con, {"source_url": src, "canonical_url": "https://boards.greenhouse.io/beta/jobs/77?gh_src=x",
                             "platform": "greenhouse"})
    assert again["id"] == agg["id"] and not again["created"]
    assert again["canonical_url"] == "https://boards.greenhouse.io/beta/jobs/77"
    assert again["platform"] == "greenhouse" and again["fit_pre"] == 55
    assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    # the employer URL alone now finds the same row
    third = db.add_job(con, {"canonical_url": "https://boards.greenhouse.io/beta/jobs/77", "title": "Analyst II"})
    assert third["id"] == agg["id"] and third["title"] == "Analyst II"
    # and an application can be made from either URL
    a = db.add_application(con, {"url": "https://boards.greenhouse.io/beta/jobs/77"})
    assert a["job_id"] == agg["id"]
    assert db.find_duplicates(con, url=src)[0]["job_id"] == agg["id"]


def test_set_job_status_logs_events(con):
    j = job(con, 1)
    out = db.set_job_status(con, j["id"], "shortlisted", "matches skills")
    assert out["status"] == "shortlisted" and out["status_reason"] == "matches skills"
    db.set_job_status(con, j["id"], "dismissed", "agency")
    db.set_job_status(con, j["id"], "expired")
    kinds = [r["kind"] for r in con.execute("SELECT kind FROM events WHERE job_id = ? ORDER BY id", (j["id"],))]
    assert kinds == ["job-added", "shortlist", "dismiss", "status-change"]
    detail = con.execute("SELECT detail FROM events WHERE kind = 'shortlist'").fetchone()[0]
    assert "seen -> shortlisted" in detail and "matches skills" in detail
    assert db.set_job_status(con, j["id"], "seen")["status_reason"] is None
    with pytest.raises(db.DBError, match="not one of"):
        db.set_job_status(con, j["id"], "liked")
    with pytest.raises(db.DBError, match="no job"):
        db.set_job_status(con, "nope", "seen")


def test_set_screening_does_not_undo_a_shortlist(con):
    j = job(con, 1)
    db.set_screening(con, j["id"], 40, {"excluded": "agency"}, "excluded")
    assert db.set_screening(con, j["id"], 41, None, "screened")["status"] == "screened"
    db.set_job_status(con, j["id"], "shortlisted")
    out = db.set_screening(con, j["id"], 90, {"x": 1}, "excluded")
    assert out["status"] == "shortlisted" and out["fit_pre"] == 90


def test_jobs_listing_filters_and_order(con):
    a = job(con, 1, source="reed", run_id="r1", fit_pre=80, salary_min=40000, salary_max=50000, currency="GBP",
            salary_period="year", title="Data Analyst")
    b = job(con, 2, source="adzuna", run_id="r2", fit_pre=30)
    c = job(con, 3, source="adzuna", run_id="r2")
    con.execute("UPDATE jobs SET first_seen = '2026-01-01T00:00:00Z' WHERE id = ?", (a["id"],))
    con.execute("UPDATE jobs SET first_seen = '2999-01-02T00:00:00Z' WHERE id = ?", (c["id"],))
    con.commit()
    db.set_job_status(con, b["id"], "dismissed", "too far")
    rows = db.list_jobs(con)
    assert [r["id"] for r in rows] == [c["id"], b["id"], a["id"]]  # newest first
    top = rows[2]
    assert top["salary"] == "£40,000 to £50,000 a year" and top["url"] == a["canonical_url"]
    assert {"id", "title", "company", "location", "remote", "salary", "contract_type", "employer_type", "source",
            "posted_at", "first_seen", "fit_pre", "status", "status_reason", "url"} <= set(top)
    assert [r["id"] for r in db.list_jobs(con, min_fit=50)] == [a["id"]]
    assert [r["id"] for r in db.list_jobs(con, min_fit=30)] == [b["id"], a["id"]]
    assert {r["id"] for r in db.list_jobs(con, run="r2")} == {b["id"], c["id"]}
    assert [r["id"] for r in db.list_jobs(con, status="dismissed")] == [b["id"]]
    assert {r["id"] for r in db.list_jobs(con, since=5)} == {b["id"], c["id"]}  # a is from January
    with pytest.raises(db.DBError):
        db.list_jobs(con, status="bogus")


def test_jobs_command(run, tmp_path):
    path = tmp_path / "j.db"
    for n, fit in ((1, 20), (2, 70)):
        run("db.py", "--db", path, "add-job", "--json",
            json.dumps({"source_url": f"https://jobs.lever.co/acme/{n}", "company": "Acme", "title": f"R{n}",
                        "fit_pre": fit, "run_id": "r1"}))
    r = run("db.py", "--db", path, "jobs", "--min-fit", "50", "--json")
    rows = json.loads(r.stdout)
    assert r.returncode == 0 and [x["title"] for x in rows] == ["R2"]
    rows = json.loads(run("db.py", "--db", path, "--json", "jobs", "--run", "r1", "--since", "1").stdout)
    assert len(rows) == 2
    assert "R2" in run("db.py", "--db", path, "jobs", "--status", "seen").stdout
    r = run("db.py", "--db", path, "set-job-status", rows[0]["id"], "shortlisted", "--reason", "good")
    assert r.returncode == 0 and "shortlisted" in r.stdout
    r = run("db.py", "--db", path, "set-job-status", rows[0]["id"], "loved")
    assert r.returncode == 1 and "not one of" in r.stderr
    assert run("db.py", "--db", path, "jobs", "--since", "x").returncode == 4
    r = run("db.py", "--db", path, "add-job", "--json",
            json.dumps({"source_url": "https://jobs.lever.co/acme/9", "remote": "sometimes"}))
    assert r.returncode == 1 and "remote" in r.stderr and "hybrid" in r.stderr


# ------------------------------------------------------------------------ runs

def test_runs(con):
    rid = db.start_run(con, 7, ["adzuna", "reed"])
    assert len(rid) == 15 and rid[8] == "-" and rid.replace("-", "").isdigit()
    rid2 = db.start_run(con, 7, ["adzuna"])
    assert rid2 != rid  # two runs in the same second still get distinct ids
    assert db.last_finished_run(con) is None
    job(con, 1, run_id=rid)
    done = db.finish_run(con, rid, 12, 1, {"reed": "key rejected"})
    assert done["found"] == 12 and done["new"] == 1 and done["errors"] == {"reed": "key rejected"}
    assert done["sources"] == ["adzuna", "reed"] and done["jobs_first_found"] == 1 and done["finished_at"]
    assert db.last_finished_run(con) is None  # that run had an error
    db.finish_run(con, rid2, 3, 3, None)
    assert db.last_finished_run(con)["id"] == rid2
    assert {r["id"] for r in db.list_runs(con)} == {rid, rid2}
    with pytest.raises(db.DBError):
        db.finish_run(con, "nope", 0, 0, None)
    assert [r["kind"] for r in con.execute("SELECT kind FROM events WHERE kind = 'run'")] == ["run"] * 4


def test_runs_commands(run, tmp_path):
    path = tmp_path / "r.db"
    con = db.connect(path)
    rid = db.start_run(con, 7, ["nhs"])
    db.finish_run(con, rid, 4, 2, [])
    con.close()
    rows = json.loads(run("db.py", "--db", path, "runs", "list", "--json").stdout)
    assert rows[0]["id"] == rid and rows[0]["found"] == 4
    assert json.loads(run("db.py", "--db", path, "--json", "runs").stdout)[0]["id"] == rid
    assert rid in run("db.py", "--db", path, "runs").stdout
    shown = json.loads(run("db.py", "--db", path, "runs", "show", rid, "--json").stdout)
    assert shown["sources"] == ["nhs"] and shown["new"] == 2
    assert run("db.py", "--db", path, "runs", "show", "nope").returncode == 1


# ---------------------------------------------------------------- applications

def test_new_application_statuses_and_columns(con):
    assert db.APP_STATUSES == ("draft", "ready", "submitted", "acknowledged", "screening", "interviewing",
                               "offer", "rejected", "withdrawn", "ghosted")
    j = job(con, 1)
    a = db.add_application(con, {"job_id": j["id"], "status": "ready", "found_via": "reed", "cv_variant": "abc123",
                                 "role_family": "analytics", "follow_up_due": "2026-11-20",
                                 "last_contact": "2026-11-03"})
    assert (a["found_via"], a["cv_variant"], a["role_family"]) == ("reed", "abc123", "analytics")
    assert a["follow_up_due"] == "2026-11-20" and a["last_contact"] == "2026-11-03"
    u = db.add_application(con, {"job_id": j["id"], "status": "ghosted", "outcome_reason": "no reply in 21 days"},
                           update=True)
    assert u["status"] == "ghosted" and u["submitted_at"] and u["outcome_reason"] == "no reply in 21 days"
    assert u["found_via"] == "reed"  # --update merges, it does not blank
    assert db.set_status(con, a["id"], "screening")["status"] == "screening"
    with pytest.raises(db.DBError, match="YYYY-MM-DD"):
        db.add_application(con, {"job_id": j["id"], "follow_up_due": "next week"}, update=True)
    with pytest.raises(db.DBError, match="not one of"):
        db.set_status(con, a["id"], "hired")
    with pytest.raises(db.DBError, match="already exists"):
        db.add_application(con, {"job_id": j["id"]})


def test_screening_counts_as_a_response(con):
    j = job(con, 1)
    a = db.add_application(con, {"job_id": j["id"], "status": "submitted"})
    db.set_status(con, a["id"], "screening")
    st = db.stats(con, {})
    assert st["responses"] == 1 and st["by_status"]["screening"] == 1 and st["by_status"]["ghosted"] == 0


# ------------------------------------------------------------ contacts, messages

def test_contact_ids_and_validation(con):
    c = db.add_contact(con, {"name": "Sam Lee", "org": "Acme", "email": "Sam@Acme.com", "kind": "hiring-manager"})
    assert c["id"] == "c-" + sha("sam@acme.com")[:10] and c["created"] and c["email"] == "sam@acme.com"
    assert c["email_verified"] == "unverified" and c["suppressed"] == 0
    li = db.add_contact(con, {"name": "Pat", "linkedin_url": "https://linkedin.com/in/Pat"})
    assert li["id"] == "c-" + sha("https://linkedin.com/in/pat")[:10] and li["kind"] == "other"
    nm = db.add_contact(con, {"name": "Kim Ng", "org": "Beta"})
    assert nm["id"] == "c-" + sha("kim ngbeta")[:10]
    again = db.add_contact(con, {"email": "sam@acme.com", "role": "Head of Data", "email_verified": "domain"})
    assert again["id"] == c["id"] and not again["created"] and again["role"] == "Head of Data"
    assert again["name"] == "Sam Lee" and again["email_verified"] == "domain"
    assert len(db.list_contacts(con)) == 3
    with pytest.raises(db.DBError, match="agency"):
        db.add_contact(con, {"email": "x@y.com", "kind": "friend"})
    with pytest.raises(db.DBError):
        db.add_contact(con, {"role": "nobody"})
    with pytest.raises(db.DBError, match="unknown contact field"):
        db.add_contact(con, {"email": "x@y.com", "phone": "1"})
    assert con.execute("SELECT COUNT(*) FROM events WHERE kind = 'contact-added'").fetchone()[0] == 3


def test_suppress_contact(con):
    c = db.add_contact(con, {"email": "a@b.com", "notes": "met at event"})
    s = db.suppress_contact(con, c["id"], "asked not to be contacted")
    assert s["suppressed"] == 1 and "met at event" in s["notes"] and "asked not to be contacted" in s["notes"]
    assert db.list_contacts(con) == [] and len(db.list_contacts(con, include_suppressed=True)) == 1
    assert db.add_contact(con, {"email": "a@b.com", "role": "x"})["suppressed"] == 1  # re-adding cannot undo it
    with pytest.raises(db.DBError, match="suppressed"):
        db.add_message(con, {"contact_id": c["id"], "channel": "email"})
    with pytest.raises(db.DBError, match="reason"):
        db.suppress_contact(con, c["id"], " ")
    with pytest.raises(db.DBError, match="no contact"):
        db.suppress_contact(con, "c-nope", "x")


def test_messages(con):
    c = db.add_contact(con, {"email": "a@b.com"})
    j = job(con, 1)
    m = db.add_message(con, {"contact_id": c["id"], "channel": "email", "job_id": j["id"],
                             "draft_path": "outreach/a.md"})
    assert m["id"].startswith("m-") and m["sent_at"] is None
    for bad in ({"contact_id": c["id"], "channel": "fax"}, {"contact_id": c["id"], "channel": "email",
                                                           "sent_by": "robot"},
                {"contact_id": "c-nope", "channel": "email"}, {"channel": "email"}, {"contact_id": c["id"]},
                {"contact_id": c["id"], "channel": "email", "follow_up_due": "soon"},
                {"contact_id": c["id"], "channel": "email", "colour": "red"}):
        with pytest.raises(db.DBError):
            db.add_message(con, bad)
    sent = db.update_message(con, m["id"], {"sent_at": "2026-11-03T09:00:00Z", "sent_by": "user",
                                            "follow_up_due": "2026-11-09"})
    assert sent["sent_by"] == "user"
    assert db.messages_due(con, "2026-11-08") == []
    due = db.messages_due(con, date(2026, 11, 9))
    assert [d["id"] for d in due] == [m["id"]] and due[0]["contact_email"] == "a@b.com"
    assert len(db.messages_due(con, "2026-12-01")) == 1
    db.update_message(con, m["id"], {"reply_at": "2026-11-05T10:00:00Z", "outcome": "replied"})
    assert db.messages_due(con, "2026-12-01") == []
    kinds = [r["kind"] for r in con.execute("SELECT kind FROM events WHERE kind IN ('message-sent','reply')")]
    assert kinds == ["message-sent", "reply"]
    with pytest.raises(db.DBError, match="not one of"):
        db.update_message(con, m["id"], {"channel": "pigeon"})
    with pytest.raises(db.DBError, match="no message"):
        db.update_message(con, "m-nope", {"outcome": "x"})
    with pytest.raises(db.DBError, match="contact_id"):
        db.update_message(con, m["id"], {"contact_id": "c-other"})


def test_messages_due_skips_suppressed_contacts(con):
    c = db.add_contact(con, {"email": "a@b.com"})
    m = db.add_message(con, {"contact_id": c["id"], "channel": "linkedin", "sent_at": "2026-11-01T09:00:00Z",
                             "sent_by": "user", "follow_up_due": "2026-11-07"})
    assert len(db.messages_due(con, "2026-11-07")) == 1
    db.suppress_contact(con, c["id"], "said no")
    assert db.messages_due(con, "2026-11-07") == []
    assert m["id"]


# ------------------------------------------------------------------------ stats

def make_apps(con, n, status="submitted"):
    for i in range(n):
        j = job(con, 100 + i, company=f"Company{i}", title="Analyst")
        db.add_application(con, {"job_id": j["id"], "status": status, "method": "ats-form"})


def test_auto_eligible_cases(con):
    assert db.stats(con, {})["auto_eligible"] is False
    make_apps(con, 19)
    st = db.stats(con, {})
    assert st["auto_eligible"] is False and "19 of 20" in st["auto_eligible_progress"]
    make_apps_one = job(con, 500, company="Twenty", title="Analyst")
    a = db.add_application(con, {"job_id": make_apps_one["id"], "status": "draft", "method": "ats-form"})
    assert db.stats(con, {})["auto_eligible"] is False  # a draft is not a submission
    db.set_status(con, a["id"], "rejected")
    assert db.stats(con, {})["auto_eligible"] is True
    db.add_event(con, "wrong-field", "put notice period in salary", application_id=a["id"])
    assert db.stats(con, {})["auto_eligible"] is False
    con.execute("DELETE FROM events WHERE kind = 'wrong-field'")
    con.commit()
    assert db.stats(con, {})["auto_eligible"] is True
    ev = db.add_event(con, "ledger-failure", "number not in cited fact", application_id=a["id"])
    assert ev["kind"] == "ledger-failure"
    st = db.stats(con, {})
    assert st["auto_eligible"] is False and st["ledger_failure_events"] == 1


def test_auto_eligible_counts_all_post_submit_statuses(con):
    statuses = ["submitted", "acknowledged", "screening", "interviewing", "offer", "rejected", "ghosted"]
    for i in range(20):
        j = job(con, 200 + i, company=f"C{i}", title="Analyst")
        db.add_application(con, {"job_id": j["id"], "status": statuses[i % len(statuses)], "method": "ats-form"})
    assert db.stats(con, {})["auto_eligible"] is True
    j = job(con, 300, company="W", title="Analyst")
    db.add_application(con, {"job_id": j["id"], "status": "withdrawn", "submitted_at": "2026-10-01T00:00:00Z"})
    assert db.stats(con, {})["auto_eligible"] is True  # withdrawn is neither counted nor blocking


def test_stats_new_keys_and_old_keys(con):
    a = job(con, 1, source="reed", status="shortlisted")
    job(con, 2, source="reed")
    job(con, 3, source="adzuna")
    j = job(con, 4)
    app = db.add_application(con, {"job_id": a["id"], "status": "submitted"})
    st = db.stats(con, {"limits": {"daily_applications": 15, "hard_cap": 25}})
    assert st["jobs_by_status"]["seen"] == 3 and st["jobs_by_status"]["shortlisted"] == 1
    assert st["jobs_by_source"] == {"reed": 2, "adzuna": 1, "unknown": 1}
    days = list(st["submitted_per_day"].items())
    assert len(days) == 14 and days[-1] == (date.today().isoformat(), 1)
    assert days[0][0] == (date.today() - timedelta(days=13)).isoformat() and sum(v for _, v in days) == 1
    for key in ("submitted_today", "daily_limit", "hard_cap", "daily_remaining", "by_status", "by_method",
                "wrong_field_events", "submitted_last_7_days", "response_rate", "interview_rate", "offer_rate"):
        assert key in st
    assert st["submitted_today"] == 1 and st["daily_remaining"] == 14 and st["schema_version"] == 2
    assert j["id"] and app["id"]


def test_events_add_ledger_failure_command(run, tmp_path):
    path = tmp_path / "e.db"
    r = run("db.py", "--db", path, "add-job", "--json", json.dumps({"source_url": "https://jobs.lever.co/a/1"}))
    jid = r.stdout.strip()
    r = run("db.py", "--db", path, "events", "add", "--kind", "ledger-failure", "--job", jid, "--detail", "x")
    assert r.returncode == 0 and r.stdout.strip().isdigit()
    st = json.loads(run("db.py", "--db", path, "stats", "--json").stdout)
    assert st["ledger_failure_events"] == 1 and st["auto_eligible"] is False
    assert "ledger-failure" in db.KNOWN_EVENT_KINDS


# ---------------------------------------------------------------------- secrets

def test_secrets_never_leave_in_json(run, tmp_path):
    path = tmp_path / "s.db"
    c = db.connect(path)
    for k, v in (("adzuna_app_key", "SECRETVALUE1"), ("reed_API_KEY", "SECRETVALUE2"), ("github_token", "SECRETVALUE3"),
                 ("client_Secret", "SECRETVALUE4"), ("locale", "uk")):
        c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (k, v))
    c.commit()
    c.close()
    r = run("db.py", "--db", path, "--json", "export", "--out", tmp_path / "x")
    assert r.returncode == 0 and "SECRETVALUE" not in r.stdout
    dump = (tmp_path / "x" / "jobferret-export.json").read_text(encoding="utf-8")
    csv_text = (tmp_path / "x" / "settings.csv").read_text(encoding="utf-8")
    assert "SECRETVALUE" not in dump and "SECRETVALUE" not in csv_text
    assert "locale" in dump and "schema_version" in dump
    for name in ("jobs", "runs", "contacts", "messages"):
        assert (tmp_path / "x" / f"{name}.csv").is_file()
    for args in (("stats",), ("jobs",), ("runs",), ("list",)):
        assert "SECRETVALUE" not in run("db.py", "--db", path, "--json", *args).stdout


def test_scrub_helper():
    rows = [{"key": "reed_api_key", "value": "x"}, {"key": "locale", "value": "uk"}]
    assert db.scrub(rows) == [{"key": "locale", "value": "uk"}]
    assert db.scrub({"api_key": "x", "appKey": "y", "token": "z", "keywords": ["a"], "n": 1}) == \
        {"keywords": ["a"], "n": 1}
