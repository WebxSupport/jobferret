"""The question queue: questions JobFerret could not ask yet, kept for later.

Purpose
    When a step needs an answer and the user skips it or isn't there, the mode
    carries on with the default and queues the question here. The next digest,
    or the next time the user is around, shows the pending ones. An answer is
    written into profile.json, so it is never asked again.

Usage
    qa.py add --key <key> --question "<text>" [--context "<why it's asked>"]
              [--options a,b,c] [--default "<value used meanwhile>"] [--mode <mode>] [--force]
    qa.py pending [--json]
    qa.py list [--all] [--json]
    qa.py answer <id> "<text>" [--force] [--json]
    qa.py drop <id> [--json]

    <key> names the profile field the answer goes to. A plain key such as
    why_looking writes profile.json answer_bank[why_looking]. A dotted key whose
    first part is a profile section (targets, eligibility, exclusions,
    preferences, personal, answer_bank) writes that path, for example
    targets.salary_floor.amount. The answer is converted to the type the field
    already has: numbers for numeric fields, yes/no for true/false fields. For a
    list field the answer is split on ";" or newlines; without either it is one item,
    so "Data analyst, public sector" stays whole. answer refuses a question that is
    not pending (exit 1) unless --force, which re-answers an answered or dropped one.

    add dedups on key: a pending question with the same key is reported, not
    added again; an answered one is left alone unless --force. A dropped one is
    reopened. <id> is Q001 or just 1.

Storage
    $JOBFERRET_HOME/questions.json (default ~/.jobferret/questions.json):
    {"version": 1, "next_id": 4, "questions": [{"id": "Q001", "key": "...",
     "question": "...", "context": "...", "options": [], "default": "...",
     "mode": "start", "status": "pending|answered|dropped", "created_at": ISO,
     "updated_at": ISO, "answer": null, "answered_at": null}]}

Exit codes
    0  ok (including "already queued" and "already answered")
    1  no question with that id, or it is not pending
    4  usage or input error (bad key, unreadable questions.json or profile.json)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jf_common import (
    EXIT_FAIL, EXIT_OK, EXIT_USAGE, atomic_write_text, die, emit_json, get_path, load_json_file,
    load_profile, make_parser, now_iso, profile_path, save_profile, set_path, setup_io, user_dir,
)

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
PROFILE_SECTIONS = ("answer_bank", "targets", "eligibility", "exclusions", "preferences", "personal")
MAX_TEXT = 2000


def queue_path() -> Path:
    return user_dir() / "questions.json"


def load_queue() -> dict:
    p = queue_path()
    if not p.is_file():
        return {"version": 1, "next_id": 1, "questions": []}
    try:
        data = load_json_file(p)
    except ValueError as exc:
        die(str(exc))
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        die(f"{p} is not a JobFerret question queue")
    data.setdefault("next_id", len(data["questions"]) + 1)
    return data


def save_queue(queue: dict) -> None:
    atomic_write_text(queue_path(), json.dumps(queue, indent=2, ensure_ascii=False) + "\n")


def normalise_id(raw: str) -> str:
    m = re.fullmatch(r"[Qq]?0*(\d+)", raw.strip())
    if not m:
        die(f"not a question id: {raw!r} (use Q001 or 1)")
    return f"Q{int(m.group(1)):03d}"


def find(queue: dict, qid: str) -> dict | None:
    return next((q for q in queue["questions"] if q["id"] == qid), None)


def profile_target(key: str) -> str:
    """The dotted profile path an answer to `key` is written to."""
    if "." in key:
        if key.split(".", 1)[0] not in PROFILE_SECTIONS:
            die(f"dotted key must start with one of: {', '.join(PROFILE_SECTIONS)}")
        return key
    return f"answer_bank.{key}"


def coerce(text: str, existing):
    """Convert the answer to the type the profile field already has."""
    t = text.strip()
    if isinstance(existing, bool):
        low = t.lower()
        if low in ("yes", "y", "true", "1"):
            return True
        if low in ("no", "n", "false", "0"):
            return False
        return t
    if isinstance(existing, (int, float)):
        num = re.sub(r"[£,\s]", "", t).lower()
        mult = 1000 if num.endswith("k") else 1
        num = num.rstrip("k")
        try:
            val = float(num) * mult
            return int(val) if isinstance(existing, int) and val.is_integer() else val
        except ValueError:
            return t
    if isinstance(existing, list):
        if ";" in t or "\n" in t:
            return [part.strip() for part in re.split(r"[;\n]", t) if part.strip()]
        return [t]          # "Data analyst, public sector" is one item
    return t


def cmd_add(a) -> int:
    if not KEY_RE.match(a.key):
        die("--key must be lower_snake_case words, optionally dotted (targets.salary_floor.amount)")
    profile_target(a.key)
    if not a.question.strip() or len(a.question) > MAX_TEXT:
        die(f"--question must be 1 to {MAX_TEXT} characters")
    queue = load_queue()
    now = now_iso()
    same = [q for q in queue["questions"] if q["key"] == a.key]
    pending = next((q for q in same if q["status"] == "pending"), None)
    answered = next((q for q in same if q["status"] == "answered"), None)
    if pending:
        return report(a, pending, f"already queued as {pending['id']}")
    if answered and not a.force:
        return report(a, answered, f"already answered ({answered['id']}): {answered['answer']}")
    options = [o.strip() for o in (a.options or "").split(",") if o.strip()]
    dropped = next((q for q in same if q["status"] == "dropped"), None)
    if dropped:
        q = dropped
        q.update({"question": a.question.strip(), "context": a.context or q.get("context", ""),
                  "options": options or q.get("options", []), "status": "pending", "updated_at": now})
        msg = f"reopened {q['id']}"
    else:
        q = {"id": f"Q{queue['next_id']:03d}", "key": a.key, "question": a.question.strip(),
             "context": (a.context or "").strip(), "options": options, "default": (a.default or "").strip(),
             "mode": a.mode or "", "status": "pending", "created_at": now, "updated_at": now,
             "answer": None, "answered_at": None}
        queue["next_id"] += 1
        queue["questions"].append(q)
        msg = f"queued {q['id']}"
    save_queue(queue)
    return report(a, q, msg)


def report(a, q: dict, msg: str) -> int:
    if getattr(a, "json", False):
        emit_json({"ok": True, "message": msg, "question": q})
    else:
        print(f"{msg}: {q['question']}")
    return EXIT_OK


def cmd_pending(a) -> int:
    queue = load_queue()
    items = [q for q in queue["questions"] if q["status"] == "pending" or (a.all and a.cmd == "list")]
    if a.json:
        emit_json({"count": len(items), "questions": items})
        return EXIT_OK
    if not items:
        print("No questions waiting.")
        return EXIT_OK
    for q in items:
        opts = f" Options: {', '.join(q['options'])}." if q.get("options") else ""
        default = f" Default meanwhile: {q['default']}." if q.get("default") else ""
        status = "" if q["status"] == "pending" else f" [{q['status']}]"
        print(f"{q['id']}{status} {q['question']}{opts}{default}")
    return EXIT_OK


def cmd_answer(a) -> int:
    queue = load_queue()
    qid = normalise_id(a.id)
    q = find(queue, qid)
    if not q:
        sys.stderr.write(f"error: no question {qid}\n")
        return EXIT_FAIL
    if q["status"] != "pending" and not (a.force and q["status"] in ("answered", "dropped")):
        hint = "; use --force to answer it again" if q["status"] == "answered" else ""
        sys.stderr.write(f"error: {qid} is {q['status']}, not pending{hint}\n")
        return EXIT_FAIL
    text = a.text.strip()
    if not text or len(text) > MAX_TEXT:
        die(f"the answer must be 1 to {MAX_TEXT} characters")
    try:
        profile = load_profile()
    except ValueError as exc:
        die(str(exc))
    path = profile_target(q["key"])
    value = coerce(text, get_path(profile, path, ""))
    set_path(profile, path, value)
    saved = save_profile(profile)
    now = now_iso()
    q.update({"status": "answered", "answer": text, "answered_at": now, "updated_at": now})
    save_queue(queue)
    if a.json:
        emit_json({"ok": True, "question": q, "profile_path": path, "value": value, "profile": str(saved)})
    else:
        print(f"{qid} answered. Saved to profile.json {path} = {json.dumps(value, ensure_ascii=False)}")
    return EXIT_OK


def cmd_drop(a) -> int:
    queue = load_queue()
    qid = normalise_id(a.id)
    q = find(queue, qid)
    if not q:
        sys.stderr.write(f"error: no question {qid}\n")
        return EXIT_FAIL
    if q["status"] != "pending":
        sys.stderr.write(f"error: {qid} is {q['status']}, not pending\n")
        return EXIT_FAIL
    q.update({"status": "dropped", "updated_at": now_iso()})
    save_queue(queue)
    if a.json:
        emit_json({"ok": True, "question": q})
    else:
        print(f"{qid} dropped.")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="qa.py")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=type(p))
    s = sub.add_parser("add", help="queue a question (dedups on --key)")
    s.add_argument("--key", required=True)
    s.add_argument("--question", required=True)
    s.add_argument("--context", default="")
    s.add_argument("--options", default="", help="comma-separated choices")
    s.add_argument("--default", default="", help="the value used until it is answered")
    s.add_argument("--mode", default="", help="the mode that asked")
    s.add_argument("--force", action="store_true", help="queue again even if already answered")
    s.add_argument("--json", action="store_true")
    for name in ("pending", "list"):
        s = sub.add_parser(name, help="show pending questions" if name == "pending" else "show questions")
        s.add_argument("--all", action="store_true", help="(list) include answered and dropped")
        s.add_argument("--json", action="store_true")
    s = sub.add_parser("answer", help="record an answer in profile.json")
    s.add_argument("id")
    s.add_argument("text")
    s.add_argument("--force", action="store_true", help="answer a question that is already answered or dropped")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("drop", help="remove a question without answering")
    s.add_argument("id")
    s.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    if not hasattr(a, "all"):
        a.all = False
    return {"add": cmd_add, "pending": cmd_pending, "list": cmd_pending, "answer": cmd_answer,
            "drop": cmd_drop}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
