"""Tests for outreach.py: contacts, verify, messages, touches, suppression, export, CLI."""
import json
import urllib.error
from datetime import date

import pytest

import db
import jf_net
import outreach


@pytest.fixture
def con(tmp_path, jf_home):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


@pytest.fixture
def draft(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text("Hi Priya, I applied for the analyst role on Monday.", encoding="utf-8")
    return p


@pytest.fixture
def net(tmp_path):
    """Online mode with a fake transport, a temp cache and no sleeping."""
    jf_net.set_offline(False)
    jf_net.set_cache_dir(tmp_path / "cache")
    old_sleep = jf_net._state["sleep"]
    jf_net._state["sleep"] = lambda s: None
    yield
    jf_net.set_offline(None)
    jf_net.set_cache_dir(None)
    jf_net._state["sleep"] = old_sleep


def priya(con, **kw):
    args = dict(name="Priya Shah", role="Talent partner", org="Acme", kind="in-house",
                email="Priya.Shah@acme.example", source_url="https://acme.example/careers/42")
    args.update(kw)
    return outreach.contacts_add(con, **args)


# ------------------------------------------------------------ syntax and stop words

@pytest.mark.parametrize("email,ok", [
    ("priya.shah@acme.co.uk", True), ("a+jobs@sub.example.org", True), ("no-at-sign.example.com", False),
    ("two@@example.com", False), (".lead@example.com", False), ("a..b@example.com", False),
    ("a@localhost", False), ("a@-bad.example.com", False), ("a@example.c", False),
])
def test_email_syntax(email, ok):
    assert outreach.email_syntax_ok(email)[0] is ok


@pytest.mark.parametrize("text,stop", [
    ("No thanks", True), ("please remove me", True), ("Unsubscribe", True), ("not interested right now", True),
    ("STOP", True), ("do not contact me again", True), ("asked for my CV", False), ("call on Friday", False),
    ("removed the old link", False), ("noted, will pass it on", False), ("knowledge of the team", False),
])
def test_stop_words_are_word_bounded(text, stop):
    assert outreach.is_stop_reply(text) is stop


# ------------------------------------------------------------ contacts

def test_contacts_add_list_suppress(con):
    c = priya(con)
    assert c["created"] and c["email"] == "priya.shah@acme.example"
    assert c["email_verified"] == "syntax" and c["consent_basis"] == "legitimate-interests"
    assert c["source_url"] == "https://acme.example/careers/42"
    assert [r["id"] for r in db.list_contacts(con)] == [c["id"]]
    outreach.contacts_suppress(con, c["id"], "asked not to be contacted")
    assert db.list_contacts(con) == []
    with pytest.raises(db.DBError, match="suppressed"):
        priya(con)
    with pytest.raises(db.DBError):
        priya(con, email="not-an-email")


# ------------------------------------------------------------ verify

def test_verify_syntax_only_never_says_valid(con):
    c = priya(con)
    res = outreach.verify(con, "priya.shah@acme.example")
    assert res["result"] == "syntax" and res["stored_on"] == [c["id"]]
    assert "valid" not in json.dumps(res).lower()
    bad = outreach.verify(con, "nope@")
    assert bad["syntax_ok"] is False and bad["result"] == "unverified"


@pytest.mark.parametrize("status", [200, 403, 404])
def test_verify_domain_any_http_status_means_domain(con, net, monkeypatch, status):
    calls = []

    def fake(url, headers, method, body, timeout):
        calls.append(url)
        return status, "<html></html>", {}
    monkeypatch.setattr(jf_net, "_do_request", fake)
    c = priya(con)
    res = outreach.verify(con, "priya.shah@acme.example", check_domain=True)
    assert res["result"] == "domain"
    assert calls == ["https://acme.example/"]
    assert db.list_contacts(con)[0]["email_verified"] == "domain"
    assert c


def test_verify_network_error_is_unverified_and_does_not_downgrade(con, net, monkeypatch):
    def ok(url, headers, method, body, timeout):
        return 200, "", {}
    monkeypatch.setattr(jf_net, "_do_request", ok)
    priya(con)
    outreach.verify(con, "priya.shah@acme.example", check_domain=True)

    def down(url, headers, method, body, timeout):
        raise urllib.error.URLError("name not resolved")
    monkeypatch.setattr(jf_net, "_do_request", down)
    res = outreach.verify(con, "someone@nowhere.example", check_domain=True)
    assert res["result"] == "unverified" and "no answer" in res["detail"]
    jf_net.clear_cache()
    res = outreach.verify(con, "priya.shah@acme.example", check_domain=True)
    assert res["result"] == "unverified"
    assert db.list_contacts(con)[0]["email_verified"] == "domain"  # weaker result does not replace it


def test_verify_offline_miss_is_unverified(con, tmp_path):
    jf_net.set_offline(True)
    jf_net.set_cache_dir(tmp_path / "cache")
    try:
        res = outreach.verify(con, "a@acme.example", check_domain=True)
    finally:
        jf_net.set_offline(None)
        jf_net.set_cache_dir(None)
    assert res["result"] == "unverified" and "offline" in res["detail"]


# ------------------------------------------------------------ messages

def test_message_lifecycle_and_touch_limit(con, draft):
    c = priya(con)
    m = outreach.messages_add(con, c["id"], "email", str(draft))
    assert m["sent_at"] is None and m["warnings"] == []
    sent = outreach.messages_sent(con, m["id"], at="2026-10-20T09:00:00Z")
    assert sent["follow_up_due"] == "2026-10-28"  # 6 working days after Tue 20 Oct
    assert [r["id"] for r in db.messages_due(con, date(2026, 10, 28))] == [m["id"]]
    with pytest.raises(db.DBError, match="already marked sent"):
        outreach.messages_sent(con, m["id"])
    done = outreach.messages_done(con, m["id"], today=date(2026, 10, 28))
    assert done["touches"] == 2 and done["last_touch"] and done["follow_up_due"] is None
    assert db.messages_due(con, date(2026, 12, 1)) == []
    with pytest.raises(db.DBError, match="limit is 2"):
        outreach.messages_done(con, m["id"])
    again = outreach.messages_add(con, c["id"], "email", str(draft))
    assert any("limit" in w for w in again["warnings"])


def test_done_schedules_next_when_more_touches_allowed(con, draft, jf_home):
    jf_home.mkdir(parents=True, exist_ok=True)
    (jf_home / "config.toml").write_text("[outreach]\nfollow_up_days = 5\nmax_touches = 3\n", encoding="utf-8")
    c = priya(con)
    m = outreach.messages_add(con, c["id"], "linkedin", str(draft))
    outreach.messages_sent(con, m["id"], at="2026-11-02")
    res = outreach.messages_done(con, m["id"], today=date(2026, 11, 9))
    assert res["touches"] == 2 and not res["last_touch"] and res["follow_up_due"] == "2026-11-16"
    res = outreach.messages_done(con, m["id"], today=date(2026, 11, 16))
    assert res["touches"] == 3 and res["last_touch"]


def test_reply_clears_follow_up_and_no_suppresses(con, draft):
    c = priya(con)
    m = outreach.messages_add(con, c["id"], "email", str(draft))
    outreach.messages_sent(con, m["id"], at="2026-10-20T09:00:00Z")
    res = outreach.messages_reply(con, m["id"], "asked for my CV and a call on Friday")
    assert res["follow_up_due"] is None and not res["contact_suppressed_now"]
    other = outreach.contacts_add(con, name="Tom Reed", role="Head of data", org="Beta", kind="hiring-manager",
                                  email="tom@beta.example")
    m2 = outreach.messages_add(con, other["id"], "email", str(draft))
    outreach.messages_sent(con, m2["id"])
    res = outreach.messages_reply(con, m2["id"], "No, please remove me from your list")
    assert res["contact_suppressed_now"] is True
    assert other["id"] not in [r["id"] for r in db.list_contacts(con)]
    with pytest.raises(db.DBError, match="suppressed"):
        outreach.messages_add(con, other["id"], "email", str(draft))


def test_messages_add_checks_inputs(con, tmp_path, draft):
    c = priya(con)
    with pytest.raises(ValueError):
        outreach.messages_add(con, c["id"], "email", str(tmp_path / "missing.md"))
    with pytest.raises(db.DBError):
        outreach.messages_add(con, c["id"], "email", str(draft), application_id="nope")
    with pytest.raises(db.DBError):
        outreach.messages_reply(con, outreach.messages_add(con, c["id"], "email", str(draft))["id"], "thanks")


def test_export_includes_suppressed(con, draft, tmp_path):
    c = priya(con)
    outreach.messages_add(con, c["id"], "email", str(draft))
    outreach.contacts_suppress(con, c["id"], "said no")
    res = outreach.export(con, tmp_path / "out")
    assert res["contacts"] == 1 and res["messages"] == 1
    rows = json.loads((tmp_path / "out" / "contacts.json").read_text(encoding="utf-8"))
    assert rows[0]["suppressed"] == 1
    assert (tmp_path / "out" / "messages.csv").read_text(encoding="utf-8").startswith("id,")


# ------------------------------------------------------------ CLI

def test_cli_round_trip(run, tmp_path, draft):
    dbp = str(tmp_path / "cli.db")
    r = run("outreach.py", "--db", dbp, "contacts", "add", "--name", "Priya Shah", "--role", "Recruiter",
            "--org", "Acme", "--kind", "agency", "--email", "priya@acme.example")
    assert r.returncode == 0, r.stderr
    cid = r.stdout.strip()
    r = run("outreach.py", "--db", dbp, "verify", "priya@acme.example", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["result"] == "syntax"
    r = run("outreach.py", "--db", dbp, "verify", "bad@", "--json")
    assert r.returncode == 1
    r = run("outreach.py", "--db", dbp, "verify", "priya@acme.example", "--check-domain", "--offline")
    assert r.returncode == 0 and "unverified" in r.stdout
    r = run("outreach.py", "--db", dbp, "messages", "add", "--contact", cid, "--channel", "email",
            "--draft", str(draft))
    assert r.returncode == 0, r.stderr
    mid = r.stdout.strip()
    r = run("outreach.py", "--db", dbp, "messages", "sent", mid, "--at", "2026-10-20", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["follow_up_due"] == "2026-10-28"
    r = run("outreach.py", "messages", "due", "--db", dbp, "--today", "2026-10-28", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)[0]["id"] == mid
    r = run("outreach.py", "--db", dbp, "messages", "reply", mid, "--outcome", "not interested")
    assert r.returncode == 0 and "suppressed" in r.stdout
    r = run("outreach.py", "--db", dbp, "contacts", "list", "--json")
    assert json.loads(r.stdout) == []
    r = run("outreach.py", "--db", dbp, "contacts", "list", "--all", "--json")
    assert json.loads(r.stdout)[0]["suppressed"] == 1
    r = run("outreach.py", "--db", dbp, "messages", "add", "--contact", cid, "--channel", "fax",
            "--draft", str(draft))
    assert r.returncode == 4
    r = run("outreach.py", "--db", dbp, "export", "--out", str(tmp_path / "exp"))
    assert r.returncode == 0 and (tmp_path / "exp" / "contacts.csv").is_file()
