"""Lint application prose for AI tells, voice drift and format limits.

Purpose
    Automates the mechanical parts of the self-review checklist in research
    04 section 7: check 2 (banned words/phrases), 3 (rationed items), 4
    (specificity), 7 (rhythm), 8 (openers/closers), 10 (voice match, partial:
    spelling locale and the voice profile), 11 (formatting and length limits)
    and 12 (agent fingerprints). Checks 1, 5, 6 and 9 need judgment and are
    listed as "manual" items for the model to do.

    Ledger citation markers ([F012], [F012,F041]) and [CONFIRM: ...] markers
    are stripped before linting, so cited drafts can be linted directly.
    In cv-bullets and cv-profile modes markdown headers of every level are
    ignored, so whole CVs and pasted fragments both work: cv-bullets lints only
    the list items; cv-profile lints only the Profile/Summary section, or, if
    there is none, the first paragraph after the name/contact line (the report
    says so). A --profile path that does not exist prints a warning and skips
    the profile-based voice-match checks; the other checks still decide the exit.

Usage
    voice_lint.py <file> --format <fmt> [--locale uk|us] [--profile voice-profile.json]
                  [--max-words N] [--lists-dir DIR] [--json]
    voice_lint.py --measure <sample1.txt> [<sample2.txt> ...] [--lists-dir DIR] [--json]

    fmt: cover-letter | email | linkedin-note | hiring-manager | cv-profile |
         cv-bullets | form-answer | follow-up | thank-you
    Limits: linkedin-note <= 300 characters; email and hiring-manager <= 120 words;
    cover-letter 150-400 words; cv-profile <= 80 words; form-answer <= --max-words.
    Locale: --locale, else the profile's "locale"/"spelling" (en-GB/en-US), else
    [locale] default in ~/.jobferret/config.toml, else uk.
    Lists: references/voice/lists/*.txt next to this skill, or --lists-dir. A
    missing list file prints a warning naming it; linting continues without it.

    --measure computes idiolect markers from the user's own writing samples
    and prints a JSON object to paste into voice-profile.json.

Exit codes
    0  pass (warnings allowed) / --measure succeeded
    1  at least one check failed
    3  missing dependency (none expected; standard library only)
    4  usage or input error (bad arguments, unreadable file or profile)
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

from jf_common import (
    ANY_MARKER_RE, CONFIRM_RE, EMAIL_RE, EXIT_FAIL, EXIT_OK, REFERENCES_DIR, ConfigError, die,
    emit_json, is_contact_line, load_config, make_parser, read_text, setup_io, split_sentences, user_dir,
    word_count,
)

FORMATS = ("cover-letter", "email", "linkedin-note", "hiring-manager", "cv-profile",
           "cv-bullets", "form-answer", "follow-up", "thank-you")
MESSAGE_FORMATS = ("email", "hiring-manager", "follow-up", "thank-you", "linkedin-note")
CV_FORMATS = ("cv-profile", "cv-bullets")
LIST_FILES = ("banned-words.txt", "banned-phrases.txt", "rationed.txt", "openers.txt",
              "closers.txt", "agent-tics.txt", "uk-us-spelling.txt")
SPECIFICITY_MIN = {"cover-letter": 6, "email": 2, "hiring-manager": 2, "linkedin-note": 1, "cv-profile": 3}
WARN_OPENERS = {"as a", "as an"}
MANUAL_CHECKS = [
    {"id": 1, "name": "fact trace", "how": "every number, name, date and claim maps to the ledger or the user's answers; run ledger_check.py"},
    {"id": 5, "name": "swap test", "how": "put a competitor's name in; if the 'why us' sentences still hold, rewrite them"},
    {"id": 6, "name": "only-me test", "how": "point to the sentence no other applicant could have written"},
    {"id": 9, "name": "read-aloud test", "how": "would the user say each sentence to the hiring manager's face?"},
    {"id": 12, "name": "agent fingerprints (judgment part)", "how": "any sentence that explains why the previous sentence was significant"},
]

GREETING_RE = re.compile(r"^(?:dear|hi|hello|hey|good (?:morning|afternoon|evening)|to whom)\b", re.IGNORECASE)
SIGNOFF_RE = re.compile(
    r"^(?:thanks|thank you|many thanks|best|best wishes|best regards|kind regards|regards|warm regards|"
    r"warmest regards|all the best|yours sincerely|yours faithfully|sincerely|yours|cheers|with thanks|"
    r"speak soon|take care)\s*[,.!]?\s*$",
    re.IGNORECASE,
)
SUBJECT_RE = re.compile(r"^\s*subject\s*:\s*(.*)$", re.IGNORECASE)
LIST_LINE_RE = re.compile(r"^\s*(?:[-*+\u2022]|\d+[.)])\s+")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")
URLISH_RE = re.compile(r"(?:https?://\S+|www\.\S+|\b[\w-]+(?:\.[\w-]+)+/\S*)", re.IGNORECASE)
DASH_SPACED_RE = re.compile(r"\s[\u2013-]\s")
DATE_DASH_RE = re.compile(
    r"(?:\d|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?)\s[\u2013-]\s"
    r"(?=\d|present|current|now|today|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))",
    re.IGNORECASE,
)
TRICOLON_RE = re.compile(
    r"\b[\w'-]+(?:\s[\w'-]+){0,2},\s[\w'-]+(?:\s[\w'-]+){0,2},?\s(?:and|or)\s[\w'-]+", re.IGNORECASE
)
ANTITHESIS_RE = re.compile(
    r"\bnot\b[^.!?;]{1,60}?,\s*but\b|\b(?:it|this|that)(?:'s|\sis)\snot\b[^.!?]{1,60}?[,;]\s*(?:it|this|that)(?:'s|\sis)\b",
    re.IGNORECASE,
)
TRAILING_ING_RE = re.compile(r",\s+(?:ensuring|enabling|driving|delivering|fostering|resulting|allowing|"
                             r"helping|creating|making|providing|supporting|reflecting|showcasing)\b",
                             re.IGNORECASE)
REAL_INTENSIFIER_RE = re.compile(
    r"\breal\s+(?:impact|difference|value|work|change|progress|results?|growth|insight|passion|"
    r"opportunity|commitment|ownership|world)\b",
    re.IGNORECASE,
)
INTENSIFIER_WITH_YEARS_RE = re.compile(r"^with\s+\d+\+?\s+years\b", re.IGNORECASE)
CONTRACTION_RE = re.compile(
    r"\b(?:\w+n't|\w+'re|\w+'ve|\w+'ll|\w+'d|i'm|(?:it|that|there|here|what|who|he|she|let|where|how)'s)\b",
    re.IGNORECASE,
)
MONTH_WORDS = {"january", "february", "march", "april", "may", "june", "july", "august", "september",
               "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
               "sep", "sept", "oct", "nov", "dec", "monday", "tuesday", "wednesday", "thursday",
               "friday", "saturday", "sunday"}
NOT_PROPER = {"i", "i'm", "i've", "i'd", "i'll", "dear", "hi", "hello", "thanks", "regards", "best",
              "yours", "sincerely", "ok"}
STOPWORDS = set("""a about above after again against all also am an and any are aren't as at be because been
before being below between both but by can can't cannot could couldn't did didn't do does doesn't doing don't
down during each few for from further had hadn't has hasn't have haven't having he he'd he'll he's her here
here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself
just let's me more most mustn't my myself no nor not now of off on once only or other ought our ours
ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than that that's the
their theirs them themselves then there there's these they they'd they'll they're they've this those through
to too under until up us very was wasn't we we'd we'll we're we've were weren't what what's when when's where
where's which while who who's whom why why's will with won't would wouldn't you you'd you'll you're you've
your yours yourself yourselves get got one two also just really thanks thank hi hello dear best regards""".split())


# ------------------------------------------------------------------ list loading

def _norm_quotes(text: str) -> str:
    return (text.replace("\u2019", "'").replace("\u2018", "'")
            .replace("\u201c", '"').replace("\u201d", '"'))


def entry_regex(entry: str) -> re.Pattern:
    """Whole-word, case-insensitive; a hyphen counts as part of a word; internal
    spaces match any whitespace; entries with no letters/digits are substrings."""
    e = _norm_quotes(entry.strip().lower())
    if not re.search(r"[a-z0-9]", e):
        return re.compile(re.escape(e))
    body = r"\s+".join(re.escape(part) for part in e.split())
    pre = r"(?<![\w-])" if re.match(r"[\w]", e) else ""
    post = r"(?![\w-])" if re.search(r"[\w]$", e) else ""
    return re.compile(pre + body + post, re.IGNORECASE)


class Lists:
    def __init__(self, lists_dir: Path):
        self.dir = lists_dir
        self.missing: list[str] = []
        self.banned_words = self._entries("banned-words.txt")
        self.banned_phrases = self._entries("banned-phrases.txt")
        self.rationed, self.groups = self._rationed()
        self.openers = self._entries("openers.txt")
        self.closers = self._entries("closers.txt")
        self.agent_tics = self._entries("agent-tics.txt")
        self.spelling_two_way, self.spelling_one_way = self._spelling()

    def _lines(self, name: str) -> list[str] | None:
        p = self.dir / name
        if not p.is_file():
            self.missing.append(name)
            sys.stderr.write(f"warning: voice list {p} not found; continuing without it\n")
            return None
        return p.read_text(encoding="utf-8-sig").splitlines()

    def _entries(self, name: str) -> list[str]:
        lines = self._lines(name) or []
        out = []
        for ln in lines:
            s = ln.strip()
            if s and not s.startswith("#"):
                out.append(_norm_quotes(s.lower()))
        return out

    def _rationed(self) -> tuple[list[str], dict[str, list[str]]]:
        lines = self._lines("rationed.txt") or []
        entries, groups = [], {}
        for ln in lines:
            s = ln.strip()
            m = re.match(r"^#\s*group:\s*([\w-]+)\s*=\s*(.+)$", s)
            if m:
                members = [x.strip().lower() for x in re.sub(r"\(.*?\)", "", m.group(2)).split("|")]
                groups[m.group(1)] = [_norm_quotes(x) for x in members if x]
                continue
            if s and not s.startswith("#"):
                entries.append(_norm_quotes(s.lower()))
        return entries, groups

    def _spelling(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        lines = self._lines("uk-us-spelling.txt") or []
        two, one = [], []
        block = 1
        for ln in lines:
            if re.match(r"^# === BLOCK 2", ln):
                block = 2
                continue
            s = ln.strip()
            if not s or s.startswith("#") or "," not in s:
                continue
            uk, us = [x.strip().lower() for x in s.split(",", 1)]
            (two if block == 1 else one).append((uk, us))
        return two, one


# --------------------------------------------------------------- document model

def preprocess(raw: str) -> tuple[list[tuple[int, str]], int]:
    """Strip markers and normalise quotes; return [(line_no, text)] and the confirm count."""
    confirms = len(CONFIRM_RE.findall(raw))
    out = []
    for no, line in enumerate(raw.splitlines(), start=1):
        out.append((no, _norm_quotes(ANY_MARKER_RE.sub("", line)).rstrip()))
    return out, confirms


HEADER_RE = re.compile(r"^\s*#{1,6}(?:\s|$)")
PROFILE_HEAD_RE = re.compile(r"(?i)^(?:personal |professional |career |executive )?(?:profile|summary)$|"
                             r"^personal statement$|^about(?: me)?$")


def select_cv_part(lines: list[tuple[int, str]], fmt: str) -> tuple[list[tuple[int, str]], str | None]:
    """For cv-bullets and cv-profile, keep only the part the format applies to.

    Markdown headers of every level are dropped. cv-bullets keeps the list items
    (or, if there are none, every non-header line). cv-profile keeps the
    Profile/Summary section; without one, the first paragraph after the name and
    contact line. Returns (lines, note-for-the-report or None).
    """
    if fmt not in CV_FORMATS:
        return lines, None
    headers = [t for _, t in lines if HEADER_RE.match(t)]
    body = [(n, t) for n, t in lines if not HEADER_RE.match(t)]
    if fmt == "cv-bullets":
        items = [(n, LIST_LINE_RE.sub("", t)) for n, t in body if LIST_LINE_RE.match(t)]
        if items:
            other = len(items) < len([t for _, t in body if t.strip()])
            note = "linted the list items only" if (headers or other) else None
            return items, note
        return body, ("no list items found; linted every non-header line" if headers else None)
    # cv-profile
    keep, on, found = [], False, False
    for n, t in lines:
        h = re.match(r"^\s*#{1,6}\s+(.*)$", t)
        if h:
            on = bool(PROFILE_HEAD_RE.match(strip_heading(h.group(1))))
            found = found or on
            continue
        if on:
            keep.append((n, t))
    if found:
        return keep, "linted the Profile section only"
    contact_seen = False
    looks_like_cv = bool(headers) or any(is_contact_line(t) for _, t in body[:6])
    if not looks_like_cv:
        return body, None
    para: list[tuple[int, str]] = []
    for n, t in body:
        s = t.strip()
        if not s:
            if para:
                break
            continue
        if is_contact_line(s):
            contact_seen = True
            continue
        if LIST_LINE_RE.match(t) or re.match(r"^\*\*[^*]+:\*\*", s):
            if para:
                break
            continue
        para.append((n, t))
    where = "after the contact line" if contact_seen else "in the file"
    return para, f"no Profile section found; linted the first paragraph {where}"


def strip_heading(text: str) -> str:
    return ANY_MARKER_RE.sub("", text).strip().rstrip(":").strip()


class Doc:
    def __init__(self, lines: list[tuple[int, str]], fmt: str):
        self.fmt = fmt
        self.lines = lines
        self.subject: tuple[int, str] | None = None
        self.greeting: tuple[int, str] | None = None
        self.signoff: tuple[int, str] | None = None
        body = [(n, t) for n, t in lines]
        # subject
        for i, (n, t) in enumerate(body):
            if t.strip():
                m = SUBJECT_RE.match(t)
                if m:
                    self.subject = (n, m.group(1).strip())
                    body = body[:i] + body[i + 1:]
                break
        # greeting (first non-empty line)
        for i, (n, t) in enumerate(body):
            if t.strip():
                if GREETING_RE.match(t.strip()) and word_count(t) <= 8 and (
                        t.strip().endswith((",", ":", "!")) or word_count(t) <= 4):
                    self.greeting = (n, t.strip())
                    body = body[i + 1:]
                break
        # sign-off: last such line within the final 4 non-empty lines
        nonempty = [i for i, (_, t) in enumerate(body) if t.strip()]
        for i in reversed(nonempty[-4:]):
            if SIGNOFF_RE.match(body[i][1].strip()):
                self.signoff = (body[i][0], body[i][1].strip())
                body = body[:i]
                break
        if fmt == "cv-bullets":
            body = [(n, LIST_LINE_RE.sub("", t)) for n, t in body]
        self.body = body
        self.paragraphs: list[list[tuple[int, str]]] = []
        cur: list[tuple[int, str]] = []
        for n, t in body:
            if not t.strip():
                if cur:
                    self.paragraphs.append(cur)
                cur = []
                continue
            if fmt == "cv-bullets":  # every bullet is its own paragraph
                self.paragraphs.append([(n, t.strip())])
                continue
            cur.append((n, t.strip()))
        if cur:
            self.paragraphs.append(cur)

    def para_text(self, para: list[tuple[int, str]]) -> str:
        return " ".join(t for _, t in para)

    @property
    def body_text(self) -> str:
        return "\n\n".join(self.para_text(p) for p in self.paragraphs)

    @property
    def full_text(self) -> str:
        return "\n".join(t for _, t in self.lines)

    def sentences(self) -> list[tuple[int, str]]:
        out = []
        for para in self.paragraphs:
            text = self.para_text(para)
            for s in split_sentences(text):
                if word_count(s):
                    out.append((para[0][0], s))
        return out


def find_all(pattern: re.Pattern, lines: list[tuple[int, str]]) -> list[tuple[int, str, tuple[int, int]]]:
    hits = []
    for n, t in lines:
        for m in pattern.finditer(t):
            hits.append((n, m.group(0), (m.start(), m.end())))
    return hits


def _strip_urls(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(n, EMAIL_RE.sub(" ", URLISH_RE.sub(" ", t))) for n, t in lines]


# ------------------------------------------------------------------- the checks

def _check(cid: int, name: str) -> dict:
    return {"id": cid, "name": name, "status": "pass", "findings": [], "note": ""}


def _finding(line: int | None, match: str, message: str, severity: str = "fail") -> dict:
    return {"line": line, "match": match, "message": message, "severity": severity}


def _settle(check: dict) -> dict:
    sev = {f["severity"] for f in check["findings"]}
    if "fail" in sev:
        check["status"] = "fail"
    elif "warn" in sev and check["status"] == "pass":
        check["status"] = "warn"
    return check


def check_banned(doc: Doc, lists: Lists, tic_spans: set[tuple[int, int, int]]) -> dict:
    c = _check(2, "banned words and phrases")
    lines = _strip_urls([(n, t) for n, t in doc.lines if not SUBJECT_RE.match(t)] +
                        ([(doc.subject[0], doc.subject[1])] if doc.subject else []))
    for entries, kind in ((lists.banned_words, "banned word"), (lists.banned_phrases, "banned phrase")):
        for e in entries:
            for n, text, (s, en) in find_all(entry_regex(e), lines):
                if any(tn == n and not (en <= ts or s >= te) for tn, ts, te in tic_spans):
                    continue  # reported once, as an agent tic (check 12)
                c["findings"].append(_finding(n, text, f"{kind}: \u201c{e}\u201d"))
    return _settle(c)


def check_agent_tics(doc: Doc, lists: Lists) -> tuple[dict, set[tuple[int, int, int]]]:
    c = _check(12, "agent fingerprints")
    spans: set[tuple[int, int, int]] = set()
    lines = _strip_urls(doc.lines)
    for e in lists.agent_tics:
        for n, text, (s, en) in find_all(entry_regex(e), lines):
            spans.add((n, s, en))
            c["findings"].append(_finding(n, text, f"agent tic: \u201c{e}\u201d"))
    for n, text, (s, en) in find_all(REAL_INTENSIFIER_RE, lines):
        spans.add((n, s, en))
        c["findings"].append(_finding(n, text, "\u201creal\u201d used as an intensifier"))
    c["note"] = "also check by reading: a sentence that explains why the previous one mattered"
    return _settle(c), spans


def check_rationed(doc: Doc, lists: Lists) -> dict:
    c = _check(3, "rationed items")
    fmt = doc.fmt
    lines = _strip_urls(doc.body)
    body_words = word_count(doc.body_text)
    counts: dict[str, list[tuple[int, str]]] = {}

    grouped = {m: g for g, members in lists.groups.items() for m in members}
    dash_group = next((g for g, ms in lists.groups.items() if any("dash" in m for m in ms)), "dashes")

    def bump(key: str, n: int, text: str) -> None:
        counts.setdefault(key, []).append((n, text))

    group_hits: dict[str, list[tuple[int, str]]] = {}
    for e in lists.rationed:
        if e == "\u2014":
            continue  # handled with the dash group
        if e == ";" and body_words >= 150:
            continue
        for n, text, _ in find_all(entry_regex(e), lines):
            bump(f"\u201c{e}\u201d", n, text)
            if e in grouped:
                group_hits.setdefault(grouped[e], []).append((n, text))

    # dashes: em dash literal + spaced en dash / hyphen, one allowance; not for cv-bullets
    if fmt != "cv-bullets":
        dash_hits = []
        for n, t in lines:
            dash_hits += [(n, "\u2014") for _ in re.finditer("\u2014", t)]
            date_spans = [m.span() for m in DATE_DASH_RE.finditer(t)]
            for m in DASH_SPACED_RE.finditer(t):
                if not any(ds <= m.start() < de for ds, de in date_spans):
                    dash_hits.append((n, m.group(0).strip()))
        if dash_hits:
            group_hits[dash_group] = dash_hits

    limits: dict[str, int] = {}
    # "!" is zero in cover letters and form answers
    if fmt in ("cover-letter", "form-answer"):
        limits["\u201c!\u201d"] = 0

    # structural
    sentences = doc.sentences()
    q_allow = 0 if fmt in ("cover-letter", "form-answer") else 1
    qs = [(n, s) for n, s in sentences if s.rstrip().endswith("?")]
    if len(qs) > q_allow:
        for n, s in qs:
            bump("rhetorical question (?)", n, s[-60:])
        limits["rhetorical question (?)"] = q_allow
    for n, text, _ in find_all(ANTITHESIS_RE, lines):
        bump("antithesis (not X, but Y)", n, text)
    if fmt != "cv-bullets":
        for n, s in sentences:
            m = re.search(r"^(?P<setup>[^:]{3,80}?):\s+(?P<pay>[^:]+)$", s)
            if m and word_count(m.group("setup")) >= 2 and word_count(m.group("pay")) <= 8 \
                    and not re.search(r"\d:\d", s):
                bump("colon punchline", n, s[:80])
        for n, text, _ in find_all(TRICOLON_RE, lines):
            bump("list of three", n, text)

    over: list[str] = []
    for key, hits in counts.items():
        allow = limits.get(key, 1)
        if len(hits) > allow:
            sev = "warn" if (fmt == "cv-bullets" and key == "list of three") else "fail"
            if sev == "fail":
                over.append(key)
            for n, text in hits:
                c["findings"].append(_finding(n, text, f"{key}: {len(hits)} uses, allowed {allow}", sev))
    for g, hits in group_hits.items():
        if len(hits) > 1:
            over.append(f"group {g}")
            for n, text in hits:
                c["findings"].append(_finding(n, text, f"group \u201c{g}\u201d: {len(hits)} uses share one allowance"))
    for n, text, _ in find_all(TRAILING_ING_RE, lines):
        c["findings"].append(_finding(n, text, "trailing -ing clause; cut it or give it its own sentence with a fact", "warn"))
    over = sorted(set(over))
    c["categories_over"] = over
    if len(over) >= 3:
        c["note"] = "three or more categories over the limit: rewrite from the facts instead of editing"
    return _settle(c)


def specificity_count(text: str) -> int:
    count = 0
    for s in split_sentences(text):
        tokens = re.findall(r"[\w'£$€%&.-]+", s)
        for i, tok in enumerate(tokens):
            t = tok.strip(".-'")
            if not t:
                continue
            low = t.lower()
            if re.search(r"\d", t) or low in MONTH_WORDS:
                count += 1
            elif i > 0 and t[0].isupper() and low not in NOT_PROPER:
                count += 1
            elif i == 0 and len(t) > 1 and (t.isupper() or re.search(r"[a-z][A-Z]", t)):
                count += 1
    return count


def check_specificity(doc: Doc, max_words: int | None) -> dict:
    c = _check(4, "specificity")
    fmt = doc.fmt
    total = specificity_count(doc.body_text)
    c["count"] = total
    need = SPECIFICITY_MIN.get(fmt)
    if fmt == "form-answer":
        need = max(1, word_count(doc.body_text) // 50)
    if need is None:
        c["status"] = "skip"
        c["note"] = f"no threshold for {fmt}"
        return c
    c["note"] = f"{total} proper nouns, numbers and dates; need at least {need}"
    if total < need:
        c["findings"].append(_finding(None, "", f"only {total} specifics (proper nouns, numbers, dates); need {need}"))
    if fmt == "cover-letter":
        for para in doc.paragraphs:
            if specificity_count(doc.para_text(para)) == 0:
                c["findings"].append(_finding(para[0][0], doc.para_text(para)[:60],
                                              "paragraph has no proper noun, number or date"))
    return _settle(c)


def check_rhythm(doc: Doc) -> dict:
    c = _check(7, "rhythm")
    words = word_count(doc.body_text)
    if doc.fmt == "cv-bullets" or words <= 100:
        c["status"] = "skip"
        c["note"] = "applies to prose over 100 words"
        return c
    sents = doc.sentences()
    lens = [word_count(s) for _, s in sents]
    if len(lens) < 3:
        c["findings"].append(_finding(None, "", f"only {len(lens)} sentences in {words} words; break them up"))
        return _settle(c)
    sd = statistics.pstdev(lens)
    med = statistics.median(lens)
    c["note"] = f"{len(lens)} sentences; lengths min {min(lens)}, max {max(lens)}, median {med:g}, sd {sd:.1f}"
    if min(lens) > 6:
        c["findings"].append(_finding(None, "", "no sentence of 6 words or fewer"))
    if max(lens) < 20:
        c["findings"].append(_finding(None, "", "no sentence of 20 words or more"))
    if sd < 5:
        c["findings"].append(_finding(None, "", f"sentence-length spread too even (sd {sd:.1f} < 5)"))
    if med < 9:
        c["findings"].append(_finding(None, "", f"median sentence is {med:g} words; join some up"))
    for i in range(len(lens) - 2):
        win = lens[i:i + 3]
        if max(win) - min(win) <= 3:
            c["findings"].append(_finding(sents[i][0], sents[i][1][:60],
                                          f"three sentences in a row of similar length {win}"))
            break
    if len(doc.paragraphs) >= 3:
        plens = [word_count(doc.para_text(p)) for p in doc.paragraphs]
        if max(plens) and (max(plens) - min(plens)) / max(plens) <= 0.2:
            c["findings"].append(_finding(None, "", f"paragraph lengths all within 20% of each other {plens}"))
    return _settle(c)


def check_ends(doc: Doc, lists: Lists) -> dict:
    c = _check(8, "openers and closers")
    if doc.fmt == "cv-bullets" or not doc.paragraphs:
        c["status"] = "skip"
        return c
    first_para = doc.paragraphs[0]
    first_sentences = split_sentences(doc.para_text(first_para))
    candidates = []
    if first_sentences:
        candidates.append(first_sentences[0])
    candidates.append(doc.para_text(first_para))  # entries that run past the first sentence ("hi! i hope")
    if doc.greeting:
        candidates.append(doc.greeting[1] + " " + (first_sentences[0] if first_sentences else ""))
    line = first_para[0][0]
    flagged = set()
    for cand in candidates:
        low = cand.strip().lower()
        for e in lists.openers:
            if e in flagged:
                continue
            m = entry_regex(e).match(low)
            if m:
                flagged.add(e)
                sev = "warn" if e in WARN_OPENERS else "fail"
                c["findings"].append(_finding(line, cand[:60], f"opener: starts with \u201c{e}\u201d", sev))
        if INTENSIFIER_WITH_YEARS_RE.match(low) and "with-years" not in flagged:
            flagged.add("with-years")
            c["findings"].append(_finding(line, cand[:60], "opener: \u201cWith N years\u2026\u201d", "warn"))
    last = doc.paragraphs[-1]
    last_text = doc.para_text(last)
    for e in lists.closers:
        for m in entry_regex(e).finditer(last_text):
            c["findings"].append(_finding(last[0][0], m.group(0), f"closer in the last paragraph: \u201c{e}\u201d"))
    if len(doc.paragraphs) >= 3 and doc.fmt in ("cover-letter",) + MESSAGE_FORMATS:
        def content(text: str) -> set[str]:
            return {w for w in re.findall(r"[a-z][a-z'-]{3,}", text.lower()) if w not in STOPWORDS}
        shared = content(doc.para_text(first_para)) & content(last_text)
        if len(shared) >= 3:
            c["findings"].append(_finding(last[0][0], ", ".join(sorted(shared)[:6]),
                                          "last paragraph repeats words from the first; is it a recap?", "warn"))
    return _settle(c)


def resolve_locale(arg: str | None, profile: dict | None) -> tuple[str, str]:
    if arg:
        return arg, "--locale"
    if profile:
        for key in ("locale", "spelling"):
            v = str(profile.get(key, "")).lower()
            if "gb" in v or v.startswith("uk") or "en-gb" in v:
                return "uk", "profile"
            if "us" in v.split(";")[0]:
                return "us", "profile"
    cfg_path = user_dir() / "config.toml"
    if cfg_path.is_file():
        try:
            cfg = load_config(cfg_path)
            loc = str(cfg.get("locale", {}).get("default", "")).lower()
            if loc in ("uk", "us"):
                return loc, "config"
        except ConfigError as exc:
            sys.stderr.write(f"warning: {exc}; using locale uk\n")
    return "uk", "default"


def check_voice(doc: Doc, lists: Lists, locale: str, profile: dict | None) -> dict:
    c = _check(10, "voice match (partial)")
    lines = _strip_urls(doc.lines)
    uk_hits, us_hits = [], []
    for uk, us in lists.spelling_two_way:
        uk_hits += [(n, t, uk) for n, t, _ in find_all(entry_regex(uk), lines)]
        us_hits += [(n, t, us) for n, t, _ in find_all(entry_regex(us), lines)]
    if uk_hits and us_hits:
        for n, t, e in uk_hits + us_hits:
            c["findings"].append(_finding(n, t, "mixed UK and US spelling in one document"))
    elif locale == "uk":
        for n, t, e in us_hits:
            c["findings"].append(_finding(n, t, f"US spelling in a UK document: \u201c{e}\u201d"))
    elif locale == "us":
        for n, t, e in uk_hits:
            c["findings"].append(_finding(n, t, f"UK spelling in a US document: \u201c{e}\u201d"))
    if locale == "us":
        for uk, us in lists.spelling_one_way:
            for n, t, _ in find_all(entry_regex(uk), lines):
                c["findings"].append(_finding(n, t, f"UK form in a US document: \u201c{uk}\u201d (US: {us})"))
    c["locale"] = locale
    if profile:
        for e in profile.get("never_uses", []) or []:
            for n, t, _ in find_all(entry_regex(str(e)), lines):
                c["findings"].append(_finding(n, t, f"the user never uses \u201c{e}\u201d"))
        for e in profile.get("pet_phrases", []) or []:
            hits = find_all(entry_regex(str(e)), lines)
            if len(hits) > 1:
                c["findings"].append(_finding(hits[1][0], hits[1][1],
                                              f"pet phrase \u201c{e}\u201d used {len(hits)} times; once is enough", "warn"))
        rate = profile.get("contraction_rate", profile.get("contractions_per_100w"))
        words = word_count(doc.body_text)
        if isinstance(rate, (int, float)) and words > 100 and doc.fmt not in CV_FORMATS:
            actual = 100 * len(CONTRACTION_RE.findall(doc.body_text)) / words
            if rate > 0 and not (0.5 * rate <= actual <= 1.5 * rate):
                c["findings"].append(_finding(None, f"{actual:.1f}/100w",
                                              f"contraction rate {actual:.1f} per 100 words vs profile {rate}", "warn"))
            elif rate == 0 and actual > 0.5:
                c["findings"].append(_finding(None, f"{actual:.1f}/100w",
                                              "contractions used; the profile has none", "warn"))
        greet = profile.get("greeting")
        if greet and doc.fmt in MESSAGE_FORMATS and doc.greeting:
            pat = re.escape(str(greet).split("{")[0].strip().lower())
            if pat and not re.match(pat, doc.greeting[1].lower()):
                c["findings"].append(_finding(doc.greeting[0], doc.greeting[1],
                                              f"greeting differs from the profile ({greet})", "warn"))
    return _settle(c)


def check_format(doc: Doc, max_words: int | None) -> dict:
    c = _check(11, "formatting and length")
    fmt = doc.fmt
    for n, t in doc.lines:
        if re.search(r"\*\*[^*]+\*\*|__[^_]+__", t):
            c["findings"].append(_finding(n, t[:60], "bold text"))
        if re.match(r"^\s*#{1,6}\s", t):
            c["findings"].append(_finding(n, t[:60], "markdown header"))
        if EMOJI_RE.search(t):
            c["findings"].append(_finding(n, t[:60], "emoji"))
        for m in re.finditer(r"\[[^\]]*\]|\{[^}]*\}|<[A-Za-z][^>]*>", t):
            c["findings"].append(_finding(n, m.group(0), "template bracket or placeholder left in"))
        if fmt not in CV_FORMATS and LIST_LINE_RE.match(t):
            c["findings"].append(_finding(n, t[:60], "bullet point outside the CV"))
    if doc.subject:
        words = doc.subject[1].split()
        caps = [w for w in words[1:] if len(w) > 3 and w[0].isupper() and not w.isupper()]
        if len(words) >= 3 and len(caps) > len([w for w in words[1:] if len(w) > 3]) / 2:
            c["findings"].append(_finding(doc.subject[0], doc.subject[1], "subject line in Title Case; use sentence case"))
    body_words = word_count(doc.body_text)
    chars = len(doc.full_text.strip())
    c["words"], c["chars"] = body_words, chars
    if fmt == "linkedin-note" and chars > 300:
        c["findings"].append(_finding(None, "", f"{chars} characters; a connection note allows 300"))
    if fmt in ("email", "hiring-manager") and body_words > 120:
        c["findings"].append(_finding(None, "", f"{body_words} words; keep it to 120"))
    if fmt == "cover-letter" and not 150 <= body_words <= 400:
        c["findings"].append(_finding(None, "", f"{body_words} words; a cover letter should be 150-400"))
    if fmt == "cv-profile" and body_words > 80:
        c["findings"].append(_finding(None, "", f"{body_words} words; a CV profile should be 80 or fewer"))
    if fmt == "form-answer" and max_words and body_words > max_words:
        c["findings"].append(_finding(None, "", f"{body_words} words; the form allows {max_words}"))
    if fmt == "cv-bullets":
        for para in doc.paragraphs:
            t = doc.para_text(para)
            if re.search(r"\b(?:I|my|me)\b", t):
                c["findings"].append(_finding(para[0][0], t[:60], "first-person pronoun in a CV bullet", "warn"))
    return _settle(c)


def lint(text: str, fmt: str, lists: Lists, locale: str | None = None, profile: dict | None = None,
         max_words: int | None = None, notes: list[str] | None = None) -> dict:
    lines, confirms = preprocess(text)
    lines, selection = select_cv_part(lines, fmt)
    doc = Doc(lines, fmt)
    loc, loc_source = resolve_locale(locale, profile)
    tics, tic_spans = check_agent_tics(doc, lists)
    checks = [
        check_banned(doc, lists, tic_spans),
        check_rationed(doc, lists),
        check_specificity(doc, max_words),
        check_rhythm(doc),
        check_ends(doc, lists),
        check_voice(doc, lists, loc, profile),
        check_format(doc, max_words),
        tics,
    ]
    warnings = list(notes or [])
    if confirms:
        warnings.append(f"{confirms} [CONFIRM] marker(s) were ignored for linting; ledger_check.py will block them")
    if lists.missing:
        warnings.append("missing voice lists: " + ", ".join(lists.missing))
    if selection:
        warnings.append(f"{fmt}: {selection}")
    ok = not any(ch["status"] == "fail" for ch in checks)
    return {
        "ok": ok, "format": fmt, "locale": loc, "locale_source": loc_source,
        "words": word_count(doc.body_text), "chars": len(doc.full_text.strip()),
        "checks": checks, "manual": MANUAL_CHECKS, "warnings": warnings,
        "lists_missing": lists.missing, "selection": selection,
        "profile_used": profile is not None,
        "summary": {
            "failed": [ch["id"] for ch in checks if ch["status"] == "fail"],
            "warned": [ch["id"] for ch in checks if ch["status"] == "warn"],
            "rewrite_recommended": len(checks[1].get("categories_over", [])) >= 3,
        },
    }


# --------------------------------------------------------------------- measure

def measure(texts: list[str], lists: Lists) -> dict:
    greetings: Counter = Counter()
    signoffs: Counter = Counter()
    sent_lens: list[int] = []
    words_all: list[str] = []
    bigrams: Counter = Counter()
    total_words = contractions = exclam = quest = 0
    uk = us = 0
    for raw in texts:
        lines, _ = preprocess(raw)
        doc = Doc(lines, "email")
        if doc.greeting:
            greetings[re.sub(r"\s+[A-Z][\w'-]*([,:!]?)$", r" {name}\1", doc.greeting[1])] += 1
        if doc.signoff:
            signoffs[doc.signoff[1]] += 1
        body = doc.body_text
        for _, s in doc.sentences():
            sent_lens.append(word_count(s))
        total_words += word_count(body)
        contractions += len(CONTRACTION_RE.findall(body))
        exclam += body.count("!")
        quest += body.count("?")
        low = _norm_quotes(body.lower())
        for para in doc.paragraphs:
            toks = re.findall(r"[a-z][a-z'-]*", _norm_quotes(doc.para_text(para).lower()))
            content = [t for t in toks if t not in STOPWORDS and len(t) > 2]
            words_all += content
            for a, b in zip(toks, toks[1:]):
                if a not in STOPWORDS and b not in STOPWORDS and len(a) > 2 and len(b) > 2:
                    bigrams[f"{a} {b}"] += 1
        for u, s in lists.spelling_two_way:
            uk += len(entry_regex(u).findall(low))
            us += len(entry_regex(s).findall(low))
    per100 = (lambda n: round(100 * n / total_words, 2) if total_words else 0.0)
    wc = Counter(words_all)
    top_words = [w for w, n in wc.most_common(15) if n >= 2]
    top_bigrams = [b for b, n in bigrams.most_common(15) if n >= 2]
    pet = (top_bigrams + [w for w in top_words if not any(w in b.split() for b in top_bigrams)])[:15]
    n = len(sent_lens)
    return {
        "samples": len(texts),
        "words": total_words,
        "sentences": n,
        "sentence_len_mean": round(statistics.mean(sent_lens), 1) if n else 0.0,
        "sentence_len_median": statistics.median(sent_lens) if n else 0,
        "sentence_len_sd": round(statistics.pstdev(sent_lens), 1) if n > 1 else 0.0,
        "short_sentence_share": round(sum(1 for x in sent_lens if x <= 6) / n, 2) if n else 0.0,
        "long_sentence_share": round(sum(1 for x in sent_lens if x >= 20) / n, 2) if n else 0.0,
        "contraction_rate": per100(contractions),
        "spelling_locale": "uk" if uk > us else ("us" if us > uk else "unknown"),
        "spelling_evidence": {"uk_forms": uk, "us_forms": us},
        "exclamation_rate": per100(exclam),
        "question_rate": per100(quest),
        "rate_units": "per 100 words",
        "pet_phrases": pet,
        "top_words": [[w, c] for w, c in wc.most_common(15)],
        "top_bigrams": [[b, c] for b, c in bigrams.most_common(15)],
        "greetings": [g for g, _ in greetings.most_common(3)],
        "signoffs": [s for s, _ in signoffs.most_common(3)],
        "note": "pet_phrases are frequency candidates; keep only the ones the user agrees are theirs",
    }


# ------------------------------------------------------------------------ CLI

def print_report(res: dict) -> None:
    print(f"{'PASS' if res['ok'] else 'FAIL'}  voice_lint --format {res['format']}  "
          f"({res['words']} words, {res['chars']} chars, locale {res['locale']})")
    for ch in res["checks"]:
        extra = f"  {ch['note']}" if ch.get("note") else ""
        print(f"  [{ch['status'].upper():4}] {ch['id']:>2} {ch['name']}{extra}")
        for f in ch["findings"]:
            where = f"line {f['line']}" if f["line"] else "doc"
            sev = "" if f["severity"] == "fail" else f" ({f['severity']})"
            match = f" \u201c{f['match']}\u201d" if f["match"] else ""
            print(f"         {where}: {f['message']}{match}{sev}")
    print("  Manual checks (do these yourself):")
    for m in res["manual"]:
        print(f"         {m['id']:>2} {m['name']}: {m['how']}")
    for w in res["warnings"]:
        print(f"  warning: {w}")
    if res["summary"]["rewrite_recommended"]:
        print("  Three or more rationed categories over: rewrite from the facts instead of editing.")


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="voice_lint.py")
    p.add_argument("file", nargs="?", help="draft to lint (markdown or plain text)")
    p.add_argument("--format", dest="fmt", choices=FORMATS)
    p.add_argument("--locale", choices=("uk", "us"))
    p.add_argument("--profile", help="voice-profile.json")
    p.add_argument("--max-words", type=int, help="word limit for form answers")
    p.add_argument("--lists-dir", help="directory holding the *.txt voice lists")
    p.add_argument("--measure", nargs="+", metavar="SAMPLE", help="measure idiolect markers from samples")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args(argv)

    lists_dir = Path(a.lists_dir) if a.lists_dir else REFERENCES_DIR / "voice" / "lists"
    if a.measure:
        if a.file or a.fmt:
            p.error("--measure takes sample files only; do not pass a draft or --format")
        lists = Lists(lists_dir)
        res = measure([read_text(Path(f)) for f in a.measure], lists)
        if a.json:
            emit_json(res)
        else:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        return EXIT_OK
    if not a.file or not a.fmt:
        p.error("give a file and --format (or use --measure)")
    if a.max_words is not None and a.max_words <= 0:
        p.error("--max-words must be positive")
    profile = None
    notes: list[str] = []
    if a.profile:
        ppath = Path(a.profile).expanduser()
        if not ppath.is_file():
            msg = (f"no voice profile at {ppath}; voice-match check skipped "
                   f"(the profile parts; locale spelling is still checked)")
            sys.stderr.write(f"warning: {msg}\n")
            notes.append(msg)
        else:
            try:
                profile = json.loads(read_text(ppath))
            except json.JSONDecodeError as exc:
                die(f"{a.profile} is not valid JSON: {exc}")
            if not isinstance(profile, dict):
                die(f"{a.profile} must hold a JSON object")
    text = read_text(Path(a.file))
    lists = Lists(lists_dir)
    res = lint(text, a.fmt, lists, a.locale, profile, a.max_words, notes)
    if a.json:
        emit_json(res)
    else:
        print_report(res)
    return EXIT_OK if res["ok"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
