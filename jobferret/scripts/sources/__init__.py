"""JobFerret discovery sources (ARCHITECTURE.md section 8.2).

Each module exports SOURCE = {"name", "kind", "needs_key", "tier", ...} and
search(query, creds, fetch) -> list of section 8.3 records. A source turns a query
into records and nothing else: no dedup, no scoring, no database.

    query  title, titles, location, radius_miles, since_days, salary_min, period,
           contract_types, work_modes, plus what a source needs (employers, feeds, inbox)
    creds  the source's own [sources.<name>] table from config.toml
    fetch  a callable with the jf_net.fetch_text signature: fetch(url, params=None,
           headers=None, auth=None, accept=None, cache_ttl=...) -> str. discover.py passes
           jf_net.fetch_text behind the never-fetch guard; tests pass a fake.

The enabled source ids are exactly SOURCE_IDS. sponsors.py is reference data for the
screener, not a job source, so it is not in the registry.

NEVER_FETCH_DOMAINS lists sites whose terms forbid automated access. No script in
JobFerret fetches them (jf_net.fetch refuses them, redirects included; the list is
defined in jf_net and re-exported here). Jobs from these sites arrive in the user's
alert emails, as a URL the user pastes (research/05 section 2.2 and finding 4), or, for
the browser sources below, from pages the user's own browser has open.

A browser source (SOURCE["kind"] == "browser": indeed) has no search(). The model opens
the board's search pages in the user's browser at a human pace, runs the read-only snippet
in scripts/browse/ with the browser's JavaScript action, saves the result, and
`discover.py browse ingest` turns it into records through the module's parse_payload().
Caps (queries, pages, pages per day) are in sources/_browser.py.
"""
from __future__ import annotations

import importlib

# The list and its checks live in jf_net so that fetch() itself enforces them.
from jf_net import (  # noqa: F401
    NEVER_FETCH_DOMAINS, NeverFetch, _WHY, _host, is_never_fetch, never_fetch_message, never_fetch_rule,
)

SOURCE_IDS = ("adzuna", "reed", "nhs", "teaching", "boards", "rss", "alerts", "indeed")
BROWSER_KIND = "browser"


def is_browser_source(name: str) -> bool:
    mod = SOURCES.get(name)
    return bool(mod) and mod.SOURCE.get("kind") == BROWSER_KIND


def guard(fetch):
    """Wrap a fetch callable so it refuses never-fetch URLs before any request is made."""
    def guarded(url, *args, **kwargs):
        if is_never_fetch(url):
            raise NeverFetch(never_fetch_message(url))
        return fetch(url, *args, **kwargs)
    guarded.__wrapped__ = fetch
    return guarded


def get_source(name: str):
    """The module for an enabled source id. Raises KeyError for anything else."""
    if name not in SOURCE_IDS:
        raise KeyError(f"unknown source {name!r}; the sources are: {', '.join(SOURCE_IDS)}")
    return importlib.import_module(f"sources.{name}")


SOURCES = {name: get_source(name) for name in SOURCE_IDS}
