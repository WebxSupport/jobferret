import json

import pytest

import jf_common as jc
from conftest import SAMPLE_MD, SCRIPTS, run_script


def test_split_sentences_keeps_trailing_citation():
    text = "Cut close from 9 to 5 days in Power Query. [F022,F043] Led the 2024 audit. [CONFIRM: which year?]"
    s = jc.split_sentences(text)
    assert s == ["Cut close from 9 to 5 days in Power Query. [F022,F043]",
                 "Led the 2024 audit. [CONFIRM: which year?]"]


def test_split_sentences_abbreviations_and_decimals():
    s = jc.split_sentences("Grew revenue 2.3x in 2024, e.g. Acme and Dr. Smith agreed. Then it fell.")
    assert len(s) == 2
    assert s[0].startswith("Grew revenue 2.3x")


def test_markers():
    t = "Built X for 12 people [F008, F041]. Also [CONFIRM: how many?] and [F12]."
    assert jc.find_citations(t) == ["F008", "F041"]
    assert jc.find_confirms(t) == ["how many?"]
    assert jc.find_malformed_citations(t) == ["[F12]"]
    assert "[" not in jc.strip_markers("Built X. [F008,F041]")
    assert jc.strip_markers("Built X [F008].") == "Built X."


def test_parse_cv_markdown_fixture():
    p = jc.parse_cv_markdown(SAMPLE_MD.read_text(encoding="utf-8"))
    assert p["name"] == "Hannah Okafor" and p["name_line"] == 1
    assert "hannah.okafor@example.com" in p["contact"] and p["contact_line"] == 2
    names = [s["name"] for s in p["sections"]]
    assert names == ["Profile", "Core skills", "Experience", "Education", "Certifications", "Projects",
                     "Earlier career", "Interests"]
    exp = p["sections"][2]["blocks"]
    assert [b["type"] for b in exp] == ["entry", "entry", "entry"]
    first = exp[0]
    assert (first["title"], first["org"], first["location"], first["dates"]) == (
        "Senior Finance Analyst", "Northgate Foods Ltd", "Leeds", "Mar 2022 – Present")
    assert first["start"] == "2022-03" and first["end"] is None and first["current"]
    assert len(first["children"]) == 6 and all(c["type"] == "bullet" for c in first["children"])
    assert first["children"][0]["citations"] == ["F010", "F034"]
    skills = p["sections"][1]["blocks"]
    assert [b["label"] for b in skills] == ["Finance", "Systems", "Data"]
    assert p["warnings"] == []


def test_entry_header_without_location():
    h = jc.parse_entry_header("BSc Computer Science (2:1) — University of Manchester | 2016 – 2019 [F050]")
    assert h["title"] == "BSc Computer Science (2:1)" and h["org"] == "University of Manchester"
    assert h["location"] == "" and h["start"] == "2016" and h["end"] == "2019"


def test_ledger_helpers(tmp_path):
    led = jc.new_ledger()
    assert jc.next_fact_id(led) == "F001"
    led["facts"] = [{"id": "F001"}, {"id": "F009"}]
    assert jc.next_fact_id(led) == "F010"
    path = tmp_path / "l.json"
    jc.save_ledger(led, path)
    assert jc.load_ledger(path)["facts"][1]["id"] == "F009"
    path.write_text(json.dumps({"facts": [{"id": "F001"}, {"id": "F001"}]}), encoding="utf-8")
    with pytest.raises(jc.LedgerError, match="duplicate"):
        jc.load_ledger(path)
    path.write_text("{nope", encoding="utf-8")
    with pytest.raises(jc.LedgerError, match="not valid JSON"):
        jc.load_ledger(path)


def test_contact_and_phone_detection():
    assert jc.is_contact_line("London · 07700 900000 · jane@example.com · linkedin.com/in/jane")
    assert not jc.is_contact_line("Analyst, Gamma Ltd 2017-2019")
    assert jc.find_phones("2017-2019") == []
    assert jc.find_phones("+44 7700 900123") == ["+44 7700 900123"]


@pytest.mark.parametrize("url,expected", [
    ("https://www.boards.greenhouse.io/acme/jobs/4021?gh_src=x&utm_source=li#apply",
     "https://boards.greenhouse.io/acme/jobs/4021"),
    ("https://job-boards.greenhouse.io/acme/jobs/4021", "https://boards.greenhouse.io/acme/jobs/4021"),
    ("https://jobs.lever.co/acme/abc-123/apply", "https://jobs.lever.co/acme/abc-123"),
    ("https://www.linkedin.com/jobs/view/data-analyst-at-acme-3912345678/?trk=x",
     "https://linkedin.com/jobs/view/3912345678"),
    ("https://uk.indeed.com/viewjob?jk=abc&from=serp&vjs=3", "https://uk.indeed.com/viewjob?jk=abc"),
    ("acme.com/careers/?b=2&a=1&utm_medium=x", "https://acme.com/careers?a=1&b=2"),
])
def test_canonicalize_url(url, expected):
    assert jc.canonicalize_url(url) == expected


def test_user_dir_and_config(jf_home):
    assert jc.user_dir() == jf_home
    cfg = jc.load_config()
    assert cfg["limits"]["daily_applications"] == 15
    jf_home.mkdir(parents=True)
    (jf_home / "config.toml").write_text('[locale]\ndefault = "us"\n[limits]\nhard_cap = 10\n', encoding="utf-8")
    cfg = jc.load_config()
    assert cfg["locale"]["default"] == "us" and cfg["limits"]["hard_cap"] == 10
    assert cfg["limits"]["per_employer_days"] == 30
    (jf_home / "config.toml").write_text("[[broken", encoding="utf-8")
    with pytest.raises(jc.ConfigError):
        jc.load_config()


@pytest.mark.parametrize("script", ["jf_common.py", "setup_check.py", "cv_extract.py", "ledger_check.py",
                                    "ledger_add.py", "voice_lint.py", "cv_render.py", "ats_detect.py", "db.py"])
def test_help_works(script, tmp_path):
    r = run_script(script, "--help", home=tmp_path)
    assert r.returncode == 0
    assert "Exit codes" in r.stdout or "exit codes" in r.stdout.lower()


def test_usage_error_exit_code(tmp_path):
    r = run_script("ledger_check.py", home=tmp_path)
    assert r.returncode == 4


def test_no_shell_true_or_network():
    """jf_net.py is the one module allowed to open a socket (ARCHITECTURE §8.1).

    Every other script, including the source modules under scripts/sources/, must go
    through it, so caching, rate limits, offline mode and key redaction cannot be bypassed.
    setup_ui.py may serve on 127.0.0.1 (http.server) but must not make outbound requests.
    """
    allowed_outbound = {"jf_net.py"}
    for f in list(SCRIPTS.glob("*.py")) + list(SCRIPTS.glob("sources/*.py")):
        src = f.read_text(encoding="utf-8")
        assert "shell=True" not in src, f.name
        if f.name in allowed_outbound:
            continue
        for banned in ("import requests", "urllib.request", "http.client", "import socket", "import httpx", "import aiohttp"):
            assert banned not in src, f"{f.name} uses {banned}; route network calls through jf_net.py"
