"""Tests for the first-run scripts: setup_ui.py, profile_prefill.py, qa.py, state.py and the jf_common helpers."""
import http.client
import json
import os
import shutil
import subprocess
import sys
import tomllib
from urllib.parse import urlsplit

import pytest

import jf_common as jc
import setup_ui
from conftest import SAMPLE_LEDGER, SCRIPTS, run_script


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- profile_prefill

def test_prefill_from_sample_ledger(tmp_path):
    home = tmp_path / "h"
    out = home / "profile.json"
    r = run_script("profile_prefill.py", "--ledger", SAMPLE_LEDGER, "--out", out, "--json", home=home)
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    p = load(out)
    assert p["personal"]["name"] == "Hannah Okafor"
    assert p["personal"]["email"] == "hannah.okafor@example.com"
    assert p["personal"]["phone"] == "07700 900123"
    assert p["personal"]["linkedin"] == "linkedin.com/in/hannah-okafor-example"
    assert p["personal"]["links"] == []  # the email's domain is not a link
    assert p["personal"]["location"] == "Leeds"
    assert p["current"] == {"title": "Senior Finance Analyst", "employer": "Northgate Foods Ltd"}
    assert p["targets"]["titles"] == ["Senior Finance Analyst"]
    assert p["targets"]["seniority"] == "senior"
    assert [r["employer"] for r in p["history"]["roles"]] == [
        "Northgate Foods Ltd", "Pennine Freight plc", "Calder Valley Housing Association"]
    assert p["history"]["highest_qualification"] == "BSc Accounting and Finance (2:1)"
    assert "Power BI" in p["history"]["skills"]
    # empty with the right types, and the apply.md field names still there
    assert p["targets"]["salary_floor"] == {"amount": 0, "currency": "GBP", "period": "year"}
    assert p["eligibility"]["sponsorship_needed_ever"] is False
    assert p["preferences"]["cover_letter"] == "ask"
    assert isinstance(p["answer_bank"]["skills_years"], list)
    assert p["meta"]["status"] == "draft"
    assert p["meta"]["prefill"]["personal.name"] == "Hannah Okafor"
    assert rep["filled"]["personal.name"]["source"] == "F001"
    assert "eligibility.right_to_work" in rep["empty"]
    # one schema, no mirror keys (ARCHITECTURE 8.4 reads the canonical fields)
    assert p["targets"]["locations"][0] == "Leeds" and p["targets"]["salary_floor"]["period"] == "year"
    assert "location" not in p and "pay" not in p


def test_prefill_refuses_overwrite_without_merge(tmp_path):
    out = tmp_path / "profile.json"
    out.write_text("{}", encoding="utf-8")
    r = run_script("profile_prefill.py", "--ledger", SAMPLE_LEDGER, "--out", out, home=tmp_path / "h")
    assert r.returncode == 4
    assert out.read_text(encoding="utf-8") == "{}"


def test_prefill_merge_keeps_user_values(tmp_path):
    home = tmp_path / "h"
    out = home / "profile.json"
    assert run_script("profile_prefill.py", "--ledger", SAMPLE_LEDGER, "--out", out, home=home).returncode == 0
    p = load(out)
    p["targets"]["titles"] = ["Finance Business Partner"]       # user changed a guess
    p["answer_bank"]["why_looking"] = "Contract ends in March"    # user-only field
    p["personal"]["phone"] = ""                                   # user cleared it: empty gets refilled
    out.write_text(json.dumps(p), encoding="utf-8")
    r = run_script("profile_prefill.py", "--ledger", SAMPLE_LEDGER, "--out", out, "--merge", "--json", home=home)
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    p2 = load(out)
    assert p2["targets"]["titles"] == ["Finance Business Partner"]
    assert p2["answer_bank"]["why_looking"] == "Contract ends in March"
    assert p2["personal"]["phone"] == "07700 900123"
    assert "targets.titles" in rep["kept_user_values"]
    assert "targets.titles" not in p2["meta"]["prefill"]


def test_prefill_empty_ledger_exits_1(tmp_path):
    led = tmp_path / "l.json"
    led.write_text(json.dumps(jc.new_ledger()), encoding="utf-8")
    r = run_script("profile_prefill.py", "--ledger", led, "--out", tmp_path / "p.json", home=tmp_path / "h")
    assert r.returncode == 1
    assert not (tmp_path / "p.json").exists()


# --------------------------------------------------------------------------- qa

def qa(home, *args):
    return run_script("qa.py", *args, home=home)


def test_qa_add_dedup_answer_drop(tmp_path):
    home = tmp_path / "h"
    r = qa(home, "add", "--key", "why_looking", "--question", "Why are you looking?", "--options", "a,b", "--json")
    assert r.returncode == 0, r.stderr
    q1 = json.loads(r.stdout)["question"]
    assert q1["id"] == "Q001" and q1["options"] == ["a", "b"]
    r = qa(home, "add", "--key", "why_looking", "--question", "Why again?", "--json")
    assert json.loads(r.stdout)["question"]["id"] == "Q001"
    qa(home, "add", "--key", "targets.salary_floor.amount", "--question", "Lowest salary?")
    qa(home, "add", "--key", "relocate", "--question", "Relocate?")
    r = qa(home, "pending", "--json")
    pend = json.loads(r.stdout)
    assert pend["count"] == 3 and [q["id"] for q in pend["questions"]] == ["Q001", "Q002", "Q003"]

    r = qa(home, "answer", "1", "Contract ends in March")
    assert r.returncode == 0, r.stderr
    r = qa(home, "answer", "Q002", "£45k")
    assert r.returncode == 0, r.stderr
    prof = load(home / "profile.json")
    assert prof["answer_bank"]["why_looking"] == "Contract ends in March"
    assert prof["targets"]["salary_floor"]["amount"] == 45000
    assert qa(home, "answer", "Q001", "again").returncode == 1        # no longer pending
    assert qa(home, "drop", "Q003").returncode == 0
    assert json.loads(qa(home, "pending", "--json").stdout)["count"] == 0
    # answered keys are not queued again; dropped ones reopen
    r = qa(home, "add", "--key", "why_looking", "--question", "Why?", "--json")
    assert json.loads(r.stdout)["question"]["status"] == "answered"
    r = qa(home, "add", "--key", "relocate", "--question", "Relocate?", "--json")
    assert json.loads(r.stdout)["question"] == {**json.loads(r.stdout)["question"], "id": "Q003", "status": "pending"}
    store = load(home / "questions.json")
    assert store["version"] == 1 and len(store["questions"]) == 3


def test_qa_bad_key_and_missing_id(tmp_path):
    home = tmp_path / "h"
    assert qa(home, "add", "--key", "Bad Key", "--question", "x").returncode == 4
    assert qa(home, "add", "--key", "secrets.x", "--question", "x").returncode == 4
    assert qa(home, "answer", "Q009", "x").returncode == 1


# ------------------------------------------------------------------- state.py

def test_state_roundtrip(jf_home):
    assert jc.load_state() is None
    s1 = jc.save_state("start", 2, step_name="Find your CV", steps_total=7, context={"cv": "a.pdf"})
    s2 = jc.save_state("start", 3, step_name="Draft profile", context={"ledger": "l.json"})
    assert s2["started_at"] == s1["started_at"]
    assert s2["steps_total"] == 7 and s2["context"] == {"cv": "a.pdf", "ledger": "l.json"}
    assert "step 3 of 7 (Draft profile)" in jc.describe_state(s2)
    s3 = jc.save_state("apply", 1)
    assert s3["context"] == {}
    with pytest.raises(ValueError):
        jc.save_state("start", 1, status="bogus")
    assert jc.clear_state() and jc.load_state() is None


def test_state_cli(tmp_path):
    home = tmp_path / "h"
    assert run_script("state.py", "show", home=home).returncode == 1
    r = run_script("state.py", "set", "--mode", "start", "--step", "4", "--of", "7", "--name", "Preferences",
                   "--status", "waiting", "--context", '{"ui": true}', "--json", home=home)
    assert r.returncode == 0, r.stderr
    st = load(home / "state.json")
    assert {k: st[k] for k in ("mode", "step", "status")} == {"mode": "start", "step": 4, "status": "waiting"}
    assert run_script("state.py", "set", "--mode", "x", "--step", "1", "--context", "[1]", home=home).returncode == 4


def test_dump_toml_roundtrip():
    data = {"locale": {"default": "uk"}, "sources": {"enabled": ["adzuna"], "boards": {"employers": [
        {"name": "Acme \"UK\"", "platform": "greenhouse", "token": "acme"}]}}, "limits": {"daily_applications": 15}}
    assert tomllib.loads(jc.dump_toml(data)) == data


# ------------------------------------------------------------------ setup_ui

def start_ui(home, *extra):
    env = dict(os.environ, JOBFERRET_HOME=str(home), PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen([sys.executable, str(SCRIPTS / "setup_ui.py"), *extra], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env, cwd=str(SCRIPTS))
    line = proc.stdout.readline().strip()
    assert line.startswith("URL: http://127.0.0.1:"), line + proc.stderr.read()
    url = urlsplit(line[5:])
    return proc, url.port, url.query[2:]


def request(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8")
    conn.close()
    return resp.status, data, resp


FORM = {
    "targets": {"titles": ["Finance Business Partner", "Senior Finance Analyst"], "seniority": "senior",
                "role_families": ["Finance and accounting"]},
    "where": {"town": "Leeds", "radius_miles": "25", "work_modes": ["hybrid", "remote"], "relocate": "no"},
    "pay": {"amount": "48000", "period": "year", "contract_types": ["permanent"], "ir35": ""},
    "filters": {"dealbreakers": ["night shifts"], "companies": [], "no_agencies": True, "no_unpaid": True,
                "no_commission_only": True, "min_company_size": "50"},
    "eligibility": {"right_to_work": "citizen", "sponsorship_needed": False, "dbs": "basic", "clearance": "none",
                    "driving_licence": "full"},
    "availability": {"notice_period": "1 month", "earliest_start": "2027-01-04"},
    "channels": {"sources": ["adzuna", "nhs", "boards"], "employers": ["https://jobs.lever.co/acme", "Beta plc"],
                 "feeds": [], "adzuna_app_id": "abc123", "adzuna_app_key": "k3y", "reed_api_key": "",
                 "daily_applications": "12"},
    "communication": {"chattiness": "brief", "cover_letter": "required", "ai_disclosure": "drafting"},
}


@pytest.fixture
def prefilled_home(tmp_path):
    home = tmp_path / "uihome"
    r = run_script("setup_check.py", "--create", home=home)
    assert r.returncode in (0, 3), r.stdout + r.stderr
    r = run_script("profile_prefill.py", "--ledger", SAMPLE_LEDGER, "--out", home / "profile.json", home=home)
    assert r.returncode == 0, r.stderr
    p = load(home / "profile.json")
    p["answer_bank"]["why_looking"] = "Contract ends in March"
    (home / "profile.json").write_text(json.dumps(p), encoding="utf-8")
    return home


def test_setup_ui_full_flow(prefilled_home):
    home = prefilled_home
    proc, port, token = start_ui(home, "--timeout", "60", "--dump")
    try:
        assert len(token) == 32 and int(token, 16) >= 0
        assert request(port, "GET", "/")[0] == 403
        assert request(port, "GET", "/?t=" + "0" * 32)[0] == 403
        assert request(port, "GET", f"/?t={token}", headers={"Host": f"evil.example:{port}"})[0] == 403
        assert request(port, "GET", f"/other?t={token}")[0] == 404
        status, page, resp = request(port, "GET", f"/?t={token}")
        assert status == 200
        assert "Senior Finance Analyst" in page and "Hannah Okafor" in page and "Leeds" in page
        assert "script-src 'nonce-" in resp.getheader("Content-Security-Policy")
        assert "http://" not in page.split("<script")[0].split("</style>")[0]  # no external resources in head
        save = f"/save?t={token}"
        body = json.dumps(FORM)
        assert request(port, "POST", save, body, {"Content-Type": "text/plain"})[0] == 415
        assert request(port, "POST", save, body, {"Content-Type": "application/json",
                                                  "Origin": "http://evil.example"})[0] == 403
        bad = json.loads(body)
        bad["pay"]["period"] = "week"
        bad["targets"]["hack"] = 1
        st, data, _ = request(port, "POST", save, json.dumps(bad), {"Content-Type": "application/json"})
        assert st == 400 and len(json.loads(data)["errors"]) == 2
        st, data, _ = request(port, "POST", save, body, {"Content-Type": "application/json"})
        assert st == 200 and "Saved. Go back to the chat." in data
        out, _ = proc.communicate(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0
    assert "SAVED profile=" in out
    dumped = json.loads(out[out.index("{"):])
    assert dumped["channels"]["adzuna_app_key"] == "(set)" and "k3y" not in out

    p = load(home / "profile.json")
    assert p["targets"]["titles"] == ["Finance Business Partner", "Senior Finance Analyst"]
    assert p["targets"]["salary_floor"] == {"amount": 48000, "currency": "GBP", "period": "year"}
    assert p["targets"]["work_modes"] == ["hybrid", "remote"] and p["targets"]["radius_miles"] == 25
    assert p["eligibility"]["right_to_work"] == "citizen" and p["eligibility"]["dbs"] == "basic"
    assert p["exclusions"]["filters"]["no_agencies"] is True
    assert p["preferences"]["cover_letter"] == "required"
    assert p["answer_bank"]["why_looking"] == "Contract ends in March"   # not owned by the page: kept
    assert p["personal"]["name"] == "Hannah Okafor"
    assert p["meta"]["status"] == "confirmed" and "targets.titles" not in p["meta"]["prefill"]
    assert p["targets"]["salary_floor"]["amount"] == 48000 and p["eligibility"]["sponsorship_needed_ever"] is False

    cfg = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["sources"]["enabled"] == ["adzuna", "nhs", "boards"]
    assert cfg["sources"]["adzuna"] == {"app_id": "abc123", "app_key": "k3y"}
    assert cfg["sources"]["boards"]["employers"] == [{"name": "acme", "platform": "lever", "token": "acme"},
                                                    {"name": "Beta plc", "platform": "", "token": ""}]
    assert cfg["limits"]["daily_applications"] == 12 and cfg["limits"]["hard_cap"] == 25
    assert cfg["ux"]["chattiness"] == "brief"
    assert cfg["locale"]["default"] == "uk"


def test_setup_ui_escapes_and_keeps_keys_secret(tmp_path):
    home = tmp_path / "h"
    p = jc.empty_profile()
    p["targets"]["titles"] = ['<script>alert(1)</script>']
    home.mkdir()
    (home / "profile.json").write_text(json.dumps(p), encoding="utf-8")
    jc.update_config({"sources": {"reed": {"api_key": "SECRET-REED"}}}, home / "config.toml")
    proc, port, token = start_ui(home, "--timeout", "30")
    try:
        _, page, _ = request(port, "GET", f"/?t={token}")
    finally:
        proc.kill()
        proc.communicate()
    assert "<script>alert(1)" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "SECRET-REED" not in page and "Saved. Leave blank to keep." in page


def test_setup_ui_timeout(tmp_path):
    proc, port, token = start_ui(tmp_path / "h", "--timeout", "1")
    out, _ = proc.communicate(timeout=20)
    assert proc.returncode == 2 and "TIMEOUT" in out
    assert not (tmp_path / "h" / "profile.json").exists()


def test_setup_ui_prefill_only_and_from_json(prefilled_home, tmp_path):
    home = prefilled_home
    r = run_script("setup_ui.py", "--prefill-only", home=home)
    assert r.returncode == 0
    st = json.loads(r.stdout)
    assert st["targets"]["titles"] == ["Senior Finance Analyst"] and st["where"]["town"] == "Leeds"
    assert st["channels"]["daily_applications"] == 15 and st["communication"]["chattiness"] == "normal"

    part = tmp_path / "answers.json"
    part.write_text(json.dumps({"targets": {"titles": ["Management Accountant"]},
                                "where": {"town": "Leeds", "work_modes": ["hybrid"]},
                                "pay": {"amount": 450, "period": "day"},
                                "eligibility": {"right_to_work": "citizen", "sponsorship_needed": False}}),
                    encoding="utf-8")
    r = run_script("setup_ui.py", "--from-json", part, home=home)
    assert r.returncode == 0, r.stdout + r.stderr
    p = load(home / "profile.json")
    assert p["targets"]["titles"] == ["Management Accountant"]
    assert p["targets"]["salary_floor"]["period"] == "day" and p["targets"]["salary_floor"]["amount"] == 450
    assert p["preferences"]["cover_letter"] == "ask"      # untouched sections keep their values
    part.write_text(json.dumps({"pay": {"amount": 9000, "period": "day"}}), encoding="utf-8")
    r = run_script("setup_ui.py", "--from-json", part, home=home)
    assert r.returncode == 1 and "day rate" in r.stdout


def test_setup_ui_usage_errors(tmp_path):
    assert run_script("setup_ui.py", "--timeout", "0", home=tmp_path / "h").returncode == 4
    home = tmp_path / "bad"
    home.mkdir()
    (home / "profile.json").write_text("{not json", encoding="utf-8")
    assert run_script("setup_ui.py", "--prefill-only", home=home).returncode == 4


def test_validate_unit():
    clean, errors = setup_ui.validate({"where": {"radius_miles": 9999}, "nope": {}}, setup_ui.DEFAULT_ENABLED)
    assert len(errors) == 2
    clean, errors = setup_ui.validate({"channels": {"feeds": ["javascript:alert(1)"]}}, setup_ui.DEFAULT_ENABLED)
    assert errors
