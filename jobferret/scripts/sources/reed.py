"""Reed: the one large UK board with an open jobseeker API (research/05 sections 2.2, 3.1).

Endpoint  GET https://www.reed.co.uk/api/1.0/search
          params keywords, locationName, distanceFromLocation (miles), resultsToTake (max 100),
          resultsToSkip, postedByRecruitmentAgency, postedByDirectEmployer
          GET https://www.reed.co.uk/api/1.0/jobs/{jobId}  (detail: externalUrl, salaryType,
          contractType, yearlyMinimumSalary, expirationDate, jobUrl)
Auth      HTTP Basic, the API key as username and an empty password. Free key at
          reed.co.uk/developers. A keyless call returns 401 with WWW-Authenticate: Basic
          (checked live 3 Nov 2026).
Rate      None published. One second between calls; detail calls capped per search
          (query max_details, default 20).
Tier      api. Reed's terms forbid only commercial copying; robots.txt allows AI crawlers
          outside /api/.
Apply     both. On-site quick apply with a Reed profile, or off-site when the detail has
          externalUrl. With externalUrl the record's canonical_url is that URL; a Reed-hosted
          job's canonical_url is its Reed jobUrl; a job whose detail was not fetched keeps
          canonical_url None until hunt resolves it.
Agency    Each title is searched twice, once with postedByDirectEmployer=true and once with
          postedByRecruitmentAgency=true, so every record knows its employer_type. With
          query no_agencies only the direct search runs.
Notes     Search fields from the docs; date, expirationDate, jobUrl and currency come from
          third-party clients (unverified). Salary fields are absent when hidden on the site.
          An unknown job id returns a blank job, not a 404.
Verified  Auth shape live 3 Nov 2026; data not seen (needs a key). The fixture is synthetic,
          built from the documented fields.
"""
from __future__ import annotations

from sources._common import (
    SourceError, contract_from_text, first, html_to_text, infer_period, iso_date, loads_json, make_record,
    within_days,
)

SOURCE = {
    "name": "reed", "kind": "api", "needs_key": True, "tier": "api", "per_title": True,
    "key_fields": ("api_key",), "key_help": "free at https://www.reed.co.uk/developers (sign in, request a jobseeker API key)",
    "rate_seconds": 1.0, "hosts": ("www.reed.co.uk",), "label": "Reed",
}
SEARCH = "https://www.reed.co.uk/api/1.0/search"
DETAIL = "https://www.reed.co.uk/api/1.0/jobs/{job_id}"
TRACKING_PARAMS = ("source", "sp")
PAGE = 100
SALARY_TYPES = {"per annum": "year", "per year": "year", "per day": "day", "per hour": "hour"}


def search_params(query: dict, posted_by: str) -> dict:
    params = {"keywords": query.get("title"), "resultsToTake": PAGE}
    if query.get("location"):
        params["locationName"] = query["location"]
        if query.get("radius_miles"):
            params["distanceFromLocation"] = int(query["radius_miles"])
    params["postedByDirectEmployer" if posted_by == "direct" else "postedByRecruitmentAgency"] = "true"
    return params


def _salary_period(detail: dict, smin, smax) -> tuple[str, bool]:
    st = str(detail.get("salaryType") or "").strip().lower()
    if st in SALARY_TYPES:
        return SALARY_TYPES[st], False
    if smin is None and smax is None:
        return "unknown", False
    return infer_period(smax if smax is not None else smin), True


def to_record(item: dict, employer_type: str, detail: dict | None = None) -> dict | None:
    detail = detail if isinstance(detail, dict) and detail.get("jobId") else {}
    title = first(detail.get("jobTitle"), item.get("jobTitle"))
    if not title:
        return None
    smin = first(item.get("minimumSalary"), detail.get("minimumSalary"))
    smax = first(item.get("maximumSalary"), detail.get("maximumSalary"))
    smin = float(smin) if isinstance(smin, (int, float)) else None
    smax = float(smax) if isinstance(smax, (int, float)) else None
    period, inferred = _salary_period(detail, smin, smax)
    job_url = first(detail.get("jobUrl"), item.get("jobUrl")) or f"https://www.reed.co.uk/jobs/job/{item.get('jobId')}"
    external = detail.get("externalUrl") or None
    canonical = external or (job_url if detail else None)
    contract = contract_from_text(detail.get("contractType"))
    if contract == "unknown" and str(detail.get("jobType") or "").lower().startswith("part"):
        contract = "part-time"
    extra = {"board_job_id": str(item.get("jobId") or ""), "applications": item.get("applications"),
             "detail_fetched": bool(detail), "apply": "off-site" if external else ("on-site" if detail else "not known"),
             "salary_period_inferred": inferred,
             "yearly_salary": {"min": detail.get("yearlyMinimumSalary"), "max": detail.get("yearlyMaximumSalary")}
             if detail.get("yearlyMinimumSalary") or detail.get("yearlyMaximumSalary") else None}
    return make_record(
        "reed",
        source_url=job_url,
        canonical_url=canonical,
        platform=None,
        company=first(detail.get("employerName"), item.get("employerName")),
        title=title,
        location=first(detail.get("locationName"), item.get("locationName")),
        salary_min=smin, salary_max=smax,
        currency=first(item.get("currency"), detail.get("currency"), "GBP" if (smin or smax) else None),
        salary_period=period,
        contract_type=contract,
        employer_type=employer_type,
        posted_at=iso_date(first(detail.get("datePosted"), item.get("date"))),
        expires_at=iso_date(first(detail.get("expirationDate"), item.get("expirationDate"))),
        description=html_to_text(first(detail.get("jobDescription"), item.get("description")) or ""),
        raw={"search": item, "detail": detail or None},
        extra=extra,
    )


def search(query: dict, creds: dict, fetch) -> list[dict]:
    key = (creds.get("api_key") or "").strip()
    if not key:
        raise SourceError("Reed needs api_key in config.toml [sources.reed]")
    if not query.get("title"):
        return []
    auth = (key, "")
    since = query.get("since_days")
    budget = int(query.get("max_details", 20))
    kinds = ("direct",) if query.get("no_agencies") else ("direct", "agency")
    out: list[dict] = []
    seen: set = set()
    for kind in kinds:
        text = fetch(SEARCH, params=search_params(query, kind), auth=auth, accept="application/json")
        data = loads_json(text, "Reed")
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            raise SourceError("Reed answered without a results list; check the API key")
        for item in results:
            if not isinstance(item, dict) or item.get("jobId") in seen:
                continue
            if not within_days(iso_date(item.get("date")), since):
                continue
            seen.add(item.get("jobId"))
            detail = None
            if budget > 0 and item.get("jobId"):
                budget -= 1
                try:
                    detail = loads_json(fetch(DETAIL.format(job_id=item["jobId"]), auth=auth, accept="application/json"),
                                        "Reed job detail")
                except Exception:          # a failed detail call costs the extra fields, not the job
                    detail = None
            rec = to_record(item, "direct" if kind == "direct" else "agency", detail)
            if rec:
                out.append(rec)
    return out
