"""Role-block layouts, divider lines, skills tables and page previews.

The fixtures in fixtures/layouts/ are synthetic; they copy the line layouts of real CVs,
not their content.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import cv_extract
import jf_common as jc
from conftest import FIXTURES, pdf_converter_available

LAYOUTS = FIXTURES / "layouts"


def _facts(name: str) -> dict:
    return cv_extract.extract(LAYOUTS / name)


def _roles(res: dict) -> list[dict]:
    return [f for f in res["facts"] if f["kind"] == "role"]


# ------------------------------------------------------------ role blocks (Part 1)

def test_employer_location_date_title_docx():
    """The owner's layout: Employer | Location, then the date line, then the title."""
    res = _facts("three-line-roles.docx")
    roles = _roles(res)
    assert len(roles) == 2
    r = roles[0]["fields"]
    assert (r["title"], r["employer"], r["location"]) == ("Director", "Example Web Ltd", "Accrington, England")
    assert (r["start"], r["end"], r["current"]) == ("2018-09", None, True)
    assert "confidence" not in r
    r2 = roles[1]["fields"]
    assert (r2["title"], r2["employer"], r2["start"], r2["end"]) == ("Lifeguard", "Pennine Leisure Trust", "2014-06", "2018-08")
    # the title keeps its own fact so a header can cite it
    titles = [f for f in res["facts"] if f["kind"] == "title"]
    assert [t["text"] for t in titles] == ["Director", "Lifeguard"]
    assert [t["parent"] for t in titles] == [roles[0]["id"], roles[1]["id"]]
    assert not [f for f in res["facts"] if f["text"] == "Director" and f["kind"] == "other"]
    # bullets hang off the role, not the title
    bullets = [f for f in res["facts"] if f["kind"] == "bullet"]
    assert [b["parent"] for b in bullets] == [roles[0]["id"]] * 2 + [roles[1]["id"]]


ROLE_CASES = [
    # (employer-line text prefix identifying the role, title, employer, location, start, end)
    ("Senior Analyst", "Senior Analyst", "Acme Ltd", "London", "2022-03", None),            # (b)
    ("Data Analyst", "Data Analyst", "Beta plc", "", "2019-06", "2022-02"),                  # (c)
    ("Gamma Ltd", "Support Technician", "Gamma Ltd", "", "2017-01", "2019-05"),             # (d) date after a tab
    ("Delta Foods", "Warehouse Operative", "Delta Foods", "", "2014-06", "2016-12"),        # (e)
    ("Orchard Dental", "Receptionist", "Orchard Dental Practice", "Leeds", "2012-03", "2014-05"),  # (d) any order
]


@pytest.mark.parametrize("prefix,title,employer,location,start,end", ROLE_CASES)
def test_role_layouts(prefix, title, employer, location, start, end):
    roles = _roles(_facts("role-layouts.txt"))
    match = [r for r in roles if r["text"].startswith(prefix)]
    assert len(match) == 1, [r["text"] for r in roles]
    f = match[0]["fields"]
    assert (f["title"], f["employer"], f["location"], f["start"], f["end"]) == (title, employer, location, start, end)
    assert f.get("confidence") != "low"


def test_ambiguous_block_is_kept_and_marked_low():
    roles = _roles(_facts("role-layouts.txt"))
    odd = [r for r in roles if "Odd Job Person" in r["text"]]
    assert len(odd) == 1
    f = odd[0]["fields"]
    assert f["confidence"] == "low"
    assert f["title"] and f["employer"] and f["start"] == "2010"   # best guess filled, nothing lost
    assert "Epsilon" in odd[0]["text"] and "Odd Job Person" in odd[0]["text"]


def test_parse_role_block_orders():
    p = cv_extract.parse_role_block
    a = p(["Example Ltd | Leeds", "Mar 2020 – Present", "Director"])
    b = p(["Director", "Example Ltd | Leeds", "Mar 2020 – Present"])
    c = p(["Example Ltd", "Director (March 2020 – Present)"])
    for res in (a, b, c):
        assert res["fields"]["title"] == "Director" and res["fields"]["employer"] == "Example Ltd"
        assert res["fields"]["start"] == "2020-03" and res["fields"]["end"] is None
        assert res["complete"] and "confidence" not in res["fields"]
    assert a["fields"]["location"] == "Leeds" and b["fields"]["location"] == "Leeds"
    assert a["title_line"] == 2 and b["title_line"] == 0 and c["title_line"] is None


def test_classify_uses_the_head_word():
    assert cv_extract.classify_part("Bank Manager") == "title"
    assert cv_extract.classify_part("Barclays Bank") == "employer"
    assert cv_extract.classify_part("Sales Partners") == "employer"
    assert cv_extract.classify_part("Head of Finance") == "title"
    assert cv_extract.classify_part("University of Leeds") == "employer"
    assert cv_extract.classify_part("Zorblax") is None


@pytest.mark.parametrize("name", ["three-line-roles.docx", "role-layouts.txt", "dividers.txt"])
def test_no_text_is_lost(name):
    """Every non-divider line is inside a fact (line..end_line), a section heading or a title fact."""
    res = _facts(name)
    covered: set[int] = set()
    for f in res["facts"]:
        covered.add(f["line"])
        covered.update(range(f["line"], (f["fields"].get("end_line") or f["line"]) + 1))
    for s in res["sections"]:
        covered.add(s["start_line"])
    missing = [ln.no for ln in res["lines"]
               if ln.text.strip() and not cv_extract.is_divider(ln.text) and ln.no not in covered]
    assert missing == []


# ------------------------------------------------------------------ dividers

def test_divider_lines_are_not_facts_but_stay_in_the_text(run, tmp_path):
    out, txt = tmp_path / "ledger.json", tmp_path / "cv.txt"
    r = run("cv_extract.py", LAYOUTS / "dividers.txt", "--out", out, "--text", txt, "--fragment")
    assert r.returncode == 0, r.stdout + r.stderr
    src = (LAYOUTS / "dividers.txt").read_text(encoding="utf-8").splitlines()
    kept = txt.read_text(encoding="utf-8").splitlines()
    assert len(kept) == len(src)   # line numbers stay stable
    assert [i for i, t in enumerate(kept) if cv_extract.is_divider(t)] ==         [i for i, t in enumerate(src) if cv_extract.is_divider(t)] and len(src) > 10
    facts = jc.load_ledger(out)["facts"]
    assert facts
    assert not [f for f in facts if re.fullmatch(r"[\s_\-=—–•*~]+", f["text"])]
    assert not [f for f in facts if f["kind"] in ("headline", "summary") and len(f["text"]) <= 2]
    role = next(f for f in facts if f["kind"] == "role")
    assert role["fields"]["employer"] == "Acme Ltd" and role["fields"]["location"] == "Leeds"
    for f in facts:
        assert f["text"].split()[0] in src[f["line"] - 1]


@pytest.mark.parametrize("text,expected", [
    ("_____", True), ("__________________________", True), ("-----", True), ("=====", True),
    ("—————", True), ("• • • • •", True), ("*****", True), ("~~~~~", True),
    ("____", False), ("--", False), ("-----x", False), ("Experience", False), ("", False),
])
def test_is_divider(text, expected):
    assert cv_extract.is_divider(text) is expected


def test_dividers_do_not_count_as_lines():
    res = _facts("dividers.txt")
    src = (LAYOUTS / "dividers.txt").read_text(encoding="utf-8").splitlines()
    real = [ln for ln in src if ln.strip() and not cv_extract.is_divider(ln)]
    assert res["report"]["line_count"] == len(real)


# -------------------------------------------------------------- skills tables

def test_skills_table_label_and_list_merge():
    res = _facts("three-line-roles.docx")
    skills = [f for f in res["facts"] if f["kind"] == "skill"]
    assert [s["text"] for s in skills] == [
        "Web Development - React, Vite, Tailwind CSS, WordPress & Shopify",
        "Tools: Git, Docker, Figma",
        "Languages - TypeScript, PHP, Python",
        "Hosting - Cloudflare, AWS, cPanel",
    ]
    first = skills[0]["fields"]
    assert first["label"] == "Web Development"
    assert first["items"] == ["React", "Vite", "Tailwind CSS", "WordPress & Shopify"]
    assert first["end_line"] == skills[0]["line"] + 1
    assert skills[1]["fields"]["items"] == ["Git", "Docker", "Figma"]
    assert not [f for f in res["facts"] if f["text"].endswith(("-", ":"))]


def test_skill_label_line_without_a_list_is_left_alone():
    lines = [cv_extract.Line(t) for t in ["Skills", "Python, SQL", "Web Development -"]]
    for i, ln in enumerate(lines, start=1):
        ln.no = i
    facts, _, _ = cv_extract.build_ledger(lines, "text")
    assert [f["text"] for f in facts if f["kind"] == "skill"] == ["Python, SQL", "Web Development -"]


# ------------------------------------------------------------ the title kind

def test_title_kind_is_accepted_by_ledger_tools(run, tmp_path):
    out = tmp_path / "ledger.json"
    r = run("cv_extract.py", LAYOUTS / "three-line-roles.docx", "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    led = jc.load_ledger(out)
    title = next(f for f in led["facts"] if f["kind"] == "title")
    role = next(f for f in led["facts"] if f["id"] == title["parent"])
    draft = tmp_path / "draft.md"
    draft.write_text(f"# Sam Example\nAccrington\n\n## Experience\n"
                     f"### Director — Example Web Ltd | Accrington | Sep 2018 – Present [{title['id']},{role['id']}]\n",
                     encoding="utf-8")
    r = run("ledger_check.py", draft, "--ledger", out)
    assert r.returncode == 0, r.stdout + r.stderr
    r = run("ledger_add.py", "--ledger", out, "--kind", "title", "--parent", role["id"], "--text", "Managing Director")
    assert r.returncode == 0, r.stdout + r.stderr


# ----------------------------------------------------------------- previews (Part 2)

SAMPLE_PDF = FIXTURES / "sample-cv-uk.pdf"


def test_preview_only_pdf(run, tmp_path):
    out_dir = tmp_path / "prev"
    r = run("cv_render.py", "--preview-only", SAMPLE_PDF, "--out-dir", out_dir, "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads(r.stdout)
    assert res["ok"] and len(res["pages"]) == 2
    for n, pg in enumerate(res["pages"], start=1):
        png = Path(pg["png"])
        assert png.name == f"page-{n}.png" and png.parent == out_dir
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert (pg["width_cm"], pg["height_cm"]) == (21.0, 29.7)


def test_preview_only_text_output_lists_paths_and_size(run, tmp_path):
    r = run("cv_render.py", "--preview-only", SAMPLE_PDF, "--out-dir", tmp_path / "p")
    assert r.returncode == 0
    assert "page-1.png" in r.stdout and "21.0 x 29.7 cm" in r.stdout


def test_preview_only_usage_errors(run, tmp_path):
    assert run("cv_render.py", "--preview-only", SAMPLE_PDF).returncode == 4
    assert run("cv_render.py", "--preview-only", tmp_path / "nope.pdf", "--out-dir", tmp_path).returncode == 4
    assert run("cv_render.py").returncode == 4


def test_preview_only_docx_needs_a_converter(run, tmp_path):
    docx = FIXTURES / "sample-cv-uk.docx"
    if not docx.exists():
        pytest.skip("fixture docx not generated yet")
    r = run("cv_render.py", "--preview-only", docx, "--out-dir", tmp_path / "d", "--json")
    res = json.loads(r.stdout)
    if pdf_converter_available():
        assert r.returncode == 0 and res["pages"]
    else:
        assert r.returncode == 1 and any("no Microsoft Word" in n for n in res["notes"])


def test_render_with_preview(run, rendered, tmp_path):
    if not pdf_converter_available():
        pytest.skip("no PDF converter on this machine")
    out = tmp_path / "cv.docx"
    r = run("cv_render.py", rendered["clean"], "--locale", "uk", "--out", out, "--preview", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    rep = json.loads(r.stdout)
    assert rep["pdf"] and len(rep["preview"]) >= 1
    assert (tmp_path / "page-1.png").is_file()


# ------------------------------------------------------------ hardening (Part 3)

@pytest.mark.parametrize("name,content,code", [
    ("empty.pdf", b"", 4),
    ("fake.pdf", b"this is not a pdf\n", 4),
    ("truncated.pdf", SAMPLE_PDF.read_bytes()[:1500], 4),
    ("empty.docx", b"", 4),
    ("fake.docx", b"not a zip", 4),
    ("empty.md", b"", 1),
])
def test_bad_files_exit_cleanly(run, tmp_path, name, content, code):
    src = tmp_path / name
    src.write_bytes(content)
    r = run("cv_extract.py", src, "--json")
    assert r.returncode == code, r.stdout + r.stderr
    assert "Traceback" not in r.stderr


def test_windows_1252_text_is_read_with_a_warning(run, tmp_path):
    src = tmp_path / "cv.txt"
    src.write_bytes("Zoë Müller\nzoe@example.com\n\nExperience\nAnalyst, Café Ltd\nMar 2020 - Present\n"
                    "- Built the café's reporting\n".encode("cp1252"))
    r = run("cv_extract.py", src, "--json", "--fragment")
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads(r.stdout)
    assert any("Windows-1252" in w for w in res["report"]["warnings"])
    assert any("Zoë" in f["text"] for f in res["ledger"]["facts"])


# ------------------------------------------- layouts seen in public CV datasets

def test_dated_list_lines_and_labels():
    """Synthetic text in the layouts that public PDF CVs use: bulleted entries that start with
    their dates, "Position:" / "Durations:" labels, "Title at Employer", dd/mm/yyyy dates,
    a first bullet on the date line, and a name given as "Full name :"."""
    res = _facts("dated-list-roles.txt")
    roles = _roles(res)
    assert len(roles) == 4
    f0, f1, f2, f3 = (r["fields"] for r in roles)
    assert (f0["title"], f0["employer"], f0["start"], f0["current"]) == (
        "Oracle ERP Consultant", "Harbour Group Ltd", "2022-02", True)
    assert (f1["title"], f1["employer"], f1["start"], f1["end"]) == (
        "Accountant", "Northern Pharma Company Limited", "2018-06", "2021-06")   # 01/06/2018 is day/month/year
    assert (f2["title"], f2["start"], f2["end"]) == ("Software Engineer", "2019-02", None)
    assert f3["employer"] == "Mercia Digital Ltd" and f3["location"] == "Leeds" and f3["confidence"] == "low"
    bullets = [f for f in res["facts"] if f["kind"] == "bullet"]
    mercia = next(b for b in bullets if b["text"].startswith("Managed the office network"))
    assert mercia["parent"] == roles[3]["id"] and mercia["line"] == roles[3]["fields"]["end_line"]
    name = next(f for f in res["facts"] if f["fields"].get("name"))
    assert name["fields"]["name"] == "Priya Example"
    assert res["report"]["reading_order"]["name_first"]
    assert any(s["kind"] == "skill" for s in res["sections"])


def test_headings_seen_in_real_cvs():
    for text, kind in [("WORKING EXPERIENCE:", "experience"), ("Work Experiences", "experience"),
                       ("EDUCATIONAL BACKGROUND", "education"), ("Soft Skills", "skill"),
                       ("Programming Languages", "skill"), ("Personal Information", "other"),
                       ("Hobby", "interest"), ("Career Objectives", "summary")]:
        assert cv_extract.section_kind(text) == kind, text


@pytest.mark.parametrize("text,start,end", [
    ("11/2019 - Currently", "2019-11", None), ("6-2018 - now", "2018-06", None),
    ("01/06/2021 to 19/10/2023", "2021-06", "2023-10"), ("2019/02 - Now", "2019-02", None),
    ("10.2014 - 11.2023", "2014-10", "2023-11"),
])
def test_date_ranges_seen_in_real_cvs(text, start, end):
    m = jc.DATE_RANGE_RE.search(text)
    assert m, text
    assert (jc.normalize_date(m.group("start")), jc.normalize_date(m.group("end"))) == (start, end)


def test_nul_bytes_from_broken_fonts():
    assert cv_extract._display("10\x002014 - 11\x002023") == "10/2014 - 11/2023"
    assert cv_extract._display("Wi\x00 router") == "Wi router"


def test_image_only_pdf_fails_cleanly(run, tmp_path):
    """A PDF that holds only a picture has no text layer: exit 1, a plain reason, no ledger."""
    from PIL import Image
    src = tmp_path / "scan.pdf"
    Image.new("RGB", (600, 800), "white").save(src)
    out = tmp_path / "ledger.json"
    r = run("cv_extract.py", src, "--out", out, "--json")
    assert r.returncode == 1 and not out.exists()
    res = json.loads(r.stdout)
    assert res["ok"] is False
    assert any("scanned image" in w for w in res["report"]["warnings"])


def test_end_dated_list_line_and_page_number(tmp_path):
    src = tmp_path / "cv.txt"
    src.write_text(
        "Dana Example\ndana@example.com\n\nWork Experience:\n"
        "\u2022 IT Specialist (From September 2022 to December 2022)\nCompany: Harbour Ltd\n"
        "\u2022 Maintained the ticketing system.\n1\n"
        "\u2022 Project leader (From 2021 to August 2022)\nCompany: Cloud Works Limited\n"
        "\u2022 Built a dashboard (2021 - 2022) used by finance.\n", encoding="utf-8")
    res = cv_extract.extract(src)
    roles = _roles(res)
    assert [(r["fields"]["title"], r["fields"]["employer"]) for r in roles] == [
        ("IT Specialist", "Harbour Ltd"), ("Project leader", "Cloud Works Limited")]
    assert roles[1]["fields"]["start"] == "2021" and roles[1]["fields"]["end"] == "2022-08"
    assert "confidence" not in roles[1]["fields"]
    # a bullet that merely mentions a date range stays a bullet
    assert any(f["kind"] == "bullet" and f["text"].startswith("Built a dashboard") for f in res["facts"])


def test_picture_files_get_a_plain_refusal(run, tmp_path):
    from PIL import Image
    src = tmp_path / "cv.png"
    Image.new("RGB", (50, 50), "white").save(src)
    r = run("cv_extract.py", src)
    assert r.returncode == 4 and "OCR" in r.stderr and "Traceback" not in r.stderr
