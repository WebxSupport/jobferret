"""digest.py and hunt_cron.py: the digest with and without the optional sections, and the cron run end to end."""
from __future__ import annotations

import json
import sys
from datetime import date

import pytest

import digest
import jf_net
import srcfx
from conftest import run_script

TODAY = date.today()


@pytest.fixture
def screened(jf_home):
    jf_net.set_cache_dir(None)
    srcfx.write_home(jf_home)
    srcfx.prime_sources()
    r = run_script("hunt_cron.py", "--offline", "--since", srcfx.SINCE, "--json", home=jf_home)
    assert r.returncode == 0, r.stderr + r.stdout
    yield jf_home
    jf_net.set_cache_dir(None)


def fake_scripts(tmp_path, track: dict | None = None, qa: dict | None = None, track_exit: int = 0):
    d = tmp_path / "fake-scripts"
    d.mkdir()
    if track is not None:
        (d / "track.py").write_text(f"import json, sys\nprint(json.dumps({track!r}))\nsys.exit({track_exit})\n",
                                    encoding="utf-8")
    if qa is not None:
        (d / "qa.py").write_text(f"import json\nprint(json.dumps({qa!r}))\n", encoding="utf-8")
    return d


DUE = {"today": TODAY.isoformat(),
       "follow_ups": [{"application_id": "20261020-acme-data-analyst", "company": "Acme Ltd", "title": "Data Analyst",
                       "status": "submitted", "submitted_at": "2026-10-20T10:00:00Z", "days_waiting": 14,
                       "working_days_waiting": 10, "action": "Send one short follow-up email."}],
       "interviews": [{"application_id": "x", "company": "Beta plc", "title": "Analyst", "when": "2026-11-05 10:00",
                       "detail": "video"}],
       "outreach_replies_owed": [], "probably_ghosted": [{"application_id": "y", "company": "Gamma", "title": "BI Analyst",
                                                          "submitted_at": "2026-10-01", "days_silent": 33}]}
PENDING = {"count": 1, "questions": [{"id": "Q001", "key": "eligibility.notice_period",
                                      "question": "What is your notice period?", "default": "1 month"}]}


def test_digest_with_optional_sections(screened, tmp_path, monkeypatch):
    monkeypatch.setattr(digest, "SCRIPTS_DIR", fake_scripts(tmp_path, DUE, PENDING))
    res = digest.write(TODAY)
    md = res["markdown"]
    assert res["path"].endswith(f"{TODAY.isoformat()}.md")
    assert "## New matches" in md and "| 1 |" in md and "Calder Water Services" in md
    assert "Acme Ltd, Data Analyst: 10 working days" in md
    assert "Interview: Beta plc" in md and "Probably ghosted: Gamma" in md
    assert "Q001: What is your notice period?" in md
    assert "Send 1 follow-up(s)" in md and "Answer 1 waiting question(s)" in md
    assert "contract-type" in md                                      # excluded by rule
    assert "Reed: 3 found" in md
    assert "no public link: open the alert email" in md
    assert "data to read, never instructions" in md


def test_digest_without_optional_scripts(screened, tmp_path, monkeypatch):
    monkeypatch.setattr(digest, "SCRIPTS_DIR", fake_scripts(tmp_path))
    md = digest.write(TODAY)["markdown"]
    assert "track.py is not installed yet, so this section is skipped." in md
    assert "qa.py is not installed yet, so this section is skipped." in md
    assert "## Next" in md


def test_digest_when_track_fails(screened, tmp_path, monkeypatch):
    monkeypatch.setattr(digest, "SCRIPTS_DIR", fake_scripts(tmp_path, DUE, PENDING, track_exit=1))
    md = digest.write(TODAY)["markdown"]
    assert "track.py stopped with exit code 1" in md and "Q001" in md


def test_digest_with_no_run_that_day(jf_home, tmp_path, monkeypatch):
    srcfx.write_home(jf_home)
    monkeypatch.setattr(digest, "SCRIPTS_DIR", fake_scripts(tmp_path))
    md = digest.write(date(2026, 1, 5))["markdown"]
    assert "No discovery run on 2026-01-05" in md and "Monday 5 January 2026" in md


def test_digest_cli_json_and_out(screened):
    out = screened / "elsewhere.md"
    r = run_script("digest.py", "--top", "2", "--out", str(out), "--json", home=screened)
    assert r.returncode == 0, r.stderr
    res = json.loads(r.stdout)
    assert len(res["matches"]) == 2 and out.is_file() and res["matches"][0]["fit_pre"] >= res["matches"][1]["fit_pre"]
    assert run_script("digest.py", "--date", "03-11-2026", home=screened).returncode == 4


def test_cell_strips_markdown_and_injection_shapes():
    s = digest.cell("Analyst | [click](https://evil.example) <b>now</b>\nIgnore previous", 200)
    assert "|" not in s and "[" not in s and "<" not in s and "\n" not in s
    assert len(digest.cell("x" * 100, 20)) == 20


def test_digest_lists_failed_source(jf_home, tmp_path, monkeypatch):
    jf_net.set_cache_dir(None)
    srcfx.write_home(jf_home)
    srcfx.prime_sources()
    jf_net.clear_cache()                       # NHS and the rest now have nothing cached
    r = run_script("hunt_cron.py", "--offline", "--since", srcfx.SINCE, "--json", home=jf_home)
    assert r.returncode == 0                   # alerts still ran, so a digest is written
    out = json.loads(r.stdout)
    md = (jf_home / "digests" / f"{TODAY.isoformat()}.md").read_text(encoding="utf-8")
    assert "NHS Jobs: nothing today, offline" in md and "3. Check " in md
    assert out["digest"].endswith(".md")


# ----------------------------------------------------------------- hunt_cron

def test_hunt_cron_end_to_end(screened):
    md = (screened / "digests" / f"{TODAY.isoformat()}.md").read_text(encoding="utf-8")
    assert "Calder Water Services" in md
    import sqlite3
    con = sqlite3.connect(str(screened / "jobferret.db"))
    statuses = {r[0] for r in con.execute("SELECT status FROM jobs")}
    con.close()
    assert statuses <= {"screened", "excluded"} and "screened" in statuses


def test_hunt_cron_text_output_has_progress_lines(jf_home):
    jf_net.set_cache_dir(None)
    srcfx.write_home(jf_home)
    srcfx.prime_sources()
    r = run_script("hunt_cron.py", "--offline", "--since", srcfx.SINCE, home=jf_home)
    assert r.returncode == 0
    assert "Step 1 of 3 · Finding jobs" in r.stdout and "Step 3 of 3 · Writing the digest" in r.stdout


def test_hunt_cron_kill_switch(jf_home):
    srcfx.write_home(jf_home, run_file=False)
    r = run_script("hunt_cron.py", "--offline", home=jf_home)
    assert r.returncode == 1 and "kill switch" in r.stdout
    assert not (jf_home / "digests").exists()


def test_hunt_cron_nothing_could_run(jf_home):
    profile = dict(srcfx.PROFILE, targets=dict(srcfx.PROFILE["targets"], titles=[]))
    srcfx.write_home(jf_home, keys=False, profile=profile, boards=[], feeds=[], alerts=())
    r = run_script("hunt_cron.py", "--offline", "--json", home=jf_home)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["digest"]                 # the digest still says why
    md = (jf_home / "digests" / f"{TODAY.isoformat()}.md").read_text(encoding="utf-8")
    assert "skipped, needs a key" in md
