"""Helpers for browser sources: boards JobFerret reads in the user's own browser, never by script.

A browser source (SOURCE["kind"] == "browser") has no search(): the model opens the search
pages in the browser the user chose (the desktop pane, Claude in Chrome, the Codex Chrome
extension), runs the board's read-only snippet from scripts/browse/ with the browser's
JavaScript action, saves what it returns, and hands the file to `discover.py browse ingest`.
The module then turns that payload into section 8.3 records like any other source.

Why a browser and not fetch(): the site's terms ban scripts, scrapers and bots, so jf_net
refuses the host. A person opening a few search pages in their own browser, at a human pace,
is the traffic the site exists for; this module keeps it at that pace with caps the user can
see (max queries, pages per query, pages per day). The ledger below is what enforces the
daily cap across sessions.

Nothing here opens a socket.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from jf_common import atomic_write_text, user_dir

LEDGER_NAME = "browse-ledger.json"
DEFAULT_CAPS = {"max_queries": 4, "max_pages_per_query": 1, "daily_page_cap": 20}


# ----------------------------------------------------------------- caps and the ledger

def caps(creds: dict | None) -> dict:
    """The three caps for a board, from its [sources.<board>] table with defaults; never below 1."""
    out = dict(DEFAULT_CAPS)
    for k in out:
        v = (creds or {}).get(k)
        if isinstance(v, int) and not isinstance(v, bool) and v >= 1:
            out[k] = v
    return out


def ledger_path() -> Path:
    return user_dir() / "cache" / LEDGER_NAME


def _load_ledger() -> dict:
    path = ledger_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def pages_today(board: str, today: date | None = None) -> int:
    day = (today or date.today()).isoformat()
    board_days = _load_ledger().get(board) or {}
    v = board_days.get(day, 0)
    return int(v) if isinstance(v, int) and not isinstance(v, bool) else 0


def note_pages(board: str, n: int = 1, today: date | None = None) -> int:
    """Record n pages read today for the board; returns the new total. Keeps the last 14 days."""
    day = (today or date.today()).isoformat()
    ledger = _load_ledger()
    board_days = {k: v for k, v in (ledger.get(board) or {}).items() if isinstance(v, int)}
    board_days[day] = board_days.get(day, 0) + max(0, int(n))
    keep = sorted(board_days)[-14:]
    ledger[board] = {k: board_days[k] for k in keep}
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(ledger, indent=1) + "\n")
    return board_days[day]


def remaining_today(board: str, creds: dict | None, today: date | None = None) -> int:
    return max(0, caps(creds)["daily_page_cap"] - pages_today(board, today))


# ----------------------------------------------------------------- payloads

class PayloadError(ValueError):
    """A saved browser capture that cannot be read. The message is shown to the user."""


def load_payload(path: str | Path, text: bool | None = None) -> dict:
    """Read a saved capture. JSON (the snippet's output, or a bare list of cards) becomes
    {"kind": "search"|"job", "cards": [...], ...}; text (page text) becomes {"kind": "text",
    "text": ...}. A .txt suffix or text=True means page text."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise PayloadError(f"cannot read {p}: {exc.strerror or exc}") from None
    if text is None:
        text = p.suffix.lower() in (".txt", ".md")
    if text:
        return {"kind": "text", "text": raw, "file": str(p)}
    stripped = raw.strip()
    if not stripped:
        raise PayloadError(f"{p} is empty")
    try:
        data = json.loads(stripped)
    except ValueError:
        # Some browser tools return the snippet's JSON as a quoted string; try that once.
        try:
            data = json.loads(json.loads(stripped))
        except ValueError:
            raise PayloadError(f"{p} is not JSON (save the snippet's return value as it is, "
                               "or pass --text for page text)") from None
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            raise PayloadError(f"{p} holds a string, not the snippet's object") from None
    if isinstance(data, list):
        data = {"kind": "search", "cards": data}
    if not isinstance(data, dict):
        raise PayloadError(f"{p}: expected an object or a list of cards")
    data.setdefault("kind", "job" if "description_html" in data or "description" in data else "search")
    data["file"] = str(p)
    return data


# ----------------------------------------------------------------- shared text helpers

_RELATIVE = re.compile(r"^(just posted|today|posted today|posted (\d+)\+? days? ago|(\d+)\+? days? ago|"
                       r"active (\d+)\+? days? ago|posted 30\+ days ago|30\+ days ago)$", re.I)


def days_from_relative(text: str | None) -> int | None:
    """0 for 'Just posted', 3 for '3 days ago' or 'Posted 3 days ago'; None for '30+ days ago' or
    anything unreadable (the date is then unknown rather than guessed)."""
    if not text:
        return None
    m = _RELATIVE.match(text.strip())
    if not m:
        return None
    s = text.lower()
    if "30+" in s:
        return None
    for g in (2, 3, 4):
        if m.group(g):
            return int(m.group(g))
    return 0
