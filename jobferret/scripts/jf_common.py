"""Shared helpers for the JobFerret scripts.

Purpose
    Paths, config, fact-ledger load/save, the CV markdown parser (ARCHITECTURE
    section 3), citation-marker handling, sentence splitting and small text
    utilities. Imported by every other script; not meant to be run directly.

Usage
    from jf_common import user_dir, load_config, load_ledger, save_ledger, \
        next_fact_id, parse_cv_markdown, split_sentences, sha256_file

Exit codes (shared by all scripts)
    0  ok / pass
    1  check failed or validation error (see each script)
    2  blocked (ledger_check only: [CONFIRM] markers or unconfirmed facts)
    3  a required Python package is missing (the pip line is printed)
    4  usage or input error (bad arguments, unreadable file)

Running this module directly prints the resolved user directory and config, with the
value of any key, secret, token or password setting shown as ***.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_BLOCKED = 2
EXIT_DEPS = 3
EXIT_USAGE = 4

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
REFERENCES_DIR = SKILL_DIR / "references"

FACT_KINDS = (
    "contact", "headline", "summary", "role", "title", "bullet", "education", "certification",
    "skill", "project", "publication", "award", "language", "interest", "metric", "other",
)
PROVENANCES = ("cv", "user", "profile")

DEFAULT_CONFIG_TOML = """\
[locale]
default = "uk"            # uk | us
[browser]
preferred = "chrome"      # chrome (Claude in Chrome) | playwright | pane
[limits]
daily_applications = 15
hard_cap = 25
per_employer_days = 30
[paths]
user_dir = "~/.jobferret"

[sources]
enabled = ["adzuna", "reed", "nhs", "teaching", "boards", "rss", "alerts", "indeed"]
[sources.adzuna]
app_id = ""               # free at developer.adzuna.com
app_key = ""
[sources.reed]
api_key = ""              # free at reed.co.uk/developers
[sources.rss]
feeds = []                # any RSS or Atom job feed URLs
[sources.boards]
employers = []            # [{name = "Acme", platform = "greenhouse", token = "acme"}]
[sources.alerts]
extra_senders = []        # alert-email sender domains to accept beyond the built-in list
[sources.indeed]          # read in your own browser during hunt, never fetched by script
max_queries = 4           # searches per hunt (titles x places)
max_pages_per_query = 1   # result pages per search (10 jobs each)
daily_page_cap = 20       # Indeed pages per day across sessions
[hunt]
since_days = 7
top_n = 15
min_fit_pre = 40
auto_per_run = 3
[outreach]
send_via = "user"         # user | connector
follow_up_days = 6
max_touches = 2
[ux]
chattiness = "normal"     # brief | normal
"""

DEFAULT_CONFIG: dict[str, Any] = {
    "locale": {"default": "uk"},
    "browser": {"preferred": "chrome"},
    "limits": {"daily_applications": 15, "hard_cap": 25, "per_employer_days": 30},
    "paths": {"user_dir": "~/.jobferret"},
    "sources": {
        "enabled": ["adzuna", "reed", "nhs", "teaching", "boards", "rss", "alerts", "indeed"],
        "adzuna": {"app_id": "", "app_key": ""},
        "reed": {"api_key": ""},
        "rss": {"feeds": []},
        "boards": {"employers": []},
        "alerts": {"extra_senders": []},
        "indeed": {"max_queries": 4, "max_pages_per_query": 1, "daily_page_cap": 20},
    },
    "hunt": {"since_days": 7, "top_n": 15, "min_fit_pre": 40, "auto_per_run": 3},
    "outreach": {"send_via": "user", "follow_up_days": 6, "max_touches": 2},
    "ux": {"chattiness": "normal"},
}


# --------------------------------------------------------------------------- I/O

def setup_io() -> None:
    """Force UTF-8 on stdout/stderr so non-ASCII text prints on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


class JFArgumentParser(argparse.ArgumentParser):
    """argparse with usage errors mapped to exit 4 (2 is reserved for 'blocked')."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise SystemExit(EXIT_USAGE)


def make_parser(doc: str | None, prog: str | None = None) -> JFArgumentParser:
    return JFArgumentParser(
        prog=prog,
        description=doc,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def die(message: str, code: int = EXIT_USAGE) -> None:
    sys.stderr.write(f"error: {message}\n")
    raise SystemExit(code)


def emit_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def pip_line(*packages: str) -> str:
    exe = sys.executable or "python"
    if " " in exe:
        exe = f'"{exe}"'
    return f"{exe} -m pip install {' '.join(packages)}"


def require(module: str, pip_name: str | None = None):
    """Import a module or print the exact pip install line and exit 3."""
    import importlib
    try:
        return importlib.import_module(module)
    except ImportError:
        sys.stderr.write(
            f"error: the Python package '{pip_name or module}' is not installed.\n"
            f"  install it with:  {pip_line(pip_name or module)}\n"
        )
        raise SystemExit(EXIT_DEPS)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        die(f"file not found: {path}")
    except UnicodeDecodeError:
        die(f"{path} is not valid UTF-8 text")
    except OSError as exc:
        die(f"cannot read {path}: {exc}")
    return ""  # unreachable


def atomic_write_text(path: Path, text: str) -> None:
    """Write UTF-8 text via a temp file in the same directory, then replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------- paths/config

def _default_user_dir() -> Path:
    env = os.environ.get("JOBFERRET_HOME")
    if env:
        return Path(os.path.expanduser(env))
    return Path.home() / ".jobferret"


def expand_path(value: str) -> Path:
    if value.startswith("~"):
        value = str(Path.home()) + value[1:]
    return Path(value)


def user_dir() -> Path:
    """The user data directory.

    Order: $JOBFERRET_HOME, else ~/.jobferret. If that directory's config.toml
    sets [paths] user_dir to somewhere else, that location wins (one hop only).
    """
    base = _default_user_dir()
    cfg_path = base / "config.toml"
    if cfg_path.is_file():
        try:
            data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
            configured = data.get("paths", {}).get("user_dir")
            if configured and not os.environ.get("JOBFERRET_HOME"):
                return expand_path(str(configured))
        except (tomllib.TOMLDecodeError, OSError):
            pass
    return base


class ConfigError(Exception):
    pass


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | str | None = None) -> dict:
    """Defaults merged with config.toml. A missing file gives the defaults."""
    cfg_path = Path(path) if path else user_dir() / "config.toml"
    if not cfg_path.is_file():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{cfg_path} is not valid TOML: {exc}") from exc
    return _deep_merge(DEFAULT_CONFIG, data)


def find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    return None


# --------------------------------------------------------------------------- ledger

FACT_ID_RE = re.compile(r"^F\d{3,}$")


class LedgerError(Exception):
    pass


def load_ledger(path: Path | str) -> dict:
    """Load and sanity-check a ledger.json. Raises LedgerError with a readable message."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise LedgerError(f"ledger not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{p} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("facts"), list):
        raise LedgerError(f"{p} has no 'facts' list; is it a JobFerret ledger?")
    seen: set[str] = set()
    for i, fact in enumerate(data["facts"]):
        if not isinstance(fact, dict):
            raise LedgerError(f"{p}: fact #{i + 1} is not an object")
        fid = fact.get("id")
        if not isinstance(fid, str) or not FACT_ID_RE.match(fid):
            raise LedgerError(f"{p}: fact #{i + 1} has a bad id {fid!r} (expected F001 style)")
        if fid in seen:
            raise LedgerError(f"{p}: duplicate fact id {fid}")
        seen.add(fid)
    return data


def save_ledger(ledger: dict, path: Path | str) -> None:
    atomic_write_text(Path(path), json.dumps(ledger, indent=2, ensure_ascii=False) + "\n")


def ledger_index(ledger: dict) -> dict[str, dict]:
    return {f["id"]: f for f in ledger.get("facts", [])}


def next_fact_id(ledger: dict) -> str:
    nums = [int(f["id"][1:]) for f in ledger.get("facts", []) if FACT_ID_RE.match(str(f.get("id", "")))]
    return f"F{(max(nums) + 1) if nums else 1:03d}"


def new_ledger(source: dict | None = None) -> dict:
    return {"version": 1, "source": source or {}, "sections": [], "facts": []}


# ------------------------------------------------------------------ citation markers

CITATION_RE = re.compile(r"\[(F\d{3,}(?:\s*,\s*F\d{3,})*)\]")
CONFIRM_RE = re.compile(r"\[\s*(?:CONFIRM|ASK)\b\s*:?\s*([^\]]*)\]", re.IGNORECASE)
# Anything that looks like an attempted fact citation but is not well formed.
CITATION_LIKE_RE = re.compile(r"\[\s*[Ff]\s*\d[^\]]*\]|\[\s*F\d{1,2}\b[^\]]*\]|\[\s*f\d+[^\]]*\]")
ANY_MARKER_RE = re.compile(
    r"\s*(?:\[F\d{3,}(?:\s*,\s*F\d{3,})*\]|\[\s*(?:CONFIRM|ASK)\b[^\]]*\])", re.IGNORECASE
)


def find_citations(text: str) -> list[str]:
    ids: list[str] = []
    for m in CITATION_RE.finditer(text):
        ids.extend(x.strip() for x in m.group(1).split(","))
    return ids


def find_confirms(text: str) -> list[str]:
    return [m.group(1).strip() for m in CONFIRM_RE.finditer(text)]


def find_malformed_citations(text: str) -> list[str]:
    bad = []
    for m in CITATION_LIKE_RE.finditer(text):
        if not CITATION_RE.fullmatch(m.group(0)):
            bad.append(m.group(0))
    return bad


def strip_markers(text: str) -> str:
    """Remove [F012] / [F012,F041] / [CONFIRM: ...] markers and tidy spacing."""
    out = ANY_MARKER_RE.sub("", text)
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.rstrip()


# ---------------------------------------------------------------------- text utils

_ABBREV = {"e.g", "i.e", "mr", "mrs", "ms", "dr", "prof", "st", "vs", "approx", "no", "cf", "fig", "al", "nos"}
_MARK = r"\[[^\[\]]{0,300}\]"
_BOUNDARY_RE = re.compile(
    r"([.!?]+[\"'\u201d\u2019)]*(?:[ \t]*" + _MARK + r")*)(\s+)(?=[\"'\u201c\u2018(]?[A-Z0-9\u00a3$\u20ac])"
)


def split_sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) spans of sentences. A citation marker after the full stop
    stays with the sentence it follows ("...in Power Query. [F022]")."""
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _BOUNDARY_RE.finditer(text):
        before = text[start:m.start(1)]
        last_word = re.findall(r"[A-Za-z.]+$", before)
        if last_word:
            w = last_word[0].lower().rstrip(".")
            if w in _ABBREV or (len(w) == 1 and w.isalpha()):
                continue
        end = m.end(1)
        if text[start:end].strip():
            spans.append((start, end))
        start = m.end(2)
    if text[start:].strip():
        spans.append((start, len(text.rstrip())))
    # trim leading whitespace in spans
    out = []
    for s, e in spans:
        while s < e and text[s].isspace():
            s += 1
        out.append((s, e))
    return out


def split_sentences(text: str) -> list[str]:
    return [text[s:e].strip() for s, e in split_sentence_spans(text)]


WORD_RE = re.compile(r"\S*[A-Za-z0-9\u00c0-\u024f]\S*")


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<![\w/])\+?\(?\d[\d\s().-]{7,18}\d(?![\w/])")


def find_phones(text: str) -> list[str]:
    """Phone-number-like runs with 9 to 15 digits that are not date ranges."""
    out = []
    for m in PHONE_RE.finditer(text):
        cand = m.group(0)
        digits = re.sub(r"\D", "", cand)
        if not 9 <= len(digits) <= 15:
            continue
        if re.fullmatch(r"\s*(?:19|20)\d{2}\s*[-.]\s*(?:19|20)\d{2}\s*", cand):
            continue
        out.append(cand)
    return out
URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+(?:com|co\.uk|uk|io|org|net|dev|me|ai|app|info|co)(?:/[^\s|·,;]*)?",
    re.IGNORECASE,
)

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
_DATE = (r"(?:" + _MONTH + r"\s+(?:19|20)\d{2}|\d{1,2}/\d{1,2}/(?:19|20)\d{2}|\d{1,2}[/.-](?:19|20)\d{2}"
         r"|(?:19|20)\d{2}[-/]\d{1,2}(?!\d)|(?:19|20)\d{2})")
_OPEN_END = r"(?:Present|Currently|Current|Now|Today|Ongoing|Date)"
DATE_RANGE_RE = re.compile(
    r"(?P<start>" + _DATE + r")\s*(?:[\u2013\u2014-]|to|until)\s*(?P<end>" + _DATE + r"|" + _OPEN_END + r")",
    re.IGNORECASE,
)
SINGLE_DATE_RE = re.compile(r"(?<!\d)" + _DATE + r"(?!\d)", re.IGNORECASE)


def normalize_date(text: str | None) -> str | None:
    """'Mar 2022' -> '2022-03'; '2019' -> '2019'; 'Present' -> None."""
    if not text:
        return None
    t = text.strip().rstrip(".")
    if re.fullmatch(_OPEN_END, t, re.IGNORECASE):
        return None
    m = re.match(r"([A-Za-z]+)\.?\s+((?:19|20)\d{2})", t)
    if m:
        mon = MONTHS.get(m.group(1).lower()[:3])
        if mon:
            return f"{m.group(2)}-{mon:02d}"
    m = re.fullmatch(r"\d{1,2}/(\d{1,2})/((?:19|20)\d{2})", t)  # 01/06/2021 is day/month/year
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.fullmatch(r"(\d{1,2})[/.-]((?:19|20)\d{2})", t)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.fullmatch(r"((?:19|20)\d{2})-(\d{2})", t)
    if m:
        return t
    m = re.fullmatch(r"((?:19|20)\d{2})[-/](\d{1,2})", t)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r"(?:19|20)\d{2}", t)
    return m.group(0) if m else None


def is_contact_line(text: str) -> bool:
    """True for a line made only of contact details (email, phone, URL, a place)."""
    t = strip_markers(text)
    phones = find_phones(t)
    if not (EMAIL_RE.search(t) or phones or URL_RE.search(t)):
        return False
    rest = EMAIL_RE.sub(" ", t)
    rest = URL_RE.sub(" ", rest)
    for ph in phones:
        rest = rest.replace(ph, " ")
    rest = re.sub(r"[\u00b7|,;:/\u2022\-\u2013\u2014()]", " ", rest)
    words = rest.split()
    return len(words) <= 6 and not re.search(r"\d", rest)


def slugify(text: str, max_len: int = 30) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-")


# ------------------------------------------------------------ CV markdown (section 3)

ENTRY_SEP = " \u2014 "  # spaced em dash
BULLET_MD_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SKILL_LINE_RE = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s*(?P<value>.*)$")


def parse_entry_header(text: str) -> dict:
    """Split '### Title — Org | Location | Mar 2022 – Present' (without the ###)."""
    clean = strip_markers(text).strip()
    parts = [p.strip() for p in clean.split(" | ")]
    head = parts[0]
    rest = parts[1:]
    if ENTRY_SEP in head:
        title, org = head.split(ENTRY_SEP, 1)
    else:
        title, org = head, ""
    dates = ""
    location_parts = []
    for p in rest:
        if not dates and (DATE_RANGE_RE.search(p) or SINGLE_DATE_RE.fullmatch(p.strip())
                          or re.fullmatch(r"(?i)present|current", p.strip())):
            dates = p
        else:
            location_parts.append(p)
    start = end = None
    current = False
    m = DATE_RANGE_RE.search(dates) if dates else None
    if m:
        start = normalize_date(m.group("start"))
        end = normalize_date(m.group("end"))
        current = end is None
    elif dates:
        start = normalize_date(dates)
        end = start
    return {
        "title": title.strip(), "org": org.strip(), "location": ", ".join(location_parts),
        "dates": dates, "start": start, "end": end, "current": current,
    }


def _block(btype: str, line: int, raw: str, **extra) -> dict:
    b = {
        "type": btype, "line": line, "end_line": line, "raw": raw,
        "text": strip_markers(raw).strip(),
        "citations": find_citations(raw), "confirm": find_confirms(raw),
    }
    b.update(extra)
    return b


def parse_cv_markdown(text: str) -> dict:
    """Parse the ARCHITECTURE section 3 CV markdown.

    Returns {"name", "name_line", "contact", "contact_line", "preamble": [blocks],
    "sections": [{"name", "line", "blocks": [...]}], "warnings": [...]}.
    Block types: paragraph | skill | entry | bullet. Entries carry title, org,
    location, dates, start, end and "children" (bullets/paragraphs under them).
    Every block has line, end_line, raw (with markers), text (markers stripped),
    citations and confirm lists. Line numbers are 1-based.
    """
    lines = text.splitlines()
    result: dict[str, Any] = {
        "name": None, "name_line": None, "contact": None, "contact_line": None,
        "contact_citations": [], "preamble": [], "sections": [], "warnings": [],
    }
    container: list = result["preamble"]
    current_entry: dict | None = None
    last_block: dict | None = None
    expect_contact = False
    in_fence = False

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            result["warnings"].append(f"line {idx}: code fences are not part of the CV format")
            continue
        if not stripped:
            last_block = None
            continue
        if expect_contact:
            expect_contact = False
            if not stripped.startswith("#"):
                result["contact"] = strip_markers(stripped)
                result["contact_line"] = idx
                result["contact_citations"] = find_citations(stripped)
                continue
            result["warnings"].append(f"line {idx}: no contact line after the name")
        hm = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if hm:
            level = len(hm.group(1))
            content = hm.group(2).strip()
            last_block = None
            if level == 1:
                if result["name"] is not None:
                    result["warnings"].append(f"line {idx}: second H1 ignored as a name")
                    continue
                result["name"] = strip_markers(content)
                result["name_line"] = idx
                expect_contact = True
                continue
            if level == 2:
                sec = {"name": strip_markers(content), "line": idx, "blocks": []}
                result["sections"].append(sec)
                container = sec["blocks"]
                current_entry = None
                continue
            entry = _block("entry", idx, content, children=[], **parse_entry_header(content))
            if not result["sections"]:
                result["warnings"].append(f"line {idx}: entry header before any section")
            container.append(entry)
            current_entry = entry
            continue
        if stripped.startswith(("|", "<", "![")):
            result["warnings"].append(f"line {idx}: tables, HTML and images are not allowed in the CV format")
        bm = BULLET_MD_RE.match(line)
        if bm:
            content = line[bm.end():].strip()
            ordered = bool(re.match(r"^\s*\d", line))
            blk = _block("bullet", idx, content, ordered=ordered)
            (current_entry["children"] if current_entry is not None else container).append(blk)
            last_block = blk
            continue
        if last_block is not None and last_block["type"] == "bullet" and raw_line.startswith(("  ", "\t")):
            # indented continuation of a list item
            last_block["raw"] += " " + stripped
            last_block["text"] = strip_markers(last_block["raw"]).strip()
            last_block["citations"] = find_citations(last_block["raw"])
            last_block["confirm"] = find_confirms(last_block["raw"])
            last_block["end_line"] = idx
            continue
        sm = SKILL_LINE_RE.match(stripped)
        if sm:
            value = sm.group("value")
            blk = _block("skill", idx, stripped, label=sm.group("label").strip(),
                         value=strip_markers(value).strip())
            (current_entry["children"] if current_entry is not None else container).append(blk)
            last_block = blk
            continue
        if last_block is not None and last_block["type"] == "paragraph":
            last_block["raw"] += " " + stripped
            last_block["text"] = strip_markers(last_block["raw"]).strip()
            last_block["citations"] = find_citations(last_block["raw"])
            last_block["confirm"] = find_confirms(last_block["raw"])
            last_block["end_line"] = idx
            last_block["lines"].append(idx)
            continue
        blk = _block("paragraph", idx, stripped, lines=[idx])
        (current_entry["children"] if current_entry is not None else container).append(blk)
        last_block = blk

    if result["name"] is None:
        result["warnings"].append("no H1 name line found")
    return result


def iter_blocks(parsed: dict) -> Iterator[tuple[str | None, dict]]:
    """Yield (section_name, block) in document order, entries before their children."""
    for blk in parsed.get("preamble", []):
        yield None, blk
        for child in blk.get("children", []):
            yield None, child
    for sec in parsed.get("sections", []):
        for blk in sec["blocks"]:
            yield sec["name"], blk
            for child in blk.get("children", []):
                yield sec["name"], child


# ------------------------------------------------------------------------ URLs

TRACKING_PARAMS = {
    "gh_src", "source", "src", "ref", "referrer", "refid", "trk", "trackingid", "lever-source",
    "lever-origin", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "_ga", "from", "iis", "iisn",
    "ccuid", "utm", "sid", "campaign", "origin", "s", "jobsource", "codes", "ebp", "alid",
}


def canonicalize_url(url: str) -> str:
    """Stable form of a job URL for dedup: lower-case host, no www, no fragment,
    no tracking parameters, sorted query, no trailing slash, platform tweaks."""
    raw = url.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.IGNORECASE):
        raw = "https://" + raw
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    netloc = host if not port or port in (80, 443) else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS]

    if host.endswith("linkedin.com"):
        m = re.search(r"/jobs/view/(?:[^/]*?-)?(\d+)", path)
        job = m.group(1) if m else dict(query).get("currentJobId")
        if job:
            return f"https://linkedin.com/jobs/view/{job}"
    if re.search(r"(^|\.)indeed\.", host):
        jk = dict(query).get("jk") or dict(query).get("vjk")
        if jk:
            return f"https://{host}/viewjob?jk={jk}"
    if host in ("jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com"):
        path = re.sub(r"/(apply|application)/?$", "", path)
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io",
                "job-boards.eu.greenhouse.io"):
        q = dict(query)
        if path.rstrip("/").endswith("/embed/job_app") and q.get("for") and q.get("token"):
            return f"https://boards.greenhouse.io/{q['for']}/jobs/{q['token']}"
        m = re.match(r"^/([^/]+)/jobs/(\d+)", path)
        if m:
            return f"https://boards.greenhouse.io/{m.group(1)}/jobs/{m.group(2)}"
    if len(path) > 1:
        path = path.rstrip("/")
    q = urlencode(sorted(query))
    return urlunsplit(("https", netloc, path, q, ""))


# ------------------------------------------------- profile, config writing, run state

PROFILE_VERSION = 1


def empty_profile() -> dict:
    """The profile.json skeleton with every field present and correctly typed.

    Field names used by modes/apply.md and modes/cv-audit.md are kept as they
    were; the onboarding fields (targets.role_families, targets.work_modes,
    targets.radius_miles, targets.ir35, exclusions.filters, eligibility.dbs,
    eligibility.security_clearance, eligibility.driving_licence,
    exclusions.companies, personal.github, current, history, meta) are additions.
    These are the only field names. ARCHITECTURE section 8.4 lists which of them
    discovery and screening read; there are no mirror keys.
    """
    return {
        "version": PROFILE_VERSION,
        "updated_at": "",
        "personal": {"name": "", "phone": "", "email": "", "location": "", "country": "GB", "linkedin": "",
                     "github": "", "links": []},
        "eligibility": {"right_to_work": "", "sponsorship_needed_ever": False, "notice_period": "",
                        "earliest_start": "", "status": "", "dbs": "", "security_clearance": "",
                        "driving_licence": ""},
        "targets": {"titles": [], "seniority": "", "role_families": [], "sectors": [], "avoid_sectors": [],
                    "locations": [], "radius_miles": 0, "remote": "hybrid", "work_modes": [],
                    "salary_floor": {"amount": 0, "currency": "GBP", "period": "year"},
                    "contract_types": [], "ir35": ""},
        "exclusions": {"dealbreakers": [], "preferences_against": [], "companies": [],
                       "filters": {"no_agencies": False, "no_unpaid": True, "no_commission_only": True,
                                   "min_company_size": 0}},
        "answer_bank": {"why_looking": "", "skills_years": [], "licences": [], "languages": [],
                        "registrations": [], "relocate": "", "travel_max_pct": 0, "start_date": "",
                        "availability": "", "heard_about_us_default": "", "salary_phrasing": "",
                        "fixed_disclosures": {}},
        "preferences": {"cover_letter": "ask", "ai_disclosure": "drafting", "confirm_via": "chat"},
        "current": {"title": "", "employer": ""},
        "history": {"roles": [], "education": [], "highest_qualification": "", "skills": [],
                    "certifications": []},
        "meta": {"status": "draft", "prefilled_from": "", "prefilled_at": "", "prefill": {}},
    }


def profile_path() -> Path:
    return user_dir() / "profile.json"


def load_json_file(path: Path | str) -> Any:
    """Parse a UTF-8 JSON file. Raises ValueError with a readable message."""
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{p} is not valid JSON: {exc}") from exc


def load_profile(path: Path | str | None = None) -> dict:
    """profile.json merged over the skeleton, so every field exists. A missing file gives the skeleton."""
    p = Path(path) if path else profile_path()
    if not p.is_file():
        return empty_profile()
    data = load_json_file(p)
    if not isinstance(data, dict):
        raise ValueError(f"{p} does not hold a JSON object")
    return _deep_merge(empty_profile(), data)


def save_profile(profile: dict, path: Path | str | None = None) -> Path:
    """Write profile.json. There is one set of field names (empty_profile());
    discovery and screening read the same canonical fields apply.md uses."""
    p = Path(path) if path else profile_path()
    for stale in ("location", "pay", "contract_types", "dealbreakers", "exclude_companies", "skills"):
        profile.pop(stale, None)          # mirrors written by an earlier build; no longer kept
    profile.get("preferences", {}).pop("no_agency", None)
    profile.get("eligibility", {}).pop("needs_sponsorship", None)
    profile["updated_at"] = now_iso()
    atomic_write_text(p, json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    return p


def get_path(data: dict, dotted: str, default: Any = None) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_path(data: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur = data
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def is_empty_value(value: Any) -> bool:
    """True for "", None, 0, [] and {}. False is a real answer, not an empty one."""
    if value is False:
        return False
    return value is None or value == "" or value == 0 or value == [] or value == {}


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    if isinstance(value, dict):  # inline table, e.g. inside [sources.boards] employers
        return "{" + ", ".join(f"{k} = {_toml_value(v)}" for k, v in value.items()) + "}"
    raise TypeError(f"cannot write {type(value).__name__} to TOML")


def dump_toml(data: dict, _prefix: str = "") -> str:
    """Write a dict of tables as TOML: str, int, float, bool, lists of those, nested tables."""
    lines: list[str] = []
    scalars = {k: v for k, v in data.items() if not isinstance(v, dict) or not v and _prefix}
    tables = {k: v for k, v in data.items() if isinstance(v, dict)}
    if _prefix and (scalars or not tables):
        lines.append(f"[{_prefix}]")
    for key, value in scalars.items():
        lines.append(f"{key} = {_toml_value(value)}")
    for key, value in tables.items():
        sub = dump_toml(value, f"{_prefix}.{key}" if _prefix else key).rstrip("\n")
        if lines and sub:
            lines.append("")
        if sub:
            lines.append(sub)
    return "\n".join(lines) + "\n"


def update_config(updates: dict, path: Path | str | None = None) -> Path:
    """Merge `updates` into config.toml and rewrite it. Keys not in `updates` are kept.

    Comments in the file are not kept; a short header explains the main keys.
    """
    cfg_path = Path(path) if path else user_dir() / "config.toml"
    if cfg_path.is_file():
        try:
            current = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{cfg_path} is not valid TOML: {exc}") from exc
    else:
        current = copy.deepcopy(DEFAULT_CONFIG)
    merged = _deep_merge(current, updates)
    header = ("# JobFerret settings. Written by setup and the preferences page; safe to edit by hand.\n"
              "# locale.default: uk | us. browser.preferred: chrome | playwright | pane.\n\n")
    atomic_write_text(cfg_path, header + dump_toml(merged))
    return cfg_path


# Run state: where a mode got to, so the next run can offer to continue.
#   {"version": 1, "mode": "start", "step": 3, "steps_total": 7, "step_name": "Reading your CV",
#    "status": "running" | "waiting" | "done" | "stopped",
#    "started_at": ISO, "updated_at": ISO, "context": {...}}
STATE_STATUSES = ("running", "waiting", "done", "stopped")


def state_path() -> Path:
    return user_dir() / "state.json"


def load_state() -> dict | None:
    """The saved run state, or None when there is none or it can't be read."""
    p = state_path()
    if not p.is_file():
        return None
    try:
        data = load_json_file(p)
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) and data.get("mode") else None


def save_state(mode: str, step: int, *, step_name: str = "", steps_total: int | None = None,
               status: str = "running", context: dict | None = None) -> dict:
    """Record progress. The same unfinished mode keeps started_at and merges context; anything else starts fresh."""
    if status not in STATE_STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATE_STATUSES)}")
    prev = load_state() or {}
    now = now_iso()
    same = prev.get("mode") == mode and prev.get("status") not in ("done", "stopped")
    ctx = dict(prev.get("context") or {}) if same else {}
    ctx.update(context or {})
    state = {
        "version": 1,
        "mode": mode,
        "step": int(step),
        "steps_total": steps_total if steps_total is not None else (prev.get("steps_total") if same else None),
        "step_name": step_name,
        "status": status,
        "started_at": prev.get("started_at", now) if same else now,
        "updated_at": now,
        "context": ctx,
    }
    atomic_write_text(state_path(), json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return state


def clear_state() -> bool:
    p = state_path()
    if p.is_file():
        p.unlink()
        return True
    return False


def describe_state(state: dict | None) -> str:
    """One line for a returning user: 'Last run: start, step 4 of 7 (Preferences), waiting since 2026-11-02.'"""
    if not state:
        return "No unfinished run."
    when = str(state.get("updated_at", ""))[:10]
    if state.get("status") == "done":
        return f"Last run: {state['mode']} finished on {when}."
    of = f" of {state['steps_total']}" if state.get("steps_total") else ""
    name = f" ({state['step_name']})" if state.get("step_name") else ""
    return f"Last run: {state['mode']}, step {state['step']}{of}{name}, {state.get('status', 'running')} since {when}."


if __name__ == "__main__":
    setup_io()
    p = make_parser(__doc__)
    p.add_argument("--json", action="store_true", help="print as JSON")
    a = p.parse_args()
    try:
        cfg = load_config()
    except ConfigError as exc:
        die(str(exc), EXIT_FAIL)
    from jf_net import redact   # imported here: jf_net imports jf_common
    info = {"user_dir": str(user_dir()), "config": redact(cfg)}
    if a.json:
        emit_json(info)
    else:
        print(f"user dir: {info['user_dir']}")
        print(json.dumps(info["config"], indent=2))
