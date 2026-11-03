"""Install a local JobFerret checkout, or build an uploadable skill ZIP.

Uses only the Python standard library. Never downloads or runs skill code.
"""

import argparse
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile


SOURCE = Path(__file__).resolve().parent / "jobferret"
EXCLUDED = {"__pycache__", ".pytest_cache", ".venv", "tests", "evals"}


def skill_files(source):
    for required in ("SKILL.md", "agents/openai.yaml", "scripts/requirements.txt", "references/platforms.md"):
        if not (source / required).is_file():
            raise ValueError(f"Incomplete skill: missing {required}")
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Skill contains a symlink: {relative}")
        if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
            yield path, relative


def install(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be separate folders")
    files = list(skill_files(source))
    if destination.exists():
        raise FileExistsError(f"Already exists: {destination}. Keep or move the existing copy before installing again.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Stage beside the destination so a copy failure cannot leave a partial skill.
    with tempfile.TemporaryDirectory(prefix=".jobferret-install-", dir=destination.parent) as temp:
        staged = Path(temp) / "jobferret"
        staged.mkdir()
        for path, relative in files:
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        if destination.exists():
            raise FileExistsError(f"Destination appeared during install: {destination}")
        staged.rename(destination)
    return destination


def bundle(source, output):
    files = list(skill_files(source))
    output = output.resolve()
    if output == source.resolve() or source.resolve() in output.parents:
        raise ValueError("Create the ZIP outside the source skill folder")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as stream:
            try:
                with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                    for path, relative in files:
                        archive.write(path, (Path("jobferret") / relative).as_posix())
            except BaseException:
                stream.close()
                output.unlink()
                raise
    except FileExistsError:
        raise FileExistsError(f"ZIP already exists: {output}") from None
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--host", choices=("codex", "claude"))
    action.add_argument("--bundle", type=Path, metavar="ZIP")
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.exit(1, "JobFerret requires Python 3.11 or later.\n")
    try:
        if args.bundle:
            print(f"Skill ZIP created: {bundle(SOURCE, args.bundle)}")
            return 0
        root = args.project.expanduser().resolve() if args.scope == "project" else Path.home()
        folder = ".agents" if args.host == "codex" else ".claude"
        destination = install(SOURCE, root / folder / "skills" / "jobferret")
    except (OSError, ValueError) as error:
        print(f"Installation/package failed: {error}", file=sys.stderr)
        if isinstance(error, PermissionError):
            print("Choose a writable project with --scope project --project PATH, or run this installer from your own terminal. No permission settings were changed.", file=sys.stderr)
        return 1
    print(f"Installed skill files: {destination}")
    print("Python dependencies have not been installed. Run:")
    command = [sys.executable, "-m", "pip", "install", "-r", str(destination / "scripts" / "requirements.txt")]
    if os.name == "nt":
        print(subprocess.list2cmdline(command))
    else:
        import shlex
        print(shlex.join(command))
    invocation = "$jobferret start" if args.host == "codex" else "/jobferret start"
    print(f"Open the project in {args.host}; if needed, restart the session. Then run: {invocation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
