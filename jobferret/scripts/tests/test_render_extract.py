import json
import re
import zipfile

import pytest

import cv_extract
import cv_render
import jf_common as jc
from conftest import SAMPLE_MD


# ----------------------------------------------------------------------- render

def test_render_report_ok(rendered):
    rep = rendered["report"]
    assert rep["returncode"] == 0, json.dumps(rep, indent=1)
    assert rep["ok"] and rep["structure"]["ok"]
    chk = rep["docx_text_check"]
    assert chk["missing"] == [] and chk["out_of_order"] == [] and chk["checked"] >= 35


def test_docx_has_no_tables_textboxes_headers_or_images(rendered):
    import docx
    with zipfile.ZipFile(rendered["docx"]) as z:
        names = z.namelist()
        doc_xml = z.read("word/document.xml").decode("utf-8")
    assert not [n for n in names if re.match(r"word/(header|footer)", n)]
    assert not [n for n in names if n.startswith("word/media/") or "thumbnail" in n]
    assert "<w:tbl>" not in doc_xml and "txbxContent" not in doc_xml and "<w:drawing" not in doc_xml
    assert "headerReference" not in doc_xml and "footerReference" not in doc_xml
    d = docx.Document(str(rendered["docx"]))
    assert d.tables == []
    sec = d.sections[0]
    assert round(sec.page_width.cm, 1) == 21.0 and round(sec.page_height.cm, 1) == 29.7
    assert round(sec.left_margin.cm, 1) == 2.0


def test_docx_uses_real_bullets_and_headings(rendered):
    import docx
    from docx.oxml.ns import qn
    d = docx.Document(str(rendered["docx"]))
    bullets = [p for p in d.paragraphs if p.style.name == "List Bullet"]
    assert len(bullets) == 18
    assert all(not p.text.lstrip().startswith(("•", "-", "*")) for p in d.paragraphs)
    style_ppr = d.styles["List Bullet"].element.find(qn("w:pPr"))
    assert style_ppr.find(qn("w:numPr")) is not None
    headings = [p.text for p in d.paragraphs if p.style.name == "Heading 1"]
    assert headings[:3] == ["Profile", "Core skills", "Experience"]
    h1 = d.styles["Heading 1"]
    assert h1.font.size.pt == 12 and h1.font.bold
    assert h1.element.find(qn("w:pPr")).find(qn("w:pBdr")) is not None
    normal = d.styles["Normal"]
    assert normal.font.size.pt == 10.5 and normal.font.name == "Calibri"
    name = d.paragraphs[0]
    assert name.text == "Hannah Okafor" and name.runs[0].bold and name.runs[0].font.size.pt == 18
    entry = next(p for p in d.paragraphs if p.text.startswith("Senior Finance Analyst"))
    assert "\tMar 2022 – Present" in entry.text
    stops = entry.paragraph_format.tab_stops
    assert len(stops) == 1 and int(stops[0].alignment) == 2  # RIGHT


def test_render_refuses_markers(run, tmp_path):
    r = run("cv_render.py", SAMPLE_MD, "--locale", "uk", "--out", tmp_path / "x.docx")
    assert r.returncode == 4 and "ledger_check.py" in r.stderr
    assert not (tmp_path / "x.docx").exists()


def test_render_us_letter(run, rendered, tmp_path):
    out = tmp_path / "us.docx"
    r = run("cv_render.py", rendered["clean"], "--locale", "us", "--out", out, "--json")
    assert r.returncode == 0
    import docx
    sec = docx.Document(str(out)).sections[0]
    assert round(sec.page_width.inches, 2) == 8.5 and round(sec.page_height.inches, 2) == 11.0
    assert round(sec.left_margin.inches, 2) == 0.75


def test_verify_text_reports_missing_and_out_of_order():
    units = [{"line": 1, "text": "Jane Smith"}, {"line": 2, "text": "Built a dashboard."},
             {"line": 3, "text": "Ran the audit."}, {"line": 4, "text": "Wrote the tests."}]
    res = cv_render.verify_text(units, "Jane Smith\nRan the audit.\nBuilt a dashboard.\n")
    assert [m["line"] for m in res["missing"]] == [4]
    assert [m["line"] for m in res["out_of_order"]] == [3]
    assert not res["ok"]


def test_pdf_render(rendered):
    if rendered["pdf"] is None:
        pytest.skip("no PDF converter (Word+docx2pdf or LibreOffice) on this machine")
    chk = rendered["report"]["pdf_text_check"]
    assert chk["missing"] == [] and chk["out_of_order"] == []
    assert chk["pages"] in (1, 2)


# ---------------------------------------------------------------------- extract

def _extract(run, src, tmp_path, *extra):
    out, txt = tmp_path / "ledger.json", tmp_path / "cv.txt"
    r = run("cv_extract.py", src, "--out", out, "--text", txt, "--json", *extra)
    return r, (json.loads(r.stdout) if r.stdout.strip().startswith("{") else None), out, txt


def _assert_lines_match(ledger, txt_path):
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    for f in ledger["facts"]:
        src = lines[f["line"] - 1]
        words = re.findall(r"\w+", f["text"])[:3]
        assert words, f
        for w in words:
            assert w in src, (f["id"], f["line"], src, f["text"])


def test_round_trip_docx(run, rendered, tmp_path):
    r, res, out, txt = _extract(run, rendered["docx"], tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    led = jc.load_ledger(out)
    facts = led["facts"]
    idx = jc.ledger_index(led)
    roles = [f for f in facts if f["kind"] == "role"]
    assert len(roles) >= 3
    northgate = roles[0]
    assert northgate["fields"]["employer"] == "Northgate Foods Ltd"
    assert northgate["fields"]["location"] == "Leeds" and northgate["fields"]["start"] == "2022-03"
    assert northgate["fields"]["end"] is None
    bullets = [f for f in facts if f["kind"] == "bullet"]
    assert len(bullets) >= 13
    exp_bullets = [b for b in bullets if b["parent"] and idx[b["parent"]]["kind"] == "role"]
    assert len(exp_bullets) == 13
    assert sum(1 for b in exp_bullets if b["parent"] == northgate["id"]) == 6
    contact = [f for f in facts if f["kind"] == "contact"]
    assert contact[0]["fields"]["name"] == "Hannah Okafor"
    assert any("hannah.okafor@example.com" in f["text"] for f in contact)
    edu = [f for f in facts if f["kind"] == "education"]
    assert edu and edu[0]["fields"]["institution"] == "University of Leeds"
    assert [s["name"] for s in led["sections"]][:3] == ["Profile", "Core skills", "Experience"]
    assert all(f["provenance"] == "cv" and f["confirmed"] for f in facts)
    assert led["source"]["extractor"] == "python-docx" and len(led["source"]["sha256"]) == 64
    _assert_lines_match(led, txt)
    ro = res["report"]["reading_order"]
    assert ro["name_first"] and ro["contact_in_body"] and not ro["columns_suspected"]
    assert "• Rebuilt the month-end close" in txt.read_text(encoding="utf-8")


def test_extract_markdown_line_numbers(run, tmp_path):
    r, res, out, txt = _extract(run, SAMPLE_MD, tmp_path)
    assert r.returncode == 0
    led = jc.load_ledger(out)
    assert txt.read_text(encoding="utf-8").splitlines() == SAMPLE_MD.read_text(encoding="utf-8").splitlines()
    _assert_lines_match(led, txt)
    assert all("[F" not in f["text"] for f in led["facts"])
    kinds = res["report"]["facts_by_kind"]
    assert kinds["role"] == 4 and kinds["skill"] == 3 and kinds["certification"] == 2


def test_extract_pdf(run, rendered, tmp_path):
    if rendered["pdf"] is None:
        pytest.skip("no PDF converter on this machine")
    r, res, out, txt = _extract(run, rendered["pdf"], tmp_path)
    assert r.returncode == 0, r.stdout
    led = jc.load_ledger(out)
    idx = jc.ledger_index(led)
    assert res["report"]["page_count"] == rendered["report"]["pdf_text_check"]["pages"]
    roles = [f for f in led["facts"] if f["kind"] == "role"]
    assert len(roles) >= 3
    exp_bullets = [f for f in led["facts"] if f["kind"] == "bullet" and f["parent"]
                   and idx[f["parent"]]["kind"] == "role"]
    assert len(exp_bullets) == 13  # wrapped bullet lines are merged, not split
    assert any(f["fields"].get("end_line") for f in exp_bullets)
    _assert_lines_match(led, txt)
    assert all(f["page"] in (1, 2) for f in led["facts"])


def test_extract_flags_tables_and_headers(run, tmp_path):
    import docx
    d = docx.Document()
    d.sections[0].header.paragraphs[0].text = "Jane Smith | jane@example.com | 07700 900000"
    d.sections[0].footer.paragraphs[0].text = "Page 1"
    d.add_paragraph("Jane Smith")
    d.add_heading("Experience", level=1)
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "Analyst, Acme Ltd, London"
    t.cell(0, 1).text = "Mar 2022 – Present"
    for i in range(10):
        d.add_paragraph(f"Built report number {i} for the finance team", style="List Bullet")
    src = tmp_path / "tabled.docx"
    d.save(str(src))
    r, res, out, txt = _extract(run, src, tmp_path)
    assert r.returncode == 0
    warns = " ".join(res["report"]["warnings"])
    assert "table" in warns and "Analyst, Acme Ltd" in warns
    assert "header text" in warns and "jane@example.com" in warns
    assert "footer" in warns
    led = jc.load_ledger(out)
    assert any(f["fields"].get("origin") == "header" for f in led["facts"])
    assert any(f["fields"].get("origin") == "table" for f in led["facts"])
    _assert_lines_match(led, txt)


def test_extract_too_short_exit_1(run, tmp_path):
    src = tmp_path / "tiny.md"
    src.write_text("# Jane Smith\njane@example.com\n\n## Experience\n- Did things\n", encoding="utf-8")
    r, res, out, txt = _extract(run, src, tmp_path)
    assert r.returncode == 1 and not out.exists() and txt.exists()
    assert any("only" in w for w in res["report"]["warnings"])


def test_extract_refuses_overwrite(run, tmp_path):
    out = tmp_path / "ledger.json"
    out.write_text('{"facts": []}', encoding="utf-8")
    r = run("cv_extract.py", SAMPLE_MD, "--out", out)
    assert r.returncode == 4 and "--force" in r.stderr
    r = run("cv_extract.py", SAMPLE_MD, "--out", out, "--force")
    assert r.returncode == 0
    assert list(tmp_path.glob("ledger.bak-*.json"))


def test_extract_unsupported_and_missing(run, tmp_path):
    (tmp_path / "cv.rtf").write_text("x", encoding="utf-8")
    assert run("cv_extract.py", tmp_path / "cv.rtf").returncode == 4
    assert run("cv_extract.py", tmp_path / "nope.pdf").returncode == 4


def test_two_column_pdf_flagged(tmp_path):
    fitz = pytest.importorskip("pymupdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 60
    for i in range(30):
        page.insert_text((40, y), f"Skill {i}", fontsize=10)
        page.insert_text((330, y), f"Built the monthly report pack number {i} for finance", fontsize=10)
        y += 16
    src = tmp_path / "cols.pdf"
    doc.save(str(src))
    res = cv_extract.extract(src)
    assert res["report"]["reading_order"]["columns_suspected"]
    assert any("multi-column" in w for w in res["report"]["warnings"])


def test_pdf_wrapped_bullets_merge(tmp_path):
    fitz = pytest.importorskip("pymupdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    lines = [(40, "Jane Smith"), (40, "London | 07700 900000 | jane@example.com"), (40, "Experience"),
             (40, "Data Analyst, Acme Ltd, London    Mar 2022 - Present"),
             (40, "•"), (54, "Built a Tableau dashboard used weekly by twelve"),
             (54, "marketers across three regions"),
             (40, "•"), (54, "Cut report run time from 4 hours to 20 minutes"),
             (40, "Education"), (40, "BSc Mathematics, University of York, 2015 - 2018"),
             (40, "Skills"), (40, "SQL, Python, Tableau")]
    y = 60
    for i, (x, text) in enumerate(lines):
        if text == "•":
            page.insert_text((x, y), text, fontsize=10)
            continue
        page.insert_text((x, y), text, fontsize=10)
        y += 14
    src = tmp_path / "wrapped.pdf"
    doc.save(str(src))
    res = cv_extract.extract(src)
    bullets = [f for f in res["facts"] if f["kind"] == "bullet"]
    assert len(bullets) == 2, [f["text"] for f in res["facts"]]
    assert bullets[0]["text"].endswith("marketers across three regions")
    role = next(f for f in res["facts"] if f["kind"] == "role")
    assert all(b["parent"] == role["id"] for b in bullets)


# -------------------------------------------------------------------- fragments

FRAGMENT = ("### Senior Finance Analyst — Northgate Foods Ltd | Leeds | Mar 2022 – Present\n"
            "- Rebuilt the month-end close around 14 reconciliations in Power Query.\n"
            "- Built the rolling 18-month EBITDA forecast.\n"
            "- Run monthly reviews with 6 site general managers.\n"
            "- Coach two finance graduates through CIMA exams.\n")


@pytest.mark.parametrize("suffix", [".md", ".txt"])
def test_fragment_needs_flag_then_builds_ledger(run, tmp_path, suffix):
    src = tmp_path / f"frag{suffix}"
    src.write_text(FRAGMENT, encoding="utf-8")
    r, res, out, txt = _extract(run, src, tmp_path)
    assert r.returncode == 1 and not out.exists()
    assert any("--fragment" in w for w in res["report"]["warnings"])
    r, res, out, txt = _extract(run, src, tmp_path, "--fragment")
    assert r.returncode == 0, r.stdout
    assert res["report"]["fragment"] is True
    led = jc.load_ledger(out)
    assert led["source"]["fragment"] is True
    role = [f for f in led["facts"] if f["kind"] == "role"]
    assert len(role) == 1 and role[0]["fields"]["employer"] == "Northgate Foods Ltd"
    bullets = [f for f in led["facts"] if f["kind"] == "bullet"]
    assert len(bullets) == 4 and all(b["parent"] == role[0]["id"] for b in bullets)
    assert not any("no email or phone" in w for w in res["report"]["warnings"])
    _assert_lines_match(led, txt)


def test_min_lines_marks_fragment(run, tmp_path):
    src = tmp_path / "frag.md"
    src.write_text(FRAGMENT, encoding="utf-8")
    r, res, out, _ = _extract(run, src, tmp_path, "--min-lines", "3")
    assert r.returncode == 0 and jc.load_ledger(out)["source"]["fragment"] is True
    full_dir = tmp_path / "full"
    full_dir.mkdir()
    full, res2, out2, _ = _extract(run, SAMPLE_MD, full_dir)
    assert full.returncode == 0 and "fragment" not in jc.load_ledger(out2)["source"]
    assert res2["report"]["fragment"] is False


def test_fragment_still_fails_on_empty_or_garbage(run, tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("\n\n", encoding="utf-8")
    r, res, out, _ = _extract(run, empty, tmp_path, "--fragment")
    assert r.returncode == 1 and not out.exists()
    junk = tmp_path / "junk.txt"
    junk.write_text("%%% 1234 5678 ### ||| 9999\n@@ 0101 0202 ··· 4545\n", encoding="utf-8")
    r, res, out, _ = _extract(run, junk, tmp_path, "--fragment")
    assert r.returncode == 1 and res["report"]["garbage_suspected"] and not out.exists()


# ---------------------------------------------------------------- cover letter

LETTER = SAMPLE_MD.parent / "sample-letter-uk.md"


def test_format_date():
    from datetime import date
    assert cv_render.format_date(date(2026, 11, 2), "uk") == "2 November 2026"
    assert cv_render.format_date(date(2026, 11, 2), "us") == "November 2, 2026"


def test_render_letter(run, tmp_path):
    import docx
    from datetime import date
    out = tmp_path / "letter.docx"
    r = run("cv_render.py", LETTER, "--letter", "--locale", "uk", "--out", out, "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    rep = json.loads(r.stdout)
    assert rep["kind"] == "letter" and rep["structure"]["ok"]
    assert rep["docx_text_check"]["missing"] == [] and rep["docx_text_check"]["out_of_order"] == []
    assert rep["date"] == cv_render.format_date(date.today(), "uk")
    d = docx.Document(str(out))
    texts = [p.text for p in d.paragraphs]
    assert texts[0] == "Hannah Okafor" and "hannah.okafor@example.com" in texts[1]
    assert texts[2] == rep["date"]
    assert texts[3] == "Ms Adeyemi, Finance Director\nHarrow & Pike Ltd, 12 Wellington Street, Leeds LS1 4DL"
    assert texts[4] == "Finance Business Partner (ref HP-4471)" and d.paragraphs[4].runs[0].bold
    assert texts[5] == "Dear Ms Adeyemi,"
    assert texts[-1] == "Yours sincerely,\nHannah Okafor"
    assert d.tables == [] and round(d.sections[0].page_width.cm, 1) == 21.0
    with zipfile.ZipFile(out) as z:
        assert not [n for n in z.namelist() if re.match(r"word/(header|footer)", n)]


def test_render_letter_us_date_and_page(run, tmp_path):
    import docx
    from datetime import date
    out = tmp_path / "letter-us.docx"
    r = run("cv_render.py", LETTER, "--letter", "--locale", "us", "--out", out, "--json")
    assert r.returncode == 0
    assert json.loads(r.stdout)["date"] == cv_render.format_date(date.today(), "us")
    assert round(docx.Document(str(out)).sections[0].page_width.inches, 2) == 8.5


def test_render_letter_refusals(run, tmp_path):
    cited = tmp_path / "cited.md"
    cited.write_text(LETTER.read_text(encoding="utf-8").replace("two years.", "two years. [F009]"),
                     encoding="utf-8")
    r = run("cv_render.py", cited, "--letter", "--locale", "uk", "--out", tmp_path / "a.docx")
    assert r.returncode == 4 and "markers" in r.stderr
    nodear = tmp_path / "nodear.md"
    nodear.write_text("# Hannah Okafor\nhannah@example.com\n\nHi Sam,\n\nShort note.\n", encoding="utf-8")
    r = run("cv_render.py", nodear, "--letter", "--locale", "uk", "--out", tmp_path / "b.docx")
    assert r.returncode == 4 and "Dear" in r.stderr


def test_letter_pdf(run, tmp_path):
    from conftest import pdf_converter_available
    if not pdf_converter_available():
        pytest.skip("no PDF converter on this machine")
    out = tmp_path / "letter.docx"
    r = run("cv_render.py", LETTER, "--letter", "--locale", "uk", "--out", out, "--pdf", "--json")
    rep = json.loads(r.stdout)
    assert r.returncode == 0 and rep["pdf_text_check"]["missing"] == [] and rep["pdf_text_check"]["pages"] == 1
