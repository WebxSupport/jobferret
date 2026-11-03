"""Home Office register of licensed sponsors (Worker and Temporary Worker routes).

Reference data for screen.py, not a job source (research/05 finding 10, sections 3.2, 5.5).

Endpoint  GET https://www.gov.uk/api/content/government/publications/register-of-licensed-sponsors-workers
          -> details.attachments[] with content_type text/csv. The CSV's URL and file name
          change every day, so it is resolved through the Content API each time.
          CSV columns: Organisation Name, Town/City, County, Type & Rating, Route.
Auth      None. Open Government Licence.
Size      About 11 MB (2 Nov 2026). Both calls are cached for seven days through jf_net, and
          offline the cached copy is used whatever its age.
Tier      api (reference data).
Matching  Names are normalised: case, "&" and "and", punctuation, and suffixes such as Ltd,
          Limited, plc, LLP, UK, Group, Holdings are ignored. "X Ltd T/A Y" registers both
          X and Y. Only an exact match on the normalised name counts.
Answers   is_sponsor(name) -> "yes" | "no" | "unknown". "unknown" when the register could not
          be loaded or the name is empty or generic ("our client", "confidential"). A "no"
          can be a name mismatch (trading names vary), which is why screen.py only flags it.
          Holding a licence does not mean this role qualifies: the user checks the current
          Skilled Worker rules on gov.uk.
Verified  Live 3 Nov 2026: Content API 200, CSV attachment text/csv, header row read.
          The fixture is a five-row synthetic register with the real header.
"""
from __future__ import annotations

import csv
import io
import json
import re

CONTENT_API = "https://www.gov.uk/api/content/government/publications/register-of-licensed-sponsors-workers"
CACHE_TTL = 7 * 24 * 3600
SUFFIXES = re.compile(r"\b(?:ltd|limited|plc|llp|llc|lp|inc|cic|co|company|uk|gb|group|holdings|the)\b")
GENERIC = re.compile(r"^(?:our client|my client|client|confidential|a leading|an? \w+ (?:company|firm|business)|"
                     r"undisclosed|private client|n/?a|none|unknown)$")

_register: dict | None = None


def normalise(name: str | None) -> str:
    s = (name or "").casefold().replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = SUFFIXES.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _names(org: str) -> list[str]:
    parts = re.split(r"\s+(?:t/a|t\\a|trading as|ta)\s+", org.strip(), flags=re.I)
    return [p for p in (normalise(x) for x in parts) if p]


def csv_url(content: dict) -> str | None:
    for a in (content.get("details") or {}).get("attachments") or []:
        url = (a or {}).get("url") or ""
        if (a.get("content_type") == "text/csv" or url.lower().endswith(".csv")) and url.startswith("https://"):
            return url
    return None


def parse_register(text: str) -> dict:
    """{normalised name: [towns]} from the register CSV."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    fields = reader.fieldnames or []
    name_col = next((f for f in fields if "organisation" in f.lower()), None)
    town_col = next((f for f in fields if "town" in f.lower()), None)
    if not name_col:
        raise ValueError("the register CSV has no Organisation Name column")
    index: dict[str, list[str]] = {}
    for row in reader:
        org = (row.get(name_col) or "").strip()
        if not org:
            continue
        town = (row.get(town_col) or "").strip() if town_col else ""
        for n in _names(org):
            towns = index.setdefault(n, [])
            if town and town not in towns:
                towns.append(town)
    return index


def load_register(fetch_text=None, refresh: bool = False) -> dict | None:
    """The register index, or None when it cannot be had (offline with nothing cached, or an error)."""
    global _register
    if _register is not None and not refresh:
        return _register
    if fetch_text is None:
        import jf_net
        fetch_text = jf_net.fetch_text
    try:
        content = json.loads(fetch_text(CONTENT_API, accept="application/json", cache_ttl=CACHE_TTL))
        url = csv_url(content)
        if not url:
            return None
        _register = parse_register(fetch_text(url, accept="text/csv", cache_ttl=CACHE_TTL))
        return _register
    except Exception:
        return None


def set_register(index: dict | None) -> None:
    """Tests and callers that already hold an index."""
    global _register
    _register = index


def is_sponsor(company_name: str | None, register: dict | None = None, fetch_text=None) -> str:
    name = normalise(company_name)
    if not name or GENERIC.match(name) or GENERIC.match((company_name or "").strip().lower()):
        return "unknown"
    reg = register if register is not None else load_register(fetch_text)
    if reg is None:
        return "unknown"
    return "yes" if name in reg else "no"
