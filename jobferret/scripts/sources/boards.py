"""Employer ATS boards: the public job feeds employers publish for their own careers pages
(research/05 section 3.3).

Driven by config.toml [sources.boards] employers = [{name, platform, token}]. Add one with
`discover.py boards add <name> <board-url>`. A token containing a dot is a full host
(a Teamtailor custom careers domain, a Personio .com board).

Platform         Endpoint (no key)                                                      Verified
greenhouse       GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true live 3 Nov 2026 (monzo)
lever            GET https://api.lever.co/v0/postings/{site}?mode=json                    live 3 Nov 2026 (octoenergy)
                 (token "eu:{site}" uses api.eu.lever.co)
ashby            GET https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true  live (synthesia)
workable         GET https://apply.workable.com/api/v1/widget/accounts/{subdomain}       live (huggingface)
teamtailor       GET https://{company}.teamtailor.com/jobs.rss (RSS)                      live (career.teamtailor.com)
recruitee        GET https://{company}.recruitee.com/api/offers/                          live (vilgain)
personio         GET https://{company}.jobs.personio.de/xml (XML)                         live (tado)
pinpoint         GET https://{company}.pinpointhq.com/postings.json                       live (goodlord)
smartrecruiters  GET https://api.smartrecruiters.com/v1/companies/{id}/postings           not re-tested (01 section C1)

Auth      None. These endpoints exist so careers sites can list jobs.
Rate      One second between calls to one host; one call per employer per run.
Tier      api for reading. Applying happens on the ATS form, which is grey tier: JobFerret
          fills it and the user confirms (gates G1 and G3; playbooks/<platform>.md).
Apply     on-site at the ATS. The record's canonical_url is the posting URL on the ATS, so
          hunt can go straight to apply.
Notes     A wrong token returns 404 (Personio returns an empty <workzag-jobs/>), reported as a
          per-employer error. Greenhouse's first_published against updated_at is the clearest
          repost signal; both are kept in extra. Workable's v1 widget has no description.
          One failed employer does not stop the others (PartialFailure).
Fixtures  Excerpts of the live responses above, two jobs each, descriptions truncated.
          SmartRecruiters' fixture is synthetic, from the documented shape.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit

from sources._common import (
    PartialFailure, SourceError, contract_from_text, first, hours_from_text, html_to_text, iso_date, loads_json,
    make_record, parse_salary_text, remote_from_text, within_days,
)

SOURCE = {
    "name": "boards", "kind": "board", "needs_key": False, "tier": "api", "per_title": False,
    "rate_seconds": 1.0, "hosts": (), "label": "Employer boards",
}
PLATFORMS = ("greenhouse", "lever", "ashby", "workable", "teamtailor", "recruitee", "personio", "pinpoint",
             "smartrecruiters")
TRACKING_PARAMS = ("gh_src", "gh_jid", "lever-source", "lever-origin", "utm_source", "src")


# ----------------------------------------------------------------- endpoints

def _host_or(token: str, pattern: str) -> str:
    return token if "." in token else pattern.format(token=token)


def endpoint(platform: str, token: str) -> tuple[str, dict, str]:
    """(url, params, accept) for one employer's board."""
    token = token.strip().strip("/")
    if platform == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", {"content": "true"}, "application/json"
    if platform == "lever":
        if token.startswith("eu:"):
            return f"https://api.eu.lever.co/v0/postings/{token[3:]}", {"mode": "json"}, "application/json"
        return f"https://api.lever.co/v0/postings/{token}", {"mode": "json"}, "application/json"
    if platform == "ashby":
        return (f"https://api.ashbyhq.com/posting-api/job-board/{token}", {"includeCompensation": "true"},
                "application/json")
    if platform == "workable":
        return f"https://apply.workable.com/api/v1/widget/accounts/{token}", {}, "application/json"
    if platform == "teamtailor":
        return f"https://{_host_or(token, '{token}.teamtailor.com')}/jobs.rss", {}, "application/rss+xml, application/xml"
    if platform == "recruitee":
        return f"https://{_host_or(token, '{token}.recruitee.com')}/api/offers/", {}, "application/json"
    if platform == "personio":
        return f"https://{_host_or(token, '{token}.jobs.personio.de')}/xml", {}, "application/xml"
    if platform == "pinpoint":
        return f"https://{_host_or(token, '{token}.pinpointhq.com')}/postings.json", {}, "application/json"
    if platform == "smartrecruiters":
        return f"https://api.smartrecruiters.com/v1/companies/{token}/postings", {}, "application/json"
    raise SourceError(f"unknown board platform {platform!r}; supported: {', '.join(PLATFORMS)}")


# ----------------------------------------------------------------- URL -> {platform, token}

def parse_board_url(url: str) -> dict | None:
    """{platform, token} from a careers-board URL, or None when the platform isn't recognised."""
    raw = url.strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    segs = [s for s in parts.path.split("/") if s]
    q = parse_qs(parts.query)
    if host.endswith("greenhouse.io"):
        if host.startswith("boards-api.") and len(segs) >= 3 and segs[:2] == ["v1", "boards"]:
            return {"platform": "greenhouse", "token": segs[2]}
        if segs and segs[0] == "embed" and q.get("for"):
            return {"platform": "greenhouse", "token": q["for"][0]}
        if segs:
            return {"platform": "greenhouse", "token": segs[0]}
    if host in ("jobs.lever.co", "jobs.eu.lever.co") and segs:
        return {"platform": "lever", "token": ("eu:" if ".eu." in host else "") + segs[0]}
    if host in ("api.lever.co", "api.eu.lever.co") and len(segs) >= 3:
        return {"platform": "lever", "token": ("eu:" if ".eu." in host else "") + segs[2]}
    if host == "jobs.ashbyhq.com" and segs:
        return {"platform": "ashby", "token": segs[0]}
    if host == "api.ashbyhq.com" and len(segs) >= 3:
        return {"platform": "ashby", "token": segs[-1]}
    if host == "apply.workable.com" and segs:
        if segs[0] == "api" and "accounts" in segs:
            return {"platform": "workable", "token": segs[segs.index("accounts") + 1]}
        if segs[0] != "j":
            return {"platform": "workable", "token": segs[0]}
    if host.endswith(".workable.com") and host not in ("apply.workable.com", "www.workable.com"):
        return {"platform": "workable", "token": host.split(".")[0]}
    if host.endswith(".teamtailor.com"):
        return {"platform": "teamtailor", "token": host.split(".")[0]}
    if host.endswith(".recruitee.com"):
        return {"platform": "recruitee", "token": host.split(".")[0]}
    m = re.match(r"^([a-z0-9-]+)\.jobs\.personio\.(de|com)$", host)
    if m:
        return {"platform": "personio", "token": m.group(1) if m.group(2) == "de" else host}
    if host.endswith(".pinpointhq.com"):
        return {"platform": "pinpoint", "token": host.split(".")[0]}
    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") and segs:
        return {"platform": "smartrecruiters", "token": segs[0]}
    if host == "api.smartrecruiters.com" and len(segs) >= 3 and segs[1] == "companies":
        return {"platform": "smartrecruiters", "token": segs[2]}
    return None


# ----------------------------------------------------------------- parsers

def _rec(employer: dict, platform: str, **fields) -> dict:
    fields.setdefault("company", employer.get("name"))
    fields.setdefault("employer_type", "direct")
    url = fields.get("source_url")
    return make_record("boards", platform=platform, canonical_url=url, **fields)


def parse_greenhouse(data, employer: dict) -> list[dict]:
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise SourceError("Greenhouse answered without a jobs list")
    out = []
    for j in jobs:
        if not isinstance(j, dict) or not j.get("title"):
            continue
        desc = html_to_text(html.unescape(j.get("content") or ""))
        raw = {k: v for k, v in j.items() if k != "content"}
        out.append(_rec(employer, "greenhouse",
                        source_url=j.get("absolute_url"), title=j.get("title"),
                        company=first(j.get("company_name"), employer.get("name")),
                        location=(j.get("location") or {}).get("name"),
                        remote=remote_from_text((j.get("location") or {}).get("name")) if "remote" in str(
                            (j.get("location") or {}).get("name", "")).lower() else "unknown",
                        posted_at=iso_date(first(j.get("first_published"), j.get("updated_at"))),
                        expires_at=iso_date(j.get("application_deadline")),
                        description=desc, raw=raw,
                        extra={"board_job_id": str(j.get("id") or ""), "first_published": j.get("first_published"),
                               "updated_at": j.get("updated_at"), "requisition_id": j.get("requisition_id")}))
    return out


def parse_lever(data, employer: dict) -> list[dict]:
    if not isinstance(data, list):
        raise SourceError("Lever answered without a list of postings")
    out = []
    for j in data:
        if not isinstance(j, dict) or not j.get("text"):
            continue
        cats = j.get("categories") or {}
        lists = "\n".join(f"{(l or {}).get('text', '')}\n{html_to_text((l or {}).get('content', ''))}"
                          for l in j.get("lists") or [])
        desc = "\n\n".join(x for x in (j.get("descriptionPlain"), lists, j.get("additionalPlain")) if x)
        sr = j.get("salaryRange") or {}
        period = {"per-year-salary": "year", "per-day-wage": "day", "per-hour-wage": "hour"}.get(sr.get("interval"), "unknown")
        commitment = cats.get("commitment")
        contract = contract_from_text(commitment)
        raw = {k: v for k, v in j.items() if k not in ("description", "descriptionBody", "additional", "lists",
                                                        "descriptionPlain", "descriptionBodyPlain", "additionalPlain")}
        out.append(_rec(employer, "lever",
                        source_url=j.get("hostedUrl"), title=j.get("text"),
                        location=first(cats.get("location"), ", ".join(cats.get("allLocations") or [])),
                        remote=remote_from_text(j.get("workplaceType")),
                        salary_min=sr.get("min") if isinstance(sr.get("min"), (int, float)) else None,
                        salary_max=sr.get("max") if isinstance(sr.get("max"), (int, float)) else None,
                        currency=sr.get("currency"), salary_period=period,
                        contract_type=contract if contract != "unknown" or hours_from_text(commitment) != "part-time"
                        else "part-time",
                        posted_at=iso_date(j.get("createdAt")),
                        description=html_to_text(desc), raw=raw,
                        extra={"board_job_id": j.get("id"), "apply_url": j.get("applyUrl"), "country": j.get("country"),
                               "hours": hours_from_text(commitment), "team": cats.get("team")}))
    return out


def _ashby_salary(comp: dict) -> dict:
    out = {"min": None, "max": None, "currency": None, "period": "unknown", "text": None}
    if not isinstance(comp, dict):
        return out
    for c in comp.get("summaryComponents") or []:
        if not isinstance(c, dict) or str(c.get("compensationType", "")).lower() != "salary":
            continue
        interval = str(c.get("interval") or "").upper()
        out.update({"min": c.get("minValue"), "max": c.get("maxValue"), "currency": c.get("currencyCode"),
                    "period": "year" if "YEAR" in interval else "hour" if "HOUR" in interval else
                    "day" if "DAY" in interval else "unknown"})
        break
    out["text"] = comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary")
    return out


def parse_ashby(data, employer: dict) -> list[dict]:
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise SourceError("Ashby answered without a jobs list")
    out = []
    for j in jobs:
        if not isinstance(j, dict) or not j.get("title") or j.get("isListed") is False:
            continue
        sal = _ashby_salary(j.get("compensation") or {})
        locs = [j.get("location")] + [(s or {}).get("location") for s in j.get("secondaryLocations") or []]
        etype = j.get("employmentType")
        contract = {"FullTime": "unknown", "PartTime": "part-time", "Contract": "contract",
                    "Temporary": "temporary", "Intern": "temporary"}.get(etype, contract_from_text(etype))
        raw = {k: v for k, v in j.items() if k not in ("descriptionHtml", "descriptionPlain")}
        out.append(_rec(employer, "ashby",
                        source_url=j.get("jobUrl"), title=j.get("title").strip(),
                        location="; ".join(l for l in locs if l) or None,
                        remote=remote_from_text(j.get("workplaceType")) if j.get("workplaceType") else
                        ("remote" if j.get("isRemote") else "unknown"),
                        salary_min=sal["min"] if isinstance(sal["min"], (int, float)) else None,
                        salary_max=sal["max"] if isinstance(sal["max"], (int, float)) else None,
                        currency=sal["currency"], salary_period=sal["period"],
                        contract_type=contract, posted_at=iso_date(j.get("publishedAt")),
                        description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml") or ""),
                        raw=raw,
                        extra={"board_job_id": j.get("id"), "apply_url": j.get("applyUrl"), "salary_text": sal["text"],
                               "hours": "part-time" if etype == "PartTime" else ("full-time" if etype == "FullTime" else None)}))
    return out


def parse_workable(data, employer: dict) -> list[dict]:
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise SourceError("Workable answered without a jobs list")
    out = []
    for j in jobs:
        if not isinstance(j, dict) or not j.get("title"):
            continue
        loc = ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        etype = j.get("employment_type")
        out.append(_rec(employer, "workable",
                        source_url=j.get("url") or j.get("shortlink"), title=j.get("title"),
                        company=first(data.get("name"), employer.get("name")),
                        location=loc or None,
                        remote="remote" if j.get("telecommuting") else "unknown",
                        contract_type=contract_from_text(etype) if contract_from_text(etype) != "unknown"
                        else ("part-time" if hours_from_text(etype) == "part-time" else "unknown"),
                        posted_at=iso_date(first(j.get("published_on"), j.get("created_at"))),
                        description="", raw=j,
                        extra={"board_job_id": j.get("shortcode"), "apply_url": j.get("application_url"),
                               "hours": hours_from_text(etype), "description_missing": True}))
    return out


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_teamtailor(xml_text: str, employer: dict) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise SourceError("Teamtailor did not return RSS") from None
    channel = root.find("channel")
    if channel is None:
        raise SourceError("Teamtailor's feed has no <channel>")
    out = []
    for item in channel.findall("item"):
        fields: dict = {}
        locations: list[str] = []
        for child in item:
            name = _local(child.tag)
            if name == "locations":
                for loc in child:
                    vals = {_local(c.tag): (c.text or "").strip() for c in loc}
                    text = ", ".join(v for v in (vals.get("city") or vals.get("name"), vals.get("country")) if v)
                    if text:
                        locations.append(text)
            else:
                fields[name] = (child.text or "").strip()
        if not fields.get("title"):
            continue
        raw = {k: v for k, v in fields.items() if k != "description"}
        raw["locations"] = locations
        out.append(_rec(employer, "teamtailor",
                        source_url=fields.get("link"), title=fields["title"],
                        location="; ".join(locations) or None,
                        remote=remote_from_text(fields.get("remoteStatus")),
                        posted_at=iso_date(fields.get("pubDate")),
                        description=html_to_text(fields.get("description", "")), raw=raw,
                        extra={"board_job_id": fields.get("guid"), "department": fields.get("department")}))
    return out


def parse_recruitee(data, employer: dict) -> list[dict]:
    offers = data.get("offers") if isinstance(data, dict) else None
    if not isinstance(offers, list):
        raise SourceError("Recruitee answered without an offers list")
    out = []
    for j in offers:
        if not isinstance(j, dict) or not j.get("title"):
            continue
        remote = "remote" if j.get("remote") else "hybrid" if j.get("hybrid") else "office" if j.get("on_site") else "unknown"
        sal = j.get("salary") if isinstance(j.get("salary"), dict) else {}
        smin, smax = sal.get("min"), sal.get("max")
        try:
            smin = float(smin) if smin not in (None, "") else None
            smax = float(smax) if smax not in (None, "") else None
        except (TypeError, ValueError):
            smin = smax = None
        period = {"year": "year", "yearly": "year", "annual": "year", "month": "unknown", "day": "day",
                  "daily": "day", "hour": "hour", "hourly": "hour"}.get(str(sal.get("period") or "").lower(), "unknown")
        etype = j.get("employment_type_code")
        desc = "\n\n".join(html_to_text(x) for x in (j.get("description"), j.get("requirements")) if x)
        raw = {k: v for k, v in j.items() if k not in ("description", "requirements")}
        out.append(_rec(employer, "recruitee",
                        source_url=j.get("careers_url"), title=j.get("title"),
                        company=first(j.get("company_name"), employer.get("name")),
                        location=j.get("location"), remote=remote,
                        salary_min=smin, salary_max=smax, currency=sal.get("currency"), salary_period=period,
                        contract_type=contract_from_text(etype) if contract_from_text(etype) != "unknown"
                        else ("part-time" if hours_from_text(etype) == "part-time" else "unknown"),
                        posted_at=iso_date(j.get("published_at")), expires_at=iso_date(j.get("close_at")),
                        description=desc, raw=raw,
                        extra={"board_job_id": j.get("guid") or j.get("slug"), "apply_url": j.get("careers_apply_url"),
                               "hours": hours_from_text(etype), "open_questions": bool(j.get("open_questions"))}))
    return out


def parse_personio(xml_text: str, employer: dict, token: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise SourceError("Personio did not return XML") from None
    host = token if "." in token else f"{token}.jobs.personio.de"
    out = []
    for p in root.findall("position"):
        def t(tag):
            el = p.find(tag)
            return (el.text or "").strip() if el is not None and el.text else None
        name = t("name")
        if not name:
            continue
        sal = p.find("salaryInformation")
        smin = smax = cur = None
        period = "unknown"
        if sal is not None:
            try:
                smin = float((sal.findtext("min") or "").strip()) if (sal.findtext("min") or "").strip() else None
                smax = float((sal.findtext("max") or "").strip()) if (sal.findtext("max") or "").strip() else None
            except ValueError:
                smin = smax = None
            cur = (sal.findtext("currencyCode") or "").strip() or None
            period = {"yearly": "year", "annual": "year", "daily": "day", "hourly": "hour"}.get(
                (sal.findtext("type") or "").strip().lower(), "unknown")
        descs = []
        for d in p.findall("jobDescriptions/jobDescription"):
            heading = (d.findtext("name") or "").strip()
            body = html_to_text(d.findtext("value") or "")
            descs.append(f"{heading}\n{body}".strip())
        contract = contract_from_text(t("employmentType"))
        if contract == "unknown" and hours_from_text(t("schedule")) == "part-time":
            contract = "part-time"
        pid = t("id")
        raw = {_local(c.tag): (c.text or "").strip() for c in p if _local(c.tag) not in ("jobDescriptions", "salaryInformation")}
        out.append(_rec(employer, "personio",
                        source_url=f"https://{host}/job/{pid}" if pid else None, title=name,
                        company=first(t("subcompany"), employer.get("name")),
                        location=t("office"),
                        salary_min=smin, salary_max=smax, currency=cur, salary_period=period,
                        contract_type=contract, posted_at=iso_date(t("createdAt")),
                        description="\n\n".join(descs), raw=raw,
                        extra={"board_job_id": pid, "hours": hours_from_text(t("schedule")), "keywords": t("keywords")}))
    return out


def parse_pinpoint(data, employer: dict) -> list[dict]:
    jobs = data.get("data") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise SourceError("Pinpoint answered without a data list")
    out = []
    for j in jobs:
        if not isinstance(j, dict) or not j.get("title"):
            continue
        smin, smax = j.get("compensation_minimum"), j.get("compensation_maximum")
        visible = j.get("compensation_visible") is not False
        freq = str(j.get("compensation_frequency") or "").lower()
        period = "year" if freq in ("year", "yearly", "annually", "annual", "per_annum") else \
            "day" if freq in ("day", "daily") else "hour" if freq in ("hour", "hourly") else "unknown"
        sal_text = j.get("compensation") if visible else None
        if smin is None and smax is None and sal_text:
            parsed = parse_salary_text(sal_text)
            smin, smax = parsed["min"], parsed["max"]
            period = parsed["period"] if period == "unknown" else period
        desc = "\n\n".join(html_to_text(j.get(k) or "") for k in ("description", "key_responsibilities",
                                                                  "skills_knowledge_expertise") if j.get(k))
        loc = j.get("location") or {}
        etype = j.get("employment_type")
        raw = {k: v for k, v in j.items() if k not in ("description", "key_responsibilities",
                                                        "skills_knowledge_expertise", "benefits")}
        out.append(_rec(employer, "pinpoint",
                        source_url=j.get("url"), title=j.get("title"),
                        location=first(loc.get("name"), loc.get("city")),
                        remote=remote_from_text(j.get("workplace_type")),
                        salary_min=float(smin) if isinstance(smin, (int, float)) and visible else None,
                        salary_max=float(smax) if isinstance(smax, (int, float)) and visible else None,
                        currency=j.get("compensation_currency") or ("GBP" if smin or smax else None),
                        salary_period=period,
                        contract_type=contract_from_text(etype) if contract_from_text(etype) != "unknown"
                        else ("part-time" if hours_from_text(etype) == "part-time" else "unknown"),
                        expires_at=iso_date(j.get("deadline_at")),
                        description=desc, raw=raw,
                        extra={"board_job_id": str(j.get("id") or ""), "salary_text": sal_text,
                               "hours": hours_from_text(etype)}))
    return out


def parse_smartrecruiters(data, employer: dict, token: str) -> list[dict]:
    jobs = data.get("content") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise SourceError("SmartRecruiters answered without a content list")
    out = []
    for j in jobs:
        if not isinstance(j, dict) or not j.get("name"):
            continue
        loc = j.get("location") or {}
        loc_text = first(loc.get("fullLocation"), ", ".join(x for x in (loc.get("city"), loc.get("country")) if x))
        etype = (j.get("typeOfEmployment") or {}).get("label")
        company = (j.get("company") or {}).get("name")
        out.append(_rec(employer, "smartrecruiters",
                        source_url=f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}" if j.get("id") else None,
                        title=j.get("name"), company=first(company, employer.get("name")),
                        location=loc_text or None,
                        remote="remote" if loc.get("remote") else ("hybrid" if loc.get("hybrid") else "unknown"),
                        contract_type=contract_from_text(etype) if contract_from_text(etype) != "unknown"
                        else ("part-time" if hours_from_text(etype) == "part-time" else "unknown"),
                        posted_at=iso_date(j.get("releasedDate")),
                        description="", raw=j,
                        extra={"board_job_id": j.get("id"), "ref_number": j.get("refNumber"),
                               "hours": hours_from_text(etype), "description_missing": True}))
    return out


def parse(platform: str, body: str, employer: dict) -> list[dict]:
    token = str(employer.get("token") or "")
    what = f"{platform} board for {employer.get('name') or token}"
    if platform == "teamtailor":
        return parse_teamtailor(body, employer)
    if platform == "personio":
        return parse_personio(body, employer, token)
    data = loads_json(body, what)
    return {
        "greenhouse": parse_greenhouse, "lever": parse_lever, "ashby": parse_ashby, "workable": parse_workable,
        "recruitee": parse_recruitee, "pinpoint": parse_pinpoint,
    }[platform](data, employer) if platform != "smartrecruiters" else parse_smartrecruiters(data, employer, token)


def search(query: dict, creds: dict, fetch) -> list[dict]:
    employers = query.get("employers")
    if employers is None:
        employers = creds.get("employers") or []
    if not employers:
        return []
    since = query.get("since_days_boards")      # boards list every open job; only filter when asked
    out: list[dict] = []
    errors: list[str] = []
    for emp in employers:
        if not isinstance(emp, dict):
            errors.append(f"board entry {emp!r} is not a table with name, platform and token")
            continue
        platform = str(emp.get("platform") or "").lower()
        token = str(emp.get("token") or "").strip()
        label = emp.get("name") or token
        if platform not in PLATFORMS or not token:
            errors.append(f"{label}: needs platform (one of {', '.join(PLATFORMS)}) and token")
            continue
        url, params, accept = endpoint(platform, token)
        try:
            body = fetch(url, params=params or None, accept=accept)
            recs = parse(platform, body, emp)
        except Exception as exc:          # one bad board should not cost the others
            status = getattr(exc, "status", None)
            hint = " (404 usually means the token is wrong)" if status == 404 else ""
            errors.append(f"{label} ({platform}): {exc}{hint}")
            continue
        out.extend(r for r in recs if within_days(r.get("posted_at"), since))
    if errors:
        raise PartialFailure(out, errors)
    return out
