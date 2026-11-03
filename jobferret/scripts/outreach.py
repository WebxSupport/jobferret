"""outreach.py: contacts, suppression, the message log and follow-ups.

Purpose
    The record behind the outreach mode (ARCHITECTURE section 10.2): who the
    user may write to, where each contact came from, what was sent and when,
    who replied, and who must never be contacted again. Built on the db.py
    helpers add_contact, list_contacts, suppress_contact, add_message,
    update_message and messages_due. It never sends anything: the user sends
    (gate G1), or the host's email connector does after the user's yes.

Usage
    outreach.py [--db PATH] contacts add --name N --role R --org O --kind agency|in-house|hiring-manager|referral|other
                                         [--email E] [--linkedin URL] [--source-url URL] [--notes "..."] [--json]
    outreach.py [--db PATH] contacts list [--all] [--json]
    outreach.py [--db PATH] contacts suppress <contact_id> --reason "..." [--json]
    outreach.py [--db PATH] verify <email> [--check-domain] [--offline] [--json]
    outreach.py [--db PATH] messages add --contact <id> --channel email|linkedin|inmail|form --draft <path>
                                         [--application <id>] [--job <id>] [--json]
    outreach.py [--db PATH] messages list [--contact <id>] [--json]
    outreach.py [--db PATH] messages sent <message_id> [--at ISO] [--by user|connector] [--follow-up-days N] [--json]
    outreach.py [--db PATH] messages reply <message_id> --outcome "..." [--at ISO] [--json]
    outreach.py [--db PATH] messages done <message_id> [--json]
    outreach.py [--db PATH] messages due [--today YYYY-MM-DD] [--json]
    outreach.py [--db PATH] export --out <dir> [--json]
    --db and --json may come before or after the subcommand.

Contacts
    A contact comes from the posting, the employer's own careers or team page,
    the agency named on the posting, or a page the user opened in their own
    browser. --source-url records which, so the user can show where an
    address came from if asked. Nothing is scraped. A contact who has been
    suppressed cannot be added again (exit 1): they asked not to be contacted.
    consent_basis is recorded as "legitimate-interests" (a one-to-one job
    enquiry; see references/outreach-law.md).

verify
    Checks an address without sending anything to it.
      syntax      the address is well formed (a conservative pattern; no DNS)
      domain      with --check-domain: one HTTPS request to https://<domain>/
                  through jf_net (cached for a day) got any HTTP answer at all,
                  even 403 or 404, so the domain exists and serves something
      unverified  the domain check could not get an answer (network error,
                  offline with nothing cached), or the syntax is bad (exit 1)
    It never reports "valid" or "deliverable". The only way to learn that is
    to probe the mail server (SMTP RCPT TO), and that is both unreliable
    (many servers accept every address, others reject all probes) and rude:
    it is what spammers do to clean lists, and it can get the user's IP
    blocklisted. A web server answering for the domain says nothing about
    whether the mailbox exists. The result is stored on every contact with
    that address; a weaker result never replaces a stronger one already
    stored (domain > syntax > unverified).

Messages
    messages add records a draft (the file must exist) for a contact who is
    not suppressed. It warns when the contact has already had max_touches
    messages and follow-ups with no reply.
    messages sent marks it sent (default now, by the user) and sets
    follow_up_due to --follow-up-days working days later (default config
    [outreach] follow_up_days, 6), or none when max_touches is 1.
    messages reply records the reply and its outcome and clears
    follow_up_due. An outcome containing, as a whole word or phrase, "no",
    "stop", "remove", "unsubscribe", "unsubscribed", "not interested",
    "do not contact" or "don't contact" suppresses the contact permanently,
    and the output says so. Write the outcome in plain words: a positive reply
    should be summarised without those words ("asked for my CV", "call on
    Friday"). Suppression errs on the side of leaving people alone.
    messages done records that a follow-up was sent and nobody has replied.
    Touches are the original message plus each "done"; they are counted from
    the follow-up events this logs (kind "follow-up", detail starting with the
    message id), so nothing is kept outside the database. If the touches now
    equal config [outreach] max_touches (default 2) follow_up_due is cleared
    and that is the last one; otherwise the next follow-up is scheduled
    follow_up_days working days on. A "done" when the limit is already
    reached is refused (exit 1).
    messages due lists sent messages whose follow-up date has arrived, with no
    reply, for contacts who are not suppressed (db.messages_due).

export
    Writes contacts.json, contacts.csv, messages.json and messages.csv to
    --out, suppressed contacts included: the suppression list is what stops
    anyone being contacted twice after saying no.

Working days are Monday to Friday; bank holidays are not excluded.

Exit codes
    0  ok
    1  not found, invalid value, a suppressed contact, the touch limit
       reached, or (verify) an address with bad syntax
    4  usage or input error (bad arguments, missing draft file, bad date)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import db
import jf_net
from db import DBError
from jf_common import (
    ConfigError, EXIT_FAIL, EXIT_OK, EXIT_USAGE, die, emit_json, load_config, make_parser, now_iso, setup_io,
)
from track import add_working_days, local_today, parse_day

DEFAULT_FOLLOW_UP_DAYS = 6
DEFAULT_MAX_TOUCHES = 2
CONSENT_BASIS = "legitimate-interests"
STOP_RE = re.compile(r"\b(?:no|stop|remove|unsubscribe|unsubscribed|not interested|do not contact|"
                     r"don'?t contact)\b", re.IGNORECASE)
LOCAL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$")
DOMAIN_RE = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")
VERIFY_RANK = {"unverified": 0, "syntax": 1, "domain": 2}


# ------------------------------------------------------------------ helpers

def outreach_config() -> dict:
    try:
        cfg = load_config()
    except ConfigError as exc:
        sys.stderr.write(f"warning: {exc}; using outreach defaults\n")
        cfg = {}
    o = cfg.get("outreach", {}) or {}
    try:
        days = int(o.get("follow_up_days", DEFAULT_FOLLOW_UP_DAYS))
    except (TypeError, ValueError):
        days = DEFAULT_FOLLOW_UP_DAYS
    try:
        touches = int(o.get("max_touches", DEFAULT_MAX_TOUCHES))
    except (TypeError, ValueError):
        touches = DEFAULT_MAX_TOUCHES
    return {"follow_up_days": max(0, days), "max_touches": max(1, touches),
            "send_via": o.get("send_via", "user")}


def email_syntax_ok(email: str) -> tuple[bool, str]:
    e = (email or "").strip()
    if len(e) > 254 or e.count("@") != 1:
        return False, "an address has exactly one @ and at most 254 characters"
    local, domain = e.rsplit("@", 1)
    if not local or len(local) > 64 or not LOCAL_RE.match(local):
        return False, "the part before the @ is not a usable mailbox name"
    if not DOMAIN_RE.match(domain):
        return False, "the part after the @ is not a domain name"
    return True, ""


def is_stop_reply(outcome: str) -> bool:
    return bool(STOP_RE.search(outcome or ""))


def _iso(text: str | None, what: str = "--at") -> str:
    """A date or date-time as a stored timestamp. A bare date is kept as YYYY-MM-DD."""
    if not text:
        return now_iso()
    t = text.strip()
    try:
        if len(t) == 10:
            return parse_day(t, what).isoformat()
        datetime.fromisoformat(t.replace("Z", "+00:00"))
        return t
    except ValueError as exc:
        raise ValueError(f"{what} {text!r} must be YYYY-MM-DD or an ISO date-time") from exc


def _day_of(stamp: str) -> date:
    if len(stamp) == 10:
        return date.fromisoformat(stamp)
    return db.local_date(stamp) or local_today()


def _message(con, message_id: str) -> dict:
    row = con.execute("SELECT m.*, c.name AS contact_name, c.org AS contact_org, c.suppressed AS suppressed "
                      "FROM messages m JOIN contacts c ON c.id = m.contact_id WHERE m.id = ?",
                      (message_id,)).fetchone()
    if row is None:
        raise DBError(f"no message {message_id}")
    return dict(row)


def message_touches(con, message_id: str) -> int:
    """The original message (if sent) plus each follow-up recorded by messages done."""
    m = _message(con, message_id)
    if not m["sent_at"]:
        return 0
    n = con.execute("SELECT COUNT(*) FROM events WHERE kind = 'follow-up' AND detail LIKE ?",
                    (message_id + ":%",)).fetchone()[0]
    return 1 + n


def contact_touches_since_reply(con, contact_id: str) -> int:
    msgs = [dict(r) for r in con.execute("SELECT * FROM messages WHERE contact_id = ? ORDER BY sent_at, id",
                                         (contact_id,))]
    replied = [m["reply_at"] for m in msgs if m["reply_at"]]
    last_reply = max(replied) if replied else None
    total = 0
    for m in msgs:
        if not m["sent_at"] or m["reply_at"]:
            continue
        if last_reply and str(m["sent_at"]) <= str(last_reply):
            continue
        total += message_touches(con, m["id"])
    return total


# ------------------------------------------------------------------ contacts

def contacts_add(con, name: str, role: str | None, org: str | None, kind: str, email: str | None = None,
                 linkedin: str | None = None, source_url: str | None = None, notes: str | None = None) -> dict:
    data = {"name": name, "role": role, "org": org, "kind": kind, "linkedin_url": linkedin,
            "source_url": source_url, "notes": notes, "consent_basis": CONSENT_BASIS}
    if email:
        ok, why = email_syntax_ok(email)
        if not ok:
            raise DBError(f"{email!r} is not a usable email address: {why}")
        data["email"] = email.strip().lower()
        data["email_verified"] = "syntax"
    cid = db.contact_id_for(name, org, data.get("email"), linkedin)
    row = con.execute("SELECT * FROM contacts WHERE id = ?", (cid,)).fetchone()
    if row is not None and row["suppressed"]:
        raise DBError(f"contact {cid} ({row['name'] or row['email']}) is suppressed: they asked not to be "
                      "contacted, so they cannot be added again")
    if row is not None and row["email_verified"] == "domain":
        data.pop("email_verified", None)  # never weaken a stronger check
    return db.add_contact(con, data)


def contacts_suppress(con, contact_id: str, reason: str) -> dict:
    return db.suppress_contact(con, contact_id, reason)


# ------------------------------------------------------------------ verify

def verify(con, email: str, check_domain: bool = False) -> dict:
    e = (email or "").strip().lower()
    ok, why = email_syntax_ok(e)
    out = {"email": e, "syntax_ok": ok, "result": "unverified", "detail": why, "domain_checked": False,
           "stored_on": []}
    if not ok:
        return out
    out["result"], out["detail"] = "syntax", "well formed; the domain was not checked"
    if check_domain:
        domain = e.rsplit("@", 1)[1]
        out["domain_checked"] = True
        try:
            rec = jf_net.fetch(f"https://{domain}/", cache_ttl=86400, accept="text/html, */*;q=0.5")
            out["result"] = "domain"
            out["detail"] = f"https://{domain}/ answered (HTTP {rec.get('status')}), so the domain exists"
        except jf_net.FetchError as exc:
            if exc.status is not None:
                out["result"] = "domain"
                out["detail"] = f"https://{domain}/ answered (HTTP {exc.status}), so the domain exists"
            else:
                out["result"] = "unverified"
                out["detail"] = f"no answer from https://{domain}/ ({exc.detail or 'network error'})"
        except jf_net.NeverFetch:
            out["domain_checked"] = False
            out["detail"] = f"well formed; {domain} prohibits automated access, so the domain was not checked"
        except jf_net.OfflineMiss:
            out["result"] = "unverified"
            out["detail"] = "offline and no earlier check is cached"
    for row in con.execute("SELECT id, email_verified FROM contacts WHERE lower(email) = ?", (e,)).fetchall():
        if VERIFY_RANK.get(out["result"], 0) >= VERIFY_RANK.get(row["email_verified"] or "unverified", 0):
            con.execute("UPDATE contacts SET email_verified = ? WHERE id = ?", (out["result"], row["id"]))
        out["stored_on"].append(row["id"])
    con.commit()
    return out


# ------------------------------------------------------------------ messages

def messages_add(con, contact_id: str, channel: str, draft: str, application_id: str | None = None,
                 job_id: str | None = None) -> dict:
    p = Path(draft).expanduser()
    if not p.is_file():
        raise ValueError(f"draft file not found: {p}")
    if application_id and con.execute("SELECT 1 FROM applications WHERE id = ?",
                                      (application_id,)).fetchone() is None:
        raise DBError(f"no application {application_id}")
    if job_id and con.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is None:
        raise DBError(f"no job {job_id}")
    contact = db._contact_row(con, contact_id)
    warnings = []
    if channel == "email" and not contact["email"]:
        warnings.append("this contact has no email address stored")
    limit = outreach_config()["max_touches"]
    touches = contact_touches_since_reply(con, contact_id)
    if touches >= limit:
        warnings.append(f"you have already been in touch {touches} time(s) with no reply, the limit is "
                        f"{limit}; send this only if it is about something new")
    row = db.add_message(con, {"contact_id": contact_id, "channel": channel, "draft_path": str(p.resolve()),
                               "application_id": application_id, "job_id": job_id})
    row["warnings"] = warnings
    return row


def messages_sent(con, message_id: str, at: str | None = None, by: str = "user",
                  follow_up_days: int | None = None) -> dict:
    m = _message(con, message_id)
    if m["sent_at"]:
        raise DBError(f"message {message_id} was already marked sent on {str(m['sent_at'])[:10]}")
    if m["suppressed"]:
        raise DBError(f"contact {m['contact_id']} is suppressed; do not send this")
    cfg = outreach_config()
    days = cfg["follow_up_days"] if follow_up_days is None else follow_up_days
    if days < 0:
        raise ValueError("--follow-up-days cannot be negative")
    sent_at = _iso(at)
    due = None
    if days > 0 and cfg["max_touches"] > 1:
        due = add_working_days(_day_of(sent_at), days).isoformat()
    row = db.update_message(con, message_id, {"sent_at": sent_at, "sent_by": by, "follow_up_due": due})
    return {**row, "touches": 1, "max_touches": cfg["max_touches"]}


def messages_reply(con, message_id: str, outcome: str, at: str | None = None) -> dict:
    m = _message(con, message_id)
    outcome = (outcome or "").strip()
    if not outcome:
        raise ValueError("--outcome is empty; say in a few words what they replied")
    if not m["sent_at"]:
        raise DBError(f"message {message_id} is not marked sent yet; run: messages sent {message_id}")
    row = db.update_message(con, message_id, {"reply_at": _iso(at), "outcome": outcome, "follow_up_due": None})
    suppressed = False
    if is_stop_reply(outcome) and not m["suppressed"]:
        db.suppress_contact(con, m["contact_id"], f"reply to {message_id}: {outcome}")
        suppressed = True
    return {**row, "suppressed": suppressed or bool(m["suppressed"]), "contact_suppressed_now": suppressed}


def messages_done(con, message_id: str, today: date | None = None) -> dict:
    m = _message(con, message_id)
    if not m["sent_at"]:
        raise DBError(f"message {message_id} is not marked sent yet")
    if m["reply_at"]:
        raise DBError(f"message {message_id} already has a reply; no follow-up is owed")
    if m["suppressed"]:
        raise DBError(f"contact {m['contact_id']} is suppressed; no more follow-ups")
    cfg = outreach_config()
    touches = message_touches(con, message_id)
    if touches >= cfg["max_touches"]:
        raise DBError(f"message {message_id} has had {touches} touch(es), the limit is {cfg['max_touches']}; "
                      "no further follow-up. Leave it there.")
    touches += 1
    db.add_event(con, "follow-up", f"{message_id}: follow-up sent, touch {touches} of {cfg['max_touches']}",
                 application_id=m["application_id"], job_id=m["job_id"])
    nxt = None
    if touches < cfg["max_touches"] and cfg["follow_up_days"] > 0:
        nxt = add_working_days(today or local_today(), cfg["follow_up_days"]).isoformat()
    row = db.update_message(con, message_id, {"follow_up_due": nxt})
    return {**row, "touches": touches, "max_touches": cfg["max_touches"], "last_touch": nxt is None}


def messages_list(con, contact_id: str | None = None) -> list[dict]:
    q = ("SELECT m.*, c.name AS contact_name, c.org AS contact_org, c.suppressed AS suppressed FROM messages m "
         "JOIN contacts c ON c.id = m.contact_id")
    args: tuple = ()
    if contact_id:
        q, args = q + " WHERE m.contact_id = ?", (contact_id,)
    return [dict(r) for r in con.execute(q + " ORDER BY COALESCE(m.sent_at, ''), m.id", args)]


# ------------------------------------------------------------------ export

def export(con, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = {"contacts": db.list_contacts(con, include_suppressed=True), "messages": messages_list(con)}
    files = []
    for name, rows in tables.items():
        jp = out_dir / f"{name}.json"
        jp.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        cp = out_dir / f"{name}.csv"
        cols = list(rows[0].keys()) if rows else []
        with open(cp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if cols:
                w.writerow(cols)
                for r in rows:
                    w.writerow([r.get(c) for c in cols])
        files += [str(jp), str(cp)]
    return {"out": str(out_dir), "files": files, "contacts": len(tables["contacts"]),
            "messages": len(tables["messages"])}


# ------------------------------------------------------------------ CLI

def _who(row: dict) -> str:
    name = row.get("contact_name", row.get("name"))
    org = row.get("contact_org", row.get("org"))
    return " at ".join(x for x in (name, org) if x) or row.get("contact_id", row.get("id", "?"))


def _common(p) -> None:
    p.add_argument("--db", default=argparse.SUPPRESS, help="database path (default <user dir>/jobferret.db)")
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="print JSON")


def build_parser():
    p = make_parser(__doc__, prog="outreach.py")
    p.add_argument("--db", default=None, help="database path (default <user dir>/jobferret.db)")
    p.add_argument("--json", action="store_true", default=False, help="print JSON")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=type(p))

    c = sub.add_parser("contacts", help="add, list or suppress contacts")
    csub = c.add_subparsers(dest="sub", required=True, parser_class=type(p))
    s = csub.add_parser("add", help="add a contact found on the posting or an employer page")
    s.add_argument("--name", required=True)
    s.add_argument("--role", required=True)
    s.add_argument("--org", required=True)
    s.add_argument("--kind", required=True, choices=db.CONTACT_KINDS)
    s.add_argument("--email")
    s.add_argument("--linkedin", help="their LinkedIn profile URL, as the user found it")
    s.add_argument("--source-url", dest="source_url", help="the page the contact came from")
    s.add_argument("--notes")
    _common(s)
    s = csub.add_parser("list", help="list contacts (suppressed ones only with --all)")
    s.add_argument("--all", action="store_true")
    _common(s)
    s = csub.add_parser("suppress", help="never contact this person again")
    s.add_argument("contact_id")
    s.add_argument("--reason", required=True)
    _common(s)

    s = sub.add_parser("verify", help="check an email address: syntax, then whether the domain answers")
    s.add_argument("email")
    s.add_argument("--check-domain", action="store_true", help="one HTTPS request to the domain's web server")
    jf_net.add_offline_arg(s)
    _common(s)

    m = sub.add_parser("messages", help="the outreach message log")
    msub = m.add_subparsers(dest="sub", required=True, parser_class=type(p))
    s = msub.add_parser("add", help="record a drafted message")
    s.add_argument("--contact", required=True)
    s.add_argument("--channel", required=True, choices=db.CHANNELS)
    s.add_argument("--draft", required=True, help="path to the draft file")
    s.add_argument("--application")
    s.add_argument("--job")
    _common(s)
    s = msub.add_parser("list", help="list messages")
    s.add_argument("--contact")
    _common(s)
    s = msub.add_parser("sent", help="mark a message sent and schedule its follow-up")
    s.add_argument("message_id")
    s.add_argument("--at", help="when it was sent (default now)")
    s.add_argument("--by", choices=db.SENT_BY, default="user")
    s.add_argument("--follow-up-days", dest="follow_up_days", type=int,
                   help="working days until the follow-up (default config [outreach] follow_up_days)")
    _common(s)
    s = msub.add_parser("reply", help="record a reply and its outcome")
    s.add_argument("message_id")
    s.add_argument("--outcome", required=True)
    s.add_argument("--at", help="when they replied (default now)")
    _common(s)
    s = msub.add_parser("done", help="a follow-up was sent and nobody has replied")
    s.add_argument("message_id")
    _common(s)
    s = msub.add_parser("due", help="follow-ups owed today")
    s.add_argument("--today", help="pretend today is YYYY-MM-DD")
    _common(s)

    s = sub.add_parser("export", help="contacts and messages as JSON and CSV")
    s.add_argument("--out", required=True)
    _common(s)
    return p


def main(argv: list[str] | None = None) -> int:
    setup_io()
    a = build_parser().parse_args(argv)
    db_path = Path(a.db).expanduser() if a.db else db.default_db_path()
    try:
        con = db.connect(db_path)
    except DBError as exc:
        die(str(exc), EXIT_FAIL)
    code = EXIT_OK
    try:
        if a.cmd == "contacts" and a.sub == "add":
            res = contacts_add(con, a.name, a.role, a.org, a.kind, a.email, a.linkedin, a.source_url, a.notes)
            if a.json:
                emit_json(res)
            else:
                print(res["id"])
                sys.stderr.write(("Added " if res["created"] else "Updated ") + _who(res) + "\n")
        elif a.cmd == "contacts" and a.sub == "list":
            rows = db.list_contacts(con, include_suppressed=a.all)
            if a.json:
                emit_json(rows)
            elif not rows:
                print("No contacts yet.")
            else:
                for r in rows:
                    flag = " [suppressed]" if r["suppressed"] else ""
                    print(f"{r['id']}  {_who(r)}, {r['role'] or 'role not known'}, {r['kind']}; "
                          f"{r['email'] or 'no email'} ({r['email_verified']}){flag}")
        elif a.cmd == "contacts" and a.sub == "suppress":
            res = contacts_suppress(con, a.contact_id, a.reason)
            emit_json(res) if a.json else print(f"{a.contact_id} suppressed. JobFerret will not draft to them again.")
        elif a.cmd == "verify":
            jf_net.apply_offline_arg(a)
            res = verify(con, a.email, a.check_domain)
            if not res["syntax_ok"]:
                code = EXIT_FAIL
            if a.json:
                emit_json(res)
            else:
                print(f"{res['email']}: {res['result']}. {res['detail']}.")
                print("This never confirms the mailbox exists; only a reply does.")
        elif a.cmd == "messages" and a.sub == "add":
            res = messages_add(con, a.contact, a.channel, a.draft, a.application, a.job)
            if a.json:
                emit_json(res)
            else:
                print(res["id"])
                for w in res["warnings"]:
                    sys.stderr.write(f"warning: {w}\n")
        elif a.cmd == "messages" and a.sub == "list":
            rows = messages_list(con, a.contact)
            if a.json:
                emit_json(rows)
            elif not rows:
                print("No messages yet.")
            else:
                for r in rows:
                    state = f"sent {str(r['sent_at'])[:10]}" if r["sent_at"] else "draft"
                    if r["reply_at"]:
                        state += f", replied: {r['outcome']}"
                    elif r["follow_up_due"]:
                        state += f", follow-up due {r['follow_up_due']}"
                    print(f"{r['id']}  {_who(r)} by {r['channel']}: {state}")
        elif a.cmd == "messages" and a.sub == "sent":
            res = messages_sent(con, a.message_id, a.at, a.by, a.follow_up_days)
            if a.json:
                emit_json(res)
            else:
                print(f"{a.message_id} marked sent. Follow-up due: {res['follow_up_due'] or 'none'}.")
        elif a.cmd == "messages" and a.sub == "reply":
            res = messages_reply(con, a.message_id, a.outcome, a.at)
            if a.json:
                emit_json(res)
            else:
                print(f"Reply recorded on {a.message_id}; no follow-up is owed.")
                if res["contact_suppressed_now"]:
                    print(f"The reply reads as a no, so {res['contact_id']} is now suppressed for good. "
                          "JobFerret will not draft to them again.")
        elif a.cmd == "messages" and a.sub == "done":
            res = messages_done(con, a.message_id)
            if a.json:
                emit_json(res)
            elif res["last_touch"]:
                print(f"Follow-up recorded ({res['touches']} of {res['max_touches']}). That was the last one; "
                      "if they do not reply, leave it there.")
            else:
                print(f"Follow-up recorded ({res['touches']} of {res['max_touches']}). "
                      f"Next one due {res['follow_up_due']} if there is still no reply.")
        elif a.cmd == "messages" and a.sub == "due":
            today = parse_day(a.today, "--today") if a.today else local_today()
            rows = db.messages_due(con, today)
            if a.json:
                emit_json(rows)
            elif not rows:
                print("No outreach follow-ups due.")
            else:
                for i, r in enumerate(rows, 1):
                    print(f"{i}. {_who(r)}, sent {str(r['sent_at'])[:10]}, due {r['follow_up_due']} [{r['id']}]")
        elif a.cmd == "export":
            res = export(con, Path(a.out).expanduser())
            emit_json(res) if a.json else print(f"Wrote {len(res['files'])} files to {res['out']} "
                                                f"({res['contacts']} contacts, {res['messages']} messages).")
    except DBError as exc:
        die(str(exc), EXIT_FAIL)
    except ValueError as exc:
        die(str(exc), EXIT_USAGE)
    finally:
        con.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
