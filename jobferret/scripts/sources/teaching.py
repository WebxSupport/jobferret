"""Teaching Vacancies (DfE): keyless JSON API for state schools in England (research/05 section 3.2).

Endpoint  GET https://teaching-vacancies.service.gov.uk/api/v1/jobs.json?page={n}
          100 jobs a page, links.next for paging, meta.count (4,754 on 3 Nov 2026).
          Each item is a schema.org JobPosting: title, description (HTML), datePosted,
          validThrough, employmentType[], hiringOrganization, jobLocation, url, directApply.
Auth      None.
Rate      Not stated. One second between pages. Query parameters were not tested, so the
          source pages from newest to oldest and stops at the first page with nothing inside
          since_days (or at query max_pages, default 10), then keeps the jobs whose title or
          category shares a word with one of the target titles.
Tier      api. Open Government Licence, with one condition: never charge a fee for hiring
          someone found through it (terms for API users, updated 9 July 2026).
Apply     both. Some schools take applications on Teaching Vacancies, others link out;
          directApply is kept in extra.
Verified  Live 3 Nov 2026: 200 JSON, 48 pages. The fixture is an excerpt of page 1.
"""
from __future__ import annotations

import re

from sources._common import (
    SourceError, contract_from_text, first, html_to_text, iso_date, loads_json, make_record,
    parse_salary_text, within_days,
)

SOURCE = {
    "name": "teaching", "kind": "api", "needs_key": False, "tier": "api", "per_title": False, "needs_titles": True,
    "rate_seconds": 1.0, "hosts": ("teaching-vacancies.service.gov.uk",), "label": "Teaching Vacancies",
}
ENDPOINT = "https://teaching-vacancies.service.gov.uk/api/v1/jobs.json"
TRACKING_PARAMS: tuple = ()
STOP = {"and", "or", "of", "the", "a", "an", "in", "for", "to", "with", "senior", "junior", "lead", "head", "assistant"}
EMPLOYMENT = {"FULL_TIME": None, "PART_TIME": "part-time", "TEMPORARY": "temporary", "CONTRACTOR": "contract",
              "INTERN": "temporary", "PER_DIEM": "temporary"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP and len(w) > 1}


def title_matches(job: dict, titles: list[str]) -> bool:
    if not titles:
        return True
    have = _words(job.get("title", "")) | _words((job.get("occupationalCategory") or "").replace("_", " "))
    return any(_words(t) & have for t in titles)


def _location(job: dict) -> str | None:
    locs = job.get("jobLocation")
    if isinstance(locs, dict):
        locs = [locs]
    parts = []
    for loc in locs or []:
        addr = (loc or {}).get("address") or {}
        if isinstance(addr, dict):
            bits = [addr.get("addressLocality"), addr.get("postalCode")]
            text = ", ".join(b for b in bits if b)
            if text and text not in parts:
                parts.append(text)
    return "; ".join(parts) or None


def to_record(job: dict) -> dict | None:
    if not isinstance(job, dict) or not job.get("title"):
        return None
    types = [t for t in (job.get("employmentType") or []) if isinstance(t, str)]
    contract = "unknown"
    for t in types:
        mapped = EMPLOYMENT.get(t.upper())
        if mapped:
            contract = mapped
            break
    salary = {"min": None, "max": None, "currency": None, "period": "unknown", "text": None}
    base = job.get("baseSalary")
    if isinstance(base, dict):
        val = base.get("value") or {}
        unit = str(val.get("unitText") or "").upper()
        salary = {"min": val.get("minValue"), "max": val.get("maxValue"), "currency": base.get("currency"),
                  "period": {"YEAR": "year", "DAY": "day", "HOUR": "hour"}.get(unit, "unknown"), "text": None}
    elif isinstance(base, str):
        salary = parse_salary_text(base)
    org = job.get("hiringOrganization") or {}
    url = job.get("url")
    return make_record(
        "teaching",
        source_url=url, canonical_url=url, platform=None,
        company=org.get("name") if isinstance(org, dict) else None,
        title=job.get("title"),
        location=_location(job),
        salary_min=salary["min"] if isinstance(salary["min"], (int, float)) else None,
        salary_max=salary["max"] if isinstance(salary["max"], (int, float)) else None,
        currency=salary["currency"], salary_period=salary["period"],
        contract_type=contract if contract != "unknown" else contract_from_text(" ".join(types)),
        employer_type="direct",
        posted_at=iso_date(job.get("datePosted")),
        expires_at=iso_date(job.get("validThrough")),
        description=html_to_text(job.get("description") or ""),
        raw=job,
        extra={"direct_apply": job.get("directApply"), "category": job.get("occupationalCategory"),
               "employment_types": types, "salary_text": salary.get("text"),
               "school_urn": first(org.get("identifier") if isinstance(org, dict) else None)},
    )


def parse(data: dict, titles: list[str], since_days: int | None) -> tuple[list[dict], bool, str | None]:
    """Records on this page, whether any job on it was inside the window, and the next page URL."""
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise SourceError("Teaching Vacancies answered without a data list; the API may have changed")
    out, any_recent = [], False
    for job in data["data"]:
        if not isinstance(job, dict):
            continue
        posted = iso_date(job.get("datePosted"))
        if not within_days(posted, since_days):
            continue
        any_recent = True
        if not title_matches(job, titles):
            continue
        rec = to_record(job)
        if rec:
            out.append(rec)
    nxt = (data.get("links") or {}).get("next")
    return out, any_recent, nxt


def search(query: dict, creds: dict, fetch) -> list[dict]:
    titles = query.get("titles") or ([query["title"]] if query.get("title") else [])
    max_pages = max(1, int(query.get("max_pages") or 10))
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        data = loads_json(fetch(ENDPOINT, params={"page": page}, accept="application/json"), "Teaching Vacancies")
        batch, any_recent, nxt = parse(data, titles, query.get("since_days"))
        out.extend(batch)
        if not nxt or not any_recent:
            break
    return out

