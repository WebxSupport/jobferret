"""Adzuna: UK aggregator with a free REST API (research/05 section 3.1).

Endpoint  GET https://api.adzuna.com/v1/api/jobs/gb/search/{page}
          params app_id, app_key, what, where, distance (km), max_days_old,
          results_per_page (50), sort_by=date, salary_min, content-type=application/json
Auth      app_id and app_key as query parameters. Free key at developer.adzuna.com.
          A keyless call returns 400 (checked live 3 Nov 2026).
Rate      The free tier is "intended for evaluating the API". The 2024 terms said
          25 calls a minute and 250 a day; plan for that until the user's dashboard says
          otherwise. One page per title per run, 2.5 seconds between calls.
Tier      api. Commercial use needs a licence; personal use with the user's own key is
          the evaluation tier.
Apply     redirect. redirect_url is an Adzuna tracking link that forwards to the source
          board or employer. Scripts never follow it: records carry canonical_url None and
          hunt resolves the posting when the user shortlists it (ARCHITECTURE 8.3).
Notes     description is a snippet (about 500 characters), not the advert.
          salary_is_predicted = 1 means Adzuna estimated the salary; it is kept in
          extra.salary_estimate, never as disclosed pay (05 section 5.1).
Verified  Endpoint, parameters and Job fields from Adzuna's OpenAPI spec, read live
          3 Nov 2026. Search responses not seen (needs a key); the fixture is synthetic.
"""
from __future__ import annotations

from sources._common import (
    SourceError, contract_from_text, hours_from_text, iso_date, loads_json, make_record, within_days,
)

SOURCE = {
    "name": "adzuna", "kind": "api", "needs_key": True, "tier": "api", "per_title": True,
    "key_fields": ("app_id", "app_key"), "key_help": "free at https://developer.adzuna.com (sign up, then copy app_id and app_key)",
    "rate_seconds": 2.5, "hosts": ("api.adzuna.com",), "label": "Adzuna",
}
ENDPOINT = "https://api.adzuna.com/v1/api/jobs/gb/search/{page}"
TRACKING_PARAMS = ("se", "v")           # per-impression values on redirect_url; utm_* go anyway
RESULTS_PER_PAGE = 50


def build_params(query: dict, creds: dict) -> dict:
    params = {
        "app_id": creds.get("app_id"), "app_key": creds.get("app_key"),
        "what": query.get("title"), "results_per_page": RESULTS_PER_PAGE, "sort_by": "date",
        "content-type": "application/json",
    }
    if query.get("location"):
        params["where"] = query["location"]
        if query.get("radius_miles"):
            params["distance"] = max(1, round(float(query["radius_miles"]) * 1.609))
    if query.get("since_days"):
        params["max_days_old"] = int(query["since_days"])
    return params


def parse(data: dict, since_days: int | None = None) -> list[dict]:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise SourceError("Adzuna answered without a results list; the key may be wrong or the API changed")
    out = []
    for job in data["results"]:
        if not isinstance(job, dict) or not job.get("title"):
            continue
        posted = iso_date(job.get("created"))
        if not within_days(posted, since_days):
            continue
        predicted = str(job.get("salary_is_predicted", "0")) == "1"
        smin, smax = job.get("salary_min"), job.get("salary_max")
        extra = {"board_job_id": str(job.get("id") or ""), "adref": job.get("adref"),
                 "category": (job.get("category") or {}).get("label"), "description_is_snippet": True,
                 "hours": hours_from_text(job.get("contract_time"))}
        if predicted:
            extra["salary_estimate"] = {"min": smin, "max": smax, "source": "Adzuna estimate, not from the advert"}
            smin = smax = None
        contract = contract_from_text(job.get("contract_type"))
        if contract == "unknown" and extra["hours"] == "part-time":
            contract = "part-time"
        out.append(make_record(
            "adzuna",
            source_url=job.get("redirect_url"),
            canonical_url=None,
            company=(job.get("company") or {}).get("display_name"),
            title=job.get("title"),
            location=(job.get("location") or {}).get("display_name"),
            salary_min=float(smin) if isinstance(smin, (int, float)) else None,
            salary_max=float(smax) if isinstance(smax, (int, float)) else None,
            currency="GBP" if (smin or smax) else None,
            salary_period="year" if (smin or smax) else "unknown",
            contract_type=contract,
            posted_at=posted,
            description=job.get("description") or "",
            raw=job,
            extra=extra,
        ))
    return out


def search(query: dict, creds: dict, fetch) -> list[dict]:
    if not (creds.get("app_id") and creds.get("app_key")):
        raise SourceError("Adzuna needs app_id and app_key in config.toml [sources.adzuna]")
    if not query.get("title"):
        return []
    pages = max(1, int(query.get("max_pages") or 1))
    out: list[dict] = []
    for page in range(1, pages + 1):
        text = fetch(ENDPOINT.format(page=page), params=build_params(query, creds), accept="application/json")
        data = loads_json(text, "Adzuna")
        out.extend(parse(data, query.get("since_days")))
        if len(data.get("results") or []) < RESULTS_PER_PAGE:
            break
    return out
