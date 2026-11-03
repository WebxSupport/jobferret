"""Build a draft profile.json from the CV fact ledger, so the user confirms rather than types.

Purpose
    Reads the ledger cv_extract.py wrote and fills what a CV can answer: name,
    contact details, a location guess, current title and employer, skills,
    roles, education and a first guess at target titles. Everything else is
    left empty with the right type, for the preferences page, the chat
    questions or the profile mode to fill. Each filled field and the fact it
    came from is recorded in meta.prefill, which is how --merge tells a value
    the user typed from one this script guessed.

Usage
    profile_prefill.py --ledger <ledger.json> --out <profile.json> [--merge] [--json]

    Without --merge the output file must not exist yet. With --merge an
    existing profile is updated: a field is written only when it is empty, or
    when it still holds the value this script put there last time (so a newer
    CV can refresh a guess). Anything the user entered or changed is kept.
    --merge on a missing file creates it.

    Location guess: the place named on the contact line, else the most recent
    role's location. Target titles: the CV headline and the current title.
    Seniority: read from the current title's wording. The script prints what
    it filled (with fact IDs) and what it left empty.

Exit codes
    0  draft written
    1  the ledger holds nothing usable (no name, contact or role found); nothing written
    4  usage or input error (ledger missing or invalid, output exists without --merge)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from jf_common import (
    EMAIL_RE, EXIT_FAIL, EXIT_OK, URL_RE, LedgerError, die, emit_json, empty_profile, find_phones, get_path,
    is_empty_value, load_ledger, load_profile, make_parser, now_iso, save_profile, set_path, setup_io,
    strip_markers,
)

QUAL_RANK = [
    (6, re.compile(r"\b(PhD|DPhil|EdD|MD|Doctorate)\b", re.I)),
    (5, re.compile(r"\b(MSc|MA|MBA|MEng|MPhil|MRes|LLM|MSci|MMath|MChem|PGCE|PGDip|Master'?s?)\b", re.I)),
    (4, re.compile(r"\b(BSc|BA|BEng|LLB|BEd|BMus|MBBS|BSc\(Hons\)|Bachelor'?s?|Hons|Degree)\b", re.I)),
    (3, re.compile(r"\b(HND|HNC|Foundation degree|FdA|FdSc|DipHE|CertHE)\b", re.I)),
    (2, re.compile(r"\b(A[- ]?levels?|BTEC|T[- ]?levels?|Highers|IB|International Baccalaureate|Level 3)\b", re.I)),
    (1, re.compile(r"\b(GCSEs?|Nationals?|Level 2)\b", re.I)),
]
CLASS_RE = re.compile(r"\b(First(?:[- ]class)?|1st|2[:.]1|2[:.]2|Upper second|Lower second|Third|"
                      r"Distinction|Merit|Pass)\b", re.I)
SENIORITY = [
    ("executive", re.compile(r"\b(Chief|CEO|CFO|CTO|COO|CIO|Managing Director|VP|Vice President|Partner)\b", re.I)),
    ("head", re.compile(r"\b(Head of|Director)\b", re.I)),
    ("lead", re.compile(r"\b(Lead|Principal|Staff)\b", re.I)),
    ("manager", re.compile(r"\bManager\b", re.I)),
    ("senior", re.compile(r"\b(Senior|Sr\.?)\b", re.I)),
    ("entry", re.compile(r"\b(Graduate|Trainee|Apprentice|Intern|Junior|Jr\.?)\b", re.I)),
]
SEPARATORS_RE = re.compile(r"\s*[|·•;]\s*")


def facts_of(ledger: dict, *kinds: str) -> list[dict]:
    return [f for f in ledger.get("facts", []) if f.get("kind") in kinds and not f.get("superseded_by")]


def find_name(ledger: dict) -> tuple[str, str] | None:
    for f in facts_of(ledger, "contact"):
        name = (f.get("fields") or {}).get("name")
        if name:
            return name.strip(), f["id"]
    for f in facts_of(ledger, "contact", "headline", "other")[:3]:
        t = strip_markers(f["text"]).strip()
        if t and not re.search(r"[\d@/]", t) and 2 <= len(t.split()) <= 5:
            return t, f["id"]
    return None


def contact_parts(ledger: dict) -> dict[str, tuple]:
    """email, phone, linkedin, github, other links and a place, each with the fact ID it came from."""
    out: dict[str, tuple] = {}
    links: list[str] = []
    for f in facts_of(ledger, "contact"):
        t = strip_markers(f["text"])
        no_email = EMAIL_RE.sub(" ", t)
        if "email" not in out and (m := EMAIL_RE.search(t)):
            out["email"] = (m.group(0), f["id"])
        phones = find_phones(t)
        if "phone" not in out and phones:
            out["phone"] = (phones[0].strip(), f["id"])
        for m in URL_RE.finditer(no_email):
            url = m.group(0).rstrip(".,;)")
            if EMAIL_RE.fullmatch(url) or "@" in url:
                continue
            low = url.lower()
            if "linkedin.com" in low and "linkedin" not in out:
                out["linkedin"] = (url, f["id"])
            elif "github.com" in low and "github" not in out:
                out["github"] = (url, f["id"])
            elif url not in links:
                links.append(url)
        if "place" not in out and (EMAIL_RE.search(t) or phones):
            for part in SEPARATORS_RE.split(t):
                p = part.strip(" ,")
                if not p or EMAIL_RE.search(p) or URL_RE.search(p) or re.search(r"\d{3}", p):
                    continue
                if len(p.split()) <= 4 and re.match(r"^[A-Z]", p):
                    out["place"] = (p, f["id"])
                    break
    if links:
        out["links"] = (links, None)
    return out


def usable_roles(ledger: dict) -> list[dict]:
    roles = []
    for f in facts_of(ledger, "role"):
        fl = f.get("fields") or {}
        title, employer = (fl.get("title") or "").strip(), (fl.get("employer") or "").strip()
        if not title or not employer or ";" in employer or ";" in (fl.get("location") or ""):
            continue  # "Earlier career" one-liners parse badly; they stay in the ledger, not the profile
        roles.append({"title": title, "employer": employer, "location": (fl.get("location") or "").strip(),
                      "start": fl.get("start") or "", "end": fl.get("end") or "",
                      "current": bool(fl.get("current")) or fl.get("end") in (None, ""), "fact": f["id"]})
    return roles


def most_recent(roles: list[dict]) -> dict | None:
    if not roles:
        return None
    current = [r for r in roles if r["current"]]
    pool = current or roles
    return max(pool, key=lambda r: (str(r["end"] or "9999"), str(r["start"])))


def education(ledger: dict) -> tuple[list[dict], dict | None]:
    items = []
    for f in facts_of(ledger, "education"):
        fl = f.get("fields") or {}
        qual = (fl.get("qualification") or strip_markers(f["text"]).split(",")[0]).strip()
        m = CLASS_RE.search(qual) or CLASS_RE.search(f["text"])
        rank = next((r for r, rx in QUAL_RANK if rx.search(qual)), 0)
        items.append({"qualification": qual, "classification": m.group(0) if m else "",
                      "institution": (fl.get("institution") or "").strip(), "end": fl.get("end") or "",
                      "rank": rank, "fact": f["id"]})
    best = max(items, key=lambda e: (e["rank"], str(e["end"]))) if items else None
    return [{k: v for k, v in e.items() if k != "rank"} for e in items], best


def skills(ledger: dict) -> tuple[list[str], list[str]]:
    out: list[str] = []
    ids: list[str] = []
    for f in facts_of(ledger, "skill"):
        items = (f.get("fields") or {}).get("items")
        if not items:
            text = strip_markers(f["text"])
            text = text.split(":", 1)[1] if ":" in text else text
            items = [s.strip() for s in re.split(r"[,;]", text)]
        for s in items:
            s = s.strip(" .")
            if s and s.lower() not in {x.lower() for x in out}:
                out.append(s)
        ids.append(f["id"])
    return out, ids


def guess_seniority(title: str) -> str:
    return next((label for label, rx in SENIORITY if rx.search(title)), "mid" if title else "")


def build(ledger: dict) -> dict[str, tuple]:
    """Dotted profile path -> (value, source fact IDs as text)."""
    found: dict[str, tuple] = {}
    name = find_name(ledger)
    if name:
        found["personal.name"] = name
    parts = contact_parts(ledger)
    for key in ("email", "phone", "linkedin", "github"):
        if key in parts:
            found[f"personal.{key}"] = parts[key]
    if "links" in parts:
        found["personal.links"] = (parts["links"][0], "contact line")
    roles = usable_roles(ledger)
    recent = most_recent(roles)
    if "place" in parts:
        found["personal.location"] = parts["place"]
    elif recent and recent["location"]:
        found["personal.location"] = (recent["location"], recent["fact"])
    if recent:
        found["current.title"] = (recent["title"], recent["fact"])
        found["current.employer"] = (recent["employer"], recent["fact"])
        found["targets.seniority"] = (guess_seniority(recent["title"]), recent["fact"])
    if roles:
        found["history.roles"] = ([{k: r[k] for k in ("title", "employer", "location", "start", "end", "fact")}
                                   for r in roles], ",".join(r["fact"] for r in roles))
    titles: list[str] = []
    title_ids: list[str] = []
    for f in facts_of(ledger, "headline"):
        t = strip_markers(f["text"]).strip()
        if t and len(t) <= 80 and not re.search(r"[@\d]{3}", t):
            titles.append(t)
            title_ids.append(f["id"])
            break
    if recent and recent["title"].lower() not in {t.lower() for t in titles}:
        titles.append(recent["title"])
        title_ids.append(recent["fact"])
    if titles:
        found["targets.titles"] = (titles, ",".join(title_ids))
    loc = found.get("personal.location")
    if loc:
        found["targets.locations"] = ([loc[0]], loc[1])
    edu, best = education(ledger)
    if edu:
        found["history.education"] = (edu, ",".join(e["fact"] for e in edu))
    if best:
        label = best["qualification"]
        if best["classification"] and best["classification"] not in label:
            label = f"{label} ({best['classification']})"
        found["history.highest_qualification"] = (label, best["fact"])
    sk, sk_ids = skills(ledger)
    if sk:
        found["history.skills"] = (sk, ",".join(sk_ids))
    certs = facts_of(ledger, "certification")
    if certs:
        found["history.certifications"] = ([strip_markers(c["text"]).strip() for c in certs],
                                           ",".join(c["id"] for c in certs))
    return found


# Paths the draft reports on, so the user sees what is still open.
REPORT_EMPTY = [
    "personal.name", "personal.email", "personal.phone", "personal.location", "personal.linkedin",
    "current.title", "current.employer", "targets.titles", "targets.seniority", "history.roles",
    "history.highest_qualification", "history.skills",
    "targets.work_modes", "targets.radius_miles", "targets.salary_floor.amount", "targets.contract_types",
    "eligibility.right_to_work", "eligibility.notice_period", "answer_bank.why_looking",
]


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="profile_prefill.py")
    p.add_argument("--ledger", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--merge", action="store_true", help="update an existing profile without overwriting the user's values")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    try:
        ledger = load_ledger(a.ledger)
    except (LedgerError, OSError, ValueError) as exc:
        die(f"cannot read ledger {a.ledger}: {exc}")
    if a.out.exists() and not a.merge:
        die(f"{a.out} already exists; use --merge to update it without losing what the user entered")
    try:
        profile = load_profile(a.out) if a.out.exists() else empty_profile()
    except ValueError as exc:
        die(str(exc))

    found = build(ledger)
    if not any(k in found for k in ("personal.name", "personal.email", "current.title")):
        msg = "the ledger has no name, contact details or dated role; nothing written"
        if a.json:
            emit_json({"ok": False, "error": msg})
        else:
            print(msg)
        return EXIT_FAIL

    prev_prefill: dict = dict(get_path(profile, "meta.prefill", {}) or {})
    filled: dict[str, dict] = {}
    kept: list[str] = []
    new_prefill: dict = {}
    for path, (value, source) in found.items():
        current = get_path(profile, path)
        ours = path in prev_prefill and prev_prefill[path] == current
        if is_empty_value(current) or ours:
            set_path(profile, path, value)
            new_prefill[path] = value
            filled[path] = {"value": value, "source": source}
        else:
            kept.append(path)
    for path, value in prev_prefill.items():
        if path not in new_prefill and get_path(profile, path) == value:
            new_prefill[path] = value  # still our guess; keep tracking it
    set_path(profile, "meta.prefill", new_prefill)
    set_path(profile, "meta.prefilled_from", str(a.ledger))
    set_path(profile, "meta.prefilled_at", now_iso())
    if not get_path(profile, "meta.status"):
        set_path(profile, "meta.status", "draft")
    save_profile(profile, a.out)

    empty = [path for path in REPORT_EMPTY if is_empty_value(get_path(profile, path))]
    if a.json:
        emit_json({"ok": True, "out": str(a.out), "filled": filled, "kept_user_values": kept, "empty": empty})
        return EXIT_OK
    print(f"Draft profile written to {a.out}")
    print("Filled from the CV:")
    for path, info in filled.items():
        v = info["value"]
        shown = (f"{len(v)} items" if len(v) > 3 or (v and isinstance(v[0], dict)) else ", ".join(map(str, v))) \
            if isinstance(v, list) else str(v)
        src = f" [{info['source']}]" if info["source"] else ""
        print(f"  {path}: {shown}{src}")
    if kept:
        print("Kept your own values for: " + ", ".join(kept))
    print("Still empty: " + (", ".join(empty) if empty else "nothing"))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
