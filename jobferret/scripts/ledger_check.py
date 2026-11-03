"""Validate fact citations in generated markdown against the fact ledger.

Purpose
    Enforces the honesty gate (ARCHITECTURE section 2.3). Every claim in a
    generated CV, cover letter or answer must cite a fact in ledger.json.

Usage
    ledger_check.py <draft.md> --ledger <ledger.json> [--strict]
                    [--strip --out <clean.md>] [--json]

Rules
    1  Every list item (- , * , 1. ), every skills line (**Label:** ...) and every
       H3+ entry header (### Title — Employer | ...) carries at least one
       citation [F012] / [F012,F041] (or a [CONFIRM: ...] marker, which then
       blocks under rule 5). An employer or institution name is a claim.
    2  Every sentence containing a digit, %, £, $, € or a multiplier (2.3x, 3×)
       carries a citation. H1/H2 headings, the contact line under the H1, and
       lines made only of contact details or a date are exempt.
    3  Every cited ID exists in the ledger and has not been superseded
       (ledger_add.py --supersede); malformed markers ([F12], [f012]) fail.
    4  --strict: every cited fact has "confirmed": true.
    5  Any [CONFIRM: ...] marker blocks. [ASK: ...] is an alias of [CONFIRM: ...].
    6  --strip writes a copy with every marker removed, only when 1-5 and 7 pass.
    7  Numbers must trace: in every cited sentence, list item, skills line or
       entry header, each number (digits, %, currency amounts, 2.3x / 3×
       multipliers, both ends of ranges such as "9 to 5") must appear in the
       text of at least one fact cited there. Compared as values: thousands
       separators are ignored, a "~" or "roughly" prefix is ignored, and
       k / m / bn equal ,000 / ,000,000 / ,000,000,000 ("£180k" = "£180,000").
       Spelled-out numbers in the fact text count ("eight years" backs "8").
       A derived figure (e.g. a percentage worked out from two facts) must be
       added to the ledger as its own confirmed fact first.

    Spelled-out numbers ("twelve", "doubled") in an uncited sentence produce a
    warning, not a violation.

Exit codes
    0  pass (and the stripped copy was written if --strip)
    1  violations of rules 1, 2, 3 or 7 (each listed with its line number)
    2  blocked: [CONFIRM]/[ASK] markers, or unconfirmed facts under --strict
       (when there are also rule 1-3 or 7 violations, the exit code is 1)
    3  missing dependency (none expected; standard library only)
    4  usage or input error (bad arguments, unreadable draft or ledger)

--json prints {"ok", "violations": [{"line", "rule", "text", "message"}],
"confirm_items": [{"line", "question"}], "warnings": [...], "stats": {...},
"stripped": path-or-null}.
"""
from __future__ import annotations

import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from jf_common import (
    EXIT_BLOCKED, EXIT_FAIL, EXIT_OK, BULLET_MD_RE, SKILL_LINE_RE, CITATION_RE, CONFIRM_RE,
    LedgerError, atomic_write_text, die, emit_json, find_citations, find_confirms,
    find_malformed_citations, is_contact_line, ledger_index, load_ledger, make_parser,
    read_text, setup_io, split_sentence_spans, strip_markers,
)

NUMERIC_RE = re.compile(r"[0-9%£$€×]")
NUMBER_WORDS_RE = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundreds?|thousands?|millions?|billions?|dozens?|doubled?|tripled?|"
    r"quadrupled?|halved|twice|tenfold|twofold|threefold)\b",
    re.IGNORECASE,
)
NUM_TOKEN_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
    r"(?:(k|m|bn)(?![a-z])|\s(thousand|million|billion)\b)?",
    re.IGNORECASE,
)
SCALE = {"k": 1000, "thousand": 1000, "m": 1000000, "million": 1000000, "bn": 1000000000,
         "billion": 1000000000}
WORD_VALUES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "dozen": 12, "twice": 2,
    "double": 2, "doubled": 2, "triple": 3, "tripled": 3, "half": 50, "halved": 50,
}
DATE_ONLY_RE = re.compile(
    r"^\s*(?:\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\s*$"
)


def _has_marker(text: str) -> bool:
    return bool(CITATION_RE.search(text) or CONFIRM_RE.search(text))


def _clip(text: str, n: int = 160) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def build_units(lines: list[str]) -> list[dict]:
    """Group markdown lines into checkable units.

    unit = {"kind": heading|entry|item|skill|paragraph|exempt, "level", "parts": [(line_no, text)]}
    """
    units: list[dict] = []
    cur: dict | None = None
    for no, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            cur = None
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", s)
        if hm:
            level = len(hm.group(1))
            if level <= 2:
                units.append({"kind": "heading", "level": level, "parts": [(no, hm.group(2))]})
            else:
                units.append({"kind": "entry", "level": level, "parts": [(no, hm.group(2))]})
            cur = None
            continue
        bm = BULLET_MD_RE.match(line)
        if bm:
            cur = {"kind": "item", "parts": [(no, line[bm.end():].strip())]}
            units.append(cur)
            continue
        if cur is not None and cur["kind"] == "item" and raw.startswith(("  ", "\t")):
            cur["parts"].append((no, s))
            continue
        if SKILL_LINE_RE.match(s):
            units.append({"kind": "skill", "parts": [(no, s)]})
            cur = None
            continue
        if is_contact_line(s) or DATE_ONLY_RE.match(strip_markers(s)):
            units.append({"kind": "exempt", "why": "contact or date line", "parts": [(no, s)]})
            cur = None
            continue
        if cur is not None and cur["kind"] == "paragraph":
            cur["parts"].append((no, s))
            continue
        cur = {"kind": "paragraph", "parts": [(no, s)]}
        units.append(cur)
    return units


def _joined(parts: list[tuple[int, str]]) -> tuple[str, list[tuple[int, int]]]:
    """Join unit lines with spaces; return text and (offset, line_no) starts."""
    text = ""
    starts = []
    for no, t in parts:
        if text:
            text += " "
        starts.append((len(text), no))
        text += t
    return text, starts


def _line_at(starts: list[tuple[int, int]], offset: int) -> int:
    line = starts[0][1]
    for off, no in starts:
        if off <= offset:
            line = no
    return line


def _norm(d: Decimal) -> str:
    return format(d.normalize(), "f")


def number_tokens(text: str) -> list[tuple[str, str, str | None]]:
    """[(as written, raw value, scaled value or None)] for every number in text."""
    out = []
    for m in NUM_TOKEN_RE.finditer(text):
        whole = m.group(1).replace(",", "")
        try:
            raw = Decimal(whole + ("." + m.group(2) if m.group(2) else ""))
        except InvalidOperation:
            continue
        suffix = (m.group(3) or m.group(4) or "").lower()
        scaled = _norm(raw * SCALE[suffix]) if suffix else None
        written = m.group(0).strip()
        before = text[m.start() - 1] if m.start() else ""
        after = text[m.end()] if m.end() < len(text) else ""
        if before in "£$€" and before:
            written = before + written
        if after in ("%", "x", "×"):
            written += after
        out.append((written, _norm(raw), scaled))
    return out


def fact_values(text: str) -> set[str]:
    """Every value a fact's text can back: raw and scaled numbers, number words."""
    vals: set[str] = set()
    for _, raw, scaled in number_tokens(text):
        vals.add(raw)
        if scaled:
            vals.add(scaled)
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in WORD_VALUES:
            vals.add(str(WORD_VALUES[w]))
    return vals


def untraced_numbers(text: str, cited: list[str], facts: dict[str, dict]) -> list[str]:
    """Numbers in text that appear in none of the cited facts (rule 7)."""
    allowed: set[str] = set()
    for fid in cited:
        if fid in facts:
            allowed |= fact_values(str(facts[fid].get("text", "")))
    missing = []
    for written, raw, scaled in number_tokens(strip_markers(text)):
        if (scaled or raw) not in allowed:
            missing.append(written)
    return missing


def check(draft_text: str, ledger: dict, strict: bool = False) -> dict:
    lines = draft_text.splitlines()
    facts = ledger_index(ledger)
    violations: list[dict] = []
    confirm_items: list[dict] = []
    warnings: list[str] = []
    stats = {"units_checked": 0, "citations": 0, "distinct_facts_cited": 0}

    def add(line: int, rule: int, text: str, message: str) -> None:
        violations.append({"line": line, "rule": rule, "text": _clip(text), "message": message})

    # Rules 3, 4, 5: scan every line.
    cited: set[str] = set()
    for no, raw in enumerate(lines, start=1):
        for bad in find_malformed_citations(raw):
            add(no, 3, bad, f"malformed citation marker {bad}; use [F012] or [F012,F041]")
        for fid in find_citations(raw):
            stats["citations"] += 1
            cited.add(fid)
            fact = facts.get(fid)
            if fact is None:
                add(no, 3, raw, f"{fid} is not in the ledger")
            elif fact.get("superseded_by"):
                add(no, 3, raw, f"{fid} superseded by {fact['superseded_by']}; cite the replacement")
            elif strict and fact.get("confirmed") is not True:
                add(no, 4, raw, f"{fid} is not confirmed by the user ({_clip(str(fact.get('text', '')), 80)})")
        for q in find_confirms(raw):
            confirm_items.append({"line": no, "question": q})
            add(no, 5, raw, f"unresolved [CONFIRM]: {q or '(no question given)'}")
    stats["distinct_facts_cited"] = len(cited)

    def trace(line: int, text: str) -> None:
        ids = find_citations(text)
        if not ids:
            return
        missing = untraced_numbers(text, ids, facts)
        if missing:
            add(line, 7, text, f"number not in cited facts: {', '.join(dict.fromkeys(missing))} "
                               f"(cited {', '.join(ids)})")

    # Rules 1, 2 and 7: per unit.
    for unit in build_units(lines):
        kind = unit["kind"]
        if kind in ("heading", "exempt"):
            continue
        stats["units_checked"] += 1
        text, starts = _joined(unit["parts"])
        first_line = unit["parts"][0][0]
        if kind in ("item", "skill", "entry") and not _has_marker(text):
            label = {"item": "list item", "skill": "skills line", "entry": "entry header"}[kind]
            add(first_line, 1, text, f"{label} has no citation")
            continue  # one violation per uncited item is enough
        if kind in ("skill", "entry"):
            trace(first_line, text)
            continue
        for s, e in split_sentence_spans(text):
            sentence = text[s:e]
            plain = strip_markers(sentence)
            if _has_marker(sentence):
                trace(_line_at(starts, s), sentence)
                continue
            if NUMERIC_RE.search(plain):
                add(_line_at(starts, s), 2, sentence, "sentence with a number has no citation")
            elif NUMBER_WORDS_RE.search(plain):
                warnings.append(f"line {_line_at(starts, s)}: spelled-out number without a citation: "
                                f"“{_clip(plain, 100)}”")

    violations.sort(key=lambda v: (v["line"], v["rule"]))
    hard = [v for v in violations if v["rule"] in (1, 2, 3, 7)]
    blocked = [v for v in violations if v["rule"] in (4, 5)]
    return {
        "ok": not violations,
        "violations": violations,
        "confirm_items": confirm_items,
        "warnings": warnings,
        "stats": stats,
        "exit": EXIT_FAIL if hard else (EXIT_BLOCKED if blocked else EXIT_OK),
    }


def strip_document(draft_text: str) -> str:
    out = [strip_markers(line) for line in draft_text.splitlines()]
    return "\n".join(out).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="ledger_check.py")
    p.add_argument("draft", help="generated markdown to check")
    p.add_argument("--ledger", required=True, help="ledger.json")
    p.add_argument("--strict", action="store_true", help="every cited fact must be confirmed")
    p.add_argument("--strip", action="store_true", help="write a marker-free copy (needs --out)")
    p.add_argument("--out", help="where --strip writes the clean markdown")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args(argv)
    if a.strip and not a.out:
        p.error("--strip needs --out <clean.md>")
    if a.out and not a.strip:
        p.error("--out is only used with --strip")

    draft = read_text(Path(a.draft))
    try:
        ledger = load_ledger(a.ledger)
    except LedgerError as exc:
        die(str(exc))
    res = check(draft, ledger, strict=a.strict)
    code = res.pop("exit")
    res["stripped"] = None
    if a.strip and code == EXIT_OK:
        out = Path(a.out)
        if out.resolve() == Path(a.draft).resolve():
            die("--out must differ from the draft; the draft keeps its citations")
        atomic_write_text(out, strip_document(draft))
        res["stripped"] = str(out)

    if a.json:
        emit_json(res)
    else:
        if res["ok"]:
            print(f"PASS  {a.draft}: {res['stats']['units_checked']} units, "
                  f"{res['stats']['citations']} citations, {res['stats']['distinct_facts_cited']} facts")
        else:
            label = {EXIT_FAIL: "FAIL", EXIT_BLOCKED: "BLOCKED"}[code]
            print(f"{label}  {a.draft}: {len(res['violations'])} problem(s)")
            for v in res["violations"]:
                print(f"  line {v['line']:>4}  rule {v['rule']}  {v['message']}")
                print(f"              “{v['text']}”")
        if res["confirm_items"]:
            print("Questions to ask the user before this can ship:")
            for c in res["confirm_items"]:
                print(f"  line {c['line']}: {c['question']}")
        for w in res["warnings"]:
            print(f"  warning: {w}")
        if a.strip:
            print(f"Stripped copy written to {res['stripped']}" if res["stripped"]
                  else "Not stripped: fix the problems above first.")
    return code


if __name__ == "__main__":
    sys.exit(main())
