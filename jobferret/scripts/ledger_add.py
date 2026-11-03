"""Append a fact to the ledger, confirm one, or supersede one, without hand-editing JSON.

Purpose
    The model records facts the user supplies in conversation (a metric, a
    scope, a corrected date) here, so every new claim gets the next sequential
    ID and the ledger stays valid. Nothing is renumbered or deleted.

Usage
    ledger_add.py --ledger <ledger.json> --kind <kind> --text "<exact sentence>"
                  [--parent F008] [--provenance user|profile]
                  [--asked "<question that produced it>"] [--confirmed] [--json]
    ledger_add.py --ledger <ledger.json> --confirm F041 [--json]
    ledger_add.py --ledger <ledger.json> --supersede F041 --text "<new wording>"
                  [--confirmed] [--kind <kind>] [--parent F008]
                  [--provenance user|profile] [--asked "..."] [--json]

    kind is one of: contact headline summary role bullet education certification
    skill project publication award language interest metric other.
    New facts get line/page null, provenance "user" by default, and
    confirmed false unless --confirmed is given. --asked adds
    note = {"asked": ..., "added_at": ISO time}. --confirm flips an existing
    fact's "confirmed" to true and records note.confirmed_at.
    --supersede adds a new fact (kind and parent copied from the old one unless
    given) with "supersedes": "F041", and sets "superseded_by" on the old fact,
    which is otherwise left unchanged and never deleted. ledger_check.py then
    rejects citations of the old ID.
    The file is written atomically (temp file + replace).

Output
    Plain: the new (or confirmed) fact ID on one line.
    --json: {"ok": true, "action": "add"|"confirm"|"supersede", "fact": {...}}
            (supersede also has "superseded": {...old fact...})
            or {"ok": false, "error": "..."}.

Exit codes
    0  ok
    1  validation error (unknown kind, unknown parent or fact ID, empty text,
       fact already superseded, unreadable or invalid ledger)
    3  missing dependency (none expected; standard library only)
    4  usage error (bad or conflicting arguments)
"""
from __future__ import annotations

import sys
from pathlib import Path

from jf_common import (
    EXIT_FAIL, EXIT_OK, FACT_ID_RE, FACT_KINDS, LedgerError, emit_json, ledger_index,
    load_ledger, make_parser, next_fact_id, now_iso, normalize_ws, save_ledger, setup_io,
)


def add_fact(ledger: dict, kind: str, text: str, parent: str | None = None,
             provenance: str = "user", asked: str | None = None, confirmed: bool = False) -> dict:
    """Validate and append a fact in place; return it. Raises ValueError."""
    if kind not in FACT_KINDS:
        raise ValueError(f"unknown kind {kind!r}; use one of: {', '.join(FACT_KINDS)}")
    if provenance not in ("user", "profile"):
        raise ValueError("provenance must be 'user' or 'profile' ('cv' facts come from cv_extract.py)")
    clean = normalize_ws(text or "")
    if not clean:
        raise ValueError("--text is empty")
    if "[" in clean and ("[F" in clean or "CONFIRM" in clean.upper() or "[ASK" in clean.upper()):
        raise ValueError("--text must be the plain fact, without citation or [CONFIRM] markers")
    index = ledger_index(ledger)
    if parent is not None:
        if not FACT_ID_RE.match(parent):
            raise ValueError(f"--parent {parent!r} is not a fact ID (expected F001 style)")
        if parent not in index:
            raise ValueError(f"--parent {parent} is not in the ledger")
    fact = {
        "id": next_fact_id(ledger), "kind": kind, "text": clean, "line": None, "page": None,
        "parent": parent, "fields": {}, "provenance": provenance, "confirmed": bool(confirmed),
    }
    if asked:
        fact["note"] = {"asked": normalize_ws(asked), "added_at": now_iso()}
    ledger.setdefault("facts", []).append(fact)
    return fact


def _live(ledger: dict, fid: str) -> dict:
    index = ledger_index(ledger)
    if fid not in index:
        raise ValueError(f"{fid} is not in the ledger")
    fact = index[fid]
    if fact.get("superseded_by"):
        raise ValueError(f"{fid} is already superseded by {fact['superseded_by']}; use that ID")
    return fact


def confirm_fact(ledger: dict, fid: str) -> dict:
    fact = _live(ledger, fid)
    fact["confirmed"] = True
    note = fact.get("note") if isinstance(fact.get("note"), dict) else {}
    note["confirmed_at"] = now_iso()
    fact["note"] = note
    return fact


def supersede_fact(ledger: dict, old_id: str, text: str, kind: str | None = None, parent: str | None = None,
                   provenance: str = "user", asked: str | None = None, confirmed: bool = False) -> tuple[dict, dict]:
    """Add the replacement fact and link the two. Returns (new, old). Raises ValueError."""
    old = _live(ledger, old_id)
    new = add_fact(ledger, kind or old.get("kind", "other"), text,
                   parent if parent is not None else old.get("parent"), provenance, asked, confirmed)
    new["supersedes"] = old_id
    old["superseded_by"] = new["id"]
    return new, old


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="ledger_add.py")
    p.add_argument("--ledger", required=True, help="ledger.json to update")
    p.add_argument("--kind", help="fact kind")
    p.add_argument("--text", help="the exact sentence, as the user confirmed or said it")
    p.add_argument("--parent", help="parent fact ID, e.g. the bullet a metric belongs to")
    p.add_argument("--provenance", choices=("user", "profile"), default="user")
    p.add_argument("--asked", help="the question that produced this fact")
    p.add_argument("--confirmed", action="store_true", help="the user has confirmed the exact wording")
    p.add_argument("--confirm", metavar="FACT_ID", help="mark an existing fact confirmed instead of adding")
    p.add_argument("--supersede", metavar="FACT_ID", help="replace an existing fact's wording with --text")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args(argv)

    if a.confirm and a.supersede:
        p.error("use --confirm or --supersede, not both")
    if a.confirm:
        if any(x is not None for x in (a.kind, a.text, a.parent, a.asked)) or a.confirmed:
            p.error("--confirm cannot be combined with --kind/--text/--parent/--asked/--confirmed")
    elif a.supersede:
        if a.text is None:
            p.error("--supersede needs --text with the new wording")
    elif not (a.kind and a.text is not None):
        p.error("adding a fact needs --kind and --text (or use --confirm / --supersede FACT_ID)")

    def fail(msg: str) -> int:
        if a.json:
            emit_json({"ok": False, "error": msg})
        else:
            sys.stderr.write(f"error: {msg}\n")
        return EXIT_FAIL

    path = Path(a.ledger)
    try:
        ledger = load_ledger(path)
    except LedgerError as exc:
        return fail(str(exc))
    extra: dict = {}
    try:
        if a.confirm:
            fact = confirm_fact(ledger, a.confirm.strip())
            action = "confirm"
        elif a.supersede:
            fact, old = supersede_fact(ledger, a.supersede.strip(), a.text, a.kind.strip() if a.kind else None,
                                       a.parent.strip() if a.parent else None, a.provenance, a.asked,
                                       a.confirmed)
            action, extra = "supersede", {"superseded": old}
        else:
            fact = add_fact(ledger, a.kind.strip(), a.text, a.parent.strip() if a.parent else None,
                            a.provenance, a.asked, a.confirmed)
            action = "add"
    except ValueError as exc:
        return fail(str(exc))
    try:
        save_ledger(ledger, path)
    except OSError as exc:
        return fail(f"could not write {path}: {exc}")
    if a.json:
        emit_json({"ok": True, "action": action, "fact": fact, **extra})
    else:
        print(fact["id"])
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
