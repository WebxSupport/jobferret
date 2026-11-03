"""RSS and Atom job feeds the user lists in config.toml [sources.rss] feeds (research/05 sections 3.5, 4).

Endpoint  Any RSS 2.0 or Atom URL, e.g. a jobs.ac.uk subject feed or an employer's
          Teamtailor feed. Entries may be plain URLs or tables {name, url}.
Auth      None. A feed that needs a login is not a feed JobFerret can use.
Rate      One request per feed per run, one second apart per host.
Tier      Depends on the site. Feeds are published to be read by software, so reading one
          is api tier; applying follows the site's own tier (ats_detect.py decides).
Apply     Through the link. Generic feeds often link to a board, not the employer, so
          records carry canonical_url None and hunt resolves the posting on shortlist.
Refuses   Any URL on NEVER_FETCH_DOMAINS (Totaljobs, CWJobs, Jobsite, Caterer, Milkround,
          LinkedIn, Indeed, Glassdoor), with a message saying why, before any request.
          The ARCHITECTURE config comment mentions CWJobs searches; since 29 Oct 2026 they
          are refused here.
Notes     Parsed with xml.etree (the bundled expat refuses entity-expansion attacks).
          Unverified feeds per 05 section 3.5: Jobserve, Technojobs, Civil Service Jobs,
          and the jobs.ac.uk URL pattern.
Verified  Parser checked against the live Teamtailor RSS (3 Nov 2026) and a synthetic Atom
          fixture.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from sources import is_never_fetch, never_fetch_message
from sources._common import PartialFailure, SourceError, html_to_text, iso_date, make_record, within_days

SOURCE = {
    "name": "rss", "kind": "feed", "needs_key": False, "tier": "api", "per_title": False,
    "rate_seconds": 1.0, "hosts": (), "label": "RSS feeds",
}
TRACKING_PARAMS: tuple = ()
ATOM = "{http://www.w3.org/2005/Atom}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _guess_company(title: str) -> tuple[str, str | None]:
    """'Data Analyst at Acme Ltd' or 'Acme Ltd: Data Analyst' -> (title, company). Conservative."""
    m = re.match(r"^(.{3,120}?)\s+at\s+([A-Z][^|]{1,80})$", title)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return title, None


def parse(xml_text: str, feed_url: str, feed_name: str | None = None, since_days: int | None = None) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceError(f"{feed_name or feed_url} is not valid RSS or Atom ({exc})") from None
    entries = []
    if _local(root.tag) == "feed":                              # Atom
        for e in root.findall(f"{ATOM}entry"):
            link = None
            for ln in e.findall(f"{ATOM}link"):
                if ln.get("rel") in (None, "alternate"):
                    link = ln.get("href")
                    break
            entries.append({
                "title": (e.findtext(f"{ATOM}title") or "").strip(),
                "link": link,
                "description": e.findtext(f"{ATOM}content") or e.findtext(f"{ATOM}summary") or "",
                "date": e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated"),
                "guid": e.findtext(f"{ATOM}id"),
                "author": e.findtext(f"{ATOM}author/{ATOM}name"),
            })
    else:                                                       # RSS 2.0 (and RDF-ish)
        items = root.findall("channel/item") or root.findall(".//item") or [
            el for el in root.iter() if _local(el.tag) == "item"]
        for it in items:
            fields = {}
            for child in it:
                fields.setdefault(_local(child.tag), (child.text or "").strip())
            entries.append({
                "title": fields.get("title", ""),
                "link": fields.get("link") or (fields.get("guid") if str(fields.get("guid", "")).startswith("http") else None),
                "description": fields.get("description") or fields.get("encoded") or "",
                "date": fields.get("pubDate") or fields.get("date"),
                "guid": fields.get("guid"),
                "author": fields.get("creator") or fields.get("author"),
                "fields": {k: v for k, v in fields.items() if k not in ("description", "encoded")},
            })
    out = []
    for e in entries:
        if not e["title"] or not e["link"] or not re.match(r"^https?://", e["link"]):
            continue
        posted = iso_date(e["date"])
        if not within_days(posted, since_days):
            continue
        title, company = _guess_company(e["title"])
        raw = {k: v for k, v in e.items() if k != "description"}
        raw["feed"] = feed_url
        out.append(make_record(
            "rss", source_url=e["link"], canonical_url=None, company=company or e.get("author") or None,
            title=title, posted_at=posted, description=html_to_text(e["description"]), raw=raw,
            extra={"feed": feed_name or feed_url, "board_job_id": e.get("guid")},
        ))
    return out


def search(query: dict, creds: dict, fetch) -> list[dict]:
    feeds = query.get("feeds")
    if feeds is None:
        feeds = creds.get("feeds") or []
    out: list[dict] = []
    errors: list[str] = []
    for f in feeds:
        url, name = (f.get("url"), f.get("name")) if isinstance(f, dict) else (str(f), None)
        if not url or not re.match(r"^https?://", url.strip(), re.I):
            errors.append(f"feed {f!r} is not an http(s) URL")
            continue
        url = url.strip()
        if is_never_fetch(url):
            errors.append(never_fetch_message(url))
            continue
        try:
            body = fetch(url, accept="application/rss+xml, application/atom+xml, application/xml, text/xml")
            out.extend(parse(body, url, name, query.get("since_days")))
        except Exception as exc:
            errors.append(f"{name or url}: {exc}")
    if errors:
        raise PartialFailure(out, errors)
    return out
