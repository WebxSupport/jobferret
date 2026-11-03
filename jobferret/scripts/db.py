"""JobFerret's local SQLite store: jobs, applications, runs, contacts, messages and events.

Purpose
    Records every job seen and every application made, so the apply mode can
    dedupe, enforce the volume limits (gate G7) and report progress. Counts and
    rates are always derived from rows; nothing is hand-maintained. This file
    owns the whole schema and its migrations. Other scripts call connect() and
    never create tables.

Usage
    db.py [--db PATH] init
    db.py [--db PATH] migrate
    db.py [--db PATH] add-job --json '<object>'
    db.py [--db PATH] set-job-status <job_id> <status> [--reason TEXT]
    db.py [--db PATH] set-screening <job_id> --fit N [--screen '<object>'] [--status S]
    db.py [--db PATH] jobs [--status S] [--since N] [--min-fit N] [--run ID] [--json]
    db.py [--db PATH] runs [list | show <id>] [--json]
    db.py [--db PATH] add-application --json '<object>' [--update]
    db.py [--db PATH] set-status <app_id> <status> [--note TEXT]
    db.py [--db PATH] list [--status S] [--jobs]
    db.py [--db PATH] show <id>
    db.py [--db PATH] stats
    db.py [--db PATH] export [--out DIR]
    db.py [--db PATH] dedup [--url URL] [--company C --title T] [--days N]
    db.py [--db PATH] events add --kind <kind> [--application <id>] [--job <id>] --detail "<text>"
    Every subcommand prints JSON when the global --json flag comes before the
    subcommand, e.g. "db.py --json list". The new listing commands (jobs, runs,
    migrate, set-job-status, stats) also take --json after the subcommand.
    (The --json after add-job and add-application is their input object.)

    The default database is <user dir>/jobferret.db (~/.jobferret unless
    $JOBFERRET_HOME is set). Write commands create the schema if needed.

Schema version 2
    PRAGMA user_version is 2. connect() opens any older database (the Phase 1
    schema, user_version 0 or 1) and brings it forward by adding columns and
    tables, never dropping or rewriting rows. "migrate" does the same on
    request and prints what it changed. Running it twice changes nothing.

Jobs
    add-job keys: canonical_url or source_url (one required), source, platform,
    company, title, location, remote, salary_min, salary_max, currency,
    salary_period, contract_type, employer_type, posted_at, expires_at,
    jd_path, content_hash, fit_pre, screen_json (object or JSON text), run_id,
    status, status_reason. "description" and "raw" are accepted and ignored:
    the database keeps the path to the description (jd_path), not the text.
    Allowed values:
      remote         remote | hybrid | office | unknown
      salary_period  year | day | hour | unknown
      contract_type  permanent | contract | fixed-term | temporary | part-time | unknown
      employer_type  direct | agency | unknown
      status         seen | screened | excluded | shortlisted | dismissed | applied | expired
    An unknown value is an error that names the allowed set. A new job gets
    "unknown" for the four type fields it does not set, and status "seen".

    Job id: sha1(canonical_url)[:12] when a canonical URL is known. If the
    canonical_url key is present and null (aggregator records), the id is
    sha1(source_url)[:12] and canonical_url stays null. If the key is left out
    and source_url is given, the cleaned source_url is used as the canonical
    URL (the Phase 1 behaviour). When the canonical URL is learned later,
    add-job with both URLs finds the row by its source_url, keeps the existing
    id and stores the canonical URL. It never makes a second row.

    Re-adding a job (same canonical_url, or the same source_url) refreshes
    last_seen and any newly known fields. It does not reset status,
    status_reason, fit_pre or screen_json once they are set, and it keeps the
    first source, source_url and run_id. A re-seen job keeps its screening.
    Use set-job-status to change the status and set-screening to re-screen.
    set-job-status logs an event of kind shortlist (shortlisted), dismiss
    (dismissed) or status-change (anything else).
    jobs lists newest first (by first_seen) with the fields the digest needs.
    --since N keeps jobs first seen in the last N days, --min-fit N keeps
    fit_pre >= N, --run keeps jobs first found by that run.

Runs
    start_run(con, since_days, sources) returns a run id (YYYYMMDD-HHMMSS) and
    finish_run(con, run_id, found, new, errors) closes it. discover.py uses both.

Applications
    add-application keys: job_id (required; or url of a job already added),
    method, status, fit_score, ats_score, ghost_risk, cv_path,
    cover_letter_path, answers_path, review_screenshot,
    confirmation_screenshot, notes, submitted_at, created_at, follow_up_due,
    last_contact, found_via, cv_variant, role_family, outcome_reason.
    id = YYYYMMDD-<company-slug>-<title-slug> (<= 60 chars).
    status: draft | ready | submitted | acknowledged | screening | interviewing |
            offer | rejected | withdrawn | ghosted
    method: ats-form | assist-linkedin | assist-indeed | assist-nhs | assist-other |
            email | manual
    follow_up_due and last_contact are dates written YYYY-MM-DD.
    add-job and add-application print the new id (plain: the id alone on stdout,
    a summary on stderr; --json: the whole row, including "id").

Contacts and messages
    Python helpers only (outreach.py builds the command line on top of them):
    add_contact, list_contacts, suppress_contact, add_message, update_message,
    messages_due. Contact id = "c-" + sha1(lower(email or linkedin_url or
    name+org))[:10]. A suppressed contact is never listed by default, never
    comes back from messages_due, and cannot be given a new message.

Events and stats
    events add records e.g. a "wrong-field" event (the model filled a field
    wrongly) or a "ledger-failure" event (the fact check failed during apply).
    Any lower-case kind with hyphens is accepted; KNOWN_EVENT_KINDS lists the
    ones the skill uses. stats counts applications and jobs, shows submissions
    per day for the last 14 days, and reports auto_eligible: true when at least
    20 ats-form applications have reached submitted or later AND there are no
    wrong-field events AND no ledger-failure events.
    submitted_today (the G7 count) covers ats-form, assist-*, email and unset methods; manual
    applications (made outside JobFerret) are left out and listed as submitted_today_manual.
    submitted_today_assisted is informational (the assist-* part of submitted_today). Only
    ats-form counts toward auto_eligible. A manual application gets no submitted_at unless one is given.
    Daily counts use the local calendar date; timestamps are stored in UTC.
    dedup: an existing application on the same canonical URL, or on the same
    company plus a similar title within N days (default [limits]
    per_employer_days, 30) -> possible duplicate (exit 1). A job that
    discovery stored but nobody applied to is reported as "known_job" (exit 0).
    JSON: {"ok", "duplicate", "known_job": {...}|null, "matches": [...], "days"}.

Secrets
    JSON output never includes a settings row whose key contains "key",
    "secret" or "token", and never includes a field with such a name.

Exit codes
    0  ok (dedup: no duplicate application; a stored job with no application is
       reported as "known_job" and still exits 0)
    1  not found, already exists, invalid value, or (dedup) an existing
       application matches
    3  missing dependency (none expected; sqlite3 is in the standard library)
    4  usage or input error (bad arguments, invalid JSON)
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jf_common import (
    EXIT_FAIL, EXIT_OK, ConfigError, canonicalize_url, die, emit_json, load_config, make_parser,
    now_iso, setup_io, slugify, user_dir,
)

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, canonical_url TEXT UNIQUE, source_url TEXT, source TEXT, platform TEXT,
  company TEXT, title TEXT, location TEXT, remote TEXT, salary_min REAL, salary_max REAL, currency TEXT,
  posted_at TEXT, first_seen TEXT, last_seen TEXT, content_hash TEXT, jd_path TEXT, status TEXT,
  salary_period TEXT, contract_type TEXT, employer_type TEXT, expires_at TEXT, fit_pre REAL, screen_json TEXT,
  run_id TEXT, status_reason TEXT);
CREATE TABLE IF NOT EXISTS applications (id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id), created_at TEXT, submitted_at TEXT,
  method TEXT, status TEXT, fit_score REAL, ats_score REAL, ghost_risk TEXT, cv_path TEXT, cover_letter_path TEXT,
  answers_path TEXT, review_screenshot TEXT, confirmation_screenshot TEXT, notes TEXT,
  follow_up_due TEXT, last_contact TEXT, found_via TEXT, cv_variant TEXT, role_family TEXT, outcome_reason TEXT);
CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, application_id TEXT, kind TEXT, path TEXT, sha256 TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts TEXT, application_id TEXT, job_id TEXT, kind TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, since_days INTEGER,
  sources_json TEXT, found INTEGER, new INTEGER, errors_json TEXT);
CREATE TABLE IF NOT EXISTS contacts (id TEXT PRIMARY KEY, name TEXT, role TEXT, org TEXT, email TEXT, linkedin_url TEXT,
  source_url TEXT, kind TEXT, email_verified TEXT, consent_basis TEXT, suppressed INTEGER DEFAULT 0,
  created_at TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, contact_id TEXT REFERENCES contacts(id), application_id TEXT,
  job_id TEXT, channel TEXT, draft_path TEXT, sent_at TEXT, sent_by TEXT, follow_up_due TEXT, reply_at TEXT, outcome TEXT);
CREATE TABLE IF NOT EXISTS questions_log (id INTEGER PRIMARY KEY, ts TEXT, key TEXT, answered INTEGER);
"""
# Columns added to Phase 1 tables when an older database is opened.
NEW_COLUMNS = {
    "jobs": (("salary_period", "TEXT"), ("contract_type", "TEXT"), ("employer_type", "TEXT"),
             ("expires_at", "TEXT"), ("fit_pre", "REAL"), ("screen_json", "TEXT"), ("run_id", "TEXT"),
             ("status_reason", "TEXT")),
    "applications": (("follow_up_due", "TEXT"), ("last_contact", "TEXT"), ("found_via", "TEXT"),
                     ("cv_variant", "TEXT"), ("role_family", "TEXT"), ("outcome_reason", "TEXT")),
}
INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_run ON jobs(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_source_url ON jobs(source_url)",
    "CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind)",
)

APP_STATUSES = ("draft", "ready", "submitted", "acknowledged", "screening", "interviewing", "offer",
                "rejected", "withdrawn", "ghosted")
POST_SUBMIT = {"submitted", "acknowledged", "screening", "interviewing", "offer", "rejected", "ghosted"}
AUTO_MIN_APPLICATIONS = 20
# Only applications JobFerret itself submitted count toward auto mode. assist-* (the user clicked) and
# manual (applied outside JobFerret) are reported separately and never count toward it.
AUTO_METHODS = ("ats-form",)
METHODS = ("ats-form", "assist-linkedin", "assist-indeed", "assist-nhs", "assist-other", "email", "manual")
EVENT_KIND_RE = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
KNOWN_EVENT_KINDS = ("wrong-field", "ledger-failure", "run", "screen", "shortlist", "dismiss", "status-change",
                     "contact-added", "message-sent", "reply", "follow-up", "interview", "offer", "rejection",
                     "note", "status", "job-added", "application-updated", "captcha")

JOB_STATUSES = ("seen", "screened", "excluded", "shortlisted", "dismissed", "applied", "expired")
JOB_ENUMS = {
    "remote": ("remote", "hybrid", "office", "unknown"),
    "salary_period": ("year", "day", "hour", "unknown"),
    "contract_type": ("permanent", "contract", "fixed-term", "temporary", "part-time", "unknown"),
    "employer_type": ("direct", "agency", "unknown"),
    "status": JOB_STATUSES,
}
JOB_KEYS = ("canonical_url", "source_url", "source", "platform", "company", "title", "location", "remote",
            "salary_min", "salary_max", "currency", "salary_period", "contract_type", "employer_type",
            "posted_at", "expires_at", "content_hash", "jd_path", "fit_pre", "screen_json", "run_id",
            "status", "status_reason")
JOB_IGNORED_KEYS = ("description", "raw")  # kept in the job file at jd_path, not in the row
APP_KEYS = ("job_id", "url", "method", "status", "fit_score", "ats_score", "ghost_risk", "cv_path",
            "cover_letter_path", "answers_path", "review_screenshot", "confirmation_screenshot", "notes",
            "submitted_at", "created_at", "follow_up_due", "last_contact", "found_via", "cv_variant",
            "role_family", "outcome_reason")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ].*)?$")

CONTACT_KINDS = ("agency", "in-house", "hiring-manager", "referral", "other")
EMAIL_VERIFIED = ("syntax", "domain", "unverified")
CHANNELS = ("email", "linkedin", "inmail", "form")
SENT_BY = ("user", "connector")
CONTACT_KEYS = ("name", "role", "org", "email", "linkedin_url", "source_url", "kind", "email_verified",
                "consent_basis", "notes")
MESSAGE_KEYS = ("contact_id", "application_id", "job_id", "channel", "draft_path", "sent_at", "sent_by",
                "follow_up_due", "reply_at", "outcome")

SECRET_SETTING_RE = re.compile(r"key|secret|token", re.IGNORECASE)
SECRET_NAME_TOKENS = {"key", "secret", "token", "apikey", "appkey", "password"}

COMPANY_SUFFIX_RE = re.compile(r"\b(?:ltd|limited|plc|llp|llc|inc|incorporated|corp|corporation|co|company|gmbh|"
                               r"ag|sa|bv|nv|pty|group|holdings|uk|the)\b\.?", re.IGNORECASE)


class DBError(Exception):
    """A readable, expected failure (exit 1)."""


class JFConnection(sqlite3.Connection):
    """A connection that remembers what the automatic migration did when it opened."""
    migrated_from: int | None = None
    migrated: tuple = ()


def default_db_path() -> Path:
    return user_dir() / "jobferret.db"


def _tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def migrate(con: sqlite3.Connection) -> list[str]:
    """Bring the database to schema version 2 and return what was done (empty if nothing).

    Adds missing columns and tables only; no row is changed or removed. Safe to
    run any number of times, including from two scripts at once.
    """
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if isinstance(con, JFConnection):
        con.migrated_from = version
    if version > SCHEMA_VERSION:
        raise DBError(f"this database is schema version {version}, newer than this JobFerret (version "
                      f"{SCHEMA_VERSION}); update JobFerret rather than opening it with this copy")
    actions: list[str] = []
    if version < SCHEMA_VERSION:
        before = _tables(con)
        con.executescript(SCHEMA)
        if not before:
            actions.append(f"created a new database at schema version {SCHEMA_VERSION}")
        else:
            actions.extend(f"created table {t}" for t in ("runs", "contacts", "messages", "questions_log")
                           if t not in before)
        for table, cols in NEW_COLUMNS.items():
            have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
            for name, typ in cols:
                if name in have:
                    continue
                try:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise
                    continue
                actions.append(f"added column {table}.{name}")
        for stmt in INDEXES:
            con.execute(stmt)
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),))
        con.commit()
        if before and not actions:
            actions.append(f"set schema version to {SCHEMA_VERSION}")
    if isinstance(con, JFConnection):
        con.migrated = tuple(actions)
    return actions


def connect(path: Path, create: bool = True, auto_migrate: bool = True) -> sqlite3.Connection:
    """Open the database, migrating an older one to schema version 2 on the way."""
    path = Path(path)
    if not create and not path.is_file():
        raise DBError(f"no database at {path}; run: db.py init")
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), factory=JFConnection, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    if auto_migrate:
        try:
            migrate(con)
        except Exception:
            con.close()
            raise
    return con


def log_event(con: sqlite3.Connection, kind: str, detail: str, application_id: str | None = None,
              job_id: str | None = None) -> None:
    con.execute("INSERT INTO events (ts, application_id, job_id, kind, detail) VALUES (?, ?, ?, ?, ?)",
                (now_iso(), application_id, job_id, kind, detail))


def job_id_for(canonical_url: str) -> str:
    return hashlib.sha1(canonical_url.encode("utf-8")).hexdigest()[:12]


def local_date(ts: str | None):
    """The user's local calendar date of a stored UTC timestamp (None if unparseable)."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date()


def application_id_for(company: str, title: str, when: datetime | None = None) -> str:
    if when is not None and when.tzinfo is not None:
        when = when.astimezone()  # local calendar day
    day = (when or datetime.now()).strftime("%Y%m%d")
    comp = slugify(company or "unknown", 20) or "unknown"
    room = 60 - len(day) - len(comp) - 2
    tit = slugify(title or "role", max(room, 5)) or "role"
    return f"{day}-{comp}-{tit}"[:60].rstrip("-")


def _check_keys(data: dict, allowed: tuple[str, ...], what: str) -> None:
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise DBError(f"unknown {what} field(s): {', '.join(unknown)}. Allowed: {', '.join(allowed)}")


def _canon(url: str) -> str:
    try:
        return canonicalize_url(url)
    except ValueError as exc:
        raise DBError(f"{url!r} is not a usable URL: {exc}") from exc


def _enum(name: str, value, allowed: tuple[str, ...]) -> str:
    v = str(value).strip().lower()
    if v not in allowed:
        raise DBError(f"{name} {value!r} is not one of: {', '.join(allowed)}")
    return v


def _number(name: str, value, lo: float | None = None, hi: float | None = None) -> float:
    try:
        if isinstance(value, bool):
            raise ValueError
        num = float(value)
    except (TypeError, ValueError):
        raise DBError(f"{name} {value!r} is not a number") from None
    if (lo is not None and num < lo) or (hi is not None and num > hi):
        raise DBError(f"{name} {value!r} must be between {lo} and {hi}")
    return num


def _date_text(name: str, value) -> str:
    if not isinstance(value, str) or not DATE_RE.match(value.strip()):
        raise DBError(f"{name} {value!r} must be a date written YYYY-MM-DD")
    return value.strip()


# ------------------------------------------------------------------------- jobs

def _clean_job_fields(data: dict) -> dict:
    """Validate and normalise the job fields that go in the row (null and empty values are dropped)."""
    out: dict = {}
    for k in JOB_KEYS:
        if k == "canonical_url":
            continue
        v = data.get(k)
        if v is None or v == "":
            continue
        if k in JOB_ENUMS:
            v = _enum(k, v, JOB_ENUMS[k])
        elif k in ("salary_min", "salary_max"):
            v = _number(k, v, 0)
        elif k == "fit_pre":
            v = _number(k, v, 0, 100)
        elif k == "screen_json":
            if not isinstance(v, str):
                v = json.dumps(v, ensure_ascii=False)
            else:
                try:
                    json.loads(v)
                except json.JSONDecodeError as exc:
                    raise DBError(f"screen_json is not valid JSON: {exc}") from exc
        out[k] = v
    return out


def _find_job(con: sqlite3.Connection, canon: str | None, source_url: str | None):
    if canon:
        row = con.execute("SELECT * FROM jobs WHERE canonical_url = ? OR id = ?", (canon, job_id_for(canon))).fetchone()
        if row is not None:
            return row
    if source_url:
        cands = {source_url, _canon(source_url)}
        marks = ", ".join("?" for _ in cands)
        return con.execute(f"SELECT * FROM jobs WHERE source_url IN ({marks}) OR canonical_url IN ({marks}) "
                           "ORDER BY first_seen LIMIT 1", (*cands, *cands)).fetchone()
    return None


def add_job(con: sqlite3.Connection, data: dict) -> dict:
    """Add a job, or refresh one already stored (see the module docstring for the rules)."""
    _check_keys(data, JOB_KEYS + JOB_IGNORED_KEYS, "job")
    source_url = (data.get("source_url") or "").strip() or None
    given = (data.get("canonical_url") or "").strip() or None
    if given:
        canon = _canon(given)
    elif "canonical_url" not in data and source_url:
        canon = _canon(source_url)
    else:
        canon = None
    if not canon and not source_url:
        raise DBError("a job needs canonical_url or source_url")
    clean = _clean_job_fields(data)
    now = now_iso()
    row = _find_job(con, canon, source_url)
    if row is None:
        jid = job_id_for(canon or _canon(source_url))
        fields = dict(clean)
        for k in ("remote", "salary_period", "contract_type", "employer_type"):
            fields.setdefault(k, "unknown")
        fields.setdefault("status", "seen")
        fields.setdefault("source_url", source_url or canon)
        fields.update({"id": jid, "canonical_url": canon, "first_seen": now, "last_seen": now})
        con.execute(f"INSERT INTO jobs ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                    tuple(fields.values()))
        log_event(con, "job-added", canon or source_url, job_id=jid)
        created = True
    else:
        jid = row["id"]
        upd: dict = {"last_seen": now}
        for k, v in clean.items():
            cur = row[k]
            if k in ("source", "source_url", "run_id", "status_reason", "fit_pre", "screen_json"):
                if cur is None:
                    upd[k] = v
            elif k == "status":
                if cur in (None, "seen"):
                    upd[k] = v
            elif k in JOB_ENUMS:
                if v != "unknown" or cur is None:
                    upd[k] = v
            else:
                upd[k] = v
        if canon and row["canonical_url"] != canon:
            clash = con.execute("SELECT 1 FROM jobs WHERE canonical_url = ? AND id != ?", (canon, jid)).fetchone()
            if clash is None:
                upd["canonical_url"] = canon
        con.execute(f"UPDATE jobs SET {', '.join(f'{k} = ?' for k in upd)} WHERE id = ?", (*upd.values(), jid))
        created = False
    con.commit()
    out = dict(con.execute("SELECT * FROM jobs WHERE id = ?", (jid,)).fetchone())
    out["created"] = created
    return out


def _job_row(con: sqlite3.Connection, job_id: str):
    row = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise DBError(f"no job {job_id}")
    return row


def set_job_status(con: sqlite3.Connection, job_id: str, status: str, reason: str | None = None) -> dict:
    """Change a job's status and note why. Logs shortlist, dismiss or status-change."""
    status = _enum("status", status, JOB_STATUSES)
    row = _job_row(con, job_id)
    reason = (reason or "").strip() or None
    con.execute("UPDATE jobs SET status = ?, status_reason = ? WHERE id = ?", (status, reason, job_id))
    kind = {"shortlisted": "shortlist", "dismissed": "dismiss"}.get(status, "status-change")
    log_event(con, kind, f"{row['status']} -> {status}" + (f": {reason}" if reason else ""), job_id=job_id)
    con.commit()
    return dict(_job_row(con, job_id))


def set_screening(con: sqlite3.Connection, job_id: str, fit_pre: float | None, screen: dict | str | None = None,
                  status: str | None = None) -> dict:
    """Write (or rewrite) a job's pre-screen result. The status changes only while the job is
    still seen, screened or excluded, so a re-screen never undoes a shortlist or a dismissal."""
    row = _job_row(con, job_id)
    sets: dict = {}
    if fit_pre is not None:
        sets["fit_pre"] = _number("fit_pre", fit_pre, 0, 100)
    if screen is not None:
        sets["screen_json"] = screen if isinstance(screen, str) else json.dumps(screen, ensure_ascii=False)
    if status is not None and row["status"] in (None, "seen", "screened", "excluded"):
        sets["status"] = _enum("status", status, JOB_STATUSES)
    if sets:
        con.execute(f"UPDATE jobs SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?", (*sets.values(), job_id))
        con.commit()
    return dict(_job_row(con, job_id))


def _salary_text(row: dict) -> str | None:
    lo, hi = row.get("salary_min"), row.get("salary_max")
    if lo is None and hi is None:
        return None
    sym = {"GBP": "£", "USD": "$", "EUR": "€"}.get((row.get("currency") or "").upper(), (row.get("currency") or "") + " ")

    def fmt(n):
        return f"{sym}{n:,.0f}"
    text = fmt(lo) if hi is None or hi == lo else (fmt(hi) if lo is None else f"{fmt(lo)} to {fmt(hi)}")
    period = row.get("salary_period")
    return text + (f" a {period}" if period and period != "unknown" else "")


def list_jobs(con: sqlite3.Connection, status: str | None = None, since: int | None = None,
              min_fit: float | None = None, run: str | None = None, limit: int | None = None) -> list[dict]:
    """Jobs newest first (by first_seen, then best fit), with what the digest needs."""
    where, args = [], []
    if status:
        where.append("status = ?")
        args.append(_enum("status", status, JOB_STATUSES))
    if since is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=since)).replace(microsecond=0)
        where.append("first_seen >= ?")
        args.append(cutoff.isoformat().replace("+00:00", "Z"))
    if min_fit is not None:
        where.append("fit_pre >= ?")
        args.append(float(min_fit))
    if run:
        where.append("run_id = ?")
        args.append(run)
    q = "SELECT * FROM jobs" + (" WHERE " + " AND ".join(where) if where else "")
    q += " ORDER BY first_seen DESC, COALESCE(fit_pre, -1) DESC, id"
    if limit:
        q += f" LIMIT {int(limit)}"
    out = []
    for r in con.execute(q, args):
        d = dict(r)
        try:
            screen = json.loads(d["screen_json"]) if d.get("screen_json") else None
        except json.JSONDecodeError:
            screen = None
        out.append({
            "id": d["id"], "title": d["title"], "company": d["company"], "location": d["location"],
            "remote": d["remote"], "salary": _salary_text(d), "salary_min": d["salary_min"],
            "salary_max": d["salary_max"], "currency": d["currency"], "salary_period": d["salary_period"],
            "contract_type": d["contract_type"], "employer_type": d["employer_type"], "source": d["source"],
            "platform": d["platform"], "posted_at": d["posted_at"], "expires_at": d["expires_at"],
            "first_seen": d["first_seen"], "last_seen": d["last_seen"], "fit_pre": d["fit_pre"],
            "screen": screen, "status": d["status"], "status_reason": d["status_reason"], "run_id": d["run_id"],
            "jd_path": d["jd_path"], "canonical_url": d["canonical_url"], "source_url": d["source_url"],
            "url": d["canonical_url"] or d["source_url"],
        })
    return out


# ------------------------------------------------------------------------- runs

def start_run(con: sqlite3.Connection, since_days: int | None, sources: list[str]) -> str:
    """Open a discovery run and return its id (YYYYMMDD-HHMMSS, local time; bumped a second if taken)."""
    when = datetime.now()
    while True:
        run_id = when.strftime("%Y%m%d-%H%M%S")
        if con.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is None:
            break
        when += timedelta(seconds=1)
    con.execute("INSERT INTO runs (id, started_at, since_days, sources_json) VALUES (?, ?, ?, ?)",
                (run_id, now_iso(), since_days, json.dumps(list(sources))))
    log_event(con, "run", f"started {run_id}: {', '.join(sources) or 'no sources'}")
    con.commit()
    return run_id


def finish_run(con: sqlite3.Connection, run_id: str, found: int, new: int, errors=None) -> dict:
    """Close a run with its totals. errors is a dict of source -> message, or a list of messages."""
    if con.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is None:
        raise DBError(f"no run {run_id}")
    con.execute("UPDATE runs SET finished_at = ?, found = ?, new = ?, errors_json = ? WHERE id = ?",
                (now_iso(), int(found), int(new), json.dumps(errors if errors is not None else {}), run_id))
    n_err = len(errors) if errors else 0
    log_event(con, "run", f"finished {run_id}: found {int(found)}, new {int(new)}, {n_err} error(s)")
    con.commit()
    return get_run(con, run_id)


def _run_dict(row) -> dict:
    d = dict(row)
    for src, dst in (("sources_json", "sources"), ("errors_json", "errors")):
        try:
            d[dst] = json.loads(d.pop(src)) if d.get(src) else None
        except json.JSONDecodeError:
            d[dst] = None
            d.pop(src, None)
    return d


def get_run(con: sqlite3.Connection, run_id: str) -> dict:
    row = con.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise DBError(f"no run {run_id}")
    d = _run_dict(row)
    d["jobs_first_found"] = con.execute("SELECT COUNT(*) FROM jobs WHERE run_id = ?", (run_id,)).fetchone()[0]
    return d


def list_runs(con: sqlite3.Connection, limit: int | None = None) -> list[dict]:
    q = "SELECT * FROM runs ORDER BY started_at DESC, id DESC" + (f" LIMIT {int(limit)}" if limit else "")
    return [_run_dict(r) for r in con.execute(q)]


def last_finished_run(con: sqlite3.Connection) -> dict | None:
    """The most recent run that finished with no errors, or None (discover.py uses it for --since)."""
    for r in con.execute("SELECT * FROM runs WHERE finished_at IS NOT NULL ORDER BY started_at DESC, id DESC"):
        d = _run_dict(r)
        errs = d["errors"]
        # discover.py stores {"errors": {...}, "counts": {...}, "skipped": {...}}; only the inner
        # errors mean the run failed. A plain list or dict of errors (older shape) still counts as is.
        if isinstance(errs, dict) and {"errors", "counts", "skipped"} & set(errs):
            errs = errs.get("errors")
        if not errs:
            return d
    return None


# ------------------------------------------------------------------ applications

def _check_app_fields(data: dict) -> None:
    if data.get("method") is not None and data["method"] not in METHODS:
        raise DBError(f"method {data['method']!r} is not one of: {', '.join(METHODS)}")
    for k in ("follow_up_due", "last_contact"):
        if data.get(k) is not None:
            data[k] = _date_text(k, data[k])


def add_application(con: sqlite3.Connection, data: dict, update: bool = False) -> dict:
    data = dict(data)
    given_id = data.pop("id", None)
    if given_id and not update:
        raise DBError("\"id\" is accepted only with --update; the script computes the id of a new application")
    _check_keys(data, APP_KEYS, "application")
    url = data.pop("url", None)
    existing = None
    if given_id:
        # --update with the id add-application printed: the one call that takes it (apply.md step 10)
        existing = con.execute("SELECT * FROM applications WHERE id = ?", (given_id,)).fetchone()
        if existing is None:
            raise DBError(f"application {given_id} does not exist")
        job_id = existing["job_id"]
        if data.get("job_id") and data["job_id"] != job_id:
            raise DBError(f"application {given_id} belongs to job {job_id}, not {data['job_id']}")
        data["job_id"] = job_id
    job_id = data.get("job_id")
    if not job_id and url:
        row = _find_job(con, _canon(url), url)
        job_id = row["id"] if row is not None else job_id_for(_canon(url))
        data["job_id"] = job_id
    if not job_id:
        raise DBError("an application needs job_id (or the url of a job added with add-job)")
    job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        raise DBError(f"job {job_id} is not in the database; add it with add-job first")
    status = data.get("status", "draft")
    if status not in APP_STATUSES:
        raise DBError(f"status {status!r} is not one of: {', '.join(APP_STATUSES)}")
    _check_app_fields(data)
    if existing is not None:
        app_id = existing["id"]
        created_at = existing["created_at"]
    else:
        created_at = data.get("created_at") or now_iso()
        try:
            when = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DBError(f"created_at {created_at!r} is not an ISO date-time") from exc
        app_id = application_id_for(job["company"] or "", job["title"] or "", when)
        existing = con.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    if existing and not update:
        raise DBError(f"application {app_id} already exists; use set-status, or add-application --update")
    if not existing and update:
        raise DBError(f"application {app_id} does not exist yet; drop --update")
    method_now = data.get("method") or (existing["method"] if existing else None)
    if (status in POST_SUBMIT and not data.get("submitted_at") and not (existing and existing["submitted_at"])
            and method_now != "manual"):
        data["submitted_at"] = now_iso()  # manual: applied outside JobFerret, the user supplies the real date
    if existing:
        fields = {k: v for k, v in data.items() if k not in ("job_id", "created_at") and v is not None}
        if fields:
            con.execute(f"UPDATE applications SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                        (*fields.values(), app_id))
        if "status" in fields and fields["status"] != existing["status"]:
            log_event(con, "status", f"{existing['status']} -> {fields['status']}", app_id, job_id)
        log_event(con, "application-updated", ", ".join(sorted(fields)), app_id, job_id)
    else:
        fields = {k: v for k, v in data.items() if v is not None}
        fields.update({"id": app_id, "job_id": job_id, "created_at": created_at, "status": status})
        con.execute(f"INSERT INTO applications ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                    tuple(fields.values()))
        log_event(con, "status", f"-> {status}", app_id, job_id)
        for kind in ("cv_path", "cover_letter_path", "answers_path", "review_screenshot", "confirmation_screenshot"):
            if fields.get(kind):
                con.execute("INSERT INTO documents (application_id, kind, path, sha256, created_at) "
                            "VALUES (?, ?, ?, ?, ?)", (app_id, kind.replace("_path", ""), fields[kind],
                                                       _sha_or_none(fields[kind]), now_iso()))
    con.commit()
    return dict(con.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone())


def _sha_or_none(path: str) -> str | None:
    p = Path(path).expanduser()
    if p.is_file():
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        return h
    return None


def set_status(con: sqlite3.Connection, app_id: str, status: str, note: str | None = None) -> dict:
    if status not in APP_STATUSES:
        raise DBError(f"status {status!r} is not one of: {', '.join(APP_STATUSES)}")
    row = con.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    if row is None:
        raise DBError(f"no application {app_id}")
    sets, vals = ["status = ?"], [status]
    if status in POST_SUBMIT and not row["submitted_at"] and row["method"] != "manual":
        sets.append("submitted_at = ?")
        vals.append(now_iso())
    con.execute(f"UPDATE applications SET {', '.join(sets)} WHERE id = ?", (*vals, app_id))
    log_event(con, "status", f"{row['status']} -> {status}" + (f" ({note})" if note else ""), app_id, row["job_id"])
    con.commit()
    return dict(con.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone())


def list_rows(con: sqlite3.Connection, status: str | None = None, jobs: bool = False) -> list[dict]:
    if jobs:
        q, args = "SELECT * FROM jobs", []
        if status:
            q, args = q + " WHERE status = ?", [status]
        return [dict(r) for r in con.execute(q + " ORDER BY last_seen DESC", args)]
    q = ("SELECT a.*, j.company AS company, j.title AS title, j.platform AS platform, j.canonical_url AS url, "
         "j.expires_at AS expires_at FROM applications a LEFT JOIN jobs j ON j.id = a.job_id")
    args = []
    if status:
        q, args = q + " WHERE a.status = ?", [status]
    return [dict(r) for r in con.execute(q + " ORDER BY a.created_at DESC", args)]


def show(con: sqlite3.Connection, ident: str) -> dict:
    row = con.execute("SELECT * FROM applications WHERE id = ?", (ident,)).fetchone()
    if row is not None:
        app = dict(row)
        job = con.execute("SELECT * FROM jobs WHERE id = ?", (app["job_id"],)).fetchone()
        return {"type": "application", "application": app, "job": dict(job) if job else None,
                "documents": [dict(r) for r in con.execute("SELECT * FROM documents WHERE application_id = ? ORDER BY id", (ident,))],
                "events": [dict(r) for r in con.execute("SELECT * FROM events WHERE application_id = ? ORDER BY id", (ident,))]}
    row = con.execute("SELECT * FROM jobs WHERE id = ?", (ident,)).fetchone()
    if row is not None:
        return {"type": "job", "job": dict(row),
                "applications": [dict(r) for r in con.execute("SELECT * FROM applications WHERE job_id = ?", (ident,))],
                "events": [dict(r) for r in con.execute("SELECT * FROM events WHERE job_id = ? ORDER BY id", (ident,))]}
    raise DBError(f"no application or job with id {ident}")


# ------------------------------------------------------------------------ stats

def stats(con: sqlite3.Connection, config: dict | None = None) -> dict:
    cfg = config or {}
    limits = cfg.get("limits", {})
    apps = [dict(r) for r in con.execute("SELECT * FROM applications")]
    reached: dict[str, set[str]] = {a["id"]: {a["status"]} for a in apps}
    for ev in con.execute("SELECT application_id, detail FROM events WHERE kind = 'status' AND application_id IS NOT NULL"):
        m = re.search(r"->\s*([a-z]+)", ev["detail"] or "")
        if m and ev["application_id"] in reached:
            reached[ev["application_id"]].add(m.group(1))
    by_status: dict[str, int] = {s: 0 for s in APP_STATUSES}
    by_method: dict[str, int] = {}
    for a in apps:
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1
        if a["method"]:
            by_method[a["method"]] = by_method.get(a["method"], 0) + 1
    submitted = [a for a in apps if a["submitted_at"] or reached[a["id"]] & POST_SUBMIT]

    def ever(*states: str) -> int:
        return sum(1 for a in submitted if reached[a["id"]] & set(states))

    def rate(n: int) -> float | None:
        return round(n / len(submitted), 3) if submitted else None

    today = datetime.now().astimezone().date()
    week_start = today - timedelta(days=6)
    sub_dates = [local_date(a["submitted_at"]) for a in submitted]
    sub_today = sum(1 for a in submitted
                    if local_date(a["submitted_at"]) == today and a["method"] != "manual")
    sub_today_assisted = sum(1 for a in submitted if local_date(a["submitted_at"]) == today
                             and (a["method"] or "").startswith("assist-"))
    sub_today_manual = sum(1 for a in submitted if local_date(a["submitted_at"]) == today
                           and a["method"] == "manual")
    per_day = {}
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        per_day[day.isoformat()] = sum(1 for d in sub_dates if d == day)
    wrong_field = con.execute("SELECT COUNT(*) FROM events WHERE kind = 'wrong-field'").fetchone()[0]
    ledger_failures = con.execute("SELECT COUNT(*) FROM events WHERE kind = 'ledger-failure'").fetchone()[0]
    qualifying = sum(1 for a in apps if a["status"] in POST_SUBMIT and a["method"] in AUTO_METHODS)
    responded = ever("acknowledged", "screening", "interviewing", "offer", "rejected")
    interviews = ever("interviewing", "offer")
    offers = ever("offer")
    by_platform = {r["platform"] or "unknown": r["n"] for r in con.execute(
        "SELECT j.platform AS platform, COUNT(*) AS n FROM applications a JOIN jobs j ON j.id = a.job_id "
        "GROUP BY j.platform")}
    jobs_by_status = {s: 0 for s in JOB_STATUSES}
    for r in con.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"):
        jobs_by_status[r["status"] or "seen"] = jobs_by_status.get(r["status"] or "seen", 0) + r["n"]
    jobs_by_source = {r["source"] or "unknown": r["n"] for r in con.execute(
        "SELECT source, COUNT(*) AS n FROM jobs GROUP BY source ORDER BY n DESC")}
    return {
        "jobs": con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "applications": len(apps),
        "by_status": by_status,
        "by_method": by_method,
        "by_platform": by_platform,
        "jobs_by_status": jobs_by_status,
        "jobs_by_source": jobs_by_source,
        "submitted": len(submitted),
        "submitted_today": sub_today,
        "submitted_today_assisted": sub_today_assisted,
        "submitted_today_manual": sub_today_manual,
        "submitted_last_7_days": sum(1 for d in sub_dates if d is not None and week_start <= d <= today),
        "submitted_per_day": per_day,
        "local_date": today.isoformat(),
        "wrong_field_events": wrong_field,
        "ledger_failure_events": ledger_failures,
        "auto_eligible": qualifying >= AUTO_MIN_APPLICATIONS and wrong_field == 0 and ledger_failures == 0,
        "auto_eligible_progress": f"{qualifying} of {AUTO_MIN_APPLICATIONS} submitted ats-form applications",
        "responses": responded, "interviews": interviews, "offers": offers,
        "response_rate": rate(responded), "interview_rate": rate(interviews), "offer_rate": rate(offers),
        "daily_limit": limits.get("daily_applications"), "hard_cap": limits.get("hard_cap"),
        "daily_remaining": (max(0, min(limits["daily_applications"], limits.get("hard_cap", 25)) - sub_today)
                            if limits.get("daily_applications") is not None else None),
        "schema_version": con.execute("PRAGMA user_version").fetchone()[0],
    }


def add_event(con: sqlite3.Connection, kind: str, detail: str, application_id: str | None = None,
              job_id: str | None = None) -> dict:
    if not EVENT_KIND_RE.match(kind or ""):
        raise DBError(f"event kind {kind!r} must be lower-case words joined by hyphens, e.g. wrong-field")
    if not (detail or "").strip():
        raise DBError("--detail is empty")
    if application_id is not None:
        row = con.execute("SELECT job_id FROM applications WHERE id = ?", (application_id,)).fetchone()
        if row is None:
            raise DBError(f"no application {application_id}")
        job_id = job_id or row["job_id"]
    if job_id is not None and con.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is None:
        raise DBError(f"no job {job_id}")
    cur = con.execute("INSERT INTO events (ts, application_id, job_id, kind, detail) VALUES (?, ?, ?, ?, ?)",
                      (now_iso(), application_id, job_id, kind, detail.strip()))
    con.commit()
    return dict(con.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone())


# ------------------------------------------------------------ contacts, messages

def contact_id_for(name: str | None, org: str | None, email: str | None, linkedin_url: str | None) -> str:
    basis = (email or linkedin_url or f"{name or ''}{org or ''}").strip().lower()
    if not basis:
        raise DBError("a contact needs an email, a LinkedIn URL or a name")
    return "c-" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]


def _contact_row(con: sqlite3.Connection, contact_id: str):
    row = con.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if row is None:
        raise DBError(f"no contact {contact_id}")
    return row


def add_contact(con: sqlite3.Connection, data: dict) -> dict:
    """Add a contact, or fill in newly known fields on one already stored. Returns the row plus
    "created". Suppression is never changed here. kind: agency | in-house | hiring-manager |
    referral | other (default other). email_verified: syntax | domain | unverified."""
    _check_keys(data, CONTACT_KEYS, "contact")
    clean = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items() if v not in (None, "")}
    if "email" in clean:
        clean["email"] = clean["email"].lower()
    if "kind" in clean:
        clean["kind"] = _enum("kind", clean["kind"], CONTACT_KINDS)
    if "email_verified" in clean:
        clean["email_verified"] = _enum("email_verified", clean["email_verified"], EMAIL_VERIFIED)
    cid = contact_id_for(clean.get("name"), clean.get("org"), clean.get("email"), clean.get("linkedin_url"))
    row = con.execute("SELECT * FROM contacts WHERE id = ?", (cid,)).fetchone()
    if row is None:
        fields = {"kind": "other", "email_verified": "unverified", **clean}
        fields.update({"id": cid, "suppressed": 0, "created_at": now_iso()})
        con.execute(f"INSERT INTO contacts ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                    tuple(fields.values()))
        label = " at ".join(x for x in (clean.get("name"), clean.get("org")) if x) or clean.get("email", cid)
        log_event(con, "contact-added", f"{cid}: {label}")
        created = True
    else:
        if clean:
            con.execute(f"UPDATE contacts SET {', '.join(f'{k} = ?' for k in clean)} WHERE id = ?",
                        (*clean.values(), cid))
        created = False
    con.commit()
    out = dict(con.execute("SELECT * FROM contacts WHERE id = ?", (cid,)).fetchone())
    out["created"] = created
    return out


def list_contacts(con: sqlite3.Connection, include_suppressed: bool = False) -> list[dict]:
    q = "SELECT * FROM contacts" + ("" if include_suppressed else " WHERE COALESCE(suppressed, 0) = 0")
    return [dict(r) for r in con.execute(q + " ORDER BY org, name, id")]


def suppress_contact(con: sqlite3.Connection, contact_id: str, reason: str) -> dict:
    """Suppress a contact for good (a "no", an unsubscribe). The reason is added to the notes."""
    row = _contact_row(con, contact_id)
    reason = (reason or "").strip()
    if not reason:
        raise DBError("a reason is needed to suppress a contact")
    notes = ((row["notes"] + "\n") if row["notes"] else "") + f"suppressed {now_iso()}: {reason}"
    con.execute("UPDATE contacts SET suppressed = 1, notes = ? WHERE id = ?", (notes, contact_id))
    log_event(con, "note", f"contact {contact_id} suppressed: {reason}")
    con.commit()
    return dict(_contact_row(con, contact_id))


def _check_message_fields(fields: dict) -> None:
    if fields.get("channel") is not None:
        fields["channel"] = _enum("channel", fields["channel"], CHANNELS)
    if fields.get("sent_by") is not None:
        fields["sent_by"] = _enum("sent_by", fields["sent_by"], SENT_BY)
    if fields.get("follow_up_due") is not None:
        fields["follow_up_due"] = _date_text("follow_up_due", fields["follow_up_due"])


def add_message(con: sqlite3.Connection, data: dict) -> dict:
    """Record a drafted or sent message. channel: email | linkedin | inmail | form;
    sent_by: user | connector. A suppressed contact cannot be given a message."""
    _check_keys(data, MESSAGE_KEYS, "message")
    fields = {k: v for k, v in data.items() if v not in (None, "")}
    if "contact_id" not in fields:
        raise DBError("a message needs contact_id")
    contact = _contact_row(con, fields["contact_id"])
    if contact["suppressed"]:
        raise DBError(f"contact {contact['id']} is suppressed; do not contact them again")
    if "channel" not in fields:
        raise DBError(f"a message needs a channel ({', '.join(CHANNELS)})")
    _check_message_fields(fields)
    fields["id"] = "m-" + uuid.uuid4().hex[:10]
    con.execute(f"INSERT INTO messages ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                tuple(fields.values()))
    if fields.get("sent_at"):
        log_event(con, "message-sent", f"{fields['id']} to {contact['id']} by {fields['channel']}",
                  fields.get("application_id"), fields.get("job_id"))
    con.commit()
    return dict(con.execute("SELECT * FROM messages WHERE id = ?", (fields["id"],)).fetchone())


def update_message(con: sqlite3.Connection, message_id: str, fields: dict) -> dict:
    """Change fields on a message (sent_at, sent_by, follow_up_due, reply_at, outcome, ...).
    A null value clears the field. Setting sent_at or reply_at for the first time logs
    a message-sent or reply event."""
    _check_keys(fields, tuple(k for k in MESSAGE_KEYS if k != "contact_id"), "message")
    if not fields:
        raise DBError("nothing to update")
    row = con.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        raise DBError(f"no message {message_id}")
    fields = dict(fields)
    _check_message_fields(fields)
    con.execute(f"UPDATE messages SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                (*fields.values(), message_id))
    app, job = fields.get("application_id", row["application_id"]), fields.get("job_id", row["job_id"])
    if fields.get("sent_at") and not row["sent_at"]:
        log_event(con, "message-sent", f"{message_id} to {row['contact_id']}", app, job)
    if fields.get("reply_at") and not row["reply_at"]:
        log_event(con, "reply", f"{message_id} from {row['contact_id']}", app, job)
    con.commit()
    return dict(con.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone())


def messages_due(con: sqlite3.Connection, today: date | datetime | str) -> list[dict]:
    """Sent messages with no reply and no outcome whose follow_up_due is on or before today,
    for contacts who are not suppressed. Clear follow_up_due (or set an outcome) once handled."""
    day = today.isoformat()[:10] if isinstance(today, (date, datetime)) else str(today)[:10]
    q = ("SELECT m.*, c.name AS contact_name, c.org AS contact_org, c.email AS contact_email "
         "FROM messages m JOIN contacts c ON c.id = m.contact_id "
         "WHERE m.sent_at IS NOT NULL AND m.reply_at IS NULL AND COALESCE(m.outcome, '') = '' "
         "AND m.follow_up_due IS NOT NULL AND substr(m.follow_up_due, 1, 10) <= ? "
         "AND COALESCE(c.suppressed, 0) = 0 ORDER BY m.follow_up_due, m.id")
    return [dict(r) for r in con.execute(q, (day,))]


# -------------------------------------------------------------------- duplicates

def normalize_company(name: str) -> str:
    s = COMPANY_SUFFIX_RE.sub(" ", (name or "").casefold())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def normalize_title(title: str) -> str:
    s = (title or "").casefold()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb)
    return round(max(seq, jac), 3)


def titles_similar(a: str, b: str, threshold: float = 0.8) -> bool:
    return title_similarity(a, b) >= threshold


def known_job(con: sqlite3.Connection, url: str | None) -> dict | None:
    """The jobs row for this URL, if discovery or an earlier run already stored it (no application needed)."""
    if not url:
        return None
    row = _find_job(con, canonicalize_url(url), url)
    if row is None:
        return None
    return {"job_id": row["id"], "company": row["company"], "title": row["title"], "status": row["status"],
            "applications": con.execute("SELECT COUNT(*) FROM applications WHERE job_id = ?",
                                        (row["id"],)).fetchone()[0]}


def find_duplicates(con: sqlite3.Connection, url: str | None = None, company: str | None = None,
                    title: str | None = None, days: int = 30) -> list[dict]:
    """Existing applications only: same canonical URL, or same company + similar title within N days.

    A job that is stored but has no application is not a duplicate; see known_job().
    """
    matches: list[dict] = []
    if url:
        canon = canonicalize_url(url)
        row = _find_job(con, canon, url)
        if row is not None:
            apps = [dict(r) for r in con.execute("SELECT id, status, created_at FROM applications WHERE job_id = ?",
                                                  (row["id"],))]
            if apps:
                matches.append({"reason": "same canonical URL", "job_id": row["id"], "company": row["company"],
                                "title": row["title"], "applications": apps})
            if not company:
                company = row["company"]
            if not title:
                title = row["title"]
    if company:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        want = normalize_company(company)
        for r in con.execute("SELECT a.id, a.status, a.created_at, j.id AS job_id, j.company, j.title "
                             "FROM applications a JOIN jobs j ON j.id = a.job_id WHERE a.created_at >= ?", (since,)):
            if normalize_company(r["company"] or "") != want:
                continue
            if any(m.get("job_id") == r["job_id"] for m in matches):
                continue
            sim = title_similarity(title or "", r["title"] or "") if title else None
            if title and sim is not None and sim >= 0.8:
                matches.append({"reason": f"same company, similar title (similarity {sim}) within {days} days",
                                "application_id": r["id"], "job_id": r["job_id"], "company": r["company"],
                                "title": r["title"], "status": r["status"], "created_at": r["created_at"]})
            elif not title:
                matches.append({"reason": f"same company within {days} days", "application_id": r["id"],
                                "job_id": r["job_id"], "company": r["company"], "title": r["title"],
                                "status": r["status"], "created_at": r["created_at"]})
    return matches


# ----------------------------------------------------------------- export, output

def export(con: sqlite3.Connection, out_dir: Path) -> dict:
    """Write each table as CSV plus one JSON file. Settings rows holding keys, secrets or tokens are left out."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    dump = {}
    for table in ("jobs", "applications", "documents", "events", "settings", "runs", "contacts", "messages",
                  "questions_log"):
        rows = [dict(r) for r in con.execute(f"SELECT * FROM {table}")]
        if table == "settings":
            rows = [r for r in rows if not SECRET_SETTING_RE.search(r["key"] or "")]
        dump[table] = rows
        cols = [d[1] for d in con.execute(f"PRAGMA table_info({table})")]
        path = out_dir / f"{table}.csv"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        files[table] = str(path)
    jpath = out_dir / "jobferret-export.json"
    jpath.write_text(json.dumps(dump, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    files["json"] = str(jpath)
    return files


def _secret_name(name: str) -> bool:
    words = re.sub(r"([a-z])([A-Z])", r"\1_\2", str(name)).lower()
    return any(t in SECRET_NAME_TOKENS for t in re.split(r"[^a-z0-9]+", words))


def scrub(obj):
    """Copy of obj without secrets: settings rows whose key looks secret, and fields named like a key, secret or token."""
    if isinstance(obj, list):
        return [scrub(x) for x in obj if not (isinstance(x, dict) and set(x) >= {"key", "value"}
                                              and SECRET_SETTING_RE.search(str(x["key"])))]
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if k == "key" or not _secret_name(k)}
    return obj


def _parse_json_arg(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        die(f"--json is not valid JSON: {exc}")
    if not isinstance(data, dict):
        die("--json must be a JSON object")
    return data


def _json_flag(parser) -> None:
    parser.add_argument("--json", dest="json_sub", action="store_true", default=argparse.SUPPRESS,
                        help="print JSON")


def _job_line(j: dict) -> str:
    fit = "  -" if j["fit_pre"] is None else f"{j['fit_pre']:>3.0f}"
    where = f" ({j['location']})" if j.get("location") else ""
    return f"{j['id']}  {fit}  {j['status'] or '':<11} {j['company'] or ''} / {j['title'] or ''}{where}"


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="db.py")
    p.add_argument("--db", help="database path (default <user dir>/jobferret.db)")
    p.add_argument("--json", dest="json_out", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=type(p))
    sub.add_parser("init", help="create the database (schema version 2)")
    s = sub.add_parser("migrate", help="bring an older database up to schema version 2 and say what changed")
    _json_flag(s)
    s = sub.add_parser("add-job", help="add or refresh a job")
    s.add_argument("--json", dest="data", required=True, help="job fields as a JSON object")
    s = sub.add_parser("set-job-status", help="change a job's status (shortlisted, dismissed, ...)")
    s.add_argument("job_id")
    s.add_argument("status", help="one of: " + ", ".join(JOB_STATUSES))
    s.add_argument("--reason", help="why, in a few words")
    _json_flag(s)
    s = sub.add_parser("set-screening", help="write a job's pre-screen score and result")
    s.add_argument("job_id")
    s.add_argument("--fit", type=float, help="fit_pre, 0 to 100")
    s.add_argument("--screen", help="screen result as a JSON object")
    s.add_argument("--status", help="screened or excluded (ignored once the job is shortlisted or dismissed)")
    s = sub.add_parser("jobs", help="list jobs, newest first")
    s.add_argument("--status", help="one of: " + ", ".join(JOB_STATUSES))
    s.add_argument("--since", type=int, metavar="N", help="first seen in the last N days")
    s.add_argument("--min-fit", type=float, metavar="N", help="fit_pre of at least N")
    s.add_argument("--run", help="first found by this run id")
    _json_flag(s)
    s = sub.add_parser("runs", help="discovery runs: list (default) or show one")
    _json_flag(s)
    rsub = s.add_subparsers(dest="runs_cmd", required=False, parser_class=type(p))
    r = rsub.add_parser("list", help="list runs, newest first")
    _json_flag(r)
    r = rsub.add_parser("show", help="show one run")
    r.add_argument("run_id")
    _json_flag(r)
    s = sub.add_parser("add-application", help="record an application")
    s.add_argument("--json", dest="data", required=True, help="application fields as a JSON object")
    s.add_argument("--update", action="store_true", help="merge fields into an existing application")
    s = sub.add_parser("set-status", help="change an application's status")
    s.add_argument("app_id")
    s.add_argument("status", choices=APP_STATUSES)
    s.add_argument("--note")
    s = sub.add_parser("list", help="list applications (or jobs)")
    s.add_argument("--status")
    s.add_argument("--jobs", action="store_true", help="list jobs instead of applications")
    s = sub.add_parser("show", help="show one application or job")
    s.add_argument("id")
    s = sub.add_parser("stats", help="counts, rates and whether auto mode is open")
    _json_flag(s)
    s = sub.add_parser("events", help="record an event (e.g. wrong-field)")
    evsub = s.add_subparsers(dest="events_cmd", required=True, parser_class=type(p))
    e = evsub.add_parser("add", help="add an event")
    e.add_argument("--kind", required=True, help="e.g. wrong-field, ledger-failure, captcha, note")
    e.add_argument("--application", help="application id")
    e.add_argument("--job", help="job id")
    e.add_argument("--detail", required=True, help="what happened")
    s = sub.add_parser("export", help="CSV + JSON export")
    s.add_argument("--out", help="directory (default <user dir>/exports/<timestamp>)")
    s = sub.add_parser("dedup", help="check for a duplicate application")
    s.add_argument("--url")
    s.add_argument("--company")
    s.add_argument("--title")
    s.add_argument("--days", type=int)
    a = p.parse_args(argv)
    as_json = a.json_out or getattr(a, "json_sub", False)

    db_path = Path(a.db).expanduser() if a.db else default_db_path()
    try:
        config = load_config()
    except ConfigError as exc:
        sys.stderr.write(f"warning: {exc}; using default limits\n")
        config = {"limits": {"daily_applications": 15, "hard_cap": 25, "per_employer_days": 30}}
    out: object
    code = EXIT_OK
    con = None
    try:
        read_only = a.cmd in ("list", "show", "stats", "export", "dedup", "events", "jobs", "runs")
        con = connect(db_path, create=not read_only)
        if a.cmd == "init":
            out = {"ok": True, "db": str(db_path), "schema_version": SCHEMA_VERSION}
            msg = f"database ready at {db_path}"
        elif a.cmd == "migrate":
            actions = list(getattr(con, "migrated", ()))
            out = {"ok": True, "db": str(db_path), "from_version": getattr(con, "migrated_from", None),
                   "to_version": SCHEMA_VERSION, "actions": actions}
            msg = ("\n".join(actions) if actions else f"already at schema version {SCHEMA_VERSION}; nothing to do")
        elif a.cmd == "add-job":
            out = add_job(con, _parse_json_arg(a.data))
            msg = out["id"]
            sys.stderr.write(f"job {out['id']} {'added' if out['created'] else 'updated'}: "
                             f"{out.get('company')} / {out.get('title')}\n")
        elif a.cmd == "set-job-status":
            out = set_job_status(con, a.job_id, a.status, a.reason)
            msg = f"job {out['id']} is now {out['status']}"
        elif a.cmd == "set-screening":
            screen = None
            if a.screen is not None:
                screen = _parse_json_arg(a.screen)
            if a.fit is None and screen is None and a.status is None:
                p.error("set-screening needs --fit, --screen or --status")
            out = set_screening(con, a.job_id, a.fit, screen, a.status)
            msg = f"job {out['id']}: fit {out['fit_pre']}, status {out['status']}"
        elif a.cmd == "jobs":
            out = list_jobs(con, a.status, a.since, a.min_fit, a.run)
            msg = "\n".join(_job_line(j) for j in out) or "(no jobs match)"
        elif a.cmd == "runs":
            if getattr(a, "runs_cmd", None) == "show":
                out = get_run(con, a.run_id)
                msg = json.dumps(out, indent=2, ensure_ascii=False)
            else:
                out = list_runs(con)
                msg = "\n".join(f"{r['id']}  found {r['found'] if r['found'] is not None else '-'}  "
                                f"new {r['new'] if r['new'] is not None else '-'}  "
                                f"{'finished' if r['finished_at'] else 'not finished'}"
                                f"{'  errors: ' + json.dumps(r['errors']) if r['errors'] else ''}"
                                for r in out) or "(no runs yet)"
        elif a.cmd == "add-application":
            out = add_application(con, _parse_json_arg(a.data), a.update)
            msg = out["id"]
            sys.stderr.write(f"application {out['id']} ({out['status']})\n")
        elif a.cmd == "set-status":
            out = set_status(con, a.app_id, a.status, a.note)
            msg = f"application {out['id']} is now {out['status']}"
        elif a.cmd == "list":
            out = list_rows(con, a.status, a.jobs)
            msg = "\n".join(
                (f"{r['id']}  {r.get('status') or '':<10} {r.get('company') or ''} / {r.get('title') or ''}")
                for r in out) or "(nothing yet)"
        elif a.cmd == "show":
            out = show(con, a.id)
            msg = json.dumps(out, indent=2, ensure_ascii=False)
        elif a.cmd == "stats":
            out = stats(con, config)
            msg = "\n".join(f"{k}: {v}" for k, v in out.items())
        elif a.cmd == "export":
            target = Path(a.out) if a.out else user_dir() / "exports" / datetime.now().strftime("%Y%m%d-%H%M%S")
            out = export(con, target)
            msg = f"exported to {target}"
        elif a.cmd == "events":
            out = add_event(con, a.kind, a.detail, a.application, a.job)
            msg = str(out["id"])
        else:  # dedup
            if not (a.url or a.company):
                p.error("dedup needs --url and/or --company")
            days = a.days if a.days is not None else int(config.get("limits", {}).get("per_employer_days", 30))
            matches = find_duplicates(con, a.url, a.company, a.title, days)
            known = known_job(con, a.url)
            out = {"ok": True, "duplicate": bool(matches), "known_job": known, "matches": matches, "days": days}
            code = EXIT_FAIL if matches else EXIT_OK
            if matches:
                msg = "possible duplicate:\n" + "\n".join(f"  {m['reason']}: {m.get('company')} / {m.get('title')}"
                                                          for m in matches)
            elif known:
                msg = (f"no duplicate application; job already stored ({known['job_id']}: "
                       f"{known['company']} / {known['title']}, status {known['status']})")
            else:
                msg = "no duplicate found"
    except DBError as exc:
        if as_json:
            emit_json({"ok": False, "error": str(exc)})
        else:
            sys.stderr.write(f"error: {exc}\n")
        return EXIT_FAIL
    except sqlite3.Error as exc:
        sys.stderr.write(f"error: database problem: {exc}\n")
        return EXIT_FAIL
    finally:
        if con is not None:
            con.close()
    if as_json:
        emit_json(scrub(out))
    else:
        print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
