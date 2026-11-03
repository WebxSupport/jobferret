"""Read and write the run state, so a mode can pick up where it stopped.

Purpose
    Each mode records the step it reached in $JOBFERRET_HOME/state.json
    (default ~/.jobferret/state.json). On the next run the skill reads it and
    offers to continue. A thin command-line wrapper over save_state(),
    load_state() and clear_state() in jf_common.py.

Usage
    state.py show [--json]
    state.py set --mode <mode> --step <n> [--of <total>] [--name "<step name>"]
                 [--status running|waiting|done|stopped] [--context '<JSON object>'] [--json]
    state.py clear [--json]

    Schema: {"version": 1, "mode": "start", "step": 3, "steps_total": 7,
    "step_name": "Draft profile", "status": "running", "started_at": ISO,
    "updated_at": ISO, "context": {...}}. Setting the same unfinished mode keeps
    started_at and merges --context into the stored context; a different mode,
    or one marked done or stopped, starts a fresh record.

Exit codes
    0  ok
    1  show: no saved state
    4  usage or input error (bad --context JSON, bad status)
"""
from __future__ import annotations

import json
import sys

from jf_common import (
    EXIT_FAIL, EXIT_OK, STATE_STATUSES, clear_state, describe_state, die, emit_json, load_state,
    make_parser, save_state, setup_io,
)


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="state.py")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=type(p))
    s = sub.add_parser("show")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("set")
    s.add_argument("--mode", required=True)
    s.add_argument("--step", required=True, type=int)
    s.add_argument("--of", type=int, default=None, dest="total")
    s.add_argument("--name", default="")
    s.add_argument("--status", default="running", choices=STATE_STATUSES)
    s.add_argument("--context", default=None, help="JSON object merged into the stored context")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("clear")
    s.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "show":
        st = load_state()
        if a.json:
            emit_json({"state": st, "line": describe_state(st)})
        else:
            print(describe_state(st))
        return EXIT_OK if st else EXIT_FAIL
    if a.cmd == "set":
        ctx = None
        if a.context:
            try:
                ctx = json.loads(a.context)
            except json.JSONDecodeError as exc:
                die(f"--context is not valid JSON: {exc}")
            if not isinstance(ctx, dict):
                die("--context must be a JSON object")
        st = save_state(a.mode, a.step, step_name=a.name, steps_total=a.total, status=a.status, context=ctx)
        if a.json:
            emit_json(st)
        else:
            print(describe_state(st))
        return EXIT_OK
    removed = clear_state()
    if a.json:
        emit_json({"cleared": removed})
    else:
        print("Cleared." if removed else "Nothing to clear.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
