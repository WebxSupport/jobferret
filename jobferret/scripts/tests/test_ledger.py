import json
import re

import pytest

import jf_common as jc
from conftest import SAMPLE_LEDGER, SAMPLE_MD


def _draft(tmp_path, text, name="draft.md"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _check(run, path, *extra):
    r = run("ledger_check.py", path, "--ledger", SAMPLE_LEDGER, "--json", *extra)
    return r.returncode, json.loads(r.stdout)


# ------------------------------------------------------------------ ledger_check

def test_fixture_passes_plain_and_strict(run):
    code, res = _check(run, SAMPLE_MD)
    assert code == 0 and res["ok"] and res["violations"] == []
    code, res = _check(run, SAMPLE_MD, "--strict")
    assert code == 0 and res["ok"]
    assert set(res) >= {"ok", "violations", "confirm_items"}


def test_uncited_numeric_sentence(run, tmp_path):
    p = _draft(tmp_path, "# Jane Smith\nLondon · 07700 900000 · jane@example.com\n\n## Profile\n"
                         "Analyst with a clean record. [F004] Cut close time by 40% in 2023.\n")
    code, res = _check(run, p)
    assert code == 1
    v = res["violations"]
    assert len(v) == 1 and v[0]["rule"] == 2 and v[0]["line"] == 5
    assert "40%" in v[0]["text"]


def test_uncited_list_item_and_skill_line(run, tmp_path):
    p = _draft(tmp_path, "# Jane Smith\njane@example.com\n\n## Core skills\n**Data:** SQL, Python\n\n"
                         "## Experience\n### Analyst — Acme | London | Mar 2022 – Present [F009]\n"
                         "- Built dashboards for the sales team\n- Ran the audit. [F010]\n")
    code, res = _check(run, p)
    assert code == 1
    rules = sorted((v["line"], v["rule"]) for v in res["violations"])
    assert rules == [(5, 1), (9, 1)]


def test_entry_header_needs_citation(run, tmp_path):
    p = _draft(tmp_path, "# Jane Smith\njane@example.com\n\n## Experience\n"
                         "### Analyst — Acme | London | Mar 2022 – Present\n- Ran the audit. [F010]\n")
    code, res = _check(run, p)
    assert code == 1 and res["violations"][0]["rule"] == 1 and res["violations"][0]["line"] == 5
    assert "entry header" in res["violations"][0]["message"]


def test_missing_and_malformed_ids(run, tmp_path):
    p = _draft(tmp_path, "- Built a forecast used by 12 people. [F999]\n- Cut costs by 5%. [F12]\n")
    code, res = _check(run, p)
    assert code == 1
    msgs = [(v["line"], v["rule"], v["message"]) for v in res["violations"]]
    assert any(l == 1 and r == 3 and "F999" in m for l, r, m in msgs)
    assert any(l == 2 and r == 3 and "malformed" in m for l, r, m in msgs)


def test_confirm_blocks(run, tmp_path):
    p = _draft(tmp_path, "- Led the 2024 audit with zero adjustments. [CONFIRM: was it zero adjustments, and which year?]\n"
                         "- Ran the purchase ledger for 400 suppliers. [F022]\n")
    code, res = _check(run, p)
    assert code == 2 and not res["ok"]
    assert res["confirm_items"] == [{"line": 1, "question": "was it zero adjustments, and which year?"}]
    assert [v["rule"] for v in res["violations"]] == [5]


def test_strict_blocks_unconfirmed_fact(run, tmp_path):
    p = _draft(tmp_path, "- Saved roughly £400k a year in the 2021 rate renegotiation. [F018,F036]\n")
    code, _ = _check(run, p)
    assert code == 0
    code, res = _check(run, p, "--strict")
    assert code == 2 and res["violations"][0]["rule"] == 4 and "F036" in res["violations"][0]["message"]


def test_violation_and_confirm_together_exit_1(run, tmp_path):
    p = _draft(tmp_path, "- Cut costs by 5%.\n- Led the audit. [CONFIRM: which year?]\n")
    code, res = _check(run, p)
    assert code == 1 and res["confirm_items"]


def test_strip_writes_marker_free_copy(run, tmp_path):
    out = tmp_path / "clean.md"
    code, res = _check(run, SAMPLE_MD, "--strip", "--out", str(out))
    assert code == 0 and res["stripped"] == str(out)
    clean = out.read_text(encoding="utf-8")
    assert not re.search(r"\[F\d+|\[CONFIRM", clean)
    assert "cutting close from 9 to 5 working days." in clean
    assert " ." not in clean
    # structure survives
    assert jc.parse_cv_markdown(clean)["name"] == "Hannah Okafor"


def test_strip_refused_when_checks_fail(run, tmp_path):
    p = _draft(tmp_path, "- Led the audit. [CONFIRM: which year?]\n")
    out = tmp_path / "clean.md"
    code, res = _check(run, p, "--strip", "--out", str(out))
    assert code == 2 and res["stripped"] is None and not out.exists()


def test_strip_needs_out(run):
    r = run("ledger_check.py", SAMPLE_MD, "--ledger", SAMPLE_LEDGER, "--strip")
    assert r.returncode == 4


def test_bad_ledger_is_input_error(run, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    r = run("ledger_check.py", SAMPLE_MD, "--ledger", bad)
    assert r.returncode == 4 and "facts" in r.stderr


def test_spelled_out_number_warns_only(run, tmp_path):
    p = _draft(tmp_path, "Coached two graduates through their exams.\n")
    code, res = _check(run, p)
    assert code == 0 and res["warnings"]


# -------------------------------------------------------------------- ledger_add

@pytest.fixture
def ledger_copy(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text(SAMPLE_LEDGER.read_text(encoding="utf-8"), encoding="utf-8")
    return p


def test_ledger_add_appends_with_next_id(run, ledger_copy):
    r = run("ledger_add.py", "--ledger", ledger_copy, "--kind", "metric", "--text",
            "Payment plans recovered £720k of aged debt", "--parent", "F020", "--asked", "How much was recovered?")
    assert r.returncode == 0 and r.stdout.strip() == "F037"
    r = run("ledger_add.py", "--ledger", ledger_copy, "--kind", "metric", "--text", "Second fact", "--json")
    res = json.loads(r.stdout)
    assert res["fact"]["id"] == "F038"
    led = jc.load_ledger(ledger_copy)
    f = jc.ledger_index(led)["F037"]
    assert f["parent"] == "F020" and f["provenance"] == "user" and f["confirmed"] is False
    assert f["line"] is None and f["page"] is None
    assert f["note"]["asked"] == "How much was recovered?" and f["note"]["added_at"].endswith("Z")


def test_ledger_add_unknown_parent_fails(run, ledger_copy):
    before = ledger_copy.read_text(encoding="utf-8")
    r = run("ledger_add.py", "--ledger", ledger_copy, "--kind", "metric", "--text", "x", "--parent", "F404")
    assert r.returncode == 1 and "F404" in r.stderr
    assert ledger_copy.read_text(encoding="utf-8") == before


def test_ledger_add_bad_kind_and_markers(run, ledger_copy):
    r = run("ledger_add.py", "--ledger", ledger_copy, "--kind", "boast", "--text", "x")
    assert r.returncode == 1
    r = run("ledger_add.py", "--ledger", ledger_copy, "--kind", "metric", "--text", "Saved 5% [F010]")
    assert r.returncode == 1


def test_ledger_add_confirm_flips_flag(run, ledger_copy):
    assert jc.ledger_index(jc.load_ledger(ledger_copy))["F036"]["confirmed"] is False
    r = run("ledger_add.py", "--ledger", ledger_copy, "--confirm", "F036", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["fact"]["confirmed"] is True
    f = jc.ledger_index(jc.load_ledger(ledger_copy))["F036"]
    assert f["confirmed"] is True and "confirmed_at" in f["note"]
    assert run("ledger_add.py", "--ledger", ledger_copy, "--confirm", "F999").returncode == 1


def test_ledger_add_confirm_conflicts_with_add(run, ledger_copy):
    r = run("ledger_add.py", "--ledger", ledger_copy, "--confirm", "F036", "--kind", "metric")
    assert r.returncode == 4


def test_ledger_add_atomic_no_temp_left(run, ledger_copy):
    r = run("ledger_add.py", "--ledger", ledger_copy, "--kind", "skill", "--text", "Alteryx", "--confirmed",
            "--provenance", "profile")
    assert r.returncode == 0
    leftovers = [p.name for p in ledger_copy.parent.iterdir() if p.name != "ledger.json"]
    assert leftovers == []
    f = jc.ledger_index(jc.load_ledger(ledger_copy))[r.stdout.strip()]
    assert f["confirmed"] is True and f["provenance"] == "profile" and "note" not in f


def test_add_fact_function_validates():
    import ledger_add
    led = jc.new_ledger()
    f = ledger_add.add_fact(led, "metric", "  Twelve   marketers  ")
    assert f["id"] == "F001" and f["text"] == "Twelve marketers"
    with pytest.raises(ValueError):
        ledger_add.add_fact(led, "metric", "   ")


def test_entry_header_without_digits_still_needs_citation(run, tmp_path):
    p = _draft(tmp_path, "## Volunteering\n### Volunteer — Oxfam\n- Sorted donations. [F031]\n")
    code, res = _check(run, p)
    assert code == 1
    assert [(v["line"], v["rule"]) for v in res["violations"] if v["rule"] == 1] == [(2, 1)]


# ------------------------------------------------------------- rule 7: numbers

@pytest.mark.parametrize("line", [
    "- Cut close from 9 to 5 working days. [F010,F034]",                      # range, both ends in F034
    "- Cut aged debt from £1,100,000 to £380,000. [F020]",             # 1.1m / 380k in the fact
    "- Saved ~£400,000 a year in the 2021 renegotiation. [F018,F036]",     # ~ prefix, k in the fact
    "- Over 8 years in FMCG, freight and housing finance. [F004]",            # "eight" in the fact
    "**Systems:** SAP S/4HANA, Sage 200 [F006]",
])
def test_rule7_numbers_that_trace_pass(run, tmp_path, line):
    code, res = _check(run, _draft(tmp_path, line + "\n"))
    assert code == 0, res["violations"]


@pytest.mark.parametrize("line,bad", [
    ("- Cut close from 9 to 4 working days. [F010,F034]", "4"),
    ("- Built a forecast used by 45 managers. [F011]", "45"),
    ("- Cut aged debt by 65% in 12 months. [F020]", "65%"),
    ("- Grew revenue 2.3x across 11 depots. [F017]", "2.3"),
    ("### Analyst — Northgate Foods Ltd | Leeds | Mar 2019 – Present [F009]", "2019"),
    ("**Systems:** SAP S/4HANA, Sage 300 [F006]", "300"),
])
def test_rule7_untraced_number_fails(run, tmp_path, line, bad):
    code, res = _check(run, _draft(tmp_path, line + "\n"))
    assert code == 1
    v = [x for x in res["violations"] if x["rule"] == 7]
    assert v and "number not in cited facts" in v[0]["message"] and bad in v[0]["message"]


def test_rule7_per_sentence_citations(run, tmp_path):
    p = _draft(tmp_path, "## Profile\nRan monthly reviews with 6 site managers. [F012] "
                         "Cut close to 5 days. [F012]\n")
    code, res = _check(run, p)
    assert code == 1 and [v["rule"] for v in res["violations"]] == [7]
    assert "5" in res["violations"][0]["message"]


def test_rule7_number_tokens():
    import ledger_check as lc
    toks = {w: (raw, scaled) for w, raw, scaled in lc.number_tokens("£1.1m, £380k, 1,200, 2.3x, 2 million")}
    assert toks["£1.1m"] == ("1.1", "1100000") and toks["£380k"] == ("380", "380000")
    assert toks["1,200"] == ("1200", None) and toks["2.3x"] == ("2.3", None)
    assert toks["2 million"] == ("2", "2000000")
    assert lc.fact_values("eight years and £180,000") >= {"8", "180000"}


# ------------------------------------------------------------------- supersede

def test_supersede_links_and_blocks_old_citation(run, tmp_path):
    led = tmp_path / "ledger.json"
    led.write_text(SAMPLE_LEDGER.read_text(encoding="utf-8"), encoding="utf-8")
    r = run("ledger_add.py", "--ledger", led, "--supersede", "F036", "--text",
            "The 2021 rate renegotiation saved £410k a year", "--confirmed", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads(r.stdout)
    new = res["fact"]
    assert new["id"] == "F037" and new["supersedes"] == "F036" and new["kind"] == "metric"
    assert new["parent"] == "F018" and new["confirmed"] is True
    idx = jc.ledger_index(jc.load_ledger(led))
    old = idx["F036"]
    assert old["superseded_by"] == "F037" and old["text"] == "The 2021 rate renegotiation saved roughly £400k a year"
    assert old["confirmed"] is False  # otherwise unchanged
    draft = _draft(tmp_path, "- Saved £400k a year in the 2021 renegotiation. [F018,F036]\n")
    r = run("ledger_check.py", draft, "--ledger", led, "--json")
    out = json.loads(r.stdout)
    assert r.returncode == 1
    assert any(v["rule"] == 3 and "F036 superseded by F037; cite the replacement" in v["message"]
               for v in out["violations"])
    draft2 = _draft(tmp_path, "- Saved £410k a year in the 2021 renegotiation. [F018,F037]\n", "d2.md")
    assert run("ledger_check.py", draft2, "--ledger", led, "--strict").returncode == 0
    # cannot supersede or confirm the old fact again
    assert run("ledger_add.py", "--ledger", led, "--supersede", "F036", "--text", "x").returncode == 1
    assert run("ledger_add.py", "--ledger", led, "--confirm", "F036").returncode == 1
    assert run("ledger_add.py", "--ledger", led, "--supersede", "F036").returncode == 4
    assert run("ledger_add.py", "--ledger", led, "--supersede", "F999", "--text", "x").returncode == 1
