"""Shared pytest fixtures for the JobFerret scripts."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent
FIXTURES = TESTS / "fixtures"
REAL_LISTS = SCRIPTS.parent / "references" / "voice" / "lists"
SAMPLE_MD = FIXTURES / "sample-cv-uk.md"
SAMPLE_LEDGER = FIXTURES / "sample-ledger.json"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def jf_home(tmp_path, monkeypatch):
    """An isolated user directory so tests never touch ~/.jobferret."""
    home = tmp_path / "jfhome"
    monkeypatch.setenv("JOBFERRET_HOME", str(home))
    return home


def run_script(script: str, *args: str, home: Path | None = None, cwd: Path | None = None,
               timeout: int = 300) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if home is not None:
        env["JOBFERRET_HOME"] = str(home)
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", env=env,
                          cwd=str(cwd or SCRIPTS), timeout=timeout)


@pytest.fixture
def run(tmp_path):
    home = tmp_path / "jfhome-cli"

    def _run(script: str, *args: str, **kw) -> subprocess.CompletedProcess:
        kw.setdefault("home", home)
        return run_script(script, *args, **kw)
    _run.home = home
    return _run


def pdf_converter_available() -> bool:
    from jf_common import find_soffice
    if find_soffice():
        return True
    if importlib.util.find_spec("docx2pdf") is None:
        return False
    if sys.platform == "win32":
        import setup_check
        return setup_check.word_installed() and importlib.util.find_spec("win32com") is not None
    return sys.platform == "darwin" and Path("/Applications/Microsoft Word.app").exists()


@pytest.fixture(scope="session")
def rendered(tmp_path_factory):
    """Strip the fixture CV, render it to DOCX (and PDF when a converter exists).

    Copies the outputs to tests/fixtures/ for manual inspection.
    """
    out = tmp_path_factory.mktemp("render")
    clean = out / "sample-cv-uk.clean.md"
    r = run_script("ledger_check.py", SAMPLE_MD, "--ledger", SAMPLE_LEDGER, "--strip", "--out", clean,
                   home=out / "home")
    assert r.returncode == 0, r.stdout + r.stderr
    docx = out / "sample-cv-uk.docx"
    want_pdf = pdf_converter_available()
    args = [clean, "--locale", "uk", "--out", docx, "--json"] + (["--pdf"] if want_pdf else [])
    r = run_script("cv_render.py", *args, home=out / "home")
    import json
    report = json.loads(r.stdout)
    report["returncode"] = r.returncode
    for f in (docx, docx.with_suffix(".pdf")):
        if f.exists():
            try:
                shutil.copy2(f, FIXTURES / f.name)
            except OSError:
                pass  # e.g. the copy is open in Word; not needed for the tests
    return {"dir": out, "clean": clean, "docx": docx, "pdf": docx.with_suffix(".pdf") if report.get("pdf") else None,
            "report": report}
