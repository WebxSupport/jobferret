"""Check the environment JobFerret needs and (with --create) set up the user directory.

Purpose
    One-screen status for the setup mode: Python version, required and
    optional packages, PDF converters (Microsoft Word via docx2pdf, or
    LibreOffice), and the ~/.jobferret user directory. With --create it makes
    the skeleton (cv/, cv/source/, applications/, exports/), a default
    config.toml, the RUN presence file (deleting it is the kill switch) and the
    SQLite database. Existing files are never overwritten.

Usage
    setup_check.py [--create] [--set KEY=VALUE ...] [--json]

    --set writes one config.toml value (repeatable), e.g. --set browser.preferred=pane.

    The user directory is $JOBFERRET_HOME if set, else ~/.jobferret. It must
    not be inside the skill folder (the skill never holds user data).

Exit codes
    0  ready (all required packages present; user directory exists or was created)
    1  not ready: Python older than 3.11, user directory missing (run with
       --create), inside the skill folder, or could not be created
    3  a required package is missing (the pip install line is printed)
    4  usage error
"""
from __future__ import annotations

import importlib.util
import platform
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

from jf_common import (
    DEFAULT_CONFIG, DEFAULT_CONFIG_TOML, EXIT_DEPS, EXIT_FAIL, EXIT_OK, SKILL_DIR, emit_json, find_soffice,
    make_parser, pip_line, setup_io, update_config, user_dir,
)


def _missing_keys(defaults: dict, current: dict) -> dict:
    """The part of `defaults` that `current` lacks, nested; {} when nothing is missing."""
    out: dict = {}
    for key, value in defaults.items():
        if key not in current:
            out[key] = value
        elif isinstance(value, dict) and isinstance(current.get(key), dict):
            sub = _missing_keys(value, current[key])
            if sub:
                out[key] = sub
    return out


def _coerce(value: str):
    v = value.strip()
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if "," in v:
        return [x.strip() for x in v.split(",") if x.strip()]
    return v


def _parse_sets(pairs: list[str]) -> dict:
    """['browser.preferred=pane', 'limits.daily_applications=10'] -> nested dict for update_config."""
    out: dict = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"--set expects KEY=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        parts = [p for p in key.strip().split(".") if p]
        if not parts or not all(re.fullmatch(r"[A-Za-z0-9_-]+", p) for p in parts):
            raise ValueError(f"--set key {key!r} must be dotted names like browser.preferred")
        cur = out
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = _coerce(value)
    return out


def _flatten_keys(d: dict, prefix: str = "") -> list[str]:
    keys: list[str] = []
    for k, v in d.items():
        name = f"{prefix}{k}"
        if isinstance(v, dict) and v:
            keys.extend(_flatten_keys(v, name + "."))
        else:
            keys.append(name)
    return keys

REQUIRED = [("pdfplumber", "pdfplumber"), ("pypdf", "pypdf"), ("docx", "python-docx")]
OPTIONAL = [("docx2pdf", "docx2pdf"), ("pytest", "pytest")]
SKELETON = ["cv", "cv/source", "applications", "exports", "digests", "inbox", "cache", "memory", "outreach"]


def module_status(mod: str, dist: str) -> dict:
    present = importlib.util.find_spec(mod) is not None
    version = None
    if present:
        try:
            version = metadata.version(dist)
        except metadata.PackageNotFoundError:
            version = "unknown"
    return {"module": mod, "package": dist, "installed": present, "version": version}


def word_installed() -> bool:
    system = platform.system()
    if system == "Windows":
        try:
            import winreg  # read-only lookup
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"):
                return True
        except OSError:
            return False
    if system == "Darwin":
        return Path("/Applications/Microsoft Word.app").exists()
    return False


def check(create: bool) -> dict:
    py_ok = sys.version_info >= (3, 11)
    req = [module_status(m, d) for m, d in REQUIRED]
    opt = [module_status(m, d) for m, d in OPTIONAL]
    missing = [r["package"] for r in req if not r["installed"]]
    word = word_installed()
    pywin32 = importlib.util.find_spec("win32com") is not None if platform.system() == "Windows" else None
    docx2pdf_ok = opt[0]["installed"] and word and (pywin32 is not False)
    soffice = find_soffice()

    ud = user_dir()
    inside_skill = False
    try:
        ud.resolve().relative_to(SKILL_DIR.resolve())
        inside_skill = True
    except ValueError:
        pass
    created: list[str] = []
    problems: list[str] = []
    if inside_skill:
        problems.append(f"user directory {ud} is inside the skill folder; set JOBFERRET_HOME elsewhere")
    elif create:
        try:
            for sub in [""] + SKELETON:
                d = ud / sub
                if not d.exists():
                    d.mkdir(parents=True, exist_ok=True)
                    created.append(str(d))
            cfg = ud / "config.toml"
            if not cfg.exists():
                cfg.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
                created.append(str(cfg))
            else:
                # A config from an earlier build: add any missing sections and keys,
                # keep every value the user has set.
                # read the file itself: load_config() fills defaults in, which would hide what is missing
                try:
                    on_disk = tomllib.loads(cfg.read_text(encoding="utf-8"))
                except tomllib.TOMLDecodeError as exc:
                    on_disk = None
                    problems.append(f"{cfg} is not valid TOML ({exc}); fix it or delete it to get defaults")
                missing_cfg = _missing_keys(DEFAULT_CONFIG, on_disk) if on_disk is not None else {}
                if missing_cfg:
                    update_config(missing_cfg, cfg)
                    created.append(f"{cfg} (added: {', '.join(_flatten_keys(missing_cfg))})")
            run = ud / "RUN"
            if not run.exists():
                run.write_text("JobFerret runs while this file exists. Delete it to stop all JobFerret activity.\n",
                               encoding="utf-8")
                created.append(str(run))
            dbp = ud / "jobferret.db"
            if not dbp.exists():
                import db  # local module
                db.connect(dbp).close()
                created.append(str(dbp))
        except OSError as exc:
            problems.append(f"could not create {ud}: {exc}")
    exists = ud.is_dir()
    layout = {sub: (ud / sub).is_dir() for sub in SKELETON}
    layout.update({name: (ud / name).exists() for name in ("config.toml", "RUN", "jobferret.db", "profile.json",
                                                           "voice-profile.json", "cv/master.md", "cv/ledger.json")})
    if not exists and not create:
        problems.append(f"{ud} does not exist yet; run setup_check.py --create")
    if not py_ok:
        problems.append(f"Python {platform.python_version()} is too old; JobFerret needs 3.11 or newer")
    return {
        "ok": py_ok and not missing and exists and not inside_skill and not problems,
        "python": {"version": platform.python_version(), "executable": sys.executable, "ok": py_ok},
        "platform": platform.system(),
        "required": req, "optional": opt,
        "pip_install": pip_line(*missing) if missing else None,
        "pdf": {"word": word, "pywin32": pywin32, "docx2pdf_usable": bool(docx2pdf_ok),
                "libreoffice": soffice, "can_make_pdf": bool(docx2pdf_ok or soffice)},
        "user_dir": {"path": str(ud), "exists": exists, "inside_skill": inside_skill, "created": created,
                     "layout": layout},
        "skill_dir": str(SKILL_DIR),
        "problems": problems,
        "missing": missing,
    }


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="setup_check.py")
    p.add_argument("--create", action="store_true", help="create the user directory skeleton")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="write a config.toml value, e.g. --set browser.preferred=pane (repeatable; "
                        "true/false, whole numbers and comma lists are converted)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args(argv)
    if a.set:
        try:
            updates = _parse_sets(a.set)
        except ValueError as exc:
            p.error(str(exc))
        update_config(updates)
        if not a.json:
            for key in _flatten_keys(updates):
                print(f"  set {key}")
    res = check(a.create)
    res["set"] = a.set
    if a.json:
        emit_json(res)
    else:
        mark = lambda ok: "ok " if ok else "-- "  # noqa: E731
        print(f"JobFerret setup check ({res['platform']})")
        print(f"  [{mark(res['python']['ok'])}] Python {res['python']['version']}")
        for r in res["required"]:
            print(f"  [{mark(r['installed'])}] {r['package']} {r['version'] or 'MISSING (required)'}")
        for r in res["optional"]:
            print(f"  [{mark(r['installed'])}] {r['package']} {r['version'] or 'not installed (optional)'}")
        pdf = res["pdf"]
        print(f"  [{mark(pdf['word'])}] Microsoft Word {'found' if pdf['word'] else 'not found'}")
        if pdf["pywin32"] is not None:
            print(f"  [{mark(pdf['pywin32'])}] pywin32 (needed by docx2pdf on Windows)")
        print(f"  [{mark(bool(pdf['libreoffice']))}] LibreOffice {pdf['libreoffice'] or 'not found'}")
        print(f"  PDF output: {'available' if pdf['can_make_pdf'] else 'not available (DOCX only)'}")
        ud = res["user_dir"]
        print(f"  [{mark(ud['exists'])}] user directory {ud['path']}")
        for c in ud["created"]:
            print(f"        created {c}")
        if res["pip_install"]:
            print(f"  install missing packages with:\n    {res['pip_install']}")
        for prob in res["problems"]:
            print(f"  problem: {prob}")
        print("READY" if res["ok"] else "NOT READY")
    if res["missing"]:
        return EXIT_DEPS
    return EXIT_OK if res["ok"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
