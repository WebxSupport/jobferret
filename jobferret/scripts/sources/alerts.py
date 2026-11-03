"""Job-alert emails the user saves into ~/.jobferret/inbox/ (research/05 section 4).

Input     .eml (a saved email, best: the sender can be checked), .txt or .html (a pasted
          body; no sender to check, so the record says so). Parsed with the email stdlib
          module. Nothing is fetched: this source never opens a socket.
Auth      None. Reading the user's own inbox is not access to the board.
Rate      Not applicable.
Tier      Data only. Each job keeps its board's own tier: LinkedIn, Indeed and the Totaljobs
          family are prepare-only (the user clicks apply), and none of them is ever fetched by
          script. An Indeed alert job is upgraded when the indeed browser source reads the same
          posting (discover.py keeps the richer record).
Apply     Through the board, or the employer once hunt resolves the posting.
Senders   .eml files are read only when the From domain is on ALLOWED_SENDERS (plus
          config [sources.alerts] extra_senders), so a phishing email in the same folder
          cannot inject jobs. Email bodies are untrusted data (references/injection.md).
Links     ESP redirect wrappers are decoded when the target sits in a query parameter.
          Job ids come from the decoded link, not the link text. Query strings are dropped
          before anything is stored.
          Totaljobs-family emails carry personalised links that sign the user in. Those links
          are never stored, logged or followed: the parser keeps the job id and title, and
          builds a public advert URL only when the decoded link holds the advert path
          (/job/{slug}/{company}-job{id}); otherwise source_url is None and the id is in raw.
Verified  Link patterns in 05 section 4.1 are from memory of these emails, not 2026 samples
          (unverified). Fixtures are synthetic Reed and Totaljobs alerts.
"""
from __future__ import annotations

import email
import re
from datetime import datetime, timezone
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from sources._common import clean_line, make_record, parse_salary_text, within_days

SOURCE = {
    "name": "alerts", "kind": "alerts", "needs_key": False, "tier": "assist", "per_title": False,
    "rate_seconds": 0, "hosts": (), "label": "Alert emails",
}
TRACKING_PARAMS: tuple = ()
SUFFIXES = (".eml", ".txt", ".html", ".htm")
STEPSTONE = ("totaljobs.com", "cwjobs.co.uk", "jobsite.co.uk", "caterer.com", "milkround.com")

# board -> sender domains (an email's From domain must equal one or end with "." + one)
ALLOWED_SENDERS = {
    "reed": ("reed.co.uk",),
    "totaljobs": ("totaljobs.com",), "cwjobs": ("cwjobs.co.uk",), "jobsite": ("jobsite.co.uk",),
    "caterer": ("caterer.com",), "milkround": ("milkround.com",),
    "linkedin": ("linkedin.com",), "indeed": ("indeed.com", "indeed.co.uk", "indeedemail.com"),
    "cv-library": ("cv-library.co.uk",), "adzuna": ("adzuna.co.uk", "adzuna.com"),
    "nhs": ("jobs.nhs.uk", "nhsbsa.nhs.uk", "nhs.net"),
    "civil-service": ("civilservicejobs.service.gov.uk", "cabinetoffice.gov.uk"),
    "findajob": ("dwp.gov.uk", "findajob.dwp.gov.uk", "jobs.service.gov.uk"),
    "teaching": ("teaching-vacancies.service.gov.uk", "education.gov.uk"),
    "jobs.ac.uk": ("jobs.ac.uk",), "charityjob": ("charityjob.co.uk",), "guardian": ("theguardian.com",),
    "tes": ("tes.com",), "google": ("google.com",), "cord": ("cord.co", "cord.com"),
    "welcometothejungle": ("welcometothejungle.com",), "jobserve": ("jobserve.com",),
}
GENERIC_ANCHORS = re.compile(r"^(view|see|apply|more|read|find|open|show|click|unsubscribe|manage|edit|"
                             r"details|job details|view job|apply now|see job|see more|view all|easy apply)\b", re.I)
WRAP_PARAMS = ("url", "u", "redirect", "redirect_url", "redirecturl", "target", "link", "dest", "destination",
               "q", "r", "returnurl", "return_url", "next", "goto")


# ----------------------------------------------------------------- per-board link rules

def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _on(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def board_for_host(host: str) -> str | None:
    for board, domains in ALLOWED_SENDERS.items():
        if any(_on(host, d) for d in domains):
            return board
    if re.search(r"(^|\.)indeed\.", host):
        return "indeed"
    return None


def decode_link(href: str, depth: int = 0) -> str:
    """Unwrap ESP click-tracking: when a query parameter holds a URL (or a path on the same
    host, as sign-in links do with returnUrl), return that target instead."""
    href = (href or "").strip()
    if depth > 3 or not re.match(r"^https?://", href, re.I):
        return href
    parts = urlsplit(href)
    for k, v in parse_qsl(parts.query, keep_blank_values=False):
        if k.lower() not in WRAP_PARAMS:
            continue
        val = unquote(v).strip()
        if re.match(r"^https?://", val, re.I):
            return decode_link(val, depth + 1)
        if val.startswith("/") and not val.startswith("//"):
            return f"{parts.scheme}://{parts.hostname}{val}"
    return href


def job_from_link(href: str) -> dict | None:
    """{board, job_id, url, host} for a job link, or None. url never carries a query string
    except Indeed's jk, and is None when no public advert URL can be built."""
    target = decode_link(href)
    host = _host(target)
    if not host:
        return None
    try:
        parts = urlsplit(target)
    except ValueError:
        return None
    path = parts.path or "/"
    q = {k.lower(): v for k, v in parse_qsl(parts.query)}
    board = board_for_host(host)
    if board == "reed":
        m = re.search(r"/jobs/([^/]+)/(\d{6,})", path)
        if m:
            return {"board": "reed", "job_id": m.group(2), "url": f"https://www.reed.co.uk/jobs/{m.group(1)}/{m.group(2)}",
                    "host": host}
    if any(_on(host, d) for d in STEPSTONE):
        brand = next(d for d in STEPSTONE if _on(host, d))
        m = (re.search(r"job(\d{8,9})\b", path) or re.search(r"/jobs?/(\d{8,9})\b", path)
             or re.search(r"(\d{8,9})", q.get("jobid", "") or q.get("job", "")))
        if m:
            clean = re.match(r"^/job/[a-z0-9-]+/[a-z0-9-]+-job\d{8,9}$", path.lower())
            return {"board": brand.split(".")[0], "job_id": m.group(1),
                    "url": f"https://www.{brand}{path}" if clean else None, "host": brand}
        return None
    if board == "linkedin":
        m = re.search(r"/jobs/view/(?:[^/]*?-)?(\d{6,})", path)
        if m:
            return {"board": "linkedin", "job_id": m.group(1), "url": f"https://www.linkedin.com/jobs/view/{m.group(1)}/",
                    "host": host}
        return None
    if board == "indeed":
        jk = q.get("jk") or q.get("vjk")
        if jk and re.match(r"^[a-f0-9]{8,32}$", jk):
            return {"board": "indeed", "job_id": jk, "url": f"https://uk.indeed.com/viewjob?jk={jk}", "host": host}
        return None
    if board == "cv-library":
        m = re.search(r"/job/(\d{5,})", path)
        if m:
            return {"board": "cv-library", "job_id": m.group(1), "url": f"https://www.cv-library.co.uk/job/{m.group(1)}",
                    "host": host}
        return None
    if board == "nhs":
        m = re.search(r"/candidate/jobadvert/([A-Za-z0-9-]+)", path)
        if m:
            return {"board": "nhs", "job_id": m.group(1),
                    "url": f"https://www.jobs.nhs.uk/candidate/jobadvert/{m.group(1)}", "host": host}
        return None
    if board == "adzuna":
        m = re.search(r"/(?:land/ad|details)/(\d+)", path)
        if m:
            return {"board": "adzuna", "job_id": m.group(1), "url": f"https://www.adzuna.co.uk/jobs/land/ad/{m.group(1)}",
                    "host": host}
        return None
    if board == "findajob":
        m = re.search(r"/details/(\d+)", path)
        if m:
            return {"board": "findajob", "job_id": m.group(1), "url": f"https://findajob.dwp.gov.uk/details/{m.group(1)}",
                    "host": host}
        return None
    if board in ("teaching", "jobs.ac.uk", "charityjob", "guardian", "tes", "jobserve", "welcometothejungle",
                 "civil-service"):
        if re.search(r"/(jobs?|vacanc|advert)", path.lower()) and len(path) > 6:
            return {"board": board, "job_id": path.rstrip("/").rsplit("/", 1)[-1],
                    "url": f"https://{host}{path.rstrip('/')}" if board != "civil-service" else None, "host": host}
    return None


# ----------------------------------------------------------------- body parsing

class _LinkText(HTMLParser):
    """Collects the text of an HTML email as lines, with each <a href> marked in place."""
    BLOCK = {"p", "div", "br", "li", "tr", "td", "table", "h1", "h2", "h3", "h4", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list = []        # ("text", str) | ("link", href, text)
        self.href: str | None = None
        self.buf: list[str] = []
        self.skip = 0
        self.hidden: list[str] = []      # hidden text is where injected instructions hide

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        style = (a.get("style") or "").replace(" ", "").lower()
        if self.hidden or "display:none" in style or "visibility:hidden" in style or "hidden" in a:
            if tag not in ("br", "img", "meta", "hr", "input"):
                self.hidden.append(tag)
            return
        if tag in ("style", "script", "head"):
            self.skip += 1
        elif tag == "a":
            self.href = dict(attrs).get("href")
            self.buf = []
        elif tag in self.BLOCK:
            self.items.append(("text", "\n"))

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag in ("style", "script", "head") and self.skip:
            self.skip -= 1
        elif tag == "a" and self.href is not None:
            self.items.append(("link", self.href, clean_line(" ".join(self.buf))))
            self.href = None
        elif tag in self.BLOCK:
            self.items.append(("text", "\n"))

    def handle_data(self, data):
        if self.skip or self.hidden:
            return
        if self.href is not None:
            self.buf.append(data)
        else:
            self.items.append(("text", data))


def _segments_from_html(body: str) -> list[dict]:
    p = _LinkText()
    try:
        p.feed(body)
        p.close()
    except Exception:
        return []
    return _segments(p.items)


def _segments_from_text(body: str) -> list[dict]:
    items: list = []
    for line in body.splitlines():
        urls = re.findall(r"https?://[^\s<>\"')]+", line)
        text = re.sub(r"<?https?://[^\s<>\"')]+>?", "", line).strip()
        if urls:
            # "Data Analyst - https://..." or a URL on its own line under the title
            items.append(("link", urls[0], clean_line(text)))
        else:
            items.append(("text", line + "\n"))
    return _segments(items)


def _segments(items: list) -> list[dict]:
    """Group the body into one segment per job: the job link, its best title, and the text
    lines that follow it until the next job link."""
    jobs: dict[str, dict] = {}
    order: list[str] = []
    current: dict | None = None
    pending_title: str | None = None
    for it in items:
        if it[0] == "link":
            info = job_from_link(it[1])
            text = it[2]
            if not info:
                continue
            key = f"{info['board']}:{info['job_id']}"
            if key not in jobs:
                jobs[key] = {**info, "titles": [], "lines": []}
                order.append(key)
            current = jobs[key]
            if text and not GENERIC_ANCHORS.match(text) and len(text) > 2:
                current["titles"].append(text)
            elif pending_title and not GENERIC_ANCHORS.match(pending_title):
                current["fallback"] = current.get("fallback") or pending_title
            pending_title = None
        else:
            for ln in it[1].split("\n"):
                ln = clean_line(ln)
                if not ln:
                    continue
                if current is not None and len(current["lines"]) < 6:
                    current["lines"].append(ln)
                pending_title = ln if len(ln) < 120 else None
    out = []
    for key in order:
        j = jobs[key]
        titles = [t for t in j["titles"] if not re.match(r"^https?://", t)]
        j["title"] = titles[0] if titles else j.get("fallback")
        j["lines"] = [ln for ln in j["lines"] if ln != j["title"] and not GENERIC_ANCHORS.match(ln)]
        out.append(j)
    return out


def _details(lines: list[str]) -> dict:
    """Company, location and salary from the lines under a job title. Best effort: alert
    layouts vary, so the record says these were guessed."""
    out = {"company": None, "location": None, "salary": None}
    rest = []
    for ln in lines[:4]:
        for part in re.split(r"\s+[·|•]\s+|\s{2,}", ln):
            part = part.strip(" -–")
            if not part:
                continue
            if out["salary"] is None and ("£" in part or re.search(r"\bcompetitive\b|\bnegotiable\b", part, re.I)):
                out["salary"] = part
            else:
                rest.append(part)
    if rest:
        out["company"] = rest[0]
    if len(rest) > 1:
        out["location"] = rest[1]
    return out


def _body_parts(msg) -> tuple[str | None, str | None]:
    html_body = text_body = None
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        try:
            content = part.get_content()
        except (LookupError, ValueError):
            payload = part.get_payload(decode=True) or b""
            content = payload.decode("utf-8", errors="replace")
        if not isinstance(content, str):
            continue
        if ctype == "text/html" and html_body is None:
            html_body = content
        elif ctype == "text/plain" and text_body is None:
            text_body = content
    return html_body, text_body


def sender_board(from_header: str, extra_senders: list[str] | None = None) -> tuple[str | None, str]:
    """(board or None when not allowed, sender domain)."""
    addr = parseaddr(from_header or "")[1].lower()
    domain = addr.rsplit("@", 1)[-1] if "@" in addr else ""
    if not domain:
        return None, ""
    for board, domains in ALLOWED_SENDERS.items():
        if any(_on(domain, d) for d in domains):
            return board, domain
    for d in extra_senders or []:
        d = str(d).lower().lstrip("@")
        if d and _on(domain, d):
            return "other", domain
    return None, domain


def parse_file(path: Path, extra_senders: list[str] | None = None) -> tuple[list[dict], str | None]:
    """Records from one saved alert, and a note when the file was skipped."""
    path = Path(path)
    data = path.read_bytes()
    received = None
    sender_checked = False
    sender_domain = None
    if path.suffix.lower() == ".eml":
        msg = email.message_from_bytes(data, policy=policy.default)
        board, sender_domain = sender_board(str(msg.get("From", "")), extra_senders)
        if board is None:
            return [], f"{path.name}: sender {sender_domain or 'unknown'} is not a known job-alert sender, so it was skipped"
        sender_checked = True
        try:
            received = parsedate_to_datetime(str(msg.get("Date"))) if msg.get("Date") else None
        except (TypeError, ValueError):
            received = None
        html_body, text_body = _body_parts(msg)
    else:
        text = data.decode("utf-8", errors="replace")
        is_html = path.suffix.lower() in (".html", ".htm") or bool(re.search(r"<a\s[^>]*href=", text, re.I))
        html_body, text_body = (text, None) if is_html else (None, text)
    segs = _segments_from_html(html_body) if html_body else []
    if not segs and text_body:
        segs = _segments_from_text(text_body)
    if received is None:
        received = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    received_iso = received.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out = []
    for s in segs:
        if not s.get("title"):
            continue
        det = _details(s["lines"])
        sal = parse_salary_text(det["salary"])
        stepstone = s["board"] in [d.split(".")[0] for d in STEPSTONE]
        platform = {"linkedin": "linkedin", "indeed": "indeed", "nhs": "nhs"}.get(s["board"])
        out.append(make_record(
            "alerts",
            source_url=s["url"],
            canonical_url=s["url"] if s["board"] == "nhs" and s["url"] else None,
            platform=platform,
            company=det["company"], title=s["title"], location=det["location"],
            salary_min=sal["min"], salary_max=sal["max"], currency=sal["currency"], salary_period=sal["period"],
            posted_at=None,
            description="",
            raw={"board": s["board"], "board_job_id": s["job_id"], "title": s["title"], "lines": s["lines"],
                 "email_file": path.name, "received_at": received_iso, "sender_domain": sender_domain,
                 "sender_checked": sender_checked},
            extra={"board": s["board"], "board_job_id": s["job_id"], "salary_text": sal["text"],
                   "details_guessed": True, "received_at": received_iso, "sender_checked": sender_checked,
                   "personalised_link_dropped": stepstone, "never_fetch": stepstone or s["board"] in ("linkedin", "indeed")},
        ))
    return out, None


def inbox_files(inbox: Path) -> list[Path]:
    if not inbox.is_dir():
        return []
    return sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in SUFFIXES)


def search(query: dict, creds: dict, fetch=None) -> list[dict]:
    """fetch is accepted for the common signature and never called."""
    from sources._common import PartialFailure
    inbox = query.get("inbox")
    if not inbox:
        from jf_common import user_dir
        inbox = user_dir() / "inbox"
    inbox = Path(inbox)
    since = query.get("since_days")
    out: list[dict] = []
    notes: list[str] = []
    for path in inbox_files(inbox):
        try:
            recs, note = parse_file(path, creds.get("extra_senders"))
        except Exception as exc:
            notes.append(f"{path.name}: could not be read ({exc.__class__.__name__})")
            continue
        if note:
            notes.append(note)
        out.extend(r for r in recs if within_days(r["extra"].get("received_at"), since))
    if notes:
        raise PartialFailure(out, notes)
    return out
