"""jf_net.py: the one JobFerret module that opens a network connection.

Discovery sources, feed readers and ATS lookups call fetch_json() or fetch_text()
so that caching, rate limits, retries, offline mode and key redaction live in one
place (ARCHITECTURE.md section 8.1). Nothing else in scripts/ imports urllib.

Offline mode never opens a socket. Turn it on with set_offline(True), the
environment variable JOBFERRET_OFFLINE=1, or a script's --offline flag
(add_offline_arg / apply_offline_arg below). Offline, a request is served from
the cache whatever its age, or raises OfflineMiss. Tests always run offline, with
prime_cache() loading recorded responses.

Secrets are redacted before anything is cached, printed or put in an exception:
any query parameter, header or JSON key whose name contains key, secret, token,
password or app_id becomes "***".

Never-fetch sites (NEVER_FETCH_DOMAINS: LinkedIn, Indeed, Glassdoor and the StepStone
family, whose terms ban automated access) are refused in fetch() before the cache or
any socket, and again at every redirect hop. sources/__init__.py re-exports the list.

Raises:
  NeverFetch   the URL, or a redirect target, is on NEVER_FETCH_DOMAINS
  FetchError   the request failed after retries (.status, .url redacted, .detail)
  OfflineMiss  offline mode and nothing cached for this request
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from jf_common import atomic_write_text, now_iso, user_dir

VERSION = "0.2"
USER_AGENT = f"JobFerret/{VERSION} (+local job-search tool)"
SECRET_KEY = re.compile(r"(key|secret|token|password|app_id|apikey)", re.I)
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_BACKOFF = (1.0, 3.0)          # seconds before the second and third attempt
DEFAULT_RATE = 1.0                   # seconds between requests to one host
DEFAULT_TTL = 3600                   # seconds a cached success stays fresh

_state: dict[str, Any] = {
    "offline": None,                 # None = read JOBFERRET_OFFLINE
    "cache_dir": None,
    "rates": {},                     # host -> seconds between requests
    "last": {},                      # host -> monotonic time of the last request
    "sleep": time.sleep,             # tests replace this
}

_request_guard = ContextVar("jobferret_request_guard", default=None)


@contextmanager
def request_guard(check):
    """Check cancellation before requests, retries and redirects within this scope."""
    token = _request_guard.set(check)
    try:
        yield
    finally:
        _request_guard.reset(token)


def _check_request_guard() -> None:
    check = _request_guard.get()
    if check is not None:
        check()


NEVER_FETCH_DOMAINS = (
    "totaljobs.com",      # StepStone UK terms 6.2.11, 29 Oct 2026: no bots for access, extraction or applying
    "cwjobs.co.uk",       # same operator and template
    "jobsite.co.uk",
    "caterer.com",
    "milkround.com",
    "linkedin.com",       # User Agreement bans scraping and bots (01 section C2)
    "indeed.*",           # bans automating Indeed Apply and scraping (01 section C2)
    "glassdoor.*",        # now Indeed's feed; 403 to scripts
)

_WHY = {
    "totaljobs.com": "Totaljobs' terms (clause 6.2.11, from 29 October 2026) ban bots and scripts",
    "cwjobs.co.uk": "CWJobs shares Totaljobs' terms, which ban bots and scripts",
    "jobsite.co.uk": "Jobsite shares Totaljobs' terms, which ban bots and scripts",
    "caterer.com": "Caterer.com's terms (clause 6.2.11) ban bots and scripts",
    "milkround.com": "Milkround shares Totaljobs' terms, which ban bots and scripts",
    "linkedin.com": "LinkedIn's User Agreement bans scraping and automated access",
    "indeed.*": "Indeed's terms ban scraping and automated applying; JobFerret reads Indeed only in your browser (source 'indeed')",
    "glassdoor.*": "Glassdoor's listings come from Indeed and it blocks scripts",
}


def _host(url: str) -> str:
    raw = (url or "").strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        raw = "https://" + raw
    try:
        return (urllib.parse.urlsplit(raw).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def never_fetch_rule(url: str) -> str | None:
    """The NEVER_FETCH_DOMAINS entry a URL falls under, or None."""
    host = _host(url)
    if not host:
        return None
    labels = host.split(".")
    for rule in NEVER_FETCH_DOMAINS:
        if rule.endswith(".*"):
            base = rule[:-2]
            if base in labels[:-1]:            # indeed.com, uk.indeed.com, indeed.co.uk
                return rule
        elif host == rule or host.endswith("." + rule):
            return rule
    return None


def is_never_fetch(url: str) -> bool:
    return never_fetch_rule(url) is not None


def never_fetch_message(url: str) -> str:
    rule = never_fetch_rule(url)
    if not rule:
        return ""
    return (f"Not fetching {_host(url)}: {_WHY.get(rule, 'its terms forbid automated access')}. "
            "Jobs from this site reach JobFerret through your alert emails (drop them in the inbox folder) "
            "or a link you paste into apply.")


class NeverFetch(Exception):
    """A URL (or a redirect hop) on NEVER_FETCH_DOMAINS: raised by fetch() before any request is made."""



class FetchError(Exception):
    def __init__(self, url: str, status: int | None, detail: str = ""):
        self.url = redact_url(url)
        self.status = status
        self.detail = detail[:300]
        what = f"HTTP {status}" if status else "network error"
        super().__init__(f"{what} fetching {self.url}: {self.detail}".rstrip(": "))


class OfflineMiss(Exception):
    def __init__(self, url: str):
        self.url = redact_url(url)
        super().__init__(f"offline and nothing cached for {self.url}")


# --- settings -------------------------------------------------------------

def is_offline() -> bool:
    if _state["offline"] is not None:
        return bool(_state["offline"])
    return os.environ.get("JOBFERRET_OFFLINE", "").strip().lower() in ("1", "true", "yes")


def set_offline(flag: bool | None) -> None:
    """True or False forces the mode; None goes back to reading JOBFERRET_OFFLINE."""
    _state["offline"] = flag


def set_cache_dir(path: Path | str | None) -> None:
    _state["cache_dir"] = Path(path) if path else None


def cache_dir() -> Path:
    path = _state["cache_dir"] or (user_dir() / "cache")
    path.mkdir(parents=True, exist_ok=True)
    return path


def set_rate(host: str, seconds: float) -> None:
    _state["rates"][host.lower()] = max(0.0, float(seconds))


def add_offline_arg(parser) -> None:
    parser.add_argument("--offline", action="store_true",
                        help="never open a socket; serve only from the cache and recorded fixtures")


def apply_offline_arg(args) -> None:
    if getattr(args, "offline", False):
        set_offline(True)


# --- redaction ------------------------------------------------------------

def redact(obj: Any) -> Any:
    """Return a copy with every secret-looking key's value replaced by '***'."""
    if isinstance(obj, dict):
        return {k: ("***" if isinstance(k, str) and SECRET_KEY.search(k) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    return obj


def redact_url(url: str) -> str:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    netloc = parts.netloc
    if "@" in netloc:
        netloc = "***@" + netloc.rsplit("@", 1)[1]
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    pairs = [(k, "***" if SECRET_KEY.search(k) else v) for k, v in pairs]
    query = urllib.parse.urlencode(pairs)
    return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


# --- cache ----------------------------------------------------------------

def _clean_params(params: dict | None) -> dict:
    return {k: v for k, v in (params or {}).items() if v is not None}


def build_url(url: str, params: dict | None = None) -> str:
    params = _clean_params(params)
    if not params:
        return url
    joiner = "&" if "?" in url else "?"
    return url + joiner + urllib.parse.urlencode(params, doseq=True)


def cache_key(url: str, params: dict | None = None, method: str = "GET", data: Any = None) -> str:
    """Stable across secret values: two runs with different API keys share a cache entry."""
    material = json.dumps([method.upper(), redact_url(build_url(url, params)), redact(data)],
                          sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(material.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return cache_dir() / f"{key}.json"


def _read_cache(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_cache(key: str, record: dict) -> None:
    atomic_write_text(_cache_path(key), json.dumps(record, ensure_ascii=False, indent=1))


def prime_cache(url: str, body: Any, params: dict | None = None, method: str = "GET",
                status: int = 200, data: Any = None, headers: dict | None = None) -> str:
    """Load a recorded response so an offline fetch returns it. Returns the cache key.

    body may be a str or anything json.dumps accepts. Used by tests and by the
    fixture loader for recorded source responses.
    """
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    key = cache_key(url, params, method, data)
    _write_cache(key, {
        "url": redact_url(build_url(url, params)),
        "method": method.upper(),
        "status": status,
        "headers": redact(headers or {}),
        "fetched_at": now_iso(),
        "fetched_ts": time.time(),
        "body": text,
        "primed": True,
    })
    return key


def clear_cache() -> int:
    n = 0
    for path in cache_dir().glob("*.json"):
        path.unlink()
        n += 1
    return n


# --- the request ----------------------------------------------------------

def _rate_wait(host: str) -> None:
    host = host.lower()
    gap = _state["rates"].get(host, DEFAULT_RATE)
    last = _state["last"].get(host)
    now = time.monotonic()
    if last is not None and now - last < gap:
        _state["sleep"](gap - (now - last))
    _state["last"][host] = time.monotonic()


class _NeverFetchRedirect(urllib.request.HTTPRedirectHandler):
    """Re-checks every redirect hop, so a permitted site cannot send us to a never-fetch one."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_request_guard()
        if is_never_fetch(newurl):
            raise NeverFetch(never_fetch_message(newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _do_request(full_url: str, headers: dict, method: str, body: bytes | None,
                timeout: float) -> tuple[int, str, dict]:
    """One attempt. Returns (status, text, headers). Tests replace this function."""
    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NeverFetchRedirect())
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.status, raw.decode(charset, errors="replace"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        return e.code, raw.decode("utf-8", errors="replace"), dict(e.headers or {})


def fetch(url: str, params: dict | None = None, headers: dict | None = None,
          auth: tuple[str, str] | None = None, timeout: float = 20.0,
          cache_ttl: float | None = DEFAULT_TTL, method: str | None = None,
          data: Any = None, accept: str | None = None) -> dict:
    """Fetch with cache, rate limit and retries. Returns a record:

    {"status", "body", "headers", "fetched_at", "from_cache", "url"} with url redacted.
    data (dict or list) is sent as a JSON body; method defaults to GET, or POST when data is given.
    cache_ttl=None always refetches (the response is still written to the cache for offline use).
    """
    _check_request_guard()
    method = (method or ("POST" if data is not None else "GET")).upper()
    full_url = build_url(url, params)
    if is_never_fetch(full_url):
        raise NeverFetch(never_fetch_message(full_url))
    key = cache_key(url, params, method, data)
    cached = _read_cache(key)

    if is_offline():
        if cached is None:
            raise OfflineMiss(full_url)
        return {**cached, "from_cache": True}

    if cached is not None and cache_ttl:
        age = time.time() - float(cached.get("fetched_ts", 0))
        if 0 <= age < cache_ttl and 200 <= int(cached.get("status", 0)) < 300:
            return {**cached, "from_cache": True}

    send_headers = {"User-Agent": USER_AGENT, "Accept": accept or "application/json, text/*;q=0.8, */*;q=0.5"}
    send_headers.update(headers or {})
    body: bytes | None = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        send_headers.setdefault("Content-Type", "application/json")
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode("utf-8")).decode("ascii")
        send_headers["Authorization"] = f"Basic {token}"

    host = urllib.parse.urlsplit(full_url).hostname or ""
    last_status: int | None = None
    last_text = ""
    for attempt in range(3):
        _check_request_guard()
        if attempt:
            _state["sleep"](RETRY_BACKOFF[attempt - 1])
        _rate_wait(host)
        _check_request_guard()
        try:
            status, text, resp_headers = _do_request(full_url, send_headers, method, body, timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_status, last_text = None, str(e)
            continue
        last_status, last_text = status, text
        if status in RETRY_STATUSES:
            continue
        if status >= 400:
            raise FetchError(full_url, status, text)
        record = {
            "url": redact_url(full_url),
            "method": method,
            "status": status,
            "headers": redact(resp_headers),
            "fetched_at": now_iso(),
            "fetched_ts": time.time(),
            "body": text,
        }
        _write_cache(key, record)
        return {**record, "from_cache": False}
    raise FetchError(full_url, last_status, last_text)


def fetch_json(url: str, **kwargs) -> Any:
    record = fetch(url, **kwargs)
    try:
        return json.loads(record["body"])
    except ValueError as e:
        raise FetchError(record["url"], record.get("status"), f"response is not JSON ({e})") from None


def fetch_text(url: str, **kwargs) -> str:
    kwargs.setdefault("accept", "text/html, application/xml, text/*;q=0.9, */*;q=0.5")
    return fetch(url, **kwargs)["body"]
