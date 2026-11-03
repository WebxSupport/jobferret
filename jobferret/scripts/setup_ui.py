"""The local preferences page: one form instead of a long chat interview.

Purpose
    Serves a single page on 127.0.0.1 where the user sets target roles,
    location, pay, dealbreakers, eligibility, availability, job sources and how
    chatty JobFerret should be. It is prefilled from profile.json (the draft
    profile_prefill.py wrote, or the user's existing one) and config.toml. On
    save it validates the form, merges it into profile.json without touching
    fields the page doesn't own, writes the config.toml keys, and exits.
    The page is an alternative to the four chat questions in the start mode,
    never a requirement.

Usage
    setup_ui.py [--port 0] [--timeout 1200] [--dump]
    setup_ui.py --prefill-only
    setup_ui.py --from-json <file | ->

    Prints exactly one line when ready:
        URL: http://127.0.0.1:PORT/?t=TOKEN
    (random free port unless --port is given; TOKEN is 32 hex characters),
    then waits. After a save it prints "SAVED profile=<path> config=<path>" and,
    with --dump, the saved form as JSON (API keys redacted). On timeout it
    prints "TIMEOUT nothing saved".

    --prefill-only prints the values the page would show, as JSON, and exits
    without serving. --from-json applies a partial form (same sections and
    validation as the page) without serving: the start mode uses it to save
    the answers to the four chat questions, so both routes write the same way.

    Files: $JOBFERRET_HOME (default ~/.jobferret)/profile.json and config.toml.
    Security: binds 127.0.0.1 only; every request needs the token (403
    otherwise); the Host header must be 127.0.0.1:PORT or localhost:PORT; POST
    must be application/json under 64 KB from the same origin; nothing but the
    one page is served; every echoed value is HTML-escaped.

Exit codes
    0  saved (or --prefill-only printed)
    1  --from-json: the form failed validation (errors printed)
    2  timed out with nothing saved
    4  usage or input error (bad arguments, unreadable profile.json or config.toml)
"""
from __future__ import annotations

import datetime as _dt
import hmac
import html
import json
import re
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from jf_common import (
    EXIT_FAIL, EXIT_OK, EXIT_USAGE, ConfigError, die, emit_json, get_path, load_config, load_profile,
    make_parser, save_profile, set_path, setup_io, update_config, user_dir,
)

EXIT_TIMEOUT = 2
MAX_BODY = 64 * 1024

# ------------------------------------------------------------------ choices

SENIORITY = [("", "Not set"), ("entry", "Entry or graduate"), ("mid", "Mid-level"), ("senior", "Senior"),
             ("lead", "Lead or principal"), ("manager", "Manager"), ("head", "Head of or director"),
             ("executive", "Executive")]
ROLE_FAMILIES = ["Finance and accounting", "Data and analytics", "Software engineering", "IT and infrastructure",
                 "Product", "Design", "Marketing", "Sales", "Customer service", "Operations",
                 "HR and people", "Legal", "Engineering (non-software)", "Healthcare", "Education",
                 "Public sector and policy", "Logistics and supply chain", "Admin and office",
                 "Hospitality and retail", "Construction and trades"]
WORK_MODES = [("remote", "Remote"), ("hybrid", "Hybrid"), ("office", "Office")]
RELOCATE = [("no", "No"), ("maybe", "Maybe"), ("yes", "Yes")]
PERIODS = [("year", "per year"), ("day", "per day")]
CONTRACT_TYPES = [("permanent", "Permanent"), ("contract", "Contract"), ("fixed-term", "Fixed-term (FTC)"),
                  ("temporary", "Temporary"), ("part-time", "Part-time")]
IR35 = [("", "Not set"), ("outside", "Outside only"), ("inside", "Inside is fine"), ("either", "Either")]
COMPANY_SIZE = [(0, "Any size"), (10, "10+ staff"), (50, "50+"), (250, "250+"), (1000, "1,000+")]
RIGHT_TO_WORK = [("", "Not set"), ("citizen", "British or Irish citizen"),
                 ("settled", "Settled status or indefinite leave"), ("visa", "A visa with the right to work"),
                 ("none", "No right to work in the UK yet")]
DBS = [("none", "None"), ("basic", "Basic"), ("standard", "Standard"), ("enhanced", "Enhanced"),
       ("enhanced-barred", "Enhanced with barred list")]
CLEARANCE = [("none", "None"), ("bpss", "BPSS"), ("ctc", "CTC"), ("sc", "SC"), ("esc", "eSC"), ("dv", "DV")]
LICENCE = [("", "Not set"), ("full", "Full UK licence"), ("provisional", "Provisional"), ("none", "No licence")]
NOTICE = ["", "immediate", "1 week", "2 weeks", "1 month", "2 months", "3 months", "6 months"]
CHATTINESS = [("brief", "Brief"), ("normal", "Normal")]
COVER = [("ask", "Ask me each time"), ("always", "Always"), ("required", "Only when the employer asks"),
         ("never", "Never")]
AI_STANCE = [("drafting", "JobFerret drafts from my facts; I edit and say so if asked"),
             ("light", "I write; JobFerret checks spelling and tightens wording"),
             ("coach", "I write every word; JobFerret coaches and points at problems")]
# ARCHITECTURE section 12, [sources] enabled.
DEFAULT_SOURCES = [
    ("adzuna", "Adzuna", "Free API key below. Wide UK coverage."),
    ("reed", "Reed", "Free API key below. Can tell agency postings from direct employers."),
    ("nhs", "NHS Jobs", "No key needed. Health and care roles."),
    ("teaching", "Teaching Vacancies (DfE)", "No key needed. Schools and trusts in England."),
    ("boards", "Employer job boards", "Greenhouse, Lever, Ashby, Workable and similar boards of the employers you list."),
    ("rss", "RSS feeds", "Any job feed URL, for example a Jobserve search."),
    ("indeed", "Indeed (in your browser)", "During a hunt JobFerret opens a few Indeed UK searches in the browser you "
                                            "use with it and reads the results, at a human pace (default 4 searches, "
                                            "20 pages a day). Never fetched by script."),
    ("alerts", "Job alert emails", "LinkedIn, Totaljobs, GOV.UK Find a job, Civil Service Jobs and others, "
                                   "through alert emails you save. JobFerret never fetches those sites itself."),
]
DEFAULT_ENABLED = [s[0] for s in DEFAULT_SOURCES]
SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
KEY_RE = re.compile(r"^[A-Za-z0-9_.-]{0,128}$")


def source_options(config: dict) -> list[tuple[str, str, str]]:
    """Default UK list plus any other source named in config.toml [sources]."""
    opts = list(DEFAULT_SOURCES)
    known = {s[0] for s in opts}
    src = config.get("sources") or {}
    extra = list(src.get("enabled") or []) + [k for k, v in src.items() if isinstance(v, dict)]
    for sid in extra:
        if isinstance(sid, str) and SOURCE_ID_RE.match(sid) and sid not in known:
            opts.append((sid, sid, "From your config.toml."))
            known.add(sid)
    return opts


# ------------------------------------------------------------------ prefill

def employer_label(e) -> str:
    if isinstance(e, dict):
        name = e.get("name") or e.get("token") or ""
        return f"{name} ({e['platform']})" if e.get("platform") else name
    return str(e)


def form_state(profile: dict, config: dict) -> dict:
    """The values the page shows: saved answers first, then sensible defaults."""
    g = lambda path, default=None: get_path(profile, path, default)  # noqa: E731
    src = config.get("sources") or {}
    floor = g("targets.salary_floor", {}) or {}
    locs = g("targets.locations", []) or []
    return {
        "from_cv": {"name": g("personal.name", ""), "title": g("current.title", ""),
                    "employer": g("current.employer", ""), "location": g("personal.location", ""),
                    "qualification": g("history.highest_qualification", ""),
                    "skills": len(g("history.skills", []) or [])},
        "targets": {"titles": list(g("targets.titles", []) or []), "seniority": g("targets.seniority", ""),
                    "role_families": list(g("targets.role_families", []) or [])},
        "where": {"town": locs[0] if locs else g("personal.location", ""),
                  "radius_miles": g("targets.radius_miles", 0) or 20,
                  "work_modes": list(g("targets.work_modes", []) or []) or ["remote", "hybrid"],
                  "relocate": g("answer_bank.relocate", "") or "no"},
        "pay": {"amount": floor.get("amount") or "", "period": floor.get("period") or "year",
                "contract_types": list(g("targets.contract_types", []) or []) or ["permanent"],
                "ir35": g("targets.ir35", "")},
        "filters": {"dealbreakers": list(g("exclusions.dealbreakers", []) or []),
                    "companies": list(g("exclusions.companies", []) or []),
                    "no_agencies": bool(g("exclusions.filters.no_agencies", False)),
                    "no_unpaid": bool(g("exclusions.filters.no_unpaid", True)),
                    "no_commission_only": bool(g("exclusions.filters.no_commission_only", True)),
                    "min_company_size": int(g("exclusions.filters.min_company_size", 0) or 0)},
        "eligibility": {"right_to_work": g("eligibility.right_to_work", ""),
                        "sponsorship_needed": bool(g("eligibility.sponsorship_needed_ever", False)),
                        "dbs": g("eligibility.dbs", "") or "none",
                        "clearance": g("eligibility.security_clearance", "") or "none",
                        "driving_licence": g("eligibility.driving_licence", "")},
        "availability": {"notice_period": g("eligibility.notice_period", ""),
                         "earliest_start": g("eligibility.earliest_start", "")},
        "channels": {"sources": list(src.get("enabled") or DEFAULT_ENABLED),
                     "employers": [employer_label(e) for e in (get_path(src, "boards.employers", []) or [])],
                     "feeds": list(get_path(src, "rss.feeds", []) or []),
                     "adzuna_saved": bool(get_path(src, "adzuna.app_id") and get_path(src, "adzuna.app_key")),
                     "reed_saved": bool(get_path(src, "reed.api_key")),
                     "daily_applications": int(get_path(config, "limits.daily_applications", 15) or 15)},
        "communication": {"chattiness": get_path(config, "ux.chattiness", "normal") or "normal",
                          "cover_letter": g("preferences.cover_letter", "ask") or "ask",
                          "ai_disclosure": g("preferences.ai_disclosure", "drafting") or "drafting"},
    }


# --------------------------------------------------------------- validation

CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


class Invalid(Exception):
    pass


def _str(v, field, max_len=120):
    if not isinstance(v, str):
        raise Invalid(f"{field}: expected text")
    v = CTRL_RE.sub(" ", v).strip()
    if len(v) > max_len:
        raise Invalid(f"{field}: at most {max_len} characters")
    return v


def _enum(v, field, allowed):
    allowed_values = [a[0] if isinstance(a, tuple) else a for a in allowed]
    if v not in allowed_values:
        raise Invalid(f"{field}: must be one of {', '.join(map(str, allowed_values)) or '(none)'}")
    return v


def _list(v, field, max_items=20, max_len=120, allowed=None):
    if not isinstance(v, list):
        raise Invalid(f"{field}: expected a list")
    if len(v) > max_items:
        raise Invalid(f"{field}: at most {max_items} items")
    out, seen = [], set()
    for item in v:
        s = _str(item, field, max_len)
        if allowed is not None:
            _enum(s, field, allowed)
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def _int(v, field, lo, hi):
    if isinstance(v, bool):
        raise Invalid(f"{field}: expected a number")
    if isinstance(v, str):
        v = v.replace(",", "").replace("£", "").strip()
        if v == "":
            return 0
        if not re.fullmatch(r"\d+(\.\d+)?", v):
            raise Invalid(f"{field}: expected a whole number")
        v = float(v)
    if not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise Invalid(f"{field}: must be between {lo:,} and {hi:,}")
    return int(v)


def _bool(v, field):
    if not isinstance(v, bool):
        raise Invalid(f"{field}: expected true or false")
    return v


def _date(v, field):
    v = _str(v, field, 10)
    if v:
        try:
            _dt.date.fromisoformat(v)
        except ValueError:
            raise Invalid(f"{field}: use YYYY-MM-DD") from None
    return v


def _url(v, field):
    v = _str(v, field, 300)
    if v and not re.match(r"^https?://[^\s<>\"']+$", v):
        raise Invalid(f"{field}: {v!r} is not an http(s) link")
    return v


def build_rules(sources: list[str]):
    return {
        "targets": {"titles": lambda v, f: _list(v, f, 10, 80), "seniority": lambda v, f: _enum(v, f, SENIORITY),
                    "role_families": lambda v, f: _list(v, f, 20, 60, ROLE_FAMILIES)},
        "where": {"town": lambda v, f: _str(v, f, 80), "radius_miles": lambda v, f: _int(v, f, 0, 500),
                  "work_modes": lambda v, f: _list(v, f, 3, 10, WORK_MODES),
                  "relocate": lambda v, f: _enum(v, f, RELOCATE)},
        "pay": {"amount": lambda v, f: _int(v, f, 0, 1_000_000), "period": lambda v, f: _enum(v, f, PERIODS),
                "contract_types": lambda v, f: _list(v, f, 5, 20, CONTRACT_TYPES),
                "ir35": lambda v, f: _enum(v, f, IR35)},
        "filters": {"dealbreakers": lambda v, f: _list(v, f, 30, 120),
                    "companies": lambda v, f: _list(v, f, 50, 120),
                    "no_agencies": _bool, "no_unpaid": _bool, "no_commission_only": _bool,
                    "min_company_size": lambda v, f: _enum(_int(v, f, 0, 1000), f, COMPANY_SIZE)},
        "eligibility": {"right_to_work": lambda v, f: _enum(v, f, RIGHT_TO_WORK), "sponsorship_needed": _bool,
                        "dbs": lambda v, f: _enum(v, f, DBS), "clearance": lambda v, f: _enum(v, f, CLEARANCE),
                        "driving_licence": lambda v, f: _enum(v, f, LICENCE)},
        "availability": {"notice_period": lambda v, f: _enum(v, f, NOTICE), "earliest_start": _date},
        "channels": {"sources": lambda v, f: _list(v, f, 30, 32, sources),
                     "employers": lambda v, f: _list(v, f, 40, 200),
                     "feeds": lambda v, f: [_url(x, f) for x in _list(v, f, 20, 300)],
                     "adzuna_app_id": lambda v, f: _key(v, f), "adzuna_app_key": lambda v, f: _key(v, f),
                     "reed_api_key": lambda v, f: _key(v, f),
                     "daily_applications": lambda v, f: _int(v, f, 1, 25)},
        "communication": {"chattiness": lambda v, f: _enum(v, f, CHATTINESS),
                          "cover_letter": lambda v, f: _enum(v, f, COVER),
                          "ai_disclosure": lambda v, f: _enum(v, f, AI_STANCE)},
    }


def _key(v, field):
    v = _str(v, field, 128)
    if not KEY_RE.match(v):
        raise Invalid(f"{field}: letters, digits and . - _ only")
    return v


def validate(payload, sources: list[str]) -> tuple[dict, list[str]]:
    """Check a full or partial form. Returns (clean, errors). Unknown sections or fields are errors."""
    if not isinstance(payload, dict):
        return {}, ["the form must be a JSON object"]
    rules = build_rules(sources)
    clean: dict = {}
    errors: list[str] = []
    for section, fields in payload.items():
        if section not in rules:
            errors.append(f"unknown section: {str(section)[:40]}")
            continue
        if not isinstance(fields, dict):
            errors.append(f"{section}: expected an object")
            continue
        for name, value in fields.items():
            rule = rules[section].get(name)
            if rule is None:
                errors.append(f"unknown field: {section}.{str(name)[:40]}")
                continue
            try:
                clean.setdefault(section, {})[name] = rule(value, f"{section}.{name}")
            except Invalid as exc:
                errors.append(str(exc))
    pay = clean.get("pay", {})
    if pay.get("period") == "day" and pay.get("amount", 0) > 5000:
        errors.append("pay.amount: a day rate above £5,000 looks like an annual figure; check the toggle")
    return clean, errors


# ------------------------------------------------------------------ saving

PAGE_PATHS = {  # (section, field) -> profile path the page owns
    ("targets", "titles"): "targets.titles", ("targets", "seniority"): "targets.seniority",
    ("targets", "role_families"): "targets.role_families",
    ("where", "radius_miles"): "targets.radius_miles", ("where", "work_modes"): "targets.work_modes",
    ("where", "relocate"): "answer_bank.relocate",
    ("pay", "contract_types"): "targets.contract_types", ("pay", "ir35"): "targets.ir35",
    ("filters", "dealbreakers"): "exclusions.dealbreakers", ("filters", "companies"): "exclusions.companies",
    ("filters", "no_agencies"): "exclusions.filters.no_agencies",
    ("filters", "no_unpaid"): "exclusions.filters.no_unpaid",
    ("filters", "no_commission_only"): "exclusions.filters.no_commission_only",
    ("filters", "min_company_size"): "exclusions.filters.min_company_size",
    ("eligibility", "right_to_work"): "eligibility.right_to_work",
    ("eligibility", "sponsorship_needed"): "eligibility.sponsorship_needed_ever",
    ("eligibility", "dbs"): "eligibility.dbs", ("eligibility", "clearance"): "eligibility.security_clearance",
    ("eligibility", "driving_licence"): "eligibility.driving_licence",
    ("availability", "notice_period"): "eligibility.notice_period",
    ("availability", "earliest_start"): "eligibility.earliest_start",
    ("communication", "cover_letter"): "preferences.cover_letter",
    ("communication", "ai_disclosure"): "preferences.ai_disclosure",
}


def parse_employer(text: str, existing: list) -> dict:
    for e in existing:
        if isinstance(e, dict) and employer_label(e) == text:
            return e
    if re.match(r"^https?://", text):
        try:
            from sources.boards import parse_board_url   # the same parser `discover.py boards add` uses
            parsed = parse_board_url(text)
        except Exception:  # an odd URL should not lose the user's form
            parsed = None
        if parsed and parsed.get("token"):
            return {"name": parsed["token"], "platform": parsed["platform"], "token": parsed["token"]}
    return {"name": text, "platform": "", "token": ""}


def apply_form(clean: dict, profile: dict, config: dict) -> tuple[dict, dict, list[str]]:
    """Merge a validated form into the profile and build the config.toml updates."""
    changed: list[str] = []
    prefill = get_path(profile, "meta.prefill", {}) or {}
    for (section, name), path in PAGE_PATHS.items():
        if name in clean.get(section, {}):
            set_path(profile, path, clean[section][name])
            prefill.pop(path, None)
            changed.append(path)
    where = clean.get("where", {})
    if "town" in where:
        set_path(profile, "targets.locations", [where["town"]] if where["town"] else [])
        prefill.pop("targets.locations", None)
        changed.append("targets.locations")
        if where["town"] and not get_path(profile, "personal.location"):
            set_path(profile, "personal.location", where["town"])
    if "work_modes" in where:
        set_path(profile, "targets.remote", ", ".join(where["work_modes"]) or "any")
    pay = clean.get("pay", {})
    if "amount" in pay or "period" in pay:
        floor = dict(get_path(profile, "targets.salary_floor", {}) or {})
        floor.update({"currency": "GBP"})
        if "amount" in pay:
            floor["amount"] = pay["amount"]
        if "period" in pay:
            floor["period"] = pay["period"]
        set_path(profile, "targets.salary_floor", floor)
        changed.append("targets.salary_floor")
    set_path(profile, "meta.prefill", prefill)
    set_path(profile, "meta.status", "confirmed")

    cfg: dict = {}
    ch = clean.get("channels", {})
    if "sources" in ch:
        set_path(cfg, "sources.enabled", ch["sources"])
    if "employers" in ch:
        existing = get_path(config, "sources.boards.employers", []) or []
        set_path(cfg, "sources.boards.employers", [parse_employer(t, existing) for t in ch["employers"]])
    if "feeds" in ch:
        set_path(cfg, "sources.rss.feeds", [f for f in ch["feeds"] if f])
    for field, path in (("adzuna_app_id", "sources.adzuna.app_id"), ("adzuna_app_key", "sources.adzuna.app_key"),
                        ("reed_api_key", "sources.reed.api_key")):
        if ch.get(field):  # blank keeps the saved key
            set_path(cfg, path, ch[field])
    if "daily_applications" in ch:
        set_path(cfg, "limits.daily_applications", ch["daily_applications"])
    if "chattiness" in clean.get("communication", {}):
        set_path(cfg, "ux.chattiness", clean["communication"]["chattiness"])
    return profile, cfg, changed


def redacted(clean: dict) -> dict:
    out = json.loads(json.dumps(clean))
    for k in ("adzuna_app_id", "adzuna_app_key", "reed_api_key"):
        if k in out.get("channels", {}):
            out["channels"][k] = "(set)" if out["channels"][k] else ""
    return out


def save_all(clean: dict, require_titles: bool = True) -> tuple[Path, Path, list[str]]:
    profile = load_profile()
    config = load_config()
    profile, cfg_updates, changed = apply_form(clean, profile, config)
    if require_titles and not get_path(profile, "targets.titles"):
        raise Invalid("targets.titles: add at least one job title to search for")
    cfg_path = update_config(cfg_updates) if cfg_updates else user_dir() / "config.toml"
    return save_profile(profile), cfg_path, changed


# ---------------------------------------------------------------------- page

def esc(v) -> str:
    return html.escape(str(v), quote=True)


def options_html(opts, selected) -> str:
    out = []
    for o in opts:
        value, label = (o if isinstance(o, tuple) else (o, o or "Not set"))
        sel = " selected" if str(value) == str(selected) else ""
        out.append(f'<option value="{esc(value)}"{sel}>{esc(label)}</option>')
    return "".join(out)


def select(name, label, opts, selected, hint="") -> str:
    values = [str(o[0] if isinstance(o, tuple) else o) for o in opts]
    if selected not in ("", None) and str(selected) not in values:
        opts = list(opts) + [(selected, f"{selected} (saved)")]
    h = f'<small>{esc(hint)}</small>' if hint else ""
    return (f'<label class="field"><span>{esc(label)}</span><select name="{esc(name)}">'
            f'{options_html(opts, selected)}</select>{h}</label>')


def pills(name, opts, selected, kind="checkbox") -> str:
    out = []
    for o in opts:
        value, label = (o if isinstance(o, tuple) else (o, o))
        on = value in selected if kind == "checkbox" else str(value) == str(selected)
        out.append(f'<label class="pill"><input type="{kind}" name="{esc(name)}" value="{esc(value)}"'
                   f'{" checked" if on else ""}><span>{esc(label)}</span></label>')
    return f'<div class="pills">{"".join(out)}</div>'


def chips(name, label, values, placeholder, hint="") -> str:
    items = "".join(f'<span class="chip"><span class="chip-text">{esc(v)}</span>'
                    f'<button type="button" class="chip-x" aria-label="Remove {esc(v)}">&times;</button></span>'
                    for v in values)
    h = f'<small>{esc(hint)}</small>' if hint else ""
    return (f'<div class="field"><span>{esc(label)}</span><div class="chips" data-chips="{esc(name)}">{items}</div>'
            f'<div class="chip-add"><input type="text" placeholder="{esc(placeholder)}" data-chip-input="{esc(name)}">'
            f'<button type="button" data-chip-btn="{esc(name)}">Add</button></div>{h}</div>')


def toggle(name, label, on, hint="") -> str:
    h = f'<small>{esc(hint)}</small>' if hint else ""
    return (f'<label class="toggle"><input type="checkbox" name="{esc(name)}"{" checked" if on else ""}>'
            f'<span>{esc(label)}{h}</span></label>')


def text(name, label, value, kind="text", attrs="", hint="") -> str:
    h = f'<small>{esc(hint)}</small>' if hint else ""
    return (f'<label class="field"><span>{esc(label)}</span><input type="{kind}" name="{esc(name)}" '
            f'value="{esc(value)}" {attrs}>{h}</label>')


def section(num, title, body, note="") -> str:
    n = f'<p class="note">{esc(note)}</p>' if note else ""
    return f'<fieldset><legend><b>{num}</b> {esc(title)}</legend>{n}{body}</fieldset>'


def render_page(state: dict, sources: list[tuple[str, str, str]], nonce: str) -> str:
    cv = state["from_cv"]
    bits = [b for b in (cv["name"], " at ".join(x for x in (cv["title"], cv["employer"]) if x), cv["location"],
                        cv["qualification"], f'{cv["skills"]} skills' if cv["skills"] else "") if b]
    from_cv = (f'<div class="cv"><b>From your CV:</b> {esc(" · ".join(bits))}. Wrong? Say so in the chat after '
               f'saving.</div>' if bits else
               '<div class="cv">No CV read yet. Fill in what you can; JobFerret will add the rest from your CV.</div>')
    t, w, p, f = state["targets"], state["where"], state["pay"], state["filters"]
    e, a, ch, c = state["eligibility"], state["availability"], state["channels"], state["communication"]
    src_html = "".join(
        f'<label class="src"><input type="checkbox" name="sources" value="{esc(sid)}"'
        f'{" checked" if sid in ch["sources"] else ""}><span><b>{esc(lbl)}</b><small>{esc(note)}</small></span></label>'
        for sid, lbl, note in sources)
    adz_ph = "Saved. Leave blank to keep." if ch["adzuna_saved"] else ""
    reed_ph = "Saved. Leave blank to keep." if ch["reed_saved"] else ""
    body = "".join([
        section(1, "Target roles", chips("titles", "Job titles to search for", t["titles"], "Add a title, e.g. Finance Business Partner",
                                         "Two to five titles works best, including the ones recruiters use. Required.")
                + select("seniority", "Seniority", SENIORITY, t["seniority"])
                + '<div class="field"><span>Role families</span>' + pills("role_families", ROLE_FAMILIES, t["role_families"])
                + "</div>"),
        section(2, "Where", '<div class="row">' + text("town", "Town or city", w["town"], attrs='maxlength="80"')
                + text("radius_miles", "Radius (miles)", w["radius_miles"], "number", 'min="0" max="500"') + "</div>"
                + '<div class="field"><span>Working pattern</span>' + pills("work_modes", WORK_MODES, w["work_modes"]) + "</div>"
                + '<div class="field"><span>Willing to relocate?</span>' + pills("relocate", RELOCATE, w["relocate"], "radio")
                + "</div>"),
        section(3, "Pay", '<div class="row">' + text("amount", "Lowest pay you would accept (£)", p["amount"], "number",
                                                     'min="0" step="any" placeholder="e.g. 45000"',
                                                     "Never shown on your CV or to employers.")
                + '<div class="field"><span>Per</span>' + pills("period", PERIODS, p["period"], "radio") + "</div></div>"
                + '<div class="field"><span>Contract types</span>' + pills("contract_types", CONTRACT_TYPES, p["contract_types"])
                + "</div>" + select("ir35", "IR35 (contracts only)", IR35, p["ir35"])),
        section(4, "Must-haves and dealbreakers",
                chips("dealbreakers", "Never show me jobs that mention", f["dealbreakers"], "e.g. night shifts, 50% travel")
                + chips("companies", "Companies to skip", f["companies"], "e.g. a current or former employer")
                + toggle("no_agencies", "Skip recruitment agency postings", f["no_agencies"])
                + toggle("no_unpaid", "Skip unpaid roles", f["no_unpaid"])
                + toggle("no_commission_only", "Skip commission-only roles", f["no_commission_only"])
                + select("min_company_size", "Smallest company size", COMPANY_SIZE, f["min_company_size"])),
        section(5, "Eligibility", select("right_to_work", "Right to work in the UK", RIGHT_TO_WORK, e["right_to_work"])
                + toggle("sponsorship_needed", "I need, or will need, visa sponsorship", e["sponsorship_needed"],
                         "Forms ask whether you will now or in future need it. Tick if it could ever apply.")
                + '<div class="row">' + select("dbs", "DBS check held", DBS, e["dbs"])
                + select("clearance", "Security clearance", CLEARANCE, e["clearance"]) + "</div>"
                + select("driving_licence", "Driving licence", LICENCE, e["driving_licence"]),
                "Used to answer screening questions exactly. Equality and diversity questions are never asked here; "
                "those are always yours to fill on each form."),
        section(6, "Availability", '<div class="row">' + select("notice_period", "Notice period", NOTICE, a["notice_period"])
                + text("earliest_start", "Earliest start", a["earliest_start"], "date") + "</div>"),
        section(7, "Where to look", f'<div class="srcs">{src_html}</div>'
                + chips("employers", "Employers whose job boards to check", ch["employers"],
                        "Company name or careers-page link")
                + chips("feeds", "RSS feed links", ch["feeds"], "https://...")
                + '<div class="row">' + text("adzuna_app_id", "Adzuna app ID", "", attrs=f'autocomplete="off" placeholder="{esc(adz_ph)}"')
                + text("adzuna_app_key", "Adzuna app key", "", "password", f'autocomplete="off" placeholder="{esc(adz_ph)}"') + "</div>"
                + '<p class="note"><a href="https://developer.adzuna.com/" target="_blank" rel="noopener noreferrer">'
                  'Get a free Adzuna key</a> · <a href="https://www.reed.co.uk/developers/jobseeker" target="_blank" '
                  'rel="noopener noreferrer">Get a free Reed key</a>. Keys are stored in config.toml on this computer only.</p>'
                + text("reed_api_key", "Reed API key", "", "password", f'autocomplete="off" placeholder="{esc(reed_ph)}"')
                + '<div class="row">' + text("daily_applications", "Applications per day", ch["daily_applications"], "number",
                                             'min="1" max="25"', "Default 15. The hard cap of 25 can't be raised.")
                + '<label class="field"><span>Auto-apply</span><input type="text" value="Off" disabled>'
                  '<small>Every application needs your yes before it is sent.</small></label></div>'),
        section(8, "How JobFerret talks to you",
                '<div class="field"><span>Chattiness</span>' + pills("chattiness", CHATTINESS, c["chattiness"], "radio")
                + "<small>Brief: results and questions only. Normal: a line on what it is doing and why.</small></div>"
                + select("cover_letter", "Cover letters", COVER, c["cover_letter"])
                + '<div class="field"><span>If a form asks whether you used AI</span>'
                + pills("ai_disclosure", AI_STANCE, c["ai_disclosure"], "radio")
                + "<small>JobFerret never answers that question for you. This sets how it helps and the wording it "
                  "suggests.</small></div>"),
    ])
    parts = {"NONCE": nonce, "FROMCV": from_cv, "BODY": body}
    return re.sub(r"\{\{(NONCE|FROMCV|BODY)\}\}", lambda m: parts[m.group(1)], PAGE)


PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JobFerret preferences</title>
<style>
:root{--bg:#f7f6f3;--card:#fff;--ink:#1d1d1b;--muted:#5f5e5a;--line:#d9d6cf;--accent:#1f5f8b;--accent-ink:#fff;
--soft:#e8f0f6;--err:#a32020;--ok:#1d6b3a}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#ecebe7;--muted:#a3a19b;--line:#3a3935;
--accent:#6fb0de;--accent-ink:#0d1b26;--soft:#22313c;--err:#f08a8a;--ok:#7fd29b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px 16px 96px}
h1{font-size:20px;margin:4px 0 2px}
.lede{color:var(--muted);margin:0 0 12px}
.cv{background:var(--soft);border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:14px}
fieldset{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:0 0 12px;padding:10px 14px 14px;min-width:0}
legend{font-weight:600;padding:0 6px}
legend b{display:inline-block;min-width:22px;height:22px;border-radius:11px;background:var(--accent);color:var(--accent-ink);
text-align:center;font-size:12px;line-height:22px;margin-right:4px}
.note{color:var(--muted);font-size:13px;margin:2px 0 8px}
.field{display:block;margin:10px 0 0}
.field>span{display:block;font-weight:600;font-size:13px;margin-bottom:4px}
small{display:block;color:var(--muted);font-size:12px;margin-top:3px;font-weight:400}
input[type=text],input[type=number],input[type=password],input[type=date],select{width:100%;padding:8px 10px;border:1px solid var(--line);
border-radius:6px;background:var(--bg);color:var(--ink);font:inherit;min-height:38px}
input:focus-visible,select:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 12px}
.pills{display:flex;flex-wrap:wrap;gap:6px}
.pill input{position:absolute;opacity:0;width:1px;height:1px}
.pill span{display:inline-block;padding:6px 11px;border:1px solid var(--line);border-radius:16px;cursor:pointer;font-size:13px;user-select:none}
.pill input:checked+span{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.pill input:focus-visible+span{outline:2px solid var(--accent);outline-offset:1px}
.toggle{display:flex;gap:8px;align-items:flex-start;margin:10px 0 0;cursor:pointer}
.toggle input{margin-top:3px;width:18px;height:18px;accent-color:var(--accent)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.chips:empty{display:none}
.chip{display:inline-flex;align-items:center;gap:2px;background:var(--soft);border-radius:16px;padding:3px 4px 3px 11px;font-size:13px;max-width:100%}
.chip-text{overflow-wrap:anywhere}
.chip-x{border:0;background:none;color:var(--muted);font-size:17px;line-height:1;cursor:pointer;padding:2px 6px;border-radius:10px}
.chip-x:hover{color:var(--err)}
.chip-add{display:flex;gap:6px}
.chip-add button,.bar button{border:1px solid var(--accent);background:var(--card);color:var(--accent);border-radius:6px;
padding:0 14px;font:inherit;font-weight:600;cursor:pointer;min-height:38px}
.srcs{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:6px}
.src{display:flex;gap:8px;align-items:flex-start;border:1px solid var(--line);border-radius:8px;padding:8px;cursor:pointer}
.src input{margin-top:3px;width:18px;height:18px;accent-color:var(--accent)}
.src b{font-size:14px}
a{color:var(--accent)}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line)}
.bar div{max-width:760px;margin:0 auto;padding:10px 16px;display:flex;gap:12px;align-items:center}
.bar button{background:var(--accent);color:var(--accent-ink);min-width:110px}
.bar button:disabled{opacity:.6;cursor:default}
#msg{font-size:13px;color:var(--muted);flex:1}
#msg.err{color:var(--err)}
#errors{color:var(--err);font-size:14px;margin:0 0 12px;padding-left:18px}
#errors:empty{display:none}
.done{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:24px;text-align:center;margin-top:24px}
.done h2{color:var(--ok);margin:0 0 6px;font-size:20px}
</style></head>
<body><main id="main">
<h1>Your job search preferences</h1>
<p class="lede">Everything has a default except the job titles. Change what's wrong, then save. You can change any of it later.</p>
{{FROMCV}}
<ul id="errors" aria-live="polite"></ul>
<form id="f" novalidate>{{BODY}}</form>
</main>
<div class="bar" id="bar"><div><span id="msg">Nothing is sent anywhere. This page talks only to your own computer.</span>
<button type="button" id="save">Save</button></div></div>
<script nonce="{{NONCE}}">
(function(){
var form=document.getElementById('f'),msg=document.getElementById('msg'),errs=document.getElementById('errors');
function chipVals(n){return Array.prototype.map.call(document.querySelectorAll('[data-chips="'+n+'"] .chip-text'),function(e){return e.textContent;});}
function addChip(n,v){v=(v||'').trim();if(!v)return;if(chipVals(n).some(function(x){return x.toLowerCase()===v.toLowerCase();}))return;
var box=document.querySelector('[data-chips="'+n+'"]'),c=document.createElement('span'),t=document.createElement('span'),x=document.createElement('button');
c.className='chip';t.className='chip-text';t.textContent=v;x.type='button';x.className='chip-x';x.setAttribute('aria-label','Remove '+v);x.textContent='\\u00d7';
c.appendChild(t);c.appendChild(x);box.appendChild(c);}
document.addEventListener('click',function(ev){var t=ev.target;
if(t.classList&&t.classList.contains('chip-x')){t.parentNode.remove();return;}
var n=t.getAttribute&&t.getAttribute('data-chip-btn');if(n){var i=document.querySelector('[data-chip-input="'+n+'"]');addChip(n,i.value);i.value='';i.focus();}});
document.addEventListener('keydown',function(ev){var n=ev.target.getAttribute&&ev.target.getAttribute('data-chip-input');
if(n&&ev.key==='Enter'){ev.preventDefault();addChip(n,ev.target.value);ev.target.value='';}});
form.addEventListener('submit',function(ev){ev.preventDefault();});
function val(n){var e=form.elements[n];return e?e.value:'';}
function checks(n){return Array.prototype.map.call(form.querySelectorAll('input[name="'+n+'"]:checked'),function(e){return e.value;});}
function on(n){return !!(form.elements[n]&&form.elements[n].checked);}
function pending(n){var i=document.querySelector('[data-chip-input="'+n+'"]');if(i&&i.value.trim()){addChip(n,i.value);i.value='';}}
function collect(){['titles','dealbreakers','companies','employers','feeds'].forEach(pending);
return {targets:{titles:chipVals('titles'),seniority:val('seniority'),role_families:checks('role_families')},
where:{town:val('town'),radius_miles:val('radius_miles'),work_modes:checks('work_modes'),relocate:val('relocate')||'no'},
pay:{amount:val('amount'),period:val('period')||'year',contract_types:checks('contract_types'),ir35:val('ir35')},
filters:{dealbreakers:chipVals('dealbreakers'),companies:chipVals('companies'),no_agencies:on('no_agencies'),
no_unpaid:on('no_unpaid'),no_commission_only:on('no_commission_only'),min_company_size:val('min_company_size')},
eligibility:{right_to_work:val('right_to_work'),sponsorship_needed:on('sponsorship_needed'),dbs:val('dbs'),
clearance:val('clearance'),driving_licence:val('driving_licence')},
availability:{notice_period:val('notice_period'),earliest_start:val('earliest_start')},
channels:{sources:checks('sources'),employers:chipVals('employers'),feeds:chipVals('feeds'),adzuna_app_id:val('adzuna_app_id'),
adzuna_app_key:val('adzuna_app_key'),reed_api_key:val('reed_api_key'),daily_applications:val('daily_applications')},
communication:{chattiness:val('chattiness')||'normal',cover_letter:val('cover_letter'),ai_disclosure:val('ai_disclosure')||'drafting'}};}
function showErrors(list){errs.textContent='';list.forEach(function(m){var li=document.createElement('li');li.textContent=m;errs.appendChild(li);});
msg.className='err';msg.textContent='Fix the items listed at the top, then save again.';window.scrollTo(0,0);}
var btn=document.getElementById('save');
btn.addEventListener('click',function(){var data=collect();
if(!data.targets.titles.length){showErrors(['Add at least one job title to search for.']);document.querySelector('[data-chip-input="titles"]').focus();return;}
btn.disabled=true;msg.className='';msg.textContent='Saving...';
fetch('/save'+window.location.search,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
.then(function(r){if(r.ok){var m=document.getElementById('main');m.textContent='';var d=document.createElement('div');d.className='done';
var h=document.createElement('h2');h.textContent='Saved.';var p=document.createElement('p');p.textContent='Go back to the chat. You can close this page.';
d.appendChild(h);d.appendChild(p);m.appendChild(d);document.getElementById('bar').remove();return;}
return r.json().then(function(j){showErrors(j.errors||['Something went wrong. Answer in the chat instead.']);btn.disabled=false;});})
.catch(function(){msg.className='err';msg.textContent='This page has closed. Answer the questions in the chat instead.';btn.disabled=false;});});
})();
</script></body></html>
"""

SAVED_PAGE = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Saved</title></head>
<body style="font:16px system-ui,sans-serif;margin:32px"><p>Saved. Go back to the chat.</p></body></html>
"""


# -------------------------------------------------------------------- server

class Handler(BaseHTTPRequestHandler):
    server_version = "JobFerret"
    sys_version = ""

    def log_message(self, fmt, *args):  # the request line holds the token; keep it out of logs
        pass

    # -- helpers
    def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8", extra: dict | None = None):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj), "application/json; charset=utf-8")

    def _allowed(self) -> bool:
        srv = self.server
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in srv.allowed_hosts:
            self._send(403, "Forbidden", "text/plain; charset=utf-8")
            return False
        query = parse_qs(urlsplit(self.path).query)
        token = (query.get("t") or [""])[0]
        if not hmac.compare_digest(token.encode(), srv.token.encode()):
            self._send(403, "Forbidden: open the exact link JobFerret printed.", "text/plain; charset=utf-8")
            return False
        return True

    # -- verbs
    def do_GET(self):
        if not self._allowed():
            return
        if urlsplit(self.path).path != "/":
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return
        nonce = secrets.token_urlsafe(16)
        csp = (f"default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; connect-src 'self'; "
               "img-src 'none'; base-uri 'none'; form-action 'none'")
        page = render_page(form_state(self.server.profile, self.server.config), self.server.sources, nonce)
        self._send(200, page, extra={"Content-Security-Policy": csp})

    def do_POST(self):
        if not self._allowed():
            return
        if urlsplit(self.path).path != "/save":
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return
        origin = self.headers.get("Origin")
        if origin is not None and origin.lower() not in {f"http://{h}" for h in self.server.allowed_hosts}:
            self._json(403, {"ok": False, "errors": ["Requests from other sites are refused."]})
            return
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            self._json(415, {"ok": False, "errors": ["Expected JSON."]})
            return
        try:
            length = int(self.headers.get("Content-Length") or "-1")
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self._json(413, {"ok": False, "errors": ["The form is too large."]})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"ok": False, "errors": ["The form could not be read."]})
            return
        srv = self.server
        with srv.lock:
            if srv.saved.is_set():
                self._json(409, {"ok": False, "errors": ["Already saved. Go back to the chat."]})
                return
            clean, errors = validate(payload, [s[0] for s in srv.sources])
            if not errors and not clean.get("targets", {}).get("titles"):
                errors.append("targets.titles: add at least one job title to search for")
            if errors:
                self._json(400, {"ok": False, "errors": errors})
                return
            try:
                prof, cfg, _ = save_all(clean)
            except (OSError, ValueError, ConfigError, Invalid) as exc:
                self._json(500, {"ok": False, "errors": [f"Could not save: {exc}"]})
                return
            srv.result = {"clean": clean, "profile": str(prof), "config": str(cfg)}
            self._send(200, SAVED_PAGE)
            srv.saved.set()


def serve(port: int, timeout: float, dump: bool, profile: dict, config: dict) -> int:
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        die(f"cannot listen on 127.0.0.1:{port}: {exc}")
    httpd.daemon_threads = True
    real_port = httpd.server_address[1]
    httpd.token = secrets.token_hex(16)
    httpd.allowed_hosts = {f"127.0.0.1:{real_port}", f"localhost:{real_port}"}
    httpd.profile, httpd.config = profile, config
    httpd.sources = source_options(config)
    httpd.lock = threading.Lock()
    httpd.saved = threading.Event()
    httpd.result = None
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    print(f"URL: http://127.0.0.1:{real_port}/?t={httpd.token}", flush=True)
    try:
        saved = httpd.saved.wait(timeout)
    except KeyboardInterrupt:
        saved = False
    httpd.shutdown()
    httpd.server_close()
    if not saved:
        print("TIMEOUT nothing saved", flush=True)
        return EXIT_TIMEOUT
    res = httpd.result
    print(f"SAVED profile={res['profile']} config={res['config']}", flush=True)
    if dump:
        emit_json(redacted(res["clean"]))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="setup_ui.py")
    p.add_argument("--port", type=int, default=0, help="port to listen on (0 = a random free port)")
    p.add_argument("--timeout", type=float, default=1200, help="seconds to wait for a save (default 1200)")
    p.add_argument("--dump", action="store_true", help="print the saved form as JSON after saving")
    mx = p.add_mutually_exclusive_group()
    mx.add_argument("--prefill-only", action="store_true", help="print the prefilled values as JSON and exit")
    mx.add_argument("--from-json", metavar="FILE", help="apply a partial form from a file (or - for stdin)")
    a = p.parse_args(argv)
    if not 0 <= a.port <= 65535:
        p.error("--port must be 0 to 65535")
    if a.timeout <= 0:
        p.error("--timeout must be more than 0 seconds")
    try:
        profile = load_profile()
        config = load_config()
    except (ValueError, ConfigError) as exc:
        die(f"{exc}. Fix or move the file, then run this again.")

    if a.prefill_only:
        emit_json(form_state(profile, config))
        return EXIT_OK
    if a.from_json:
        try:
            raw = sys.stdin.read() if a.from_json == "-" else Path(a.from_json).read_text(encoding="utf-8-sig")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            die(f"cannot read {a.from_json}: {exc}")
        clean, errors = validate(payload, [s[0] for s in source_options(config)])
        if not errors:
            try:
                prof, cfg, changed = save_all(clean)
            except Invalid as exc:
                errors = [str(exc)]
        if errors:
            emit_json({"ok": False, "errors": errors})
            return EXIT_FAIL
        emit_json({"ok": True, "profile": str(prof), "config": str(cfg), "changed": changed,
                   "saved": redacted(clean)})
        return EXIT_OK
    return serve(a.port, a.timeout, a.dump, profile, config)


if __name__ == "__main__":
    sys.exit(main())
