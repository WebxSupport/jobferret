"""hunt_cron.py: discover, screen and write the digest in one command. Needs no model.

Usage
    hunt_cron.py [--since N] [--offline] [--json]

Schedule it with Windows Task Scheduler or cron (references/modes/hunt.md shows both,
plus the Claude Code and Codex forms). It only reads job sources and writes to
~/.jobferret: it never applies, sends or submits anything, so an unattended run is safe.
The user reviews the digest and runs `/jobferret hunt` to pick and apply.

Steps
    1. Check the kill switch (~/.jobferret/RUN). Missing: stop, write nothing.
    2. discover.py run (every enabled source with its key; the rest are skipped and named).
    3. screen.py --run <that run>.
    4. digest.py for today: ~/.jobferret/digests/YYYY-MM-DD.md, listing any source that
       failed and why.

Exit codes
    0  a digest was written (even if some sources failed; the digest lists them)
    1  nothing could run: the kill switch is set, or no source ran (the digest is still
       written in that case, saying why)
    4  usage or input error (bad config.toml or profile.json)
"""
from __future__ import annotations

import sys
from datetime import date

import db
import digest
import discover
import jf_net
import screen
from jf_common import EXIT_FAIL, EXIT_OK, EXIT_USAGE, ConfigError, emit_json, make_parser, setup_io, user_dir


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="hunt_cron.py")
    p.add_argument("--since", type=int, help="days to look back (default: per source, since its last good run)")
    jf_net.add_offline_arg(p)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    jf_net.apply_offline_arg(a)
    if a.since is not None and a.since < 1:
        p.error("--since must be 1 or more days")
    result: dict = {"ok": False, "steps": []}

    def say(line: str) -> None:
        result["steps"].append(line)
        if not a.json:
            print(line, flush=True)

    if discover.kill_switch_set():
        msg = f"Stopped: the kill switch is set ({user_dir() / 'RUN'} is missing). Nothing was fetched."
        say(msg)
        if a.json:
            emit_json(result)
        return EXIT_FAIL
    try:
        say("Step 1 of 3 · Finding jobs")
        summary = discover.run_discovery(None, a.since)
        ran = discover.any_ran(summary)
        result["discover"] = jf_net.redact({k: v for k, v in summary.items()})
        if summary.get("stopped") or discover.kill_switch_set():
            say(summary.get("stop_reason") or "Stopped: the kill switch is set.")
            if a.json:
                emit_json(result)
            return EXIT_FAIL
        say(f"  {summary['found']} found, {summary['new']} new" + ("" if ran else "; no source could run"))
        for name, s in summary["sources"].items():
            if s["status"] == "error":
                say(f"  {s['label']} failed: {'; '.join(s['errors'])[:160]}")
        say("Step 2 of 3 · Screening")
        if summary.get("run_id"):
            sc = screen.screen_jobs(summary["run_id"])
            result["screen"] = {k: v for k, v in sc.items() if k != "jobs"}
            say(f"  {sc['kept']} kept, {sc['excluded']} excluded")
        else:
            say("  nothing to screen")
        if discover.kill_switch_set():
            say("Stopped: the kill switch is set. No digest was written.")
            if a.json:
                emit_json(result)
            return EXIT_FAIL
        say("Step 3 of 3 · Writing the digest")
        res = digest.write(date.today())
        result["digest"] = res["path"]
        result["matches"] = len(res["matches"])
        say(f"  {res['path']} ({len(res['matches'])} new matches)")
    except (ConfigError, ValueError) as exc:
        say(f"Stopped: {exc}")
        if a.json:
            emit_json(result)
        return EXIT_USAGE
    except db.DBError as exc:
        say(f"Stopped: the database could not be used ({exc}).")
        if a.json:
            emit_json(result)
        return EXIT_FAIL
    result["ok"] = ran
    if a.json:
        emit_json(result)
    return EXIT_OK if ran else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
