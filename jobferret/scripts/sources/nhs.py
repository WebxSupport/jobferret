"""NHS Jobs: keyless XML search (research/05 sections 3.2, 5.7).

Endpoint  GET https://www.jobs.nhs.uk/api/v1/search_xml
          params keyword, location, distance (miles), contractType, page
          Root <nhsJobs>; each <vacancyDetails> has id, reference, title, description
          (truncated), employer, type, salary (free text), closeDate, postDate, url,
          locations/location; then totalPages and totalResults. 10 results a page.
Auth      None.
Rate      Not stated. Poll gently: at most query max_pages (default 3) pages per title,
          two seconds apart.
Tier      api. No jobseeker clause on automated reading was found.
Apply     on-site through NHS Jobs (some adverts redirect to Trac or an employer site).
          ats_detect.py treats jobs.nhs.uk as assist tier: supporting statements are long
          and the user should own them.
Risk      NHSBSA's integration page lists a "Removed External Jobs Board API", so this
          endpoint may be withdrawn. Any failure here is reported as a soft error and the
          rest of the run carries on.
Notes     Adverts often say they may close early on volume; closeDate becomes expires_at so
          the digest can show it. Advert pages have no JobPosting markup.
Verified  Live 3 Nov 2026: 200, application/xml, 4,642 results for "nurse"; location and
          distance filter; sort had no visible effect. Fixture is an excerpt of that response.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from sources._common import (
    SourceError, contract_from_text, html_to_text, iso_date, make_record, parse_salary_text, within_days,
)

SOURCE = {
    "name": "nhs", "kind": "feed", "needs_key": False, "tier": "api", "per_title": True,
    "rate_seconds": 2.0, "hosts": ("www.jobs.nhs.uk",), "label": "NHS Jobs",
}
ENDPOINT = "https://www.jobs.nhs.uk/api/v1/search_xml"
TRACKING_PARAMS: tuple = ()
CONTRACT_PARAM = {"permanent": "Permanent", "fixed-term": "Fixed term", "temporary": "Bank"}


def build_params(query: dict, page: int) -> dict:
    params = {"keyword": query.get("title"), "page": page}
    if query.get("location"):
        params["location"] = query["location"]
        if query.get("radius_miles"):
            params["distance"] = int(query["radius_miles"])
    return params


def _text(el, tag: str) -> str | None:
    child = el.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip() or None


def parse(xml_text: str, since_days: int | None = None) -> tuple[list[dict], int]:
    """Records and the total page count."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise SourceError("NHS Jobs did not return XML; the feed may have been withdrawn") from None
    if root.tag != "nhsJobs":
        raise SourceError(f"NHS Jobs returned <{root.tag}>, not <nhsJobs>; the feed may have changed")
    out = []
    for v in root.findall("vacancyDetails"):
        title = _text(v, "title")
        if not title:
            continue
        posted = iso_date(_text(v, "postDate"))
        if not within_days(posted, since_days):
            continue
        sal = parse_salary_text(_text(v, "salary"))
        locs = [ (l.text or "").strip() for l in v.findall("locations/location") if (l.text or "").strip()]
        url = _text(v, "url")
        raw = {child.tag: (child.text or "").strip() for child in v if child.tag != "locations"}
        raw["locations"] = locs
        out.append(make_record(
            "nhs",
            source_url=url,
            canonical_url=url,
            platform="nhs",
            company=_text(v, "employer"),
            title=title,
            location="; ".join(locs) or None,
            salary_min=sal["min"], salary_max=sal["max"], currency=sal["currency"], salary_period=sal["period"],
            contract_type=contract_from_text(_text(v, "type")),
            employer_type="direct",
            posted_at=posted,
            expires_at=iso_date(_text(v, "closeDate")),
            description=html_to_text(_text(v, "description") or ""),
            raw=raw,
            extra={"board_job_id": _text(v, "reference"), "salary_text": sal["text"], "description_is_snippet": True},
        ))
    total = _text(root, "totalPages")
    return out, int(total) if total and total.isdigit() else 1


def search(query: dict, creds: dict, fetch) -> list[dict]:
    if not query.get("title"):
        return []
    pages = max(1, int(query.get("max_pages") or 3))
    out: list[dict] = []
    page = 1
    while page <= pages:
        text = fetch(ENDPOINT, params=build_params(query, page), accept="application/xml")
        batch, total = parse(text, query.get("since_days"))
        out.extend(batch)
        if page >= total:
            break
        page += 1
    return out
