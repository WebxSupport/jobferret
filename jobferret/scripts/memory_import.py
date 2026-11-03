"""memory_import.py: chat exports and memory folders -> memory/signals.json, on this computer only.

Purpose
    Finds evidence of what the user does and cares about in their own past
    chats and assistant memory files, so the suggest mode can propose role
    families with reasons (ARCHITECTURE section 10.3). Extraction is
    deterministic: a word list and a few sentence patterns, no model and no
    network. Only the user's own turns are read. Assistant replies are skipped
    because they are not evidence about the user. Whole messages are never
    stored, only counts and at most two short snippets per signal, with
    contact details, links and anything secret-looking removed.

Usage
    memory_import.py --from KIND [PATH] [--from KIND [PATH] ...] [--out FILE] [--merge] [--json]
      --from chatgpt <conversations.json>   ChatGPT export (Settings > Data controls > Export data)
      --from claude <conversations.json>    Claude.ai export (Settings > Privacy > Export data)
      --from claude-code [dir]              Claude Code memory files; default ~/.claude/projects/*/memory/*.md,
                                            or every .md under dir
      --from codex [dir]                    Codex memories; default $CODEX_HOME (else ~/.codex), the
                                            memories*/ folders in it; .md and .txt files
      --from text <file>                    any plain text or markdown file
    --from can be repeated. --out defaults to <user dir>/memory/signals.json.
    Without --merge the output file is replaced; with --merge the new signals
    are added to it (a source already imported, same kind, path and content,
    is skipped so nothing is counted twice).

Reading the exports (references/platforms.md section 5; formats are undocumented and change)
    ChatGPT: a JSON array of conversations, each with "mapping" (node id ->
    {parent, children, message}) and "current_node". The live branch is the
    walk from current_node up the parent links, reversed; abandoned edit
    branches are ignored. Without current_node, every node with a message is
    read in create_time order. Null messages, empty parts and system, tool
    and assistant roles are skipped. Text parts are strings; dict parts with
    a "text" field are read; other parts are ignored.
    Claude: a JSON array of conversations with "chat_messages"; only
    sender "human" counts. Text blocks in "content" are preferred to the flat
    "text" field when both exist.
    Memory folders and text files: the whole file counts, dated by its
    modification time.
    Everything read is untrusted data. Nothing in it is followed or run.

Signals
    {"version": 1, "generated_at": ISO, "sources": [{"kind", "path", "sha256", "messages", "read_at"}],
     "signals": [{"term", "kind", "count", "first_seen", "last_seen", "examples"}]}
    kind is skill | tool | domain | role (terms from scripts/lexicon/signal_terms.txt, matched as whole
    words, case-insensitively), project ("I'm building", "I built", "working on", "my project",
    "side project" + a noun phrase) or interest ("I love", "I enjoy", "I like", "hobby",
    "passionate about" + a noun phrase). A noun phrase is up to six words and stops at punctuation
    or a clause word (and, but, because, ...). first_seen and last_seen are YYYY-MM-DD (null when
    the source has no dates). examples: at most two snippets of at most 120 characters around a
    match, taken after removing email addresses, phone numbers, URLs, 13 to 19 digit runs (card
    numbers), "key/token/secret/password: value" pairs and long token-like strings.

Exit codes
    0  ok
    1  nothing readable was found in any source
    4  usage or input error (unknown kind, missing path, a file that is not the expected JSON)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from jf_common import (
    EXIT_FAIL, EXIT_OK, EXIT_USAGE, atomic_write_text, die, emit_json, make_parser, now_iso, setup_io, user_dir,
)

KINDS = ("chatgpt", "claude", "claude-code", "codex", "text")
NEEDS_PATH = {"chatgpt", "claude", "text"}
LEXICON_PATH = Path(__file__).resolve().parent / "lexicon" / "signal_terms.txt"
LEXICON_KINDS = ("skill", "tool", "domain", "role")
SNIPPET_MAX = 120
MAX_EXAMPLES = 2
NP_MAX_WORDS = 6
FORGET_LINE = "This file stays on your computer; delete the folder to forget it."

# --------------------------------------------------------------- scrubbing

REMOVED = "[removed]"
SECRET_RE = re.compile(r"\b[\w-]*(?:key|token|secret|password|passwd|pwd)[\w-]*\s*[:=]\s*\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|co\.uk|org\.uk|ac\.uk|gov\.uk|org|io|"
                    r"uk|ai|app|dev|me|info|ly|gg)(?:/\S*)?(?![\w.])", re.IGNORECASE)
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
PHONE_RE = re.compile(r"(?<![\w])\+?\(?\d[\d ().-]{7,18}\d(?![\w])")
TOKEN_RE = re.compile(r"\b(?:sk|pk|rk|ghp|gho|xox[abprs])[-_][A-Za-z0-9_-]{8,}|\b[A-Za-z0-9_\-]{32,}\b")


def scrub(text: str) -> str:
    """Remove secrets, emails, URLs, card-like and phone-like numbers and long tokens."""
    t = SECRET_RE.sub(REMOVED, text)
    t = EMAIL_RE.sub(REMOVED, t)
    t = URL_RE.sub(REMOVED, t)
    t = CARD_RE.sub(REMOVED, t)

    def phone(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return REMOVED if 9 <= len(digits) <= 15 else m.group(0)
    t = PHONE_RE.sub(phone, t)
    return TOKEN_RE.sub(REMOVED, t)


# --------------------------------------------------------------- lexicon

TOKEN_SPLIT_RE = re.compile(r"[a-z0-9][a-z0-9+#./&'-]*[a-z0-9+#]|[a-z0-9]", re.IGNORECASE)


def _tokens(text: str) -> list[tuple[str, int, int]]:
    """Lower-case tokens with their spans. Possessive 's is dropped; a/b-style tokens not in the
    lexicon are split on / so "SQL/Python" yields both words."""
    out = []
    for m in TOKEN_SPLIT_RE.finditer(text):
        tok, start = m.group(0).lower(), m.start()
        if tok.endswith("'s"):
            tok = tok[:-2]
        out.append((tok, start, start + len(tok)))
    return out


def _norm(term: str) -> str:
    return " ".join(t for t, _, _ in _tokens(term))


def load_lexicon(path: Path = LEXICON_PATH) -> dict[str, tuple[str, str]]:
    """normalised term -> (term as written, kind). "# kind: X" lines set the kind for the lines below."""
    lex: dict[str, tuple[str, str]] = {}
    kind = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"#\s*kind:\s*(\w+)", line)
        if m:
            kind = m.group(1).lower()
            if kind not in LEXICON_KINDS:
                raise ValueError(f"{path}: unknown kind {kind!r}")
            continue
        if line.startswith("#"):
            continue
        if kind is None:
            raise ValueError(f"{path}: term {line!r} comes before any '# kind:' line")
        key = _norm(line)
        if key and key not in lex:
            lex[key] = (line.lower(), kind)
    return lex


class Matcher:
    def __init__(self, lexicon: dict[str, tuple[str, str]]):
        self.lex = lexicon
        self.max_n = max((len(k.split()) for k in lexicon), default=1)

    def find(self, text: str):
        """Yield (term, kind, start, end) for lexicon terms, longest match first, no overlaps."""
        toks = []
        for tok, s, e in _tokens(text):
            if "/" in tok and tok not in self.lex:
                pos = s
                for part in tok.split("/"):
                    if part:
                        toks.append((part, pos, pos + len(part)))
                    pos += len(part) + 1
            else:
                toks.append((tok, s, e))
        i = 0
        while i < len(toks):
            hit = None
            for n in range(min(self.max_n, len(toks) - i), 0, -1):
                key = " ".join(t for t, _, _ in toks[i:i + n])
                if key in self.lex:
                    hit = (n, self.lex[key])
                    break
            if hit:
                n, (term, kind) = hit
                yield term, kind, toks[i][1], toks[i + n - 1][2]
                i += n
            else:
                i += 1


# --------------------------------------------------------------- patterns

NP_BODY = r"(?P<np>[^.,;:!?\n()\[\]\"]{1,120})"
PROJECT_RE = re.compile(r"\b(?:i'?m building|i am building|i built|i'?ve built|i have built|i'?m working on|"
                        r"i am working on|working on|my side project|side project|my project)\b[\s:,-]*" + NP_BODY,
                        re.IGNORECASE)
INTEREST_RE = re.compile(r"\b(?:i really love|i love|i really enjoy|i enjoy|i really like|i like|"
                         r"i'?m passionate about|passionate about|my hobbies are|my hobbies include|my hobby is|"
                         r"hobbies|hobby|i'?m into)\b[\s:,-]*" + NP_BODY, re.IGNORECASE)
LEADING_SKIP = {"a", "an", "the", "my", "our", "some", "another", "called", "is", "was", "are", "were",
                "include", "includes", "on", "of", "about", "doing", "to"}
DISCARD_FIRST = {"it", "this", "that", "these", "those", "them", "something", "stuff", "things", "you", "your",
                 "how", "what", "when", "why", "where", "if", "when", "whether", "here", "there", "him", "her",
                 "me", "us", "everything", "anything", "nothing", "a lot", "lot", "very", "too", "much", "more"}
STOP_WORDS = {"and", "but", "because", "so", "that", "which", "who", "when", "while", "if", "then", "since",
              "though", "although", "or", "i", "i'm", "im", "we", "you", "it", "it's", "as", "than", "please",
              "can", "could", "would", "should", "will", "but"}
TRAILING_DROP = {"for", "with", "in", "on", "of", "at", "to", "from", "by", "a", "an", "the", "my", "our", "about",
                 "into", "right", "now", "currently", "recently", "really", "very", "too"}
NP_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.'&/-]*")


def noun_phrase(raw: str) -> str | None:
    words = [w.lower().rstrip(".'") for w in NP_WORD_RE.findall(raw)]
    while words and words[0] in LEADING_SKIP:
        words.pop(0)
    if not words or words[0] in DISCARD_FIRST:
        return None
    out = []
    for w in words:
        if w in STOP_WORDS or w == REMOVED.strip("[]"):
            break
        out.append(w)
        if len(out) == NP_MAX_WORDS:
            break
    while out and out[-1] in TRAILING_DROP:
        out.pop()
    if not out or not any(len(re.sub(r"[^a-z]", "", w)) >= 3 for w in out):
        return None
    return " ".join(out)


# --------------------------------------------------------------- readers

class InputError(Exception):
    """A source file is missing or not in the expected shape (exit 4)."""


def _date_from_epoch(value) -> str | None:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _date_from_iso(value) -> str | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        m = re.match(r"\d{4}-\d{2}-\d{2}", value)
        return m.group(0) if m else None


def _file_date(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
    except OSError:
        return None


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise InputError(f"file not found: {path}") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise InputError(f"{path} is not a JSON file ({exc})") from exc


def _conversations(data, path: Path) -> list:
    if isinstance(data, list):
        return [c for c in data if isinstance(c, dict)]
    if isinstance(data, dict):
        for key in ("conversations", "data", "items"):
            if isinstance(data.get(key), list):
                return [c for c in data[key] if isinstance(c, dict)]
        if "mapping" in data or "chat_messages" in data:
            return [data]
    raise InputError(f"{path} does not hold a list of conversations")


def _chatgpt_text(message: dict) -> str:
    content = message.get("content") or {}
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    texts = []
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, str):
                texts.append(p)
            elif isinstance(p, dict) and isinstance(p.get("text"), str):
                texts.append(p["text"])
    elif isinstance(content.get("text"), str):
        texts.append(content["text"])
    return "\n".join(t for t in texts if t.strip())


def read_chatgpt(path: Path) -> list[tuple[str, str | None]]:
    out = []
    for conv in _conversations(_load_json(path), path):
        mapping = conv.get("mapping")
        if not isinstance(mapping, dict):
            continue
        nodes = []
        cur = conv.get("current_node")
        seen = set()
        if cur in mapping:
            while cur and cur in mapping and cur not in seen:
                seen.add(cur)
                node = mapping[cur] if isinstance(mapping[cur], dict) else {}
                nodes.append(node)
                cur = node.get("parent")
            nodes.reverse()
        else:
            nodes = sorted((n for n in mapping.values() if isinstance(n, dict) and isinstance(n.get("message"), dict)),
                           key=lambda n: float((n["message"].get("create_time") or 0)))
        for node in nodes:
            msg = node.get("message")
            if not isinstance(msg, dict):
                continue
            role = (msg.get("author") or {}).get("role") if isinstance(msg.get("author"), dict) else None
            if role != "user":
                continue
            text = _chatgpt_text(msg)
            if text.strip():
                out.append((text, _date_from_epoch(msg.get("create_time")) or _date_from_epoch(conv.get("create_time"))))
    return out


def read_claude(path: Path) -> list[tuple[str, str | None]]:
    out = []
    for conv in _conversations(_load_json(path), path):
        msgs = conv.get("chat_messages")
        if not isinstance(msgs, list):
            continue
        msgs = [m for m in msgs if isinstance(m, dict)]
        if any(m.get("created_at") for m in msgs):
            msgs.sort(key=lambda m: str(m.get("created_at") or ""))
        for m in msgs:
            if m.get("sender") != "human":
                continue
            blocks = m.get("content")
            text = ""
            if isinstance(blocks, list):
                text = "\n".join(b["text"] for b in blocks if isinstance(b, dict) and b.get("type") == "text"
                                 and isinstance(b.get("text"), str))
            if not text.strip() and isinstance(m.get("text"), str):
                text = m["text"]
            if text.strip():
                out.append((text, _date_from_iso(m.get("created_at")) or _date_from_iso(conv.get("created_at"))))
    return out


def _read_files(files: list[Path]) -> list[tuple[str, str | None]]:
    out = []
    for f in sorted(set(files)):
        try:
            text = f.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if text.strip():
            out.append((text, _file_date(f)))
    return out


def claude_code_files(directory: Path | None) -> tuple[Path, list[Path]]:
    if directory is None:
        base = Path.home() / ".claude" / "projects"
        return base, sorted(base.glob("*/memory/*.md"))
    return directory, sorted(directory.rglob("*.md"))


def codex_files(directory: Path | None) -> tuple[Path, list[Path]]:
    base = directory or Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    dirs = [d for d in base.glob("memories*") if d.is_dir()]
    if not dirs and directory is not None:
        dirs = [base]
    files: list[Path] = []
    for d in dirs:
        files += [f for f in d.rglob("*") if f.is_file() and f.suffix.lower() in (".md", ".txt")]
    return base, sorted(files)


def read_source(kind: str, path: str | None) -> tuple[str, list[tuple[str, str | None]], str | None]:
    """Return (display path, [(text, date)], sha256 of the content read)."""
    if kind in NEEDS_PATH and not path:
        raise InputError(f"--from {kind} needs a file path")
    p = Path(path).expanduser() if path else None
    if kind in ("chatgpt", "claude", "text"):
        if not p.is_file():
            raise InputError(f"file not found: {p}")
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if kind == "chatgpt":
            return str(p), read_chatgpt(p), sha
        if kind == "claude":
            return str(p), read_claude(p), sha
        return str(p), _read_files([p]), sha
    if p is not None and not p.is_dir():
        raise InputError(f"folder not found: {p}")
    base, files = claude_code_files(p) if kind == "claude-code" else codex_files(p)
    h = hashlib.sha256()
    for f in files:
        try:
            h.update(f.as_posix().encode("utf-8") + b"\0" + f.read_bytes())
        except OSError:
            pass
    return str(base), _read_files(files), (h.hexdigest() if files else None)


# --------------------------------------------------------------- extraction

def snippet(text: str, start: int, end: int) -> str:
    room = max(0, SNIPPET_MAX - (end - start))
    a = max(0, start - room // 2)
    b = min(len(text), end + room - (start - a))
    a = max(0, min(a, b - SNIPPET_MAX))
    s = re.sub(r"\s+", " ", text[a:b]).strip()
    return s[:SNIPPET_MAX].strip()


def extract(messages: list[tuple[str, str | None]], matcher: Matcher) -> dict[tuple[str, str], dict]:
    sig: dict[tuple[str, str], dict] = {}

    def add(term: str, kind: str, day: str | None, text: str, s: int, e: int) -> None:
        rec = sig.setdefault((term, kind), {"term": term, "kind": kind, "count": 0, "first_seen": None,
                                            "last_seen": None, "examples": []})
        rec["count"] += 1
        if day:
            rec["first_seen"] = min(filter(None, (rec["first_seen"], day)))
            rec["last_seen"] = max(filter(None, (rec["last_seen"], day)))
        if len(rec["examples"]) < MAX_EXAMPLES:
            snip = snippet(text, s, e)
            if snip and snip not in rec["examples"]:
                rec["examples"].append(snip)

    for raw, day in messages:
        text = scrub(raw)
        for term, kind, s, e in matcher.find(text):
            add(term, kind, day, text, s, e)
        for rx, kind in ((PROJECT_RE, "project"), (INTEREST_RE, "interest")):
            pos = 0
            while True:
                m = rx.search(text, pos)
                if m is None:
                    break
                np = noun_phrase(m.group("np"))
                if np:
                    add(np, kind, day, text, m.start(), m.end("np"))
                pos = m.start("np")  # a second trigger inside this phrase ("... and I enjoy X") still counts
    return sig


def merge_signals(old: list[dict], new: dict[tuple[str, str], dict]) -> list[dict]:
    combined: dict[tuple[str, str], dict] = {}
    for rec in old:
        if isinstance(rec, dict) and rec.get("term") and rec.get("kind"):
            combined[(rec["term"], rec["kind"])] = {**rec, "examples": list(rec.get("examples") or [])[:MAX_EXAMPLES]}
    for key, rec in new.items():
        if key not in combined:
            combined[key] = rec
            continue
        cur = combined[key]
        cur["count"] = int(cur.get("count") or 0) + rec["count"]
        firsts = [d for d in (cur.get("first_seen"), rec["first_seen"]) if d]
        lasts = [d for d in (cur.get("last_seen"), rec["last_seen"]) if d]
        cur["first_seen"] = min(firsts) if firsts else None
        cur["last_seen"] = max(lasts) if lasts else None
        for ex in rec["examples"]:
            if len(cur["examples"]) < MAX_EXAMPLES and ex not in cur["examples"]:
                cur["examples"].append(ex)
    order = {"skill": 0, "tool": 1, "domain": 2, "role": 3, "project": 4, "interest": 5}
    return sorted(combined.values(), key=lambda r: (-int(r.get("count") or 0), order.get(r["kind"], 9), r["term"]))


def run_import(sources: list[tuple[str, str | None]], out: Path, merge: bool = False,
               lexicon_path: Path = LEXICON_PATH) -> dict:
    matcher = Matcher(load_lexicon(lexicon_path))
    existing = {"sources": [], "signals": []}
    if merge and out.is_file():
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                existing = {"sources": list(data.get("sources") or []), "signals": list(data.get("signals") or [])}
        except ValueError as exc:
            raise InputError(f"{out} is not a signals file ({exc}); move it aside or drop --merge") from exc
    done = {(s.get("kind"), s.get("path"), s.get("sha256")) for s in existing["sources"] if isinstance(s, dict)}
    collected: dict[tuple[str, str], dict] = {}
    read, skipped, scanned = [], [], 0
    for kind, path in sources:
        shown, messages, sha = read_source(kind, path)
        if merge and sha and (kind, shown, sha) in done:
            skipped.append({"kind": kind, "path": shown, "reason": "already imported"})
            continue
        found = extract(messages, matcher)
        for key, rec in found.items():
            if key in collected:
                c = collected[key]
                c["count"] += rec["count"]
                c["first_seen"] = min(filter(None, (c["first_seen"], rec["first_seen"])), default=None)
                c["last_seen"] = max(filter(None, (c["last_seen"], rec["last_seen"])), default=None)
                for ex in rec["examples"]:
                    if len(c["examples"]) < MAX_EXAMPLES and ex not in c["examples"]:
                        c["examples"].append(ex)
            else:
                collected[key] = rec
        scanned += len(messages)
        read.append({"kind": kind, "path": shown, "sha256": sha, "messages": len(messages), "read_at": now_iso()})
    signals = merge_signals(existing["signals"] if merge else [], collected)
    doc = {"version": 1, "generated_at": now_iso(), "sources": (existing["sources"] if merge else []) + read,
           "signals": signals}
    by_kind: dict[str, int] = {}
    for rec in collected.values():
        by_kind[rec["kind"]] = by_kind.get(rec["kind"], 0) + 1
    summary = {"sources_read": read, "sources_skipped": skipped, "messages_scanned": scanned,
               "signals_found": len(collected), "signals_by_kind": by_kind, "signals_in_file": len(signals),
               "out": str(out), "note": FORGET_LINE}
    if scanned == 0 and not skipped:
        return {**summary, "written": False}
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(out, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return {**summary, "written": True}


# --------------------------------------------------------------- CLI

def parse_sources(values: list[list[str]]) -> list[tuple[str, str | None]]:
    out = []
    for v in values:
        kind = v[0].lower()
        if kind not in KINDS:
            raise InputError(f"--from {v[0]!r}: use one of {', '.join(KINDS)}")
        if len(v) > 2:
            raise InputError(f"--from {kind} takes at most one path (got {len(v) - 1})")
        path = v[1] if len(v) == 2 else None
        if kind in NEEDS_PATH and not path:
            raise InputError(f"--from {kind} needs a file path")
        out.append((kind, path))
    return out


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="memory_import.py")
    p.add_argument("--from", dest="sources", action="append", nargs="+", required=True, metavar="KIND [PATH]",
                   help="chatgpt FILE | claude FILE | claude-code [DIR] | codex [DIR] | text FILE")
    p.add_argument("--out", help="output file (default <user dir>/memory/signals.json)")
    p.add_argument("--merge", action="store_true", help="add to an existing signals file")
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    a = p.parse_args(argv)
    out = Path(a.out).expanduser() if a.out else user_dir() / "memory" / "signals.json"
    try:
        res = run_import(parse_sources(a.sources), out, a.merge)
    except InputError as exc:
        die(str(exc), EXIT_USAGE)
    except ValueError as exc:
        die(str(exc), EXIT_USAGE)
    if a.json:
        emit_json(res)
    else:
        for s in res["sources_read"]:
            print(f"Read {s['kind']}: {s['path']} ({s['messages']} messages or files)")
        for s in res["sources_skipped"]:
            print(f"Skipped {s['kind']}: {s['path']} ({s['reason']})")
        print(f"Messages scanned: {res['messages_scanned']}")
        kinds = ", ".join(f"{k} {n}" for k, n in sorted(res["signals_by_kind"].items())) or "none"
        print(f"Signals found: {res['signals_found']} ({kinds})")
        if res["written"]:
            print(f"Written to: {res['out']}")
            print(FORGET_LINE)
        else:
            print("Nothing readable was found, so no file was written.")
    return EXIT_OK if res["written"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
