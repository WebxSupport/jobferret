"""Indeed UK, read in the user's own browser (research/05 section 1; decision 2026-11-03).

Input     What the browser's JavaScript action returns when it runs scripts/browse/indeed_cards.js
          on a uk.indeed.com search page (the page's own job-card data, window.mosaic
          providerData "mosaic-provider-jobcards", with a DOM fallback), or indeed_job.js on a
          /viewjob page. The model saves that JSON and runs `discover.py browse ingest`. Page
          text (get_page_text) also parses, best effort, with --text.
Auth      None for reading. Being signed in is the user's choice; the capture notes it.
Rate      Human pace, enforced here: [sources.indeed] max_queries (4), max_pages_per_query (1),
          daily_page_cap (20, ledger in ~/.jobferret/cache/browse-ledger.json). One search page
          is one request; nothing is prefetched; nothing runs unattended (hunt_cron skips it).
Tier      assist. Indeed's Job Seeker Terms (29 Sep 2026) prohibit automating Indeed Apply and
          scraping; JobFerret never fetches indeed.* by script (jf_net refuses the host) and
          never clicks through Indeed Apply (G2). Reading search pages the user opened in their
          own browser, a few per day, is the traffic Indeed is for. The risk of a challenge page
          or an account flag is the user's and the docs say so; a challenge means stop.
Apply     "Apply on company site" lands on the employer's ATS: ats_detect that URL and apply
          there (ats-form). Indeed Apply postings are assist-indeed: the user clicks.
Verified  Live on uk.indeed.com, 2026-11-03: search page fields and the viewjob
          _initialData model; fixtures in tests/fixtures/sources/browse/ are from that page.
          Query parameters q, l, radius, fromage, jt, sort, start; a pay floor as "£40,000" in q.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit

from sources._browser import caps, days_from_relative
from sources._common import (
    clean_line, contract_from_text, hours_from_text, html_to_text, iso_date, make_record, parse_salary_text,
)

SOURCE = {
    "name": "indeed", "kind": "browser", "needs_key": False, "tier": "assist", "per_title": True,
    "rate_seconds": 0, "hosts": (), "label": "Indeed (browser)",
    "board": "indeed", "host": "uk.indeed.com",
    "snippets": {"search": "browse/indeed_cards.js", "job": "browse/indeed_job.js"},
}
TRACKING_PARAMS = ("from", "tk", "vjs", "bb", "xkcb", "fccid", "vjfrom", "viewtype", "continueurl", "mvj", "spon",
                   "adid", "jobsearchtk", "astse", "assa", "pos", "asub", "advn", "vjk", "sjdu", "jsa", "mclk")
BASE = "https://uk.indeed.com/jobs"
JOB_URL = "https://uk.indeed.com/viewjob?jk={jk}"
FROMAGE = (1, 3, 7, 14)
JOB_TYPES = {"permanent": "permanent", "contract": "contract", "temporary": "temporary", "part-time": "parttime",
             "fixed-term": "contract"}
PAGE_SIZE = 10
JK = re.compile(r"^[a-f0-9]{8,32}$")
REMOTE_TYPES = {"REMOTE_ALWAYS": "remote", "REMOTE_HYBRID": "hybrid", "REMOTE_TEMPORARILY": "remote",
                "REMOTE_TEMP": "remote"}
SALARY_TYPES = {"YEARLY": ("year", 1), "ANNUAL": ("year", 1), "DAILY": ("day", 1), "HOURLY": ("hour", 1),
                "MONTHLY": ("year", 12), "WEEKLY": ("year", 52)}


# ----------------------------------------------------------------- search URLs

def fromage_for(since_days: int | None) -> int | None:
    """Indeed's 'date posted' buckets: the smallest of 1, 3, 7, 14 that covers since_days."""
    if not since_days or since_days < 1:
        return None
    for d in FROMAGE:
        if since_days <= d:
            return d
    return None


def job_type_for(contract_types: list | None) -> str | None:
    """Indeed takes one jt; use it only when the user wants exactly one kind."""
    wanted = {JOB_TYPES[c] for c in (contract_types or []) if c in JOB_TYPES}
    return next(iter(wanted)) if len(wanted) == 1 else None


def search_url(title: str, location: str | None = None, radius_miles: int | None = None,
               since_days: int | None = None, contract_types: list | None = None, salary_min=None,
               period: str | None = "year", remote: bool = False, start: int = 0) -> str:
    q = clean_line(title)
    if salary_min and (period or "year") == "year" and float(salary_min) >= 5000:
        q += f" £{int(float(salary_min)):,}"          # Indeed's own pay filter is a figure in the query
    params: list[tuple[str, str]] = [("q", q)]
    if remote:
        params.append(("l", "Remote"))
    elif location:
        params.append(("l", clean_line(location)))
        if radius_miles:
            params.append(("radius", str(int(radius_miles))))
    fa = fromage_for(since_days)
    if fa:
        params.append(("fromage", str(fa)))
    jt = job_type_for(contract_types)
    if jt:
        params.append(("jt", jt))
    params.append(("sort", "date"))
    if start:
        params.append(("start", str(int(start))))
    return BASE + "?" + urlencode(params)


def plan_urls(query: dict, creds: dict | None = None) -> list[dict]:
    """The search pages for one title: {"title", "label", "url", "page", "remote"}. Page 1 at the
    user's location, then page 1 for Remote when they want remote work, then further pages up
    to max_pages_per_query. discover.py applies max_queries and the daily cap across titles."""
    c = caps(creds)
    title = query.get("title") or ""
    if not title:
        return []
    common = dict(radius_miles=query.get("radius_miles"), since_days=query.get("since_days"),
                  contract_types=query.get("contract_types"), salary_min=query.get("salary_min"),
                  period=query.get("period"))
    modes = [m for m in (query.get("work_modes") or []) if isinstance(m, str)]
    variants: list[tuple[bool, str]] = []
    location = query.get("location")
    remote_only = modes == ["remote"]
    if location and not remote_only:
        variants.append((False, f"{title} · {location}"))
    if "remote" in modes or not location:
        variants.append((True, f"{title} · Remote"))
    out = []
    for page in range(1, c["max_pages_per_query"] + 1):
        for remote, label in variants:
            out.append({"title": title, "label": label + (f" · page {page}" if page > 1 else ""), "page": page,
                        "remote": remote,
                        "url": search_url(title, None if remote else location, remote=remote,
                                          start=(page - 1) * PAGE_SIZE, **common)})
    return out


# ----------------------------------------------------------------- cards (JSON from the snippet)

def _jk_from(card: dict) -> str | None:
    for k in ("jobkey", "jk", "id"):
        v = card.get(k)
        if isinstance(v, str) and JK.match(v.strip()):
            return v.strip()
        if isinstance(v, str) and v.startswith("job_") and JK.match(v[4:]):
            return v[4:]
    for k in ("link", "viewJobLink", "url", "href"):
        v = card.get(k)
        if isinstance(v, str):
            try:
                q = dict(parse_qsl(urlsplit(v).query))
            except ValueError:
                continue
            jk = q.get("jk") or q.get("vjk")
            if jk and JK.match(jk):
                return jk
    return None


def _salary(card: dict) -> dict:
    """min, max, currency, period, text, estimated from extractedSalary / salarySnippet / salary text."""
    out = {"min": None, "max": None, "currency": None, "period": "unknown", "text": None, "estimated": False}
    snip = card.get("salarySnippet") if isinstance(card.get("salarySnippet"), dict) else {}
    text = snip.get("text") or card.get("salary_text") or (card.get("salary") if isinstance(card.get("salary"), str) else None)
    ext = card.get("extractedSalary") if isinstance(card.get("extractedSalary"), dict) else None
    if ext is None and isinstance(card.get("salary"), dict):
        ext = card["salary"]
    if ext and (ext.get("min") is not None or ext.get("max") is not None):
        period, mult = SALARY_TYPES.get(str(ext.get("type") or "").upper(), ("unknown", 1))
        lo, hi = ext.get("min"), ext.get("max")
        lo = float(lo) * mult if isinstance(lo, (int, float)) and lo > 0 else None
        hi = float(hi) * mult if isinstance(hi, (int, float)) and hi > 0 else None
        out.update(min=lo, max=hi, currency="GBP" if (snip.get("currency") or "GBP") in ("", "GBP") else snip.get("currency"),
                   period=period)
    elif text:
        p = parse_salary_text(text)
        out.update(min=p["min"], max=p["max"], currency=p["currency"], period=p["period"])
    out["text"] = clean_line(text) or None
    est = card.get("estimatedSalary") if isinstance(card.get("estimatedSalary"), dict) else None
    est_text = (est.get("formattedRange") or est.get("text")) if est else card.get("salary_estimated")
    if est_text and not ext and not text:
        out["estimated"] = True                  # Indeed's estimate, not the advert: shown, not filtered on
        out["text"] = clean_line(str(est_text)) or None
    return out


def _job_type_labels(card: dict) -> list[str]:
    labels = [str(x) for x in (card.get("jobTypes") or []) if x]
    for group in card.get("taxonomyAttributes") or []:
        if isinstance(group, dict) and group.get("label") in ("job-types", "job-types-cc"):
            labels += [a.get("label") for a in group.get("attributes") or [] if isinstance(a, dict) and a.get("label")]
    if isinstance(card.get("job_types"), list):
        labels += [str(x) for x in card["job_types"] if x]
    seen, out = set(), []
    for l in labels:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def _remote(card: dict, location: str | None) -> str:
    model = card.get("remoteWorkModel")
    t = (model.get("type") if isinstance(model, dict) else model) or card.get("remote_type")
    if isinstance(t, str) and t.upper() in REMOTE_TYPES:
        return REMOTE_TYPES[t.upper()]
    if card.get("remoteLocation") is True or (location or "").strip().lower() == "remote":
        return "remote"
    loc = (location or "").lower()
    if loc.startswith("hybrid"):
        return "hybrid"
    if loc.startswith("remote"):
        return "remote"
    return "unknown"


def _posted(card: dict, captured_at: datetime | None) -> tuple[str | None, str | None]:
    """(posted_at ISO, relative text). pubDate (epoch ms) first; else the relative label."""
    rel = card.get("formattedRelativeTime") or card.get("relative_time")
    for k in ("pubDate", "pub_date", "posted_at", "date"):
        v = card.get(k)
        if v not in (None, "", 0):
            d = iso_date(v)
            if d:
                return d, rel
    days = days_from_relative(rel)
    if days is None:
        return None, rel
    base = captured_at or datetime.now(timezone.utc)
    return (base - timedelta(days=days)).date().isoformat(), rel


def card_to_record(card: dict, search_url_: str | None = None, page: int | None = None,
                   captured_at: datetime | None = None) -> dict | None:
    """One 8.3 record from one job card, or None for an expired card or one with no title."""
    if not isinstance(card, dict) or card.get("expired") is True:
        return None
    title = clean_line(unescape(re.sub(r"<[^>]+>", "", str(card.get("title") or card.get("displayTitle") or ""))))
    if not title:
        return None
    jk = _jk_from(card)
    company = clean_line(card.get("company") or card.get("truncatedCompany") or "") or None
    location = clean_line(card.get("formattedLocation") or card.get("location") or card.get("jobLocationCity") or "") or None
    if location and location.lower().startswith("hybrid work in "):
        location = location[len("hybrid work in "):]
    if location and location.lower().startswith("remote in "):
        location = location[len("remote in "):]
    remote = _remote(card, card.get("formattedLocation") or card.get("location"))
    if not location and remote == "remote":
        location = "Remote"
    sal = _salary(card)
    labels = _job_type_labels(card)
    contract = contract_from_text(" ".join(labels)) if labels else "unknown"
    posted_at, rel = _posted(card, captured_at)
    snippet_html = card.get("snippet") or card.get("snippet_html") or card.get("description") or ""
    description = html_to_text(str(snippet_html))
    apply_kind = card.get("apply_kind")
    if apply_kind not in ("company-site", "indeed-apply"):
        flag = card.get("indeedApplyEnabled") if "indeedApplyEnabled" in card else card.get("indeed_apply")
        if "indeedApplyEnabled" in card or "indeed_apply" in card:
            apply_kind = "indeed-apply" if flag else "company-site"
        else:
            apply_kind = "unknown"
    if card.get("from_text") and apply_kind == "company-site":
        apply_kind = "unknown"               # page text only shows "Easily apply", never the other button
    extra = {
        "board": "indeed", "board_job_id": jk, "description_is_snippet": True, "apply": apply_kind,
        "sponsored": bool(card.get("sponsored")),
        "urgently_hiring": bool(card.get("urgentlyHiring") or card.get("urgently_hiring")),
        "new": bool(card.get("newJob") or card.get("new")),
        "company_rating": card.get("companyRating", card.get("company_rating")) or None,
        "benefits": [str(b) for b in (card.get("benefits") or []) if b],
        "relative_time": rel, "salary_text": sal["text"], "salary_estimated": sal["estimated"],
        "job_types": labels, "hours": hours_from_text(" ".join(labels)) if labels else None,
        "search_url": search_url_, "page": page, "read_in": "browser",
    }
    raw = {k: v for k, v in card.items() if k not in ("snippet",)}
    return make_record(
        "indeed", source_url=JOB_URL.format(jk=jk) if jk else None, canonical_url=None, platform="indeed",
        company=company, title=title, location=location, remote=remote,
        salary_min=sal["min"], salary_max=sal["max"], currency=sal["currency"], salary_period=sal["period"],
        contract_type=contract, employer_type="unknown", posted_at=posted_at, description=description,
        raw=raw, extra=extra,
    )


def _captured_at(payload: dict) -> datetime | None:
    v = payload.get("captured_at")
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_search(payload: dict) -> list[dict]:
    """Records from a saved search-page capture ({"cards": [...], "url", "page", "captured_at"})."""
    cards = payload.get("cards") or payload.get("results") or []
    if not isinstance(cards, list):
        return []
    url = payload.get("url") if isinstance(payload.get("url"), str) else None
    page = payload.get("page") if isinstance(payload.get("page"), int) else None
    when = _captured_at(payload)
    out, seen = [], set()
    for card in cards:
        rec = card_to_record(card, url, page, when)
        if rec is None:
            continue
        key = rec["source_url"] or f"{rec['title']}|{rec['company']}"
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


# ----------------------------------------------------------------- one job page

def parse_job(payload: dict) -> dict | None:
    """A full record from an indeed_job.js capture of a /viewjob page: the whole description,
    the apply kind, and the "Apply on company site" address (an Indeed redirect, never fetched;
    the user or the model clicks it in the browser and ats_detect reads where it lands)."""
    jk = _jk_from(payload) or _jk_from({"url": payload.get("url") or ""})
    title = clean_line(payload.get("title") or "")
    if not title:
        return None
    desc_html = payload.get("description_html") or payload.get("description") or ""
    description = html_to_text(str(desc_html))
    sal = _salary(payload)
    apply = payload.get("apply") if isinstance(payload.get("apply"), dict) else {}
    apply_kind = apply.get("kind") if apply.get("kind") in ("company-site", "indeed-apply") else "unknown"
    apply_url = apply.get("url") if isinstance(apply.get("url"), str) and apply.get("url").startswith("http") else None
    location = clean_line(payload.get("location") or "") or None
    remote = _remote(payload, location)
    labels = [str(x) for x in (payload.get("job_types") or []) if x]
    posted_at = iso_date(payload.get("date_published")) if payload.get("date_published") else None
    extra = {
        "board": "indeed", "board_job_id": jk, "description_is_snippet": False, "apply": apply_kind,
        "apply_url": apply_url, "apply_url_note": "Indeed redirect; click it in the browser, never fetch it",
        "salary_text": sal["text"], "job_types": labels, "expired": bool(payload.get("expired")),
        "read_in": "browser", "logged_in": bool(payload.get("logged_in")),
    }
    return make_record(
        "indeed", source_url=JOB_URL.format(jk=jk) if jk else None, canonical_url=None, platform="indeed",
        company=clean_line(payload.get("company") or "") or None, title=title, location=location, remote=remote,
        salary_min=sal["min"], salary_max=sal["max"], currency=sal["currency"], salary_period=sal["period"],
        contract_type=contract_from_text(" ".join(labels)) if labels else "unknown", employer_type="unknown",
        posted_at=posted_at, description=description,
        raw={k: v for k, v in payload.items() if k not in ("description_html", "description", "file")}, extra=extra,
    )


# ----------------------------------------------------------------- page text (fallback)

BADGES = re.compile(r"^(easily apply|new|hiring multiple candidates|urgently hiring|responsive employer|sponsored|"
                    r"hiring ongoing|typically responds within .*|promoted)$", re.I)
TRAILER = re.compile(r"^(view all .* jobs|salary search: .*|see popular questions .*|view similar jobs.*)$", re.I)
SALARY_LINE = re.compile(r"^(up to |from )?£\s?\d", re.I)
JOB_TYPE_LINE = re.compile(r"^((full[- ]time|part[- ]time|permanent|contract|temporary|temp to perm|fixed term contract|"
                           r"fixed[- ]term|apprenticeship|internship|freelance|zero hours contract|volunteer|graduate)"
                           r"(,? ?| ?/ ?| ?\+ ?\d+)?)+$", re.I)
DATE_LINE = re.compile(r"^(just posted|today|posted .*|active \d+\+? days? ago|\d+\+? days? ago)$", re.I)
POSTCODE = r"[A-Z]{1,2}\d[A-Z\d]?(?: \d[A-Z]{2})?"
TOWN = re.compile(r"^(?:[A-Z][A-Za-z'’.-]+|upon|on|in|under|le|de|the|and|&|of|by|St\.?)(?: (?:[A-Z][A-Za-z'’.-]+|upon|on|in|"
                  r"under|le|de|the|and|&|of|by|St\.?)){0,4}(?: " + POSTCODE + r")?$")
BENEFIT_WORDS = re.compile(r"\b(pension|insurance|discount|holiday|bonus|parking|gym|childcare|wellness|assistance|"
                           r"scheme|allowance|cycle|events|canteen|programme|program)\b", re.I)


def _location_like(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 60:
        return False
    low = s.lower()
    if low == "remote" or low.startswith(("hybrid work in ", "remote in ", "hybrid work", "hybrid remote in ")):
        return True
    if SALARY_LINE.match(s) or JOB_TYPE_LINE.match(s) or BADGES.match(s) or BENEFIT_WORDS.search(s):
        return False
    return bool(TOWN.match(s))


def _title_like(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 150:
        return False
    if BADGES.match(s) or TRAILER.match(s) or SALARY_LINE.match(s) or JOB_TYPE_LINE.match(s) or DATE_LINE.match(s):
        return False
    if s.endswith(("…", ".")) and len(s) > 60:
        return False
    return True


def _card_start(lines: list[str], i: int) -> bool:
    """A title, then (after badges) a company line, then a location-like line."""
    if not _title_like(lines[i]):
        return False
    j = i + 1
    while j < len(lines) and (BADGES.match(lines[j]) or DATE_LINE.match(lines[j])):
        j += 1
    if j + 1 >= len(lines):
        return False
    company = lines[j].strip()
    # A one-word employer ("AXA", "Stagecoach") looks like a town, so the company line is only
    # checked for what it cannot be; the line after it must look like a place.
    if not company or SALARY_LINE.match(company) or JOB_TYPE_LINE.match(company) or TRAILER.match(company) \
            or BADGES.match(company) or len(company) > 120:
        return False
    return _location_like(lines[j + 1])


def _results_block(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    start = 0
    for i, ln in enumerate(lines):
        if re.match(r"^sort by:?$", ln, re.I):
            start = i + 1
            if start < len(lines) and re.match(r"^relevance\s*-\s*date$", lines[start], re.I):
                start += 1
            break
    end = len(lines)
    for i in range(start, len(lines)):
        if re.match(r"^(get email updates for|people also searched:?|job post details|return to search result)$",
                    lines[i], re.I):
            end = i
            break
    return [ln for ln in lines[start:end] if ln]


def parse_page_text(text: str, search_url_: str | None = None, captured_at: datetime | None = None) -> list[dict]:
    """Best-effort records from a search page's visible text (no job ids, so no public link; the
    snippet route is better). Each card: title, badges, company, location, [pay], [job types],
    benefit and snippet lines, trailer lines."""
    lines = _results_block(text)
    starts = [i for i in range(len(lines)) if _card_start(lines, i)]
    out: list[dict] = []
    for n, i in enumerate(starts):
        block = lines[i:(starts[n + 1] if n + 1 < len(starts) else len(lines))]
        title = block[0]
        j = 1
        badges: list[str] = []
        rel = None
        while j < len(block) and (BADGES.match(block[j]) or DATE_LINE.match(block[j])):
            (badges if BADGES.match(block[j]) else [None]).append(block[j])
            if DATE_LINE.match(block[j]):
                rel = block[j]
            j += 1
        company = block[j] if j < len(block) else None
        location = block[j + 1] if j + 1 < len(block) else None
        j += 2
        salary_text, job_types, rest = None, [], []
        while j < len(block):
            ln = block[j]
            j += 1
            if TRAILER.match(ln):
                continue
            if DATE_LINE.match(ln):
                rel = rel or ln
                continue
            if SALARY_LINE.match(ln) and salary_text is None:
                salary_text = ln
            elif JOB_TYPE_LINE.match(ln) and not job_types:
                job_types = [p.strip() for p in re.split(r"\s*\+\s*\d+|\s*/\s*|,\s*", ln) if p.strip()]
            else:
                rest.append(ln)
        card = {
            "title": title, "company": company, "location": location, "salary_text": salary_text,
            "job_types": job_types, "snippet": "\n".join(rest), "relative_time": rel,
            "sponsored": any(b.lower() == "sponsored" for b in badges), "new": any(b.lower() == "new" for b in badges),
            "indeed_apply": any(b.lower() == "easily apply" for b in badges),
            "from_text": True,
        }
        rec = card_to_record(card, search_url_, None, captured_at)
        if rec is not None:
            rec["extra"]["from_page_text"] = True
            rec["extra"]["no_public_link"] = True
            out.append(rec)
    return out


def parse_payload(payload: dict) -> list[dict]:
    """Records from any saved capture: a search snippet result, a job snippet result, or page text."""
    kind = payload.get("kind")
    if kind == "text":
        return parse_page_text(payload.get("text") or "", payload.get("url"), _captured_at(payload))
    if kind == "job":
        rec = parse_job(payload)
        return [rec] if rec else []
    return parse_search(payload)
