"""Render a CV in ARCHITECTURE section 3 markdown to an ATS-safe DOCX (and PDF).

Purpose
    Builds the DOCX from scratch with python-docx (no template file): one
    column, body text only, no tables, text boxes, images, headers or footers,
    real Word bullet styles (not typed bullet characters), section headings as
    Word "Heading 1" with a thin bottom rule, and dates right-aligned on a tab
    stop. Then "proofs the file" (research 03 TL;DR #20): it re-extracts the
    text from the DOCX (and the PDF if made) and reports any source line that
    is missing or out of order, and checks the structure is still ATS-safe.

    UK: A4, 2 cm margins. US: Letter, 0.75 in margins. Both: Calibri 10.5 body,
    name 18 bold, headings 12 bold.

    The input must already be stripped of citation markers
    (ledger_check.py --strip --out clean.md). Markers in the input are refused,
    because their presence means the honesty check has not passed.

Usage
    cv_render.py <cv.md> --locale uk|us --out <file.docx> [--pdf] [--json]
    cv_render.py <letter.md> --letter --locale uk|us --out <file.docx> [--pdf] [--json]

    --letter renders a cover letter: '# Name', then the contact line, then
    optional 'To: ...' lines (address block) and a 'Re: ...' line (bold
    subject), then the body from the first line starting 'Dear '. Today's date
    is inserted after the contact line ('2 November 2026' uk, 'November 2, 2026'
    us). Same page, margins, font and checks as the CV.

    --pdf writes <file>.pdf next to the DOCX using docx2pdf (Microsoft Word on
    Windows/macOS), else LibreOffice (soffice --headless). If neither is
    available it says so and still exits 0 with the DOCX.

    --preview (implies --pdf) also writes page-1.png, page-2.png ... next to the
    output, rendered from the PDF at 100 dpi, so the Visual formatting dimension
    of the audit can be judged by looking at the pages.

    cv_render.py --preview-only <file.docx|file.pdf> --out-dir <dir> [--json]
    renders any existing CV to page PNGs without building anything. A PDF is used
    directly. A DOCX is converted first with docx2pdf (needs Microsoft Word) or
    LibreOffice; if neither exists it says so and exits 1. Prints each PNG path
    and the page size in cm.

Exit codes
    0  DOCX written and verified (PDF written and verified, or not available);
       with --preview-only, the PNGs were written
    1  written, but verification found missing/out-of-order text or an
       ATS-unsafe structure (listed in the report); with --preview-only, the
       file could not be turned into page images (no converter, unreadable PDF)
    3  python-docx is missing (the pip line is printed)
    4  usage or input error (missing file, citation markers present, no H1
       name, --letter without a 'Dear ' line, output file locked)
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from jf_common import (
    ANY_MARKER_RE, EXIT_FAIL, EXIT_OK, die, emit_json, find_soffice, iter_blocks, make_parser,
    parse_cv_markdown, read_text, require, setup_io,
)

LOCALES = {
    "uk": {"width_cm": 21.0, "height_cm": 29.7, "margin_cm": 2.0, "lang": "en-GB"},
    "us": {"width_cm": 21.59, "height_cm": 27.94, "margin_cm": 1.905, "lang": "en-US"},
}
BODY_PT = 10.5
NAME_PT = 18
HEADING_PT = 12
FONT = "Calibri"
TOKEN_RE = re.compile(r"[0-9a-zà-ɏ£$€%]+")


# ---------------------------------------------------------------- docx helpers

def _fonts_xml(rpr, qn, OxmlElement, lang: str | None = None) -> None:
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in list(rfonts.attrib):
        del rfonts.attrib[attr]
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), FONT)
    if lang:
        el = rpr.find(qn("w:lang"))
        if el is None:
            el = OxmlElement("w:lang")
            rpr.append(el)
        el.set(qn("w:val"), lang)


def _style_rpr(style, qn):
    return style.element.get_or_add_rPr()


def _strip_color_theme(rpr, qn) -> None:
    color = rpr.find(qn("w:color"))
    if color is not None:
        for a in ("w:themeColor", "w:themeShade", "w:themeTint"):
            if color.get(qn(a)) is not None:
                del color.attrib[qn(a)]
        color.set(qn("w:val"), "000000")


def _bottom_rule(ppr, qn, OxmlElement) -> None:
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pbdr.append(bottom)
    # pBdr must come after keepNext/keepLines/pageBreakBefore etc. and before spacing
    spacing = ppr.find(qn("w:spacing"))
    if spacing is not None:
        spacing.addprevious(pbdr)
    else:
        ppr.append(pbdr)


def _add_inline(paragraph, text: str, Pt) -> None:
    """Add text with **bold** spans as runs."""
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not part:
            continue
        run = paragraph.add_run(part)
        if i % 2 == 1:
            run.bold = True


def _base_document(locale: str):
    """A blank, ATS-safe document with the page, fonts and styles both CV and letter use."""
    docx = require("docx", "python-docx")
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    spec = LOCALES[locale]
    doc = docx.Document()

    # drop the template's thumbnail image from the package
    pkg = doc.part.package
    for rid, rel in list(pkg.rels.items()):
        if rel.reltype == RT.THUMBNAIL:
            del pkg.rels[rid]

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(spec["width_cm"]), Cm(spec["height_cm"])
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(spec["margin_cm"]))
    sec.header_distance = sec.footer_distance = Cm(1.0)
    text_width = sec.page_width - sec.left_margin - sec.right_margin

    # document defaults and Normal
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    if defaults is not None:
        rpr = defaults.find(qn("w:rPrDefault") + "/" + qn("w:rPr"))
        if rpr is not None:
            _fonts_xml(rpr, qn, OxmlElement, spec["lang"])
    normal = doc.styles["Normal"]
    _fonts_xml(_style_rpr(normal, qn), qn, OxmlElement, spec["lang"])
    normal.font.size = Pt(BODY_PT)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    pf = normal.paragraph_format
    pf.space_before, pf.space_after, pf.line_spacing = Pt(0), Pt(2), 1.0

    h1 = doc.styles["Heading 1"]
    rpr = _style_rpr(h1, qn)
    _fonts_xml(rpr, qn, OxmlElement)
    _strip_color_theme(rpr, qn)
    h1.font.size, h1.font.bold, h1.font.italic = Pt(HEADING_PT), True, False
    h1.font.color.rgb = RGBColor(0, 0, 0)
    h1.paragraph_format.space_before, h1.paragraph_format.space_after = Pt(9), Pt(3)
    h1.paragraph_format.keep_with_next = True
    _bottom_rule(h1.element.get_or_add_pPr(), qn, OxmlElement)

    bullet = doc.styles["List Bullet"]
    bullet.paragraph_format.space_after = Pt(1)
    bullet.paragraph_format.line_spacing = 1.0
    return doc, text_width


def _add_name_contact(doc, name: str, contact: str | None) -> None:
    from docx.shared import Pt
    p = doc.add_paragraph()
    r = p.add_run(name)
    r.bold, r.font.size = True, Pt(NAME_PT)
    p.paragraph_format.space_after = Pt(2)
    if contact:
        p = doc.add_paragraph(contact)
        p.paragraph_format.space_after = Pt(4)


def _set_core_properties(doc, name: str, title: str) -> None:
    cp = doc.core_properties
    cp.author = name
    cp.last_modified_by = name
    cp.title = title.strip()
    cp.comments = ""
    cp.keywords = ""
    cp.subject = ""
    cp.category = ""


def build_docx(parsed: dict, locale: str):
    from docx.enum.text import WD_TAB_ALIGNMENT
    from docx.shared import Pt

    doc, text_width = _base_document(locale)
    name = parsed["name"] or ""
    _add_name_contact(doc, name, parsed.get("contact"))

    def add_block(blk: dict) -> None:
        t = blk["type"]
        if t == "entry":
            para = doc.add_paragraph()
            para.paragraph_format.tab_stops.add_tab_stop(text_width, WD_TAB_ALIGNMENT.RIGHT)
            para.paragraph_format.space_before = Pt(5)
            para.paragraph_format.keep_with_next = True
            title = para.add_run(blk["title"])
            title.bold = True
            if blk["org"]:
                para.add_run(" — " + blk["org"])
            if blk["location"]:
                para.add_run(", " + blk["location"])
            if blk["dates"]:
                para.add_run("\t" + blk["dates"])
            for child in blk.get("children", []):
                add_block(child)
        elif t == "bullet":
            _add_inline(doc.add_paragraph(style="List Bullet"), blk["text"], Pt)
        elif t == "skill":
            para = doc.add_paragraph()
            lab = para.add_run(blk["label"] + ": ")
            lab.bold = True
            _add_inline(para, blk["value"], Pt)
        else:
            _add_inline(doc.add_paragraph(), blk["text"], Pt)

    for blk in parsed["preamble"]:
        add_block(blk)
    for section in parsed["sections"]:
        doc.add_paragraph(section["name"], style="Heading 1")
        for blk in section["blocks"]:
            add_block(blk)

    _set_core_properties(doc, name, f"{name} CV")
    return doc


# --------------------------------------------------------------- cover letter

MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December")


def format_date(d: date, locale: str) -> str:
    """'2 November 2026' (uk) or 'November 2, 2026' (us), independent of the OS locale."""
    month = MONTH_NAMES[d.month - 1]
    return f"{d.day} {month} {d.year}" if locale == "uk" else f"{month} {d.day}, {d.year}"


def parse_letter_markdown(text: str) -> dict:
    """H1 name; next non-empty line the contact line; optional 'To: ...' lines and one
    're: ...' line; then the body from the first line starting 'Dear '.

    Body blocks are blank-line separated. A block whose lines are all short (<= 6
    words, e.g. the sign-off and name) keeps its line breaks; others are joined.
    """
    res: dict = {"name": None, "name_line": None, "contact": None, "contact_line": None,
                 "to": [], "re": None, "body": [], "warnings": []}
    lines = text.splitlines()
    i = 0
    n = len(lines)

    def skip_blank(j: int) -> int:
        while j < n and not lines[j].strip():
            j += 1
        return j

    i = skip_blank(i)
    m = re.match(r"^#\s+(.+)$", lines[i].strip()) if i < n else None
    if not m:
        raise ValueError("a letter starts with '# Name'")
    res["name"], res["name_line"] = m.group(1).strip(), i + 1
    i = skip_blank(i + 1)
    if i < n and not re.match(r"(?i)^(to|re):|^dear\s", lines[i].strip()):
        res["contact"], res["contact_line"] = lines[i].strip(), i + 1
        i += 1
    while i < n:
        s = lines[i].strip()
        if re.match(r"^Dear\s", s):
            break
        if s:
            mt = re.match(r"(?i)^to:\s*(.+)$", s)
            mr = re.match(r"(?i)^re:\s*(.+)$", s)
            if mt:
                res["to"].append((i + 1, mt.group(1).strip()))
            elif mr and res["re"] is None:
                res["re"] = (i + 1, mr.group(1).strip())
            else:
                res["warnings"].append(f"line {i + 1}: text before 'Dear' is not a To:/Re: line; rendered as is")
                res["to"].append((i + 1, s))
        i += 1
    if i >= n:
        raise ValueError("no line starting 'Dear ' found; the letter body starts at the greeting")
    block: list[tuple[int, str]] = []
    for j in range(i, n):
        s = lines[j].strip()
        if not s:
            if block:
                res["body"].append(block)
            block = []
            continue
        if re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|\|)", s):
            res["warnings"].append(f"line {j + 1}: headings, bullets and tables do not belong in a letter")
            s = re.sub(r"^(#{1,6}|[-*+]|\d+[.)])\s+", "", s)
        block.append((j + 1, s))
    if block:
        res["body"].append(block)
    return res


def _block_keeps_breaks(block: list[tuple[int, str]]) -> bool:
    return len(block) > 1 and all(len(t.split()) <= 6 for _, t in block)


def letter_units(parsed: dict, date_text: str) -> list[dict]:
    units = [{"line": parsed["name_line"], "text": parsed["name"]}]
    if parsed["contact"]:
        units.append({"line": parsed["contact_line"], "text": parsed["contact"]})
    units.append({"line": None, "text": date_text})
    units += [{"line": ln, "text": t} for ln, t in parsed["to"]]
    if parsed["re"]:
        units.append({"line": parsed["re"][0], "text": parsed["re"][1]})
    for block in parsed["body"]:
        if _block_keeps_breaks(block):
            units += [{"line": ln, "text": t} for ln, t in block]
        else:
            units.append({"line": block[0][0], "text": " ".join(t for _, t in block)})
    return units


def build_letter_docx(parsed: dict, locale: str, date_text: str):
    from docx.enum.text import WD_BREAK
    from docx.shared import Pt

    doc, _ = _base_document(locale)
    doc.styles["Normal"].paragraph_format.space_after = Pt(8)
    _add_name_contact(doc, parsed["name"], parsed["contact"])
    p = doc.add_paragraph(date_text)
    p.paragraph_format.space_before = Pt(10)
    if parsed["to"]:
        p = doc.add_paragraph()
        for k, (_, t) in enumerate(parsed["to"]):
            if k:
                p.add_run().add_break(WD_BREAK.LINE)
            p.add_run(t)
    if parsed["re"]:
        run = doc.add_paragraph().add_run(parsed["re"][1])
        run.bold = True
    for block in parsed["body"]:
        para = doc.add_paragraph()
        if _block_keeps_breaks(block):
            for k, (_, t) in enumerate(block):
                if k:
                    para.add_run().add_break(WD_BREAK.LINE)
                _add_inline(para, t, Pt)
        else:
            _add_inline(para, " ".join(t for _, t in block), Pt)
    _set_core_properties(doc, parsed["name"], f"{parsed['name']} cover letter")
    return doc


# --------------------------------------------------------------- verification

def _unit_text(blk: dict) -> str:
    if blk["type"] == "entry":
        return " ".join(x for x in (blk["title"], blk["org"], blk["location"], blk["dates"]) if x)
    if blk["type"] == "skill":
        return f"{blk['label']}: {blk['value']}"
    return blk["text"]


def source_units(parsed: dict) -> list[dict]:
    """Every source line that must appear in the rendered file, in order."""
    units = []
    if parsed.get("name"):
        units.append({"line": parsed["name_line"], "text": parsed["name"]})
    if parsed.get("contact"):
        units.append({"line": parsed["contact_line"], "text": parsed["contact"]})
    for _, blk in iter_blocks({"sections": [], "preamble": parsed["preamble"]}):
        units.append({"line": blk["line"], "text": _unit_text(blk)})
    for sec in parsed["sections"]:
        units.append({"line": sec["line"], "text": sec["name"]})
        for _, blk in iter_blocks({"sections": [sec], "preamble": []}):
            units.append({"line": blk["line"], "text": _unit_text(blk)})
    return units


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.casefold())


def _find(hay: list[str], needle: list[str], start: int) -> int:
    n = len(needle)
    first = needle[0]
    i = start
    while True:
        try:
            i = hay.index(first, i)
        except ValueError:
            return -1
        if hay[i:i + n] == needle:
            return i
        i += 1


def verify_text(units: list[dict], extracted_text: str) -> dict:
    hay = _tokens(extracted_text)
    pos = 0
    missing, out_of_order = [], []
    for u in units:
        needle = _tokens(u["text"])
        if not needle:
            continue
        at = _find(hay, needle, pos)
        if at >= 0:
            pos = at + len(needle)
            continue
        if _find(hay, needle, 0) >= 0:
            out_of_order.append({"line": u["line"], "text": u["text"]})
        else:
            missing.append({"line": u["line"], "text": u["text"]})
    return {"checked": len(units), "missing": missing, "out_of_order": out_of_order,
            "ok": not missing and not out_of_order}


def verify_structure(docx_path: Path) -> dict:
    import docx  # already required
    from docx.oxml.ns import qn
    problems = []
    with zipfile.ZipFile(docx_path) as z:
        names = z.namelist()
    headers = [n for n in names if re.match(r"word/(header|footer)\d*\.xml$", n)]
    if headers:
        problems.append(f"header/footer parts present: {headers}")
    media = [n for n in names if n.startswith("word/media/")]
    if media:
        problems.append(f"images present: {media}")
    d = docx.Document(str(docx_path))
    if d.tables:
        problems.append(f"{len(d.tables)} table(s) present")
    body = d.element.body
    if list(body.iter(qn("w:txbxContent"))):
        problems.append("text boxes present")
    if list(body.iter(qn("w:drawing"))) or list(body.iter(qn("w:pict"))):
        problems.append("drawings or pictures present")
    typed = [p.text[:40] for p in d.paragraphs if re.match(r"^\s*[•●▪–\-*]\s", p.text)]
    if typed:
        problems.append(f"typed bullet characters instead of a bullet style: {typed[:3]}")
    bullets = [p for p in d.paragraphs if p.style is not None and p.style.name == "List Bullet"]
    sectPr = d.sections[0]
    return {"ok": not problems, "problems": problems, "bullet_paragraphs": len(bullets),
            "page_size_cm": [round(sectPr.page_width.cm, 2), round(sectPr.page_height.cm, 2)]}


# -------------------------------------------------------------------- PDF

def convert_pdf(docx_path: Path, pdf_path: Path, timeout: int = 180) -> tuple[str | None, list[str]]:
    """Return (converter used or None, notes)."""
    notes = []
    if importlib.util.find_spec("docx2pdf") is not None:
        code = "import sys\nfrom docx2pdf import convert\nconvert(sys.argv[1], sys.argv[2])\n"
        try:
            r = subprocess.run([sys.executable, "-c", code, str(docx_path), str(pdf_path)],
                               capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 and pdf_path.is_file():
                return "docx2pdf", notes
            notes.append("docx2pdf failed: " + (r.stderr.strip().splitlines() or ["no output"])[-1][:300])
        except subprocess.TimeoutExpired:
            notes.append(f"docx2pdf timed out after {timeout}s (is a Word dialog open?)")
    else:
        notes.append("docx2pdf not installed")
    soffice = find_soffice()
    if soffice:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                r = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp,
                                    str(docx_path)], capture_output=True, text=True, timeout=timeout)
                produced = Path(tmp) / (docx_path.stem + ".pdf")
                if r.returncode == 0 and produced.is_file():
                    os.replace(produced, pdf_path)
                    return "libreoffice", notes
                notes.append("LibreOffice conversion failed: " + (r.stderr.strip()[-300:] or "no output"))
            except (subprocess.TimeoutExpired, OSError) as exc:
                notes.append(f"LibreOffice conversion failed: {exc}")
    else:
        notes.append("LibreOffice (soffice) not found")
    return None, notes


# ---------------------------------------------------------------- page preview

def make_previews(pdf_path: Path, out_dir: Path, resolution: int = 100) -> list[dict]:
    """Write page-1.png, page-2.png ... into out_dir from a PDF. Returns one dict per page
    with the PNG path and the page size in cm."""
    pdfplumber = require("pdfplumber")
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for n, page in enumerate(pdf.pages, start=1):
            png = out_dir / f"page-{n}.png"
            page.to_image(resolution=resolution).save(str(png))
            pages.append({"page": n, "png": str(png),
                          "width_cm": round(float(page.width) / 72 * 2.54, 1),
                          "height_cm": round(float(page.height) / 72 * 2.54, 1)})
    return pages


def preview_file(src: Path, out_dir: Path) -> dict:
    """Page images for a DOCX or PDF. Returns {"ok", "source", "converter", "pages", "notes"}."""
    res: dict = {"ok": False, "source": str(src), "converter": None, "pages": [], "notes": []}
    ext = src.suffix.lower()
    if ext == ".pdf":
        res["converter"] = "none (PDF used directly)"
        try:
            res["pages"] = make_previews(src, out_dir)
        except Exception as exc:  # unreadable or encrypted PDF
            res["notes"].append(f"cannot render {src.name}: {exc}")
    elif ext == ".docx":
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / (src.stem + ".pdf")
            converter, notes = convert_pdf(src, pdf_path)
            res["notes"] = notes
            if not converter:
                res["notes"].append(
                    "Cannot turn this DOCX into page images here: no Microsoft Word (with docx2pdf) and "
                    "no LibreOffice found. Export the CV to PDF yourself and run --preview-only on the PDF.")
                return res
            res["converter"] = converter
            res["pages"] = make_previews(pdf_path, out_dir)
    else:
        res["notes"].append(f"unsupported file type {ext!r}; use .docx or .pdf")
        return res
    res["ok"] = bool(res["pages"])
    return res


def _print_preview(res: dict) -> None:
    print(f"{'OK' if res['ok'] else 'NO PREVIEW'}  {res['source']} (via {res['converter'] or 'no converter'})")
    for pg in res["pages"]:
        print(f"  {pg['png']}  page {pg['page']}, {pg['width_cm']} x {pg['height_cm']} cm")
    for n in res["notes"]:
        print(f"  note: {n}")


# ------------------------------------------------------------------------ CLI

def render(md_text: str, locale: str, out: Path, pdf: bool = False, letter: bool = False,
           today: date | None = None) -> dict:
    """Render a CV (or, with letter=True, a cover letter); write the DOCX; verify it."""
    date_text = None
    if letter:
        parsed = parse_letter_markdown(md_text)
        date_text = format_date(today or date.today(), locale)
        doc = build_letter_docx(parsed, locale, date_text)
        units = letter_units(parsed, date_text)
    else:
        parsed = parse_cv_markdown(md_text)
        doc = build_docx(parsed, locale)
        units = source_units(parsed)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{out.stem}.", suffix=".docx", dir=str(out.parent))
    os.close(fd)
    try:
        doc.save(tmp)
        os.replace(tmp, out)
    except PermissionError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise PermissionError(f"cannot write {out}; is it open in Word? ({exc})") from exc

    import cv_extract  # local module
    lines, _, _, _ = cv_extract.read_docx_lines(out)
    docx_check = verify_text(units, "\n".join(ln.text for ln in lines))
    structure = verify_structure(out)
    report = {
        "ok": docx_check["ok"] and structure["ok"], "docx": str(out), "locale": locale,
        "kind": "letter" if letter else "cv", "date": date_text,
        "parse_warnings": parsed["warnings"], "structure": structure, "docx_text_check": docx_check,
        "pdf": None, "pdf_converter": None, "pdf_text_check": None, "pdf_notes": [],
    }
    if pdf:
        pdf_path = out.with_suffix(".pdf")
        converter, notes = convert_pdf(out, pdf_path)
        report["pdf_notes"] = notes
        if converter:
            report["pdf"], report["pdf_converter"] = str(pdf_path), converter
            plines, _, warns, _, pages = cv_extract.read_pdf(pdf_path)
            check = verify_text(units, "\n".join(ln.text for ln in plines))
            check["pages"] = pages
            report["pdf_text_check"] = check
            report["ok"] = report["ok"] and check["ok"]
        else:
            report["pdf_notes"].append("No PDF converter available; the DOCX is ready. "
                                       "Install Microsoft Word (with docx2pdf) or LibreOffice to get a PDF.")
    return report


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="cv_render.py")
    p.add_argument("cv", nargs="?", help="CV markdown (section 3 format, citations stripped)")
    p.add_argument("--locale", choices=("uk", "us"))
    p.add_argument("--out", help="output .docx path")
    p.add_argument("--pdf", action="store_true", help="also make a PDF next to the DOCX")
    p.add_argument("--preview", action="store_true",
                   help="also write page-N.png next to the output (implies --pdf)")
    p.add_argument("--preview-only", metavar="FILE",
                   help="render page PNGs of an existing .docx or .pdf and nothing else (needs --out-dir)")
    p.add_argument("--out-dir", help="folder for the page PNGs with --preview-only")
    p.add_argument("--letter", action="store_true", help="the input is a cover letter, not a CV")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args(argv)

    if a.preview_only:
        if not a.out_dir:
            p.error("--preview-only needs --out-dir")
        src = Path(a.preview_only)
        if not src.is_file():
            die(f"file not found: {src}")
        require("pdfplumber")
        res = preview_file(src, Path(a.out_dir))
        if a.json:
            emit_json(res)
        else:
            _print_preview(res)
        return EXIT_OK if res["ok"] else EXIT_FAIL
    if not a.cv or not a.locale or not a.out:
        p.error("a CV markdown file, --locale and --out are required "
                "(or use --preview-only FILE --out-dir DIR)")
    if a.preview:
        a.pdf = True

    out = Path(a.out)
    if out.suffix.lower() != ".docx":
        p.error("--out must end in .docx")
    md = read_text(Path(a.cv))
    marker_lines = [i for i, ln in enumerate(md.splitlines(), start=1) if ANY_MARKER_RE.search(ln)]
    if marker_lines:
        die(f"{a.cv} still has citation or [CONFIRM] markers (lines {marker_lines[:10]}). "
            f"Run ledger_check.py <file.md> --ledger <ledger.json> --strip --out <clean.md> and render the clean file.")
    if not re.search(r"(?m)^#\s+\S", md):
        die(f"{a.cv} has no '# Name' line; is it in the ARCHITECTURE section 3 format?")
    require("docx", "python-docx")
    try:
        report = render(md, a.locale, out, a.pdf, letter=a.letter)
        if a.preview:
            report["preview"] = None
            if report["pdf"]:
                report["preview"] = make_previews(Path(report["pdf"]), out.parent)
            else:
                report["pdf_notes"].append("No page previews: there is no PDF to render them from.")
    except PermissionError as exc:
        die(str(exc))
    except ValueError as exc:  # letter structure problems
        die(f"{a.cv}: {exc}")

    if a.json:
        emit_json(report)
    else:
        what = "letter" if a.letter else "CV"
        print(f"{'OK' if report['ok'] else 'CHECK FAILED'}  {report['docx']} ({what}, {a.locale.upper()})")
        if report["date"]:
            print(f"  dated {report['date']}")
        s = report["structure"]
        print(f"  structure: {'ATS-safe' if s['ok'] else 'PROBLEMS'}; {s['bullet_paragraphs']} bullet paragraphs; "
              f"page {s['page_size_cm'][0]} x {s['page_size_cm'][1]} cm")
        for prob in s["problems"]:
            print(f"    - {prob}")
        for label, chk in (("DOCX", report["docx_text_check"]), ("PDF", report["pdf_text_check"])):
            if not chk:
                continue
            pages = f", {chk['pages']} page(s)" if "pages" in chk else ""
            print(f"  {label} text check: {chk['checked']} source lines{pages}; "
                  f"{len(chk['missing'])} missing, {len(chk['out_of_order'])} out of order")
            for m in chk["missing"]:
                print(f"    missing   line {m['line']}: {m['text'][:80]}")
            for m in chk["out_of_order"]:
                print(f"    reordered line {m['line']}: {m['text'][:80]}")
        if report["pdf"]:
            print(f"  PDF: {report['pdf']} (via {report['pdf_converter']})")
        for pg in report.get("preview") or []:
            print(f"  preview: {pg['png']}  page {pg['page']}, {pg['width_cm']} x {pg['height_cm']} cm")
        for n in report["pdf_notes"]:
            print(f"  note: {n}")
        for w in report["parse_warnings"]:
            print(f"  warning: {w}")
    return EXIT_OK if report["ok"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
