import json
import shutil
from pathlib import Path

import pytest

import voice_lint as vl
from conftest import FIXTURES, REAL_LISTS, SAMPLE_MD

FIX_LISTS = FIXTURES / "lists"
CLEAN_LETTER = FIXTURES / "clean-cover-letter.md"
needs_real_lists = pytest.mark.skipif(not (REAL_LISTS / "rationed.txt").is_file(),
                                      reason="references/voice/lists not present")


def lint(text, fmt, lists_dir=FIX_LISTS, locale="uk", profile=None, max_words=None):
    return vl.lint(text, fmt, vl.Lists(Path(lists_dir)), locale, profile, max_words)


def check(res, cid):
    return next(c for c in res["checks"] if c["id"] == cid)


def letter_with(extra_sentence: str) -> str:
    text = CLEAN_LETTER.read_text(encoding="utf-8")
    return text.replace("It took longer than planned.", "It took longer than planned. " + extra_sentence)


# ----------------------------------------------------------- with fixture lists

def test_clean_sample_passes_fixture_lists():
    res = lint(CLEAN_LETTER.read_text(encoding="utf-8"), "cover-letter")
    assert res["ok"], json.dumps(res["checks"], indent=1)
    assert {m["id"] for m in res["manual"]} >= {1, 5, 6, 9}


def test_banned_phrase_fails():
    res = lint(letter_with("I am a team player at heart."), "cover-letter")
    assert not res["ok"] and check(res, 2)["status"] == "fail"
    assert "team player" in check(res, 2)["findings"][0]["message"]


def test_rationed_item_twice_fails():
    once = lint(letter_with("I was keen to fix it."), "cover-letter")
    assert check(once, 3)["status"] == "pass"
    twice = lint(letter_with("I was keen to fix it, and keen to learn from it."), "cover-letter")
    assert check(twice, 3)["status"] == "fail" and not twice["ok"]


def test_cover_letter_under_150_words_fails(tmp_path, run):
    short = "Dear Ms Adeyemi,\n\nI rebuilt the close at Northgate Foods in 2023 and cut it to 5 days.\n\n" \
            "I can start in December.\n\nYours sincerely,\nHannah Okafor\n"
    p = tmp_path / "short.md"
    p.write_text(short, encoding="utf-8")
    r = run("voice_lint.py", p, "--format", "cover-letter", "--lists-dir", FIX_LISTS, "--locale", "uk", "--json")
    assert r.returncode == 1
    res = json.loads(r.stdout)
    assert any("150-400" in f["message"] for f in check(res, 11)["findings"])


def test_cli_clean_sample_exit_0(run):
    r = run("voice_lint.py", CLEAN_LETTER, "--format", "cover-letter", "--lists-dir", FIX_LISTS, "--locale", "uk")
    assert r.returncode == 0, r.stdout


def test_missing_list_warns_and_continues(tmp_path, run):
    partial = tmp_path / "lists"
    partial.mkdir()
    shutil.copy(FIX_LISTS / "banned-words.txt", partial)
    r = run("voice_lint.py", CLEAN_LETTER, "--format", "cover-letter", "--lists-dir", partial, "--locale", "uk",
            "--json")
    assert r.returncode == 0
    assert "rationed.txt" in r.stderr and "warning" in r.stderr
    assert "rationed.txt" in json.loads(r.stdout)["lists_missing"]


def test_format_limits():
    note = "Hi Sam,\n\n" + ("I enjoyed your post on the Leeds finance meetup and would like to connect. " * 5)
    assert check(lint(note, "linkedin-note"), 11)["status"] == "fail"
    email = "Hi Sam,\n\n" + " ".join(["I ran the Northgate close for 3 years."] * 20) + "\n\nThanks,\nHannah"
    assert any("120" in f["message"] for f in check(lint(email, "email"), 11)["findings"])
    answer = "At Northgate Foods I rebuilt 14 reconciliations in 2023. " * 10
    assert check(lint(answer, "form-answer", max_words=50), 11)["status"] == "fail"
    profile = "Finance analyst at Northgate Foods since 2022. " * 12
    assert check(lint(profile, "cv-profile"), 11)["status"] == "fail"


def test_formatting_tells():
    text = "Hi Sam,\n\n**Why me:** I ran the 2023 close at Northgate.\n\n- point one at Acme\n\n" \
           "Thanks for reading [Your Name] \U0001F680\n\nThanks,\nHannah"
    msgs = " ".join(f["message"] for f in check(lint(text, "email"), 11)["findings"])
    for want in ("bold", "bullet", "template bracket", "emoji"):
        assert want in msgs


def test_title_case_subject():
    text = "Subject: Exciting Opportunity To Connect About Finance\n\nHi Sam,\n\nI ran the 2023 close at Northgate.\n"
    assert any("Title Case" in f["message"] for f in check(lint(text, "email"), 11)["findings"])


def test_rhythm_flags_uniform_sentences():
    para = " ".join(f"I reviewed the {m} ledger with the Northgate site managers each week." for m in
                    ("March", "April", "May", "June", "July", "August", "September", "October", "November",
                     "December", "January", "February"))
    res = lint(para, "form-answer")
    assert check(res, 7)["status"] == "fail"


def test_profile_never_uses_and_spelling():
    prof = {"locale": "en-GB", "never_uses": ["super"], "pet_phrases": ["to be fair"]}
    text = "To be fair, the super close at Northgate in 2023 had a new color scheme. To be fair, it was."
    res = lint(text, "form-answer", locale=None, profile=prof)
    msgs = [f["message"] for f in check(res, 10)["findings"]]
    assert any("never uses" in m for m in msgs)
    assert any("US spelling" in m for m in msgs)
    assert any("pet phrase" in m for m in msgs)
    assert res["locale"] == "uk" and res["locale_source"] == "profile"


def test_cv_markdown_input_selects_part():
    res = lint(SAMPLE_MD.read_text(encoding="utf-8"), "cv-profile")
    assert res["ok"] and res["words"] < 80
    assert res["selection"] == "linted the Profile section only"
    res = lint(SAMPLE_MD.read_text(encoding="utf-8"), "cv-bullets")
    assert res["ok"], json.dumps([c for c in res["checks"] if c["status"] == "fail"], indent=1)


# --------------------------------------------------------------- the real lists

@needs_real_lists
def test_real_lists_clean_sample_passes():
    res = lint(CLEAN_LETTER.read_text(encoding="utf-8"), "cover-letter", REAL_LISTS)
    assert res["ok"], json.dumps([c for c in res["checks"] if c["status"] != "pass"], indent=1)
    assert res["lists_missing"] == []


@needs_real_lists
def test_real_rationed_groups_share_one_allowance():
    res = lint(letter_with("I was excited by the result and keen to repeat it."), "cover-letter", REAL_LISTS)
    c = check(res, 3)
    assert c["status"] == "fail"
    assert any("feelings" in f["message"] for f in c["findings"])
    assert "group feelings" in c["categories_over"]


@needs_real_lists
def test_real_exclamation_zero_in_cover_letter_one_in_email():
    res = lint(letter_with("It worked!"), "cover-letter", REAL_LISTS)
    assert check(res, 3)["status"] == "fail"
    email = "Hi Sam,\n\nThe Northgate close now takes 5 days in 2024! Could we talk on Tuesday 10 November?\n\nThanks,\nHannah"
    res = lint(email, "email", REAL_LISTS)
    assert check(res, 3)["status"] == "pass"
    res = lint(email.replace("in 2024!", "in 2024! Huge!"), "email", REAL_LISTS)
    assert check(res, 3)["status"] == "fail"


@needs_real_lists
def test_real_dash_group_and_date_ranges():
    one = lint(letter_with("The fix — a format check — took a week."), "cover-letter", REAL_LISTS)
    assert check(one, 3)["status"] == "fail"
    mixed = lint(letter_with("The fix took a week - longer than planned. It ran from Mar 2022 – Present."),
                 "cover-letter", REAL_LISTS)
    dash_findings = [f for f in check(mixed, 3)["findings"] if "dash" in f["message"]]
    assert dash_findings == []  # one spaced hyphen; the date-range dash does not count
    two = lint(letter_with("The fix took a week - longer than planned — and cost a weekend."),
               "cover-letter", REAL_LISTS)
    assert any("dash" in f["message"] for f in check(two, 3)["findings"])


@needs_real_lists
def test_real_dash_check_skipped_for_cv_bullets():
    text = "- Ran the close — 5 days\n- Built the forecast — within 2%\n"
    assert check(lint(text, "cv-bullets", REAL_LISTS), 3)["status"] == "pass"


@needs_real_lists
def test_real_spelling_blocks():
    mixed = lint("I organised the Northgate close in 2023 and the color scheme of the 2024 pack.",
                 "form-answer", REAL_LISTS, locale="uk")
    assert any("mixed" in f["message"] for f in check(mixed, 10)["findings"])
    us_in_uk = lint("I organized the Northgate close in 2023.", "form-answer", REAL_LISTS, locale="uk")
    assert check(us_in_uk, 10)["status"] == "fail"
    # block 2 is one-way: UK form flagged only in US documents
    assert check(lint("I ran the Northgate graduate programme in 2023.", "form-answer", REAL_LISTS,
                      locale="us"), 10)["status"] == "fail"
    assert check(lint("I ran the Northgate graduate programme in 2023.", "form-answer", REAL_LISTS,
                      locale="uk"), 10)["status"] == "pass"
    assert check(lint("I wrote a Python program at Northgate in 2023.", "form-answer", REAL_LISTS,
                      locale="uk"), 10)["status"] == "pass"


@needs_real_lists
def test_real_locale_default_from_config(jf_home):
    jf_home.mkdir(parents=True)
    (jf_home / "config.toml").write_text('[locale]\ndefault = "us"\n', encoding="utf-8")
    res = lint("I ran the Northgate graduate programme in 2023.", "form-answer", REAL_LISTS, locale=None)
    assert res["locale"] == "us" and res["locale_source"] == "config"
    (jf_home / "config.toml").unlink()
    res = lint("I ran the Northgate graduate programme in 2023.", "form-answer", REAL_LISTS, locale=None)
    assert res["locale"] == "uk" and res["locale_source"] == "default"


@needs_real_lists
def test_real_openers_first_sentence_only():
    base = "Dear Ms Adeyemi,\n\n{first}\n\nAt Northgate Foods I cut the close from 9 to 5 days in 2023.\n\nYours sincerely,\nHannah"
    res = lint(base.format(first="I am writing about the Harrow & Pike analyst role."), "cover-letter", REAL_LISTS)
    assert any(f["severity"] == "fail" and "opener" in f["message"] for f in check(res, 8)["findings"])
    res = lint(base.format(first="As a Harrow & Pike customer since 2019, I know your stores."), "cover-letter",
               REAL_LISTS)
    c = check(res, 8)
    assert c["status"] == "warn" and all(f["severity"] == "warn" for f in c["findings"])
    res = lint(base.format(first="With 8 years in FMCG finance, I know month-end at Harrow & Pike."), "cover-letter",
               REAL_LISTS)
    assert any("With N years" in f["message"] and f["severity"] == "warn" for f in check(res, 8)["findings"])
    # an opener phrase later in the document is not an opener
    later = base.format(first="Your Harrow & Pike advert asks for a faster close. I hope to talk about it.")
    assert check(lint(later, "cover-letter", REAL_LISTS), 8)["status"] == "pass"


@needs_real_lists
def test_real_closers_last_paragraph_only():
    base = "Dear Ms Adeyemi,\n\n{p1}\n\nAt Northgate Foods I cut the close from 9 to 5 days in 2023.\n\n{p3}\n\nYours sincerely,\nHannah"
    bad = base.format(p1="Your Harrow & Pike advert asks for a faster close.",
                      p3="In conclusion, I can start in December.")
    assert check(lint(bad, "cover-letter", REAL_LISTS), 8)["status"] == "fail"
    ok = base.format(p1="Overall, your Harrow & Pike advert asks for a faster close.",
                     p3="I can start in December.")
    assert check(lint(ok, "cover-letter", REAL_LISTS), 8)["status"] == "pass"


@needs_real_lists
def test_real_markers_stripped_before_linting(tmp_path, run):
    text = letter_with("The check runs every night. [F010] [CONFIRM: does it run nightly?]")
    p = tmp_path / "cited.md"
    p.write_text(text, encoding="utf-8")
    r = run("voice_lint.py", p, "--format", "cover-letter", "--locale", "uk", "--json")
    res = json.loads(r.stdout)
    assert r.returncode == 0, json.dumps(check(res, 11), indent=1)
    assert check(res, 11)["findings"] == []
    assert any("CONFIRM" in w for w in res["warnings"])


@needs_real_lists
def test_real_agent_tic_reported_once():
    res = lint(letter_with("I quietly fixed it."), "cover-letter", REAL_LISTS)
    tics = check(res, 12)["findings"]
    assert any("quietly" in f["message"] for f in tics)
    assert not any("quietly" in f["message"] for f in check(res, 2)["findings"])


@needs_real_lists
def test_real_measure(tmp_path, run):
    s1 = tmp_path / "s1.txt"
    s2 = tmp_path / "s2.txt"
    s1.write_text("Hi Tom,\n\nI've organised the month-end pack for Thursday. It's shorter than last time, "
                  "because the depot numbers now come straight from Power BI. Shout if anything looks odd.\n\n"
                  "Thanks,\nHannah\n", encoding="utf-8")
    s2.write_text("Hi Priya,\n\nQuick one. The month-end pack is late because the bank feed broke again, and I "
                  "don't want to send numbers I haven't checked against the ledger. I'll have it with you by "
                  "noon. Is that OK?\n\nThanks,\nHannah\n", encoding="utf-8")
    r = run("voice_lint.py", "--measure", s1, s2, "--json")
    assert r.returncode == 0, r.stderr
    m = json.loads(r.stdout)
    for key in ("sentence_len_mean", "sentence_len_sd", "short_sentence_share", "long_sentence_share",
                "contraction_rate", "spelling_locale", "exclamation_rate", "question_rate", "pet_phrases",
                "greetings", "signoffs"):
        assert key in m
    assert m["samples"] == 2 and m["contraction_rate"] > 0
    assert m["spelling_locale"] == "uk"
    assert m["greetings"] == ["Hi {name},"] and m["signoffs"] == ["Thanks,"]
    assert "month-end pack" in m["pet_phrases"]
    assert m["question_rate"] > 0 and m["exclamation_rate"] == 0


@needs_real_lists
def test_real_opener_spanning_greeting():
    text = "Hi! I hope you are keeping busy at Harrow & Pike in 2026.\n\nThanks,\nHannah"
    res = lint(text, "email", REAL_LISTS)
    assert any("hi! i hope" in f["message"] for f in check(res, 8)["findings"])


# ------------------------------------------------- fragments and missing profile

FRAGMENT = ("### Senior Finance Analyst — Northgate Foods Ltd | Leeds | Mar 2022 – Present [F009]\n"
            "- Rebuilt the month-end close around 14 reconciliations in Power Query. [F010]\n"
            "- Built the rolling 18-month EBITDA forecast. [F011]\n"
            "- Run monthly reviews with 6 site general managers. [F012]\n")


def test_cv_bullets_fragment_ignores_headers(tmp_path, run):
    p = tmp_path / "frag.md"
    p.write_text(FRAGMENT, encoding="utf-8")
    r = run("voice_lint.py", p, "--format", "cv-bullets", "--lists-dir", FIX_LISTS, "--locale", "uk", "--json")
    res = json.loads(r.stdout)
    assert r.returncode == 0, json.dumps(check(res, 11), indent=1)
    assert check(res, 11)["findings"] == []
    assert res["selection"] == "linted the list items only"


def test_cv_bullets_ignores_every_header_level():
    text = "# Jane Smith\n## Experience\n#### Sub\n- Ran the Northgate close in 2023.\n"
    res = lint(text, "cv-bullets")
    assert res["ok"] and res["words"] == 6


def test_cv_profile_without_profile_section():
    text = ("# Jane Smith\nLeeds · 07700 900000 · jane@example.com\n\n"
            "Management accountant at Northgate Foods since 2022, with 8 years in FMCG.\n"
            "I rebuilt the close in Power Query.\n\n"
            "## Experience\n### Analyst — Acme | Leeds | 2019 – 2022\n- Ran the ledger.\n")
    res = lint(text, "cv-profile")
    assert res["selection"] == "no Profile section found; linted the first paragraph after the contact line"
    assert res["words"] == 19 and res["ok"]
    assert any("no Profile section" in w for w in res["warnings"])


def test_cv_profile_plain_paragraph_file():
    res = lint("Management accountant at Northgate Foods since 2022, with 8 years in FMCG.", "cv-profile")
    assert res["selection"] is None and res["ok"]


def test_missing_profile_warns_and_continues(tmp_path, run):
    missing = tmp_path / "nope" / "voice-profile.json"
    r = run("voice_lint.py", CLEAN_LETTER, "--format", "cover-letter", "--lists-dir", FIX_LISTS, "--locale", "uk",
            "--profile", missing, "--json")
    assert r.returncode == 0, r.stdout
    assert f"no voice profile at {missing}; voice-match check skipped" in r.stderr
    res = json.loads(r.stdout)
    assert res["profile_used"] is False
    assert any("no voice profile at" in w for w in res["warnings"])
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    r = run("voice_lint.py", CLEAN_LETTER, "--format", "cover-letter", "--profile", bad)
    assert r.returncode == 4
