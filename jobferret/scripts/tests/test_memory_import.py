"""Tests for memory_import.py against synthetic exports in fixtures/memory/."""
import json
import re
from pathlib import Path

import pytest

import memory_import as mi

MEM = Path(__file__).resolve().parent / "fixtures" / "memory"
CHATGPT = MEM / "chatgpt-conversations.json"
CLAUDE = MEM / "claude-conversations.json"


def signals(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {(s["term"], s["kind"]): s for s in data["signals"]}, data


# ------------------------------------------------------------ lexicon

def test_lexicon_shape():
    lex = mi.load_lexicon()
    assert 400 <= len(lex) <= 700
    assert {k for _, k in lex.values()} == set(mi.LEXICON_KINDS)
    raw = [l.strip() for l in mi.LEXICON_PATH.read_text(encoding="utf-8").splitlines()
           if l.strip() and not l.startswith("#")]
    assert len(raw) == len(set(raw)) == len(lex)
    assert all(t == t.lower() for t in raw)


def test_matcher_whole_words_longest_first_and_slashes():
    m = mi.Matcher(mi.load_lexicon())
    hits = [(t, k) for t, k, _, _ in m.find("Used SQL/Python, Power BI and machine learning; not a pythonista. C++ too.")]
    assert ("sql", "tool") in hits and ("python", "tool") in hits
    assert ("power bi", "tool") in hits and ("machine learning", "skill") in hits
    assert ("c++", "tool") in hits
    assert sum(1 for t, _ in hits if t == "python") == 1


@pytest.mark.parametrize("raw,np", [
    ("a budgeting app in Python", "budgeting app in python"),
    ("it", None), ("this approach a lot", None), ("the", None),
    ("hiking in the Peak District with my dog every weekend", "hiking in the peak district"),
    ("volunteering at the food bank and running", "volunteering at the food bank"),
])
def test_noun_phrase(raw, np):
    assert mi.noun_phrase(raw) == np


def test_scrub_removes_personal_and_secret_text():
    s = mi.scrub("Mail jane@example.com, ring +44 7700 900123, see www.example.co.uk/x or https://a.io/b, "
                 "card 4111-1111-1111-1111, token = abc123def, password: hunter2, ghp_ABCDEFGHIJKLMNOP1234")
    for bad in ("jane@", "7700", "example.co.uk", "https", "4111", "abc123def", "hunter2", "ghp_"):
        assert bad not in s
    assert "Mail" in s and "card" in s


# ------------------------------------------------------------ readers

def test_chatgpt_reads_only_the_users_live_branch():
    msgs = mi.read_chatgpt(CHATGPT)
    text = "\n".join(t for t, _ in msgs)
    assert "budgeting app" in text and "Peak District" in text and "Power BI dashboard" in text
    assert "knitting" not in text            # abandoned branch
    assert "Tableau" not in text             # assistant
    assert "tool run" not in text and "You are ChatGPT" not in text
    assert "github.com/jane" in text         # dict part with text is read (scrubbed later)
    days = [d for _, d in msgs]
    assert days[0] == "2026-01-10" and "2026-02-03" in days
    assert text.index("Can Power BI") < text.index("Still working on")  # no current_node: by time


def test_claude_reads_human_turns_prefers_blocks():
    msgs = mi.read_claude(CLAUDE)
    text = "\n".join(t for t, _ in msgs)
    assert "data analyst" in text and "dbt package" in text
    assert "docker" not in text and "Machine learning" not in text and "kubernetes" not in text
    assert [d for _, d in msgs] == ["2026-03-01", "2026-03-02"]


def test_bad_inputs():
    with pytest.raises(mi.InputError):
        mi.read_source("chatgpt", None)
    with pytest.raises(mi.InputError):
        mi.read_source("chatgpt", str(MEM / "missing.json"))
    with pytest.raises(mi.InputError):
        mi.read_source("claude", str(MEM / "notes.txt"))
    with pytest.raises(mi.InputError):
        mi.parse_sources([["slack", "x"]])


# ------------------------------------------------------------ end to end

def test_full_import(tmp_path):
    out = tmp_path / "signals.json"
    res = mi.run_import([("chatgpt", str(CHATGPT)), ("claude", str(CLAUDE)),
                         ("claude-code", str(MEM / "claude-code")), ("codex", str(MEM / "codex")),
                         ("text", str(MEM / "notes.txt"))], out)
    assert res["written"] and res["messages_scanned"] == 9
    sig, data = signals(out)
    assert {s["kind"] for s in data["sources"]} == {"chatgpt", "claude", "claude-code", "codex", "text"}
    assert sig[("python", "tool")]["count"] == 3
    assert sig[("python", "tool")]["first_seen"] == "2026-01-10"
    assert sig[("python", "tool")]["last_seen"] == "2026-01-11"
    assert ("budgeting app in python", "project") in sig
    assert ("dbt package for housing data", "project") in sig
    assert ("power bi dashboard for the finance", "project") in sig
    assert ("hiking in the peak district", "interest") in sig
    assert ("volunteering at the food bank", "interest") in sig
    assert ("photography", "interest") in sig and ("teaching beginners", "interest") in sig
    assert ("data analyst", "role") in sig and ("management accountant", "role") in sig
    assert ("xero", "tool") in sig and ("terraform", "tool") in sig
    assert ("tableau", "tool") not in sig and ("photoshop", "tool") not in sig
    assert not any(k[0].startswith("knitting") for k in sig)
    assert ("machine learning", "skill") not in sig and ("docker", "tool") not in sig
    blob = json.dumps(data)
    for bad in ("jane.smith@", "07700", "sk-abcdef", "4111", "github.com", "hunter2"):
        assert bad not in blob
    for s in data["signals"]:
        assert set(s) == {"term", "kind", "count", "first_seen", "last_seen", "examples"}
        assert len(s["examples"]) <= 2 and all(len(e) <= 120 for e in s["examples"])
    assert data["signals"][0]["count"] >= data["signals"][-1]["count"]


def test_merge_adds_and_skips_repeats(tmp_path):
    out = tmp_path / "s.json"
    mi.run_import([("chatgpt", str(CHATGPT))], out)
    first, _ = signals(out)
    res = mi.run_import([("chatgpt", str(CHATGPT)), ("text", str(MEM / "notes.txt"))], out, merge=True)
    assert [s["kind"] for s in res["sources_skipped"]] == ["chatgpt"]
    sig, data = signals(out)
    assert sig[("python", "tool")]["count"] == first[("python", "tool")]["count"]
    assert ("photography", "interest") in sig
    assert len(data["sources"]) == 2
    mi.run_import([("text", str(MEM / "notes.txt"))], out)  # no --merge replaces the file
    sig, data = signals(out)
    assert ("python", "tool") not in sig and len(data["sources"]) == 1


def test_codex_reads_memories_folders_only(tmp_path):
    shown, msgs, sha = mi.read_source("codex", str(MEM / "codex"))
    assert len(msgs) == 1 and "Terraform" in msgs[0][0] and sha


# ------------------------------------------------------------ CLI

def test_cli_summary_and_exit_codes(run, tmp_path):
    out = tmp_path / "o" / "signals.json"
    r = run("memory_import.py", "--from", "chatgpt", str(CHATGPT), "--from", "text", str(MEM / "notes.txt"),
            "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert "Messages scanned: 5" in r.stdout and "Signals found:" in r.stdout
    assert str(out) in r.stdout
    assert "This file stays on your computer; delete the folder to forget it." in r.stdout
    r = run("memory_import.py", "--from", "claude", str(CLAUDE), "--out", str(out), "--merge", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["messages_scanned"] == 2
    blank = tmp_path / "blank.txt"
    blank.write_text("   \n", encoding="utf-8")
    r = run("memory_import.py", "--from", "text", str(blank), "--out", str(tmp_path / "x.json"))
    assert r.returncode == 1 and not (tmp_path / "x.json").exists()
    r = run("memory_import.py", "--from", "chatgpt", "--out", str(out))
    assert r.returncode == 4
    r = run("memory_import.py", "--from", "claude", str(MEM / "notes.txt"), "--out", str(out))
    assert r.returncode == 4
    r = run("memory_import.py", "--from", "claude-code", str(MEM / "claude-code"))
    assert r.returncode == 0
    default_out = run.home / "memory" / "signals.json"
    assert default_out.is_file()
    assert re.search(r"management accountant", default_out.read_text(encoding="utf-8"))
