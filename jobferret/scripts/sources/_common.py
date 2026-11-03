"""Helpers shared by the source modules: record shape, text clean-up, dates, salary text.

A source returns records in the shape of ARCHITECTURE.md section 8.3. make_record()
fills every field so a source only sets what it knows. Two keys go beyond 8.3 and
never reach the database row: "extra" (JobFerret's own notes on the record, such as
the salary text or the board's job id) and "raw" (the source's own record). discover.py
saves both in the job file at jd_path.

Nothing in this module opens a socket. Sources call the fetch callable they are given.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

RECORD_FIELDS = (
    "source", "source_url", "canonical_url", "platform", "company", "title", "location", "remote",
    "salary_min", "salary_max", "currency", "salary_period", "contract_type", "employer_type",
    "posted_at", "expires_at", "description", "raw", "extra",
)
REMOTE = ("remote", "hybrid", "office", "unknown")
PERIODS = ("year", "day", "hour", "unknown")
CONTRACTS = ("permanent", "contract", "fixed-term", "temporary", "part-time", "unknown")
EMPLOYER_TYPES = ("direct", "agency", "unknown")
DESCRIPTION_MAX = 20000


class SourceError(Exception):
    """A source could not run. The message is shown to the user, so keep it plain."""


class PartialFailure(SourceError):
    """Some parts of a source worked and some did not (one employer board of five failed).

    discover.py keeps .records and reports .errors.
    """

    def __init__(self, records: list[dict], errors: list[str]):
        self.records = records
        self.errors = errors
        super().__init__("; ".join(errors))


def make_record(source: str, **fields) -> dict:
    rec = {k: None for k in RECORD_FIELDS}
    rec.update({"source": source, "remote": "unknown", "salary_period": "unknown", "contract_type": "unknown",
                "employer_type": "unknown", "description": "", "raw": {}, "extra": {}})
    for k, v in fields.items():
        if k not in RECORD_FIELDS:
            raise KeyError(f"not a record field: {k}")
        if v is not None:
            rec[k] = v
    for k in ("company", "title", "location"):
        if isinstance(rec[k], str):
            rec[k] = clean_line(rec[k]) or None
    rec["description"] = (rec["description"] or "")[:DESCRIPTION_MAX]
    return rec


def validate_record(rec: dict) -> list[str]:
    """Problems with a record, empty when it is valid. Used by the tests and by discover.py."""
    problems = []
    missing = [k for k in RECORD_FIELDS if k not in rec]
    if missing:
        problems.append(f"missing fields: {', '.join(missing)}")
    extra = [k for k in rec if k not in RECORD_FIELDS]
    if extra:
        problems.append(f"unknown fields: {', '.join(extra)}")
    if not rec.get("title"):
        problems.append("no title")
    for name, allowed in (("remote", REMOTE), ("salary_period", PERIODS), ("contract_type", CONTRACTS),
                          ("employer_type", EMPLOYER_TYPES)):
        if rec.get(name) not in allowed:
            problems.append(f"{name} {rec.get(name)!r} not in {allowed}")
    for name in ("salary_min", "salary_max"):
        v = rec.get(name)
        if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0):
            problems.append(f"{name} {v!r} is not a non-negative number")
    for name in ("posted_at", "expires_at"):
        v = rec.get(name)
        if v is not None and not re.match(r"^\d{4}-\d{2}-\d{2}", str(v)):
            problems.append(f"{name} {v!r} is not an ISO date")
    for name in ("source_url", "canonical_url"):
        v = rec.get(name)
        if v is not None and not re.match(r"^https?://", str(v)):
            problems.append(f"{name} {v!r} is not an http(s) URL")
    if not isinstance(rec.get("raw"), (dict, list)):
        problems.append("raw is not a dict or list")
    if not isinstance(rec.get("extra"), dict):
        problems.append("extra is not a dict")
    return problems


# --------------------------------------------------------------------- text

class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table",
             "section", "article", "header", "footer", "blockquote", "pre", "hr"}
    SKIP = {"script", "style", "noscript", "template", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(text: str | None) -> str:
    """Plain text from an HTML fragment (or text that is already plain)."""
    if not text:
        return ""
    if "<" not in text and "&" not in text:
        return normalise_text(text)
    parser = _TextExtractor()
    try:
        parser.feed(text)
        parser.close()
        out = "".join(parser.parts)
    except Exception:
        out = re.sub(r"<[^>]+>", " ", html.unescape(text))
    return normalise_text(out)


def normalise_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[​-‏⁠﻿]", "", text)          # zero-width characters
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    out: list[str] = []
    for ln in lines:
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


def clean_line(text: str | None) -> str:
    """One line of display text: no newlines, collapsed spaces, at most 200 characters."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(text))).strip()[:200]


# --------------------------------------------------------------------- dates

def iso_date(value) -> str | None:
    """ISO 8601 (UTC, seconds) from the shapes sources use, or None.

    Accepts ISO strings, 'YYYY-MM-DD HH:MM:SS UTC', RFC 822 (RSS), 'dd/mm/yyyy' (Reed)
    and epoch milliseconds (Lever).
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        secs = value / 1000 if value > 10**11 else value
        return datetime.fromtimestamp(secs, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    s = str(value).strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date().isoformat()
        except ValueError:
            return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    t = s.replace(" UTC", "Z").replace(" ", "T", 1) if re.match(r"^\d{4}-\d{2}-\d{2} \d", s) else s
    t = re.sub(r"(\.\d{6})\d+", r"\1", t)                        # NHS sends nanoseconds
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(s)
        except (TypeError, ValueError, IndexError):
            m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
            return m.group(1) if m else None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    s = str(value)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        s += "T00:00:00Z"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def within_days(posted_at: str | None, since_days: int | None, now: datetime | None = None) -> bool:
    """True when the posting date is unknown or no older than since_days (plus a day of slack)."""
    if not since_days or since_days <= 0:
        return True
    dt = parse_iso(posted_at)
    if dt is None:
        return True
    now = now or datetime.now(timezone.utc)
    return dt >= now - timedelta(days=since_days + 1)


# --------------------------------------------------------------------- salary and labels

_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k)?"


def _num(m_num: str, k: str | None) -> float:
    v = float(m_num.replace(",", ""))
    return v * 1000 if k else v


def parse_salary_text(text: str | None) -> dict:
    """Best-effort read of a UK salary string: '£39959.00 to £48117.00', '£35k-£42k',
    'up to £50,000', '£550 per day', 'Negotiable'. Returns min, max, currency, period, text."""
    out = {"min": None, "max": None, "currency": None, "period": "unknown", "text": clean_line(text) or None}
    if not text:
        return out
    s = text.lower().replace("gbp", "£")
    nums = [(_num(n, k)) for n, k in re.findall(r"£\s*" + _NUM, s)]
    if not nums:
        return out
    out["currency"] = "GBP"
    if re.search(r"\bper\s+hour\b|\d\s*p/?h\b|/\s*h(?:ou)?r\b|\bhourly\b|\ban hour\b", s):
        out["period"] = "hour"
    elif re.search(r"\bper\s+day\b|\d\s*p/?d\b|/\s*day\b|\bday rate\b|\ba day\b|\bdaily\b", s):
        out["period"] = "day"
    elif re.search(r"\bper\s+annum\b|\bp\.?a\.?\b|\ba year\b|\bper year\b|\bannual", s) or max(nums) >= 5000:
        out["period"] = "year"
    if re.search(r"\bup to\b", s) and len(nums) == 1:
        out["max"] = nums[0]
    elif re.search(r"\bfrom\b", s) and len(nums) == 1:
        out["min"] = nums[0]
    else:
        out["min"], out["max"] = min(nums[:2]), max(nums[:2])
    return out


def infer_period(amount: float | None) -> str:
    """Guess the pay period of a bare UK figure: under 100 is hourly, under 2,000 a day rate."""
    if amount is None:
        return "unknown"
    if amount < 100:
        return "hour"
    if amount < 2000:
        return "day"
    return "year"


def contract_from_text(text: str | None) -> str:
    """Map an ATS or board employment-type label to the 8.3 contract_type."""
    s = re.sub(r"[_\-]+", " ", (text or "").lower()).strip()
    if not s:
        return "unknown"
    if re.search(r"fixed ?term|ftc|maternity|secondment", s):
        return "fixed-term"
    if re.search(r"\btemp|temporary|seasonal|bank\b|locum|casual|zero hours", s):
        return "temporary"
    if re.search(r"contract|freelance|interim|contractor", s):
        return "contract"
    if re.search(r"permanent|\bperm\b", s):
        return "permanent"
    if re.search(r"part ?time", s):
        return "part-time"
    return "unknown"


def hours_from_text(text: str | None) -> str | None:
    s = re.sub(r"[_\-]+", " ", (text or "").lower())
    if re.search(r"part ?time", s):
        return "part-time"
    if re.search(r"full ?time", s):
        return "full-time"
    return None


def remote_from_text(text: str | None) -> str:
    s = re.sub(r"[_\-]+", " ", (text or "").lower()).strip()
    if not s or s in ("unspecified", "none", "null"):
        return "unknown"
    if "hybrid" in s:
        return "hybrid"
    if "remote" in s or s in ("telecommute", "fully remote", "home based", "true"):
        return "remote"
    if re.search(r"on ?site|onsite|office|in person|in office|false", s):
        return "office"
    return "unknown"


def loads_json(text: str, what: str):
    try:
        return json.loads(text)
    except (TypeError, ValueError) as exc:
        raise SourceError(f"{what} did not return JSON ({exc.__class__.__name__}); the endpoint may have changed") from None


def first(*values):
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None
