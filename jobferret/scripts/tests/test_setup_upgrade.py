"""setup_check.py --create adds missing config sections to an older config.toml without touching set values."""
import subprocess
import sys
import tomllib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]

OLD_CONFIG = """[locale]
default = "us"
[browser]
preferred = "pane"
[limits]
daily_applications = 7
hard_cap = 25
per_employer_days = 30
[paths]
user_dir = "~/.jobferret"
"""


def run(home: Path, *args: str) -> subprocess.CompletedProcess:
    import os
    env = {**os.environ, "JOBFERRET_HOME": str(home)}   # the full environment, so user site-packages resolve
    return subprocess.run([sys.executable, str(SCRIPTS / "setup_check.py"), *args],
                          capture_output=True, text=True, env=env, encoding="utf-8")


def test_create_adds_missing_sections_and_keeps_values(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text(OLD_CONFIG, encoding="utf-8")
    proc = run(home, "--create")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    cfg = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["locale"]["default"] == "us" and cfg["limits"]["daily_applications"] == 7   # user values kept
    assert cfg["sources"]["enabled"][0] == "adzuna" and cfg["sources"]["adzuna"]["app_key"] == ""
    assert cfg["hunt"]["top_n"] == 15 and cfg["outreach"]["max_touches"] == 2 and cfg["ux"]["chattiness"] == "normal"
    assert "sources" in proc.stdout and "added" in proc.stdout
    for sub in ("digests", "inbox", "cache", "memory", "outreach"):
        assert (home / sub).is_dir()


def test_create_is_idempotent(tmp_path):
    home = tmp_path / "home"
    first = run(home, "--create")
    assert first.returncode == 0, first.stdout + first.stderr
    before = (home / "config.toml").read_text(encoding="utf-8")
    second = run(home, "--create")
    assert second.returncode == 0
    assert (home / "config.toml").read_text(encoding="utf-8") == before
    assert "added" not in second.stdout
