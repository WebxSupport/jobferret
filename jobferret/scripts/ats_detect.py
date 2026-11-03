"""Identify the applicant tracking system (ATS) behind a job URL.

Purpose
    Tells the apply mode which platform a posting lives on, which automation
    tier applies (gate G2) and which playbook to read. Pure string matching on
    the URL; with --html it also sniffs a saved copy of an employer careers page
    for embedded ATS iframes, scripts and links. Never fetches anything and
    never executes anything from the page.

Usage
    ats_detect.py <url> [--html saved.html] [--json]

Output (--json)
    {"platform": "greenhouse", "tier": "grey", "playbook": "playbooks/greenhouse.md",
     "board": "acme", "job_id": "4021", "canonical_url": "...", "detected_by": "url",
     "evidence": ["host boards.greenhouse.io"], "html_candidates": []}

    tier: api | grey | assist | prohibited-automation | unknown
      grey    the user's own browser session fills the employer's ATS form;
              the user solves any challenge and approves submit (gate G1)
      assist  LinkedIn, Indeed, NHS Jobs: JobFerret prepares, the user clicks
      prohibited-automation
              Totaljobs, CWJobs, Jobsite, Caterer, Milkround, Glassdoor (every host on
              jf_net.NEVER_FETCH_DOMAINS except LinkedIn and Indeed, which stay "assist"):
              platform is the site name, playbook is playbooks/indeed-assist.md, and
              "note" says the user applies on the site. Nothing is fetched or automated.
      unknown no ATS recognised; use playbooks/generic.md
    "note" is null unless the host is on the never-fetch list (LinkedIn and Indeed get it too).
    No platform is mapped to "api" in Phase 1.

Exit codes
    0  detection ran (an unrecognised URL is platform "generic", tier "unknown")
    3  missing dependency (none expected; standard library only)
    4  usage or input error (empty or non-http URL, unreadable --html file)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from jf_common import EXIT_OK, canonicalize_url, die, emit_json, make_parser, setup_io
from jf_net import _host, never_fetch_rule  # the one list of sites that forbid automated access

PLAYBOOKS = {
    "greenhouse": "playbooks/greenhouse.md", "lever": "playbooks/lever.md",
    "ashby": "playbooks/ashby.md", "workday": "playbooks/workday.md",
    "smartrecruiters": "playbooks/smartrecruiters.md", "linkedin": "playbooks/linkedin-assist.md",
    "indeed": "playbooks/indeed-assist.md",
}
ASSIST = {"linkedin", "indeed", "nhs"}
# LinkedIn and Indeed keep tier "assist" (they have playbooks); every other never-fetch site is
# "prohibited-automation": prepare the pack, the user applies on the site.
ASSIST_PLAYBOOK_SITES = ("linkedin", "indeed")
MAX_HTML_BYTES = 5 * 1024 * 1024


def _seg(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def _result(platform: str, board: str | None = None, job_id: str | None = None,
            evidence: list[str] | None = None) -> dict:
    tier = "unknown" if platform == "generic" else ("assist" if platform in ASSIST else "grey")
    return {"platform": platform, "tier": tier,
            "playbook": PLAYBOOKS.get(platform, "playbooks/generic.md"),
            "board": board, "job_id": job_id, "evidence": evidence or []}


def detect_url(url: str) -> dict:
    parts = urlsplit(url if re.match(r"^[a-z]+://", url, re.I) else "https://" + url)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    seg = _seg(parts.path)
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    ev = [f"host {host}"]

    def first(i: int) -> str | None:
        return seg[i] if len(seg) > i else None

    # Greenhouse
    if host == "greenhouse.io" or host.endswith(".greenhouse.io") or host == "grnh.se":
        board = q.get("for") or (first(0) if first(0) not in (None, "embed") else None)
        job = q.get("token") or q.get("gh_jid")
        if "jobs" in seg and seg.index("jobs") + 1 < len(seg):
            job = seg[seg.index("jobs") + 1]
        return _result("greenhouse", board, job, ev)
    if "gh_jid" in q:
        return _result("greenhouse", None, q["gh_jid"], [f"query parameter gh_jid on {host}"])
    # Lever
    if host in ("jobs.lever.co", "jobs.eu.lever.co") or host.endswith(".lever.co"):
        return _result("lever", first(0), first(1), ev)
    # Ashby
    if host == "jobs.ashbyhq.com" or host.endswith(".ashbyhq.com"):
        return _result("ashby", first(0), first(1), ev)
    if "ashby_jid" in q:
        return _result("ashby", None, q["ashby_jid"], [f"query parameter ashby_jid on {host}"])
    # Workday
    if host.endswith(".myworkdayjobs.com") or host == "myworkdayjobs.com":
        tenant = host.split(".")[0]
        job = None
        m = re.search(r"_([A-Za-z0-9-]+)$", seg[-1]) if seg else None
        if "job" in seg and m:
            job = m.group(1)
        return _result("workday", tenant, job, ev)
    if host.endswith(".myworkdaysite.com"):
        tenant = seg[1] if len(seg) > 1 and seg[0] == "recruiting" else None
        m = re.search(r"_([A-Za-z0-9-]+)$", seg[-1]) if seg else None
        return _result("workday", tenant, m.group(1) if m and "job" in seg else None, ev)
    # SmartRecruiters
    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") or host.endswith(".smartrecruiters.com"):
        job = None
        if len(seg) > 1:
            m = re.match(r"^(\d+)", seg[1])
            job = m.group(1) if m else None
        return _result("smartrecruiters", first(0), job, ev)
    # iCIMS
    if host.endswith(".icims.com"):
        board = re.sub(r"^(?:careers|jobs|uscareers|ukcareers)-", "", host.split(".")[0])
        m = re.search(r"/jobs/(\d+)", parts.path)
        return _result("icims", board, m.group(1) if m else None, ev)
    # Taleo
    if host.endswith(".taleo.net"):
        return _result("taleo", host.split(".")[0], q.get("job"), ev)
    # Workable
    if host == "apply.workable.com":
        job = seg[seg.index("j") + 1] if "j" in seg and seg.index("j") + 1 < len(seg) else None
        return _result("workable", first(0), job, ev)
    if host.endswith(".workable.com"):
        m = re.search(r"/j(?:obs)?/([A-Za-z0-9]+)", parts.path)
        return _result("workable", host.split(".")[0], m.group(1) if m else None, ev)
    # Teamtailor
    if host.endswith(".teamtailor.com"):
        m = re.search(r"/jobs/(\d+)", parts.path)
        return _result("teamtailor", host.split(".")[0], m.group(1) if m else None, ev)
    # BambooHR
    if host.endswith(".bamboohr.com"):
        m = re.search(r"/(?:careers|jobs)/(\d+)", parts.path)
        return _result("bamboohr", host.split(".")[0], m.group(1) if m else q.get("id"), ev)
    # Pinpoint
    if host.endswith(".pinpointhq.com"):
        m = re.search(r"/postings/([A-Za-z0-9-]+)", parts.path)
        return _result("pinpoint", host.split(".")[0], m.group(1) if m else None, ev)
    # Recruitee
    if host.endswith(".recruitee.com"):
        m = re.search(r"/o/([A-Za-z0-9-]+)", parts.path)
        return _result("recruitee", host.split(".")[0], m.group(1) if m else None, ev)
    # Personio
    if re.search(r"\.jobs\.personio\.[a-z.]+$", host):
        m = re.search(r"/job/(\d+)", parts.path)
        return _result("personio", host.split(".")[0], m.group(1) if m else None, ev)
    # Jobvite
    if host in ("jobs.jobvite.com", "app.jobvite.com") or host.endswith(".jobvite.com"):
        job = seg[seg.index("job") + 1] if "job" in seg and seg.index("job") + 1 < len(seg) else q.get("j")
        return _result("jobvite", first(0) if host == "jobs.jobvite.com" else None, job, ev)
    # LinkedIn (assist)
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        if "jobs" in seg or "currentJobId" in q:
            m = re.search(r"/jobs/view/(?:[^/]*?-)?(\d+)", parts.path)
            return _result("linkedin", None, m.group(1) if m else q.get("currentJobId"), ev)
    # Indeed (assist)
    if re.search(r"(^|\.)indeed\.[a-z.]+$", host):
        return _result("indeed", None, q.get("jk") or q.get("vjk"), ev)
    # NHS Jobs / TRAC (assist)
    if host == "jobs.nhs.uk" or host.endswith(".jobs.nhs.uk"):
        m = re.search(r"/jobadvert/([A-Za-z0-9-]+)", parts.path)
        return _result("nhs", None, m.group(1) if m else None, ev)
    if host == "trac.jobs" or host.endswith(".trac.jobs"):
        m = re.search(r"/(?:vacancy|job)/([A-Za-z0-9-]+)", parts.path)
        return _result("nhs", None, m.group(1) if m else None, ev)
    return _result("generic", None, None, [f"no ATS pattern matched host {host}"])


ATS_HOST_RE = re.compile(
    r"(?:https?:)?//[a-z0-9.-]*(?:greenhouse\.io|grnh\.se|lever\.co|ashbyhq\.com|myworkdayjobs\.com|"
    r"myworkdaysite\.com|smartrecruiters\.com|icims\.com|taleo\.net|workable\.com|teamtailor\.com|"
    r"bamboohr\.com|pinpointhq\.com|recruitee\.com|jobs\.personio\.[a-z]+|jobvite\.com)[^\s\"'<>)]*",
    re.IGNORECASE,
)


def sniff_html(html: str) -> list[dict]:
    """ATS URLs found in the saved page, strongest signal first (iframe, script, form, link, text)."""
    found: list[dict] = []
    seen: set[str] = set()
    patterns = [
        ("iframe", r"<iframe\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)"),
        ("script", r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)"),
        ("form", r"<form\b[^>]*\baction\s*=\s*[\"']([^\"']+)"),
        ("link", r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"']+)"),
    ]
    for kind, pat in patterns:
        for m in re.finditer(pat, html, re.IGNORECASE):
            u = m.group(1).replace("&amp;", "&")
            if ATS_HOST_RE.search(u) and u not in seen:
                seen.add(u)
                found.append({"via": kind, "url": u})
    for m in ATS_HOST_RE.finditer(html):
        u = m.group(0).replace("&amp;", "&")
        if u not in seen:
            seen.add(u)
            found.append({"via": "text", "url": u})
    if re.search(r"Grnhse\.Iframe\.load|grnhse_app|grnhse_iframe", html):
        found.append({"via": "script", "url": "greenhouse-embed"})
    return found


def _never_fetch_overlay(url: str, res: dict) -> dict:
    """Totaljobs, CWJobs, Jobsite, Caterer, Milkround, Glassdoor, LinkedIn, Indeed: add the note, set the tier."""
    rule = never_fetch_rule(url)
    res["note"] = None
    if not rule:
        return res
    name = rule.split(".")[0]
    host = _host(url)
    res["note"] = f"{host} prohibits automated access and applying (05 §2); prepare the pack, the user applies on the site."
    if name == "indeed":
        res["note"] = (f"{host} is read in the user's browser only (never fetched by script); 'Apply on company site' "
                       "leads to the employer's ATS, Indeed Apply is the user's click (G2).")
    if name in ASSIST_PLAYBOOK_SITES:
        if res["platform"] == "generic":     # e.g. a LinkedIn profile or company page
            res.update(platform=name, tier="assist", playbook=PLAYBOOKS[name],
                       evidence=[f"host {host} is on the never-fetch list"])
        return res
    res.update(platform=name, tier="prohibited-automation", playbook=PLAYBOOKS["indeed"], board=None,
               job_id=None, evidence=[f"host {host} is on the never-fetch list"])
    return res


def detect(url: str, html: str | None = None) -> dict:
    res = _never_fetch_overlay(url, detect_url(url))
    res["canonical_url"] = canonicalize_url(url)
    res["detected_by"] = "url" if res["platform"] != "generic" else "none"
    res["html_candidates"] = []
    if html is not None:
        cands = sniff_html(html)
        res["html_candidates"] = cands[:20]
        if res["platform"] == "generic":
            for c in cands:
                if c["url"] == "greenhouse-embed":
                    sub = _result("greenhouse", None, None)
                else:
                    u = c["url"]
                    sub = detect_url("https:" + u if u.startswith("//") else u)
                if sub["platform"] != "generic":
                    keep = {"canonical_url": res["canonical_url"], "html_candidates": res["html_candidates"],
                            "note": res.get("note")}
                    res = sub
                    res.update(keep)
                    res["detected_by"] = "html"
                    res["evidence"] = [f"{c['via']} {c['url'][:200]} in the saved page"]
                    break
    return res


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="ats_detect.py")
    p.add_argument("url", help="job posting URL")
    p.add_argument("--html", help="saved HTML of the page (read only, never executed)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args(argv)
    url = a.url.strip()
    if not url or re.match(r"^(?!https?://)[a-z][a-z0-9+.-]*:", url, re.IGNORECASE):
        die("give an http(s) job URL")
    html = None
    if a.html:
        hp = Path(a.html)
        try:
            with open(hp, "rb") as fh:
                html = fh.read(MAX_HTML_BYTES).decode("utf-8", errors="replace")
        except OSError as exc:
            die(f"cannot read {hp}: {exc}")
    res = detect(url, html)
    if a.json:
        emit_json(res)
    else:
        print(f"platform: {res['platform']}  tier: {res['tier']}  playbook: {res['playbook']}")
        print(f"board: {res['board']}  job id: {res['job_id']}  detected by: {res['detected_by']}")
        print(f"canonical url: {res['canonical_url']}")
        if res.get("note"):
            print(f"note: {res['note']}")
        for e in res["evidence"]:
            print(f"  evidence: {e}")
        if res["html_candidates"] and res["detected_by"] != "html":
            print("  ATS links in the saved page (possible apply-at-source routes):")
            for c in res["html_candidates"][:5]:
                print(f"    {c['via']}: {c['url'][:120]}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
