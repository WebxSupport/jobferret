"""Fixes found by the smoke tests: --update by id, backdated submissions, setup_check --set, digest reasons."""
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def run(home: Path, script: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "JOBFERRET_HOME": str(home)}
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                          capture_output=True, text=True, env=env, encoding="utf-8")


def seed_application(home: Path) -> str:
    assert run(home, "setup_check.py", "--create").returncode == 0
    job = json.loads(run(home, "db.py", "--json", "add-job", "--json",
                         '{"canonical_url": "https://boards.greenhouse.io/x/jobs/1", "company": "X Ltd", "title": "Data Analyst"}').stdout)
    app = json.loads(run(home, "db.py", "--json", "add-application", "--json",
                         json.dumps({"job_id": job["id"], "status": "draft", "method": "ats-form"})).stdout)
    return app["id"]


def test_add_application_update_accepts_id(tmp_path):
    home = tmp_path / "home"
    app_id = seed_application(home)
    r = run(home, "db.py", "add-application", "--update", "--json",
            json.dumps({"id": app_id, "submitted_at": "2026-10-22T10:00:00", "status": "submitted"}))
    assert r.returncode == 0, r.stdout + r.stderr
    shown = json.loads(run(home, "db.py", "--json", "show", app_id).stdout)
    app = shown.get("application", shown)
    assert app["status"] == "submitted" and app["submitted_at"].startswith("2026-10-22")
    # id without --update is refused with a plain message
    r = run(home, "db.py", "add-application", "--json", json.dumps({"id": app_id, "job_id": "whatever"}))
    assert r.returncode != 0 and "accepted only with --update" in (r.stdout + r.stderr)


def test_track_set_when_backdates_the_submission(tmp_path):
    home = tmp_path / "home"
    app_id = seed_application(home)
    r = run(home, "track.py", "set", app_id, "--status", "submitted", "--when", "2026-10-20")
    assert r.returncode == 0, r.stdout + r.stderr
    due = json.loads(run(home, "track.py", "due", "--today", "2026-11-03", "--json").stdout)
    owed = [f for f in due["follow_ups"] if f["application_id"] == app_id]
    assert owed and owed[0]["submitted_at"].startswith("2026-10-20") and owed[0]["working_days_waiting"] >= 7


def test_setup_check_set_writes_config(tmp_path):
    home = tmp_path / "home"
    r = run(home, "setup_check.py", "--create", "--set", "browser.preferred=pane",
            "--set", "limits.daily_applications=10", "--set", "sources.enabled=nhs,teaching", "--set", "ux.chattiness=brief")
    assert r.returncode == 0, r.stdout + r.stderr
    cfg = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["browser"]["preferred"] == "pane" and cfg["limits"]["daily_applications"] == 10
    assert cfg["sources"]["enabled"] == ["nhs", "teaching"] and cfg["ux"]["chattiness"] == "brief"
    assert cfg["limits"]["hard_cap"] == 25          # untouched defaults stay
    bad = run(home, "setup_check.py", "--set", "nonsense")
    assert bad.returncode != 0 and "KEY=VALUE" in (bad.stdout + bad.stderr)


def test_digest_prefers_recorded_reason():
    sys.path.insert(0, str(SCRIPTS))
    import digest
    job = {"status": "shortlisted", "status_reason": "fit 8/10: SQL and Power BI asked for",
           "screen": {"scores": {"title": 40}, "flags": ["salary-not-stated"]}}
    assert digest.why(job) == "fit 8/10: SQL and Power BI asked for"
    job["status"] = "screened"
    assert digest.why(job).startswith("title matches")
