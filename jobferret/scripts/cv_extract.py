"""Extract a CV (PDF, DOCX or markdown) to plain text and a fact ledger.

Purpose
    First step of cv-audit. Turns the user's CV into numbered plain-text lines
    and ledger.json facts (ARCHITECTURE section 2.1), one fact per logical line,
    each tied to its line number in the --text output so a human can look any
    fact up. Also reports how well the file extracts (the same problem an ATS
    parser has): page count, line count, reading-order checks and warnings.

    PDF: pdfplumber (fallback pypdf). DOCX: python-docx, in body order; tables,
    text boxes and header/footer text are extracted too, but flagged, because
    many ATS parsers drop them. Markdown/plain text: read directly.

Usage
    cv_extract.py <file> [--out ledger.json] [--text out.txt] [--force]
                  [--fragment | --min-lines N] [--json]

    --fragment: the input is only part of a CV (e.g. one pasted role). No
    minimum line count; no name or contact line needed. The ledger's "source"
    and the report get "fragment": true so the audit is known to be partial.
    --min-lines N changes the minimum (default 10); an accepted extraction
    under 10 lines is also marked as a fragment.

    --out refuses to overwrite an existing ledger (IDs must stay stable and the
    old one may hold user-supplied facts) unless --force, which first copies the
    old file to <name>.bak-<timestamp>.json.

Notes on facts
    One fact per non-empty line, except: a wrapped continuation line (PDF/text)
    or a soft-wrapped markdown paragraph line is merged into the fact above
    (fields.end_line records the last line), and a role title on its own line
    directly above its dates line is merged with that line. Section headings
    are recorded in "sections", not as facts. The name is a "contact" fact with
    fields.name.

    A job header can be one to three lines in any order: employer (with an optional
    "| location"), a date range, and a title. The line holding the date range is
    the date line; scripts/lexicon/role_words.txt and employer_words.txt decide
    which of the other lines is the title and which the employer. The role fact
    carries title, employer, location, start and end. A title alone on its own
    line is kept as its own fact of kind "title" whose parent is the role. When the
    lexicons cannot settle it, the best guess is filled in and the role's
    fields.confidence is "low": the model should confirm it with the user.

    Divider lines (five or more of _ - = em dash, bullet, * ~ and nothing else)
    stay in the --text output so line numbers do not move, but never become facts
    and do not count towards the line total. In a skills section, a label line
    ending in "-" or ":" followed by a list line becomes one skill fact
    ("Web Development - React, Vite, ...") with fields.label and fields.items.

Exit codes
    0  extraction ok (ledger written if --out)
    1  extraction too poor to trust: no usable text, fewer lines than the
       minimum (10, or --min-lines; none with --fragment), or garbage text (e.g.
       a scanned image or broken font encoding). --text is still written; the
       ledger is not.
    3  a required package is missing (the pip line is printed)
    4  usage or input error (missing file, unsupported type, a damaged, empty or
       password-protected file, ledger exists)
"""
from __future__ import annotations

import functools
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from jf_common import (
    DATE_RANGE_RE, EMAIL_RE, EXIT_FAIL, EXIT_OK, SINGLE_DATE_RE, atomic_write_text,
    die, emit_json, find_phones, is_contact_line, make_parser, new_ledger, normalize_date,
    now_iso, parse_entry_header, pip_line, save_ledger, setup_io, sha256_file, strip_markers,
    user_dir,
)

GLYPH_RE = re.compile(
    r"^\s*(?:[•●▪■◦○‣⁃∙·➢✓✔→►▶"
    r"*\-–—]|\(cid:\d+\))\s*"
)
MD_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SECTION_PATTERNS: list[tuple[str, str]] = [
    ("summary", r"(?:personal |professional |career |executive )?(?:profile|summary)|personal statement|about(?: me)?|(?:career )?objectives?|career goals?"),
    ("skill", r"(?:core |key |technical |relevant |professional |personal |soft |it |computer |additional )?(?:skills|competencies)(?: (?:and|&) (?:tools|technologies|expertise))?|technical expertise|tools(?: (?:and|&) technologies)?|technologies|expertise|programming languages|technical proficiency"),
    ("achievements", r"(?:key |career |notable |selected )?achievements"),
    ("experience", r"(?:(?:work|working|professional|relevant|employment|career|industry|work and|other|practical|internship) )?experiences?|work(?:ing)? history|internships?|employment(?: history)?|career history|work history|professional background|earlier career|previous experience|additional experience|volunteering|volunteer(?:ing)? experience|voluntary (?:work|experience)|military service"),
    ("education", r"education(?:al)?(?: (?:and|&) (?:qualifications|training))?(?: background)?|academic (?:background|qualifications)|qualifications|education(?:al)? history"),
    ("certification", r"certifications?|certificates|licen[cs]es(?: (?:and|&) certifications)?|professional development|training|courses|accreditations|(?:professional )?memberships"),
    ("project", r"(?:selected |personal |key |academic )?projects?|portfolio"),
    ("publication", r"publications|papers|presentations|talks|research"),
    ("award", r"awards(?: (?:and|&) honou?rs)?|honou?rs|prizes"),
    ("language", r"languages?|language skills"),
    ("interest", r"(?:personal )?interests|hobbies(?: (?:and|&) interests)?|hobby|outside work|activities|extracurricular activities"),
    ("other", r"references|additional information|other information|personal (?:details|information|data)|basic information|contact(?: details| information)?"),
]
LIST_KINDS = {"skill", "certification", "publication", "award", "language", "interest"}
TITLE_WORDS = {"curriculum vitae", "cv", "resume", "résumé"}
LEXICON_DIR = Path(__file__).resolve().parent / "lexicon"
DIVIDER_CHARS = set("_-=—–•*~")
LABEL_PREFIX_RE = re.compile(
    r"^(?P<lab>designation|position|job title|job role|role|title|company|employer|organi[sz]ation|"
    r"client|workplace)\s*[:\-–]\s*(?P<rest>\S.*)$", re.IGNORECASE)
ENUM_PREFIX_RE = re.compile(r"^(?:[IVXL]{1,4}|\d{1,2}(?:\.\d{1,2})*)[.)]\s+")
NAME_LABEL_RE = re.compile(r"^(?:full name|candidate name|name|surname)\s*[:\-]\s*(?P<n>\S.*)$", re.IGNORECASE)
CV_TITLE_NAME_RE = re.compile(r"^(?:curriculum vitae|resume|résumé|cv)\s*(?:of|[-–—:])\s*(?P<n>\S.*)$",
                              re.IGNORECASE)
INLINE_GLYPH_RE = re.compile(r"\s*[•●▪■◦○‣⁃∙➢✓✔►▶]")
LABEL_END_RE = re.compile(r"^(?P<label>.{2,60}?)\s*(?P<end>[-–—:])\s*$")


class Line:
    __slots__ = ("no", "text", "page", "is_list", "heading", "x0", "origin")

    def __init__(self, text: str, page: int | None = None, is_list: bool = False,
                 heading: int | None = None, x0: float | None = None, origin: str = "body"):
        self.no = 0
        self.text = text
        self.page = page
        self.is_list = is_list
        self.heading = heading
        self.x0 = x0
        self.origin = origin


def _display(text: str) -> str:
    # a NUL between digits is a date separator lost to a bad font map ("10\x002014"); elsewhere drop it
    text = re.sub(r"(?<=\d)\x00(?=\d)", "/", text).replace("\x00", "")
    t = text.replace(" ", " ").strip()
    t = re.sub(r"[ \t]*\t+[ \t]*", " | ", t)
    return re.sub(r" {2,}", " ", t)


# ----------------------------------------------------------------------- readers

def _columns_side_by_side(chars: list[dict], width: float) -> bool:
    """True when one extracted line is really two columns glued together: a wide
    gap left of 60% of the page with substantial text on its right. A right-aligned
    date after a tab stop does not count (its right-hand text is short)."""
    visible = [c for c in chars if str(c.get("text", "")).strip()]
    best_gap, split = 0.0, -1
    for i in range(1, len(visible)):
        gap = float(visible[i]["x0"]) - float(visible[i - 1]["x1"])
        if gap > best_gap:
            best_gap, split = gap, i
    if best_gap < 25 or split < 0:
        return False
    left = "".join(c["text"] for c in visible[:split])
    right = "".join(c["text"] for c in visible[split:])
    return float(visible[split - 1]["x1"]) < 0.6 * width and len(right) > 25 and len(left) >= 2


def _read_pdf(path: Path) -> tuple[list[Line], dict, list[str], str, int]:
    warnings: list[str] = []
    meta: dict = {"right_column_lines": 0, "page_widths": []}
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        pdfplumber = None
    if pdfplumber is not None:
        lines: list[Line] = []
        with pdfplumber.open(str(path)) as pdf:
            pages = len(pdf.pages)
            for pno, page in enumerate(pdf.pages, start=1):
                width = float(page.width or 1)
                try:
                    tl = page.extract_text_lines(layout=False, strip=True, return_chars=True)
                except Exception:  # older pdfplumber, or a page pdfplumber cannot lay out
                    try:
                        tl = [{"text": t, "x0": None} for t in (page.extract_text() or "").splitlines()]
                    except Exception as exc:
                        warnings.append(f"page {pno} could not be read ({type(exc).__name__}); its text is missing")
                        continue
                for item in tl:
                    text = _display(item.get("text", ""))
                    x0 = item.get("x0")
                    if x0 is not None and x0 > 0.4 * width:
                        meta["right_column_lines"] += 1
                    if _columns_side_by_side(item.get("chars") or [], width):
                        meta["split_lines"] = meta.get("split_lines", 0) + 1
                    lines.append(Line(text, page=pno, is_list=bool(GLYPH_RE.match(text)), x0=x0))
        return lines, meta, warnings, "pdfplumber", pages
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        sys.stderr.write("error: reading PDFs needs pdfplumber (preferred) or pypdf.\n"
                         f"  install with:  {pip_line('pdfplumber', 'pypdf')}\n")
        raise SystemExit(3)
    warnings.append("pdfplumber not installed; used pypdf (no layout positions, weaker column checks)")
    reader = PdfReader(str(path))
    lines = []
    for pno, page in enumerate(reader.pages, start=1):
        for t in (page.extract_text() or "").splitlines():
            text = _display(t)
            lines.append(Line(text, page=pno, is_list=bool(GLYPH_RE.match(text))))
    return lines, meta, warnings, "pypdf", len(reader.pages)


def read_pdf(path: Path) -> tuple[list[Line], dict, list[str], str, int]:
    """PDF to lines. A damaged, empty or password-protected file raises ValueError (exit 4),
    never a traceback."""
    try:
        return _read_pdf(path)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as exc:
        reason = str(exc).strip().splitlines()[0][:120] if str(exc).strip() else type(exc).__name__
        raise ValueError(f"cannot read {path.name} as a PDF ({reason}); it may be damaged, empty or "
                         f"password-protected. Export it again or send a DOCX") from exc


def read_text_file(path: Path) -> tuple[str, list[str]]:
    """Text of a .md/.txt file. UTF-8 first; a Windows-1252 file is decoded with a warning
    rather than refused."""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig"), []
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace"), [
            f"{path.name} is not UTF-8; read as Windows-1252, so some characters may be wrong"]


def _style_has_numpr(style) -> bool:
    from docx.oxml.ns import qn
    depth = 0
    while style is not None and depth < 10:
        ppr = style.element.find(qn("w:pPr"))
        if ppr is not None and ppr.find(qn("w:numPr")) is not None:
            return True
        style = style.base_style
        depth += 1
    return False


def _in_fallback(el) -> bool:
    fallback = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
    p = el.getparent()
    while p is not None:
        if p.tag == fallback:
            return True
        p = p.getparent()
    return False


def read_docx_lines(path: Path) -> tuple[list[Line], dict, list[str], int]:
    """DOCX paragraphs in body order, plus flagged table/text-box/header/footer text."""
    try:
        import docx  # type: ignore
        from docx.oxml.ns import qn
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
        from docx.text.paragraph import Paragraph
    except ImportError:
        sys.stderr.write(f"error: reading DOCX needs python-docx.\n  install with:  {pip_line('python-docx')}\n")
        raise SystemExit(3)
    try:
        document = docx.Document(str(path))
    except Exception as exc:  # corrupt or not a docx
        raise ValueError(f"cannot open {path} as DOCX: {exc}") from exc
    warnings: list[str] = []
    found: dict = {"tables": 0, "table_text": [], "textboxes": [], "header_text": [], "footer_text": []}
    lines: list[Line] = []
    page = 1

    def para_lines(p_el, origin: str, parent) -> list[Line]:
        nonlocal page
        para = Paragraph(p_el, parent)
        if p_el.findall(".//" + qn("w:lastRenderedPageBreak")) or any(
                br.get(qn("w:type")) == "page" for br in p_el.iter(qn("w:br"))):
            if lines:
                page += 1
        style = para.style
        name = (style.name if style is not None else "") or ""
        ppr = p_el.find(qn("w:pPr"))
        is_list = (ppr is not None and ppr.find(qn("w:numPr")) is not None) or name.startswith("List") \
            or (style is not None and _style_has_numpr(style))
        heading = None
        m = re.match(r"(?i)heading (\d)", name)
        if m:
            heading = int(m.group(1)) + 1  # Word "Heading 1" plays the role of markdown H2
        elif name.lower() == "title":
            heading = 1
        out = []
        for i, chunk in enumerate((para.text or "").split("\n")):
            text = _display(chunk)
            listed = is_list and i == 0 and bool(text)
            if listed and not GLYPH_RE.match(text):
                text = "• " + text  # show Word list bullets in the plain text
            out.append(Line(text, page=page, is_list=listed,
                            heading=heading if i == 0 else None, origin=origin))
        # text boxes anchored in this paragraph (skip the VML fallback duplicate)
        for tx in p_el.iter(qn("w:txbxContent")):
            if _in_fallback(tx):
                continue
            for inner in tx.iter(qn("w:p")):
                t = _display(Paragraph(inner, parent).text or "")
                if t:
                    found["textboxes"].append(t)
                    out.append(Line(t, page=page, origin="textbox"))
        return out

    # headers first: an ATS may never see them, but the facts may live there
    for rel in document.part.rels.values():
        if rel.is_external or rel.reltype not in (RT.HEADER, RT.FOOTER):
            continue
        kind = "header" if rel.reltype == RT.HEADER else "footer"
        for p_el in rel.target_part.element.iter(qn("w:p")):
            t = _display(Paragraph(p_el, None).text or "")
            if t:
                found[f"{kind}_text"].append(t)
    for t in found["header_text"]:
        lines.append(Line(t, page=1, origin="header"))

    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            lines.extend(para_lines(child, "body", document))
        elif child.tag == qn("w:tbl"):
            found["tables"] += 1
            for tr in child.iter(qn("w:tr")):
                for tc in tr.iter(qn("w:tc")):
                    for p_el in tc.iter(qn("w:p")):
                        for ln in para_lines(p_el, "table", document):
                            if ln.text:
                                found["table_text"].append(ln.text)
                            lines.append(ln)
        elif child.tag == qn("w:sdt"):
            for p_el in child.iter(qn("w:p")):
                lines.extend(para_lines(p_el, "body", document))
    for t in found["footer_text"]:
        lines.append(Line(t, page=page, origin="footer"))

    if found["tables"]:
        warnings.append(f"{found['tables']} table(s) found; ATS parsers often scramble table text. "
                        f"Text found there: {found['table_text'][:8]}")
    if found["textboxes"]:
        warnings.append(f"{len(found['textboxes'])} text box line(s) found; many ATS parsers drop text boxes. "
                        f"Text found there: {found['textboxes'][:8]}")
    if found["header_text"]:
        warnings.append(f"header text found; many ATS parsers ignore headers: {found['header_text'][:5]}")
    if found["footer_text"]:
        warnings.append(f"footer text found; many ATS parsers ignore footers: {found['footer_text'][:5]}")
    return lines, found, warnings, page


def read_markdown(path: Path, text: str | None = None) -> list[Line]:
    if text is None:
        text = read_text_file(path)[0]
    lines = []
    for raw in text.splitlines():
        s = raw.rstrip()
        m = re.match(r"^(#{1,6})\s+(.*)$", s.strip())
        heading = len(m.group(1)) if m else None
        lines.append(Line(s.replace("\t", "    "), is_list=bool(MD_LIST_RE.match(s)), heading=heading))
    return lines


# ------------------------------------------------------------------ classifying

def section_kind(text: str) -> str | None:
    t = strip_markers(text).strip().strip("#").strip().rstrip(":").strip()
    t = re.sub(r"\*\*|__", "", t)
    if not t or len(t.split()) > 6 or re.search(r"\d", t):
        return None
    for kind, pat in SECTION_PATTERNS:
        if re.fullmatch(pat, t, re.IGNORECASE):
            return kind
    return None


def clean_fact_text(line: Line) -> str:
    t = line.text
    t = re.sub(r"^#{1,6}\s+", "", t.strip())
    t = MD_LIST_RE.sub("", t) if line.heading is None else t
    t = GLYPH_RE.sub("", t) if line.is_list else t
    t = strip_markers(t)
    t = re.sub(r"\*\*|__", "", t)
    return re.sub(r"\s+", " ", t).strip()


def role_fields(text: str, md_header: bool) -> dict:
    """Fields for a job header. Markdown H3 headers use the section 3 split; anything else
    goes through the block parser (title / employer / location from the lexicons)."""
    if md_header:
        h = parse_entry_header(text)
        org, loc = h["org"], h["location"]
        return {"title": h["title"], "employer": org, "location": loc,
                "start": h["start"], "end": h["end"], "current": h["current"]}
    return parse_role_block([text])["fields"]


def simple_fields(text: str, md_header: bool) -> dict:
    if md_header or (" — " in text and " | " in text):
        h = parse_entry_header(text)
        org, loc = h["org"], h["location"]
        if not md_header and not loc and ", " in org:
            org, loc = org.rsplit(", ", 1)  # rendered form "Title - Org, Location | dates"
        return {"title": h["title"], "employer": org, "location": loc,
                "start": h["start"], "end": h["end"], "current": h["current"]}
    m = DATE_RANGE_RE.search(text)
    fields: dict = {}
    rest = text
    if m:
        fields["start"] = normalize_date(m.group("start"))
        fields["end"] = normalize_date(m.group("end"))
        fields["current"] = fields["end"] is None
        rest = (text[:m.start()] + " " + text[m.end():])
    rest = re.sub(r"[()]", " ", rest)
    parts = [p.strip(" ,;|") for p in re.split(r"\s[—–|-]\s|,|\s\|\s|\bat\b", rest) if p.strip(" ,;|")]
    parts = [re.sub(r"\s{2,}", " ", x) for x in parts]
    if parts:
        fields["title"] = parts[0]
    if len(parts) > 1:
        fields["employer"] = parts[1]
    if len(parts) > 2:
        fields["location"] = ", ".join(parts[2:])
    return fields


def education_fields(text: str, md_header: bool) -> dict:
    f = simple_fields(text, md_header)
    out = {}
    if f.get("title"):
        out["qualification"] = f["title"]
    if f.get("employer"):
        out["institution"] = f["employer"]
    for k in ("start", "end"):
        if k in f:
            out[k] = f[k]
    if "start" not in out:
        m = SINGLE_DATE_RE.search(text)
        if m:
            out["end"] = normalize_date(m.group(0))
    return out


def skill_fields(text: str) -> dict:
    m = re.match(r"^([^:]{2,40}):\s*(.+)$", text)
    if not m:
        m = re.match(r"^([^:,;|]{2,40}?)\s+[-–—]\s+(.+[,;].*)$", text)  # "Label - a, b, c"
    if not m:
        return {"items": [x.strip() for x in re.split(r"[,;|·]", text) if x.strip()]}
    return {"label": m.group(1).strip(),
            "items": [x.strip() for x in re.split(r"[,;|·]", m.group(2)) if x.strip()]}


def looks_like_name(text: str) -> bool:
    t = text.strip()
    return (0 < len(t.split()) <= 5 and not re.search(r"[\d@:/|]", t)
            and t.lower() not in TITLE_WORDS and any(c.isalpha() for c in t))


def is_divider(text: str) -> bool:
    """Five or more rule characters and nothing else, e.g. a typed row of underscores."""
    t = re.sub(r"\s", "", text)
    return len(t) >= 5 and all(c in DIVIDER_CHARS for c in t)


# ------------------------------------------------------------- role block parsing

@functools.lru_cache(maxsize=None)
def _lexicon(name: str):
    """Compiled word-boundary pattern for scripts/lexicon/<name>, or None if the file is
    missing or empty (then nothing is classified and roles come out low confidence)."""
    path = LEXICON_DIR / name
    try:
        raw = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    words = sorted({w.strip().lower() for w in raw if w.strip() and not w.lstrip().startswith("#")},
                   key=len, reverse=True)
    if not words:
        return None
    alt = "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in words)
    return re.compile(r"(?<![\w])(?:" + alt + r")(?![\w])", re.IGNORECASE)


def _last_end(pat, text: str) -> int:
    if pat is None:
        return -1
    end = -1
    for m in pat.finditer(text):
        end = max(end, m.end())
    return end


def classify_part(text: str) -> str | None:
    """'title', 'employer' or None. When both kinds of word appear, the later one wins:
    the last word of a phrase is its head ("Bank Manager" is a title, "Sales Partners" an employer)."""
    t = _last_end(_lexicon("role_words.txt"), text)
    e = _last_end(_lexicon("employer_words.txt"), text)
    if t < 0 and e < 0:
        return None
    return "title" if t > e else "employer"


def _split_dash(s: str) -> list[str]:
    return [p.strip() for p in re.split(r"\s+[—–-]\s+", s, maxsplit=1)]


def _employer_location(s: str) -> tuple[str, str | None]:
    """'Northgate Foods Ltd, Leeds' -> ('Northgate Foods Ltd', 'Leeds'). Company suffixes
    after a comma ('Acme, Inc., Leeds') stay with the name."""
    segs = [x.strip() for x in s.split(",") if x.strip()]
    if len(segs) < 2:
        return s.strip(), None
    emp = segs[0]
    i = 1
    while i < len(segs) and classify_part(segs[i]) == "employer" and len(segs[i].split()) <= 2:
        emp += ", " + segs[i]
        i += 1
    loc = ", ".join(segs[i:]) or None
    return emp, loc


def _join(*parts: str | None) -> str | None:
    return ", ".join(p for p in parts if p) or None


def _parse_unit(text: str) -> dict:
    """Read one line (date range already removed) into title / employer / location.
    'unknown' holds text that could not be placed; 'guess' marks a positional guess."""
    u: dict = {"text": text, "title": None, "employer": None, "location": None,
               "unknown": None, "guess": False, "pipe": False}
    text = ENUM_PREFIX_RE.sub("", text, count=1)  # "IV. ", "3.3. ", "2) "
    lab = LABEL_PREFIX_RE.match(text)
    if lab:  # "Position: Product Manager", "Company: Acme Ltd"
        word = lab.group("lab").lower()
        key = "title" if word in ("designation", "position", "job title", "job role", "role", "title") else "employer"
        u[key] = lab.group("rest").strip(" ,;")
        return u
    parts = [p.strip(" ,;:") for p in re.split(r"\s*\|\s*", text) if p.strip(" ,;:|")]
    if not parts:
        return u
    head, rest = parts[0], parts[1:]
    u["pipe"] = bool(rest)
    loc_rest = ", ".join(rest) or None
    dashed = _split_dash(head)
    if len(dashed) == 2:
        a, b = dashed
        ca, cb = classify_part(a), classify_part(b)
        if (ca == "employer" and cb != "employer") or (cb == "title" and ca != "title"):
            u["employer"], u["title"] = a, b
            u["guess"] = not (ca == "employer" or cb == "title")
        else:
            u["title"], u["employer"] = a, b
            u["guess"] = not (ca == "title" or cb == "employer")
        emp, loc = _employer_location(u["employer"])
        u["employer"], u["location"] = emp, _join(loc, loc_rest)
        return u
    segs = [x.strip() for x in head.split(",") if x.strip()]
    if len(segs) >= 2:
        a, b, more = segs[0], segs[1], segs[2:]
        ca, cb = classify_part(a), classify_part(b)
        if ca == "title":
            u["title"], u["employer"], u["location"] = a, b, _join(*more)
        elif ca == "employer":
            u["employer"] = a
            if cb == "title":
                u["title"], u["location"] = b, _join(*more)
            else:
                u["location"] = _join(*segs[1:])
        elif cb == "title":
            u["employer"], u["title"], u["location"] = a, b, _join(*more)
        elif cb == "employer":
            u["title"], u["employer"], u["location"] = a, b, _join(*more)
        else:
            u["title"], u["employer"], u["location"] = a, b, _join(*more)
            u["guess"] = True
        u["location"] = _join(u["location"], loc_rest)
        return u
    c = classify_part(head)
    at = re.match(r"^(?P<t>.+?)\s+(?:at|@|for|in|with)\s+(?P<e>\S.*)$", head, re.IGNORECASE)
    if at and not rest and classify_part(at.group("t")) == "title":  # "Accountant at Acme Ltd"
        emp, loc = _employer_location(at.group("e"))
        u["title"], u["employer"], u["location"] = at.group("t"), emp, loc
        return u
    if rest:
        c1 = classify_part(rest[0])
        if c == "title" and c1 == "employer":
            u["title"], u["employer"], u["location"] = head, rest[0], _join(*rest[1:])
        elif c == "title":
            u["title"], u["location"] = head, loc_rest
        else:
            u["employer"], u["location"] = head, loc_rest  # "Employer | Location"
    elif c == "title":
        u["title"] = head
    elif c == "employer":
        u["employer"] = head
    else:
        u["unknown"] = head
    return u


def _remove_date(text: str) -> tuple[str, "re.Match | None"]:
    m = DATE_RANGE_RE.search(text)
    if not m:
        return text, None
    rest = text[:m.start()] + " " + text[m.end():]
    rest = re.sub(r"\(\s*(?:from|since)?\s*\)|\[\s*\]", " ", rest, flags=re.IGNORECASE)
    rest = re.sub(r"\s{2,}", " ", rest)
    rest = re.sub(r"\(\s*\d+\s*(?:years?|yrs?|months?|mos?)[^)]*\)", " ", rest)  # "(1 year 2 months)"
    rest = re.sub(r"(?i)(?:^|\s)(?:time\s+duration|dates?\s+from|working\s+time|tenure|durations?|period|dates?|from)"
                  r"\s*[:\-–]?\s*$", " ", rest)
    rest = re.sub(r"(?i)^\s*(?:from|since|dates?|period|durations?)\s*[:\-–]?\s+", " ", rest)
    return rest.strip(" ,;|:-–—"), m


def parse_role_block(texts: list[str]) -> dict:
    """Work out title, employer, location and dates from 1 to 3 consecutive lines, one of
    which holds a date range, in any order.

    Returns {"fields", "title_line", "date_line", "complete"}. title_line is the index of
    a line that holds only the title (it stays its own fact), else None. fields gets
    confidence "low" when a position or elimination guess was needed."""
    date_idx = next((i for i, t in enumerate(texts) if DATE_RANGE_RE.search(t)), None)
    units: list[dict] = []
    fields: dict = {}
    for i, t in enumerate(texts):
        rest = t
        if i == date_idx:
            rest, m = _remove_date(t)
            fields["start"] = normalize_date(m.group("start"))
            fields["end"] = normalize_date(m.group("end"))
            fields["current"] = fields["end"] is None
        u = _parse_unit(rest)
        u["idx"] = i
        u["is_date_line"] = i == date_idx
        units.append(u)
    got: dict[str, str | None] = {"title": None, "employer": None, "location": None}
    owner: dict[str, dict] = {}
    guess = False
    for u in units:
        for key in got:
            if u[key] and got[key] is None:
                got[key], owner[key] = u[key], u
        guess = guess or (u["guess"] and bool(u["title"] or u["employer"]))
    unknown = [u for u in units if u["unknown"]]
    if got["title"] is None and got["employer"] is not None and unknown:
        got["title"], guess = unknown.pop(0)["unknown"], True
    elif got["employer"] is None and got["title"] is not None and unknown:
        got["employer"], guess = unknown.pop(0)["unknown"], True
    elif got["title"] is None and got["employer"] is None and unknown:
        # nothing recognised: a line with a "|" is the employer; otherwise the first line is the title
        piped = [u for u in unknown if u["pipe"]]
        if piped:
            got["employer"] = piped[0]["unknown"]
            unknown.remove(piped[0])
        if unknown:
            if got["employer"] is None and len(unknown) > 1:
                got["title"], got["employer"] = unknown[0]["unknown"], unknown[1]["unknown"]
                unknown = unknown[2:]
            else:
                got["title"] = unknown.pop(0)["unknown"]
        guess = True
    if unknown and got["location"] is None:
        got["location"] = unknown[0]["unknown"]
    if got["title"] is None or got["employer"] is None:
        guess = True
    # a title that sits alone on its own non-date line stays its own fact
    title_line = None
    tu = owner.get("title")
    if tu is not None and not tu["is_date_line"] and not tu["employer"] and not tu["location"]:
        others = [u for u in units if u is not tu and (u["text"] or u["is_date_line"])]
        if others and tu["title"] == got["title"]:
            title_line = tu["idx"]
    out = {"title": got["title"] or "", "employer": got["employer"] or "",
           "location": got["location"] or "", **fields}
    if guess:
        out["confidence"] = "low"
    return {"fields": out, "title_line": title_line, "date_line": date_idx,
            "complete": bool(got["title"] and got["employer"])}


def _header_like(text: str, has_date: bool) -> bool:
    if text[:1].islower() or re.fullmatch(r"(?i)(?:page\s*)?\d{1,3}(?:\s*(?:/|of)\s*\d{1,3})?", text.strip()):
        return False  # a wrapped sentence or a page number, not a job header
    if has_date:
        rest, _ = _remove_date(text)
        return len(rest.split()) <= 14
    return 0 < len(text.split()) <= 12 and not text.endswith((".", "!", "?"))


def build_ledger(lines: list[Line], source_kind: str) -> tuple[list[dict], list[dict], list[str]]:
    facts: list[dict] = []
    sections: list[dict] = []
    warnings: list[str] = []
    seq = 0
    cur_section: dict | None = None
    cur_kind: str | None = None  # None = preamble
    parent: str | None = None
    name_done = False
    name_found = False
    last_fact: dict | None = None
    last_line: Line | None = None
    prev_blank = True

    # Active lines: not blank, not a divider rule, something left after cleaning. gaps[i] is
    # True when a blank or divider line sits between active line i and the one before it.
    act: list[Line] = []
    texts: list[str] = []
    gaps: list[bool] = []
    gap = True
    for ln in lines:
        if not ln.text.strip() or is_divider(ln.text):
            gap = True
            continue
        t = clean_fact_text(ln)
        if not t:
            continue
        dm = DATE_RANGE_RE.search(t) if not (ln.is_list or ln.heading) else None
        gm = INLINE_GLYPH_RE.search(t, dm.end()) if dm else None
        if gm and len(t[:gm.start()].split()) <= 14 and t[gm.end():].strip():
            # "06/2014 - 08/2015 •Manage the network": the header and the first bullet share a
            # line. Both facts point at that line; the header part is a role header, the rest a bullet.
            head = Line(t[:gm.start()].strip(), ln.page, False, None, ln.x0, ln.origin)
            tail = Line(t[gm.start():].strip(), ln.page, True, None, ln.x0, ln.origin)
            head.no = tail.no = ln.no
            for part, ptxt in ((head, head.text), (tail, clean_fact_text(tail))):
                act.append(part)
                texts.append(ptxt)
                gaps.append(gap)
                gap = False
            continue
        act.append(ln)
        texts.append(t)
        gaps.append(gap)
        gap = False

    def add(kind: str, line: Line, text: str, fields: dict | None = None, par: str | None = None) -> dict:
        nonlocal seq
        seq += 1
        fields = dict(fields or {})
        if line.origin != "body":
            fields["origin"] = line.origin
        fact = {"id": f"F{seq:03d}", "kind": kind, "text": text, "line": line.no, "page": line.page,
                "parent": par, "fields": fields, "provenance": "cv", "confirmed": True}
        facts.append(fact)
        return fact

    def merge(fact: dict, line: Line, text: str, sep: str = " ") -> None:
        fact["text"] = (fact["text"] + sep + text).strip()
        fact["fields"]["end_line"] = line.no
        if fact["kind"] == "skill":
            fact["fields"].update(skill_fields(fact["text"]))

    def is_continuation(line: Line, text: str) -> bool:
        if last_fact is None or last_line is None or line.is_list or line.heading:
            return False
        if source_kind == "markdown":
            return (not prev_blank and last_fact["kind"] in ("summary", "other", "headline")
                    and not last_line.is_list and not last_line.heading and not text.startswith("**"))
        if source_kind not in ("pdf", "text") or last_line.page != line.page:
            return False
        if DATE_RANGE_RE.search(text) or is_contact_line(text):
            return False
        prev = last_line.text.rstrip()
        if last_fact["kind"] == "bullet":
            if line.x0 is not None and last_line.x0 is not None:
                return line.x0 > last_line.x0 + 3
            return text[:1].islower() or not re.search(r"[.!?]$", prev)
        if last_fact["kind"] in ("summary", "skill", "other", "certification", "project", "publication",
                                 "award", "interest", "language"):
            return text[:1].islower() or bool(re.search(r"[,;&/\-]$|\b(?:and|or|of|in|to|with)$", prev)) or (
                last_fact["kind"] == "summary" and not re.search(r"[.!?]$", prev))
        return False

    def has_date(j: int) -> bool:
        return bool(DATE_RANGE_RE.search(texts[j]))

    def dated_list_line(j: int) -> bool:
        """A bulleted line that starts with its date range ("- 3/2018 – 4/2018 freelance for Acme")
        is a job entry, not an achievement."""
        m = DATE_RANGE_RE.search(texts[j])
        if not (m and act[j].is_list):
            return False
        if m.start() <= 8:
            return True
        # date at the end: "IT Specialist (From September 2022 to December 2022)"; only when what
        # is left looks like a job title or an employer, so "Built a dashboard (2021 - 2022)" stays a bullet
        before = texts[j][:m.start()].strip(" (-,:").split(" (")[0]
        return len(texts[j][m.end():].strip(" ).,")) <= 3 and classify_part(before) is not None

    def block_candidate(j: int) -> bool:
        ln = act[j]
        if ln.heading or section_kind(ln.text) or is_contact_line(texts[j]):
            return False
        return not ln.is_list or dated_list_line(j)

    def plan_block(i: int) -> dict | None:
        """Find a job header made of up to three lines starting at active line i, with one
        date-range line anywhere in it. Returns {"members": [indexes], "parsed": ...} or None."""
        if not block_candidate(i) or not _header_like(texts[i], has_date(i)):
            return None
        w = [i]
        for j in range(i + 1, min(i + 3, len(act))):
            if gaps[j] or not block_candidate(j) or not _header_like(texts[j], has_date(j)):
                break
            w.append(j)
        dpos = [p for p, j in enumerate(w) if has_date(j)]
        if not dpos:
            return None
        d = dpos[0]
        members = w[:d + 1]
        if d == 2 and parse_role_block([texts[j] for j in w[1:3]])["complete"]:
            return None  # the first line is something else; the block starts on the next line
        parsed = parse_role_block([texts[j] for j in members])
        if not parsed["complete"] and len(members) < 3 and d + 1 < len(w):
            j = w[d + 1]
            starts_next = (j + 1 < len(act) and not gaps[j + 1] and has_date(j + 1)
                           and (not act[j + 1].is_list or dated_list_line(j + 1)))
            if (not has_date(j) and len(texts[j].split()) <= 8 and not texts[j][:1].islower()
                    and not starts_next):
                members.append(j)
                parsed = parse_role_block([texts[j2] for j2 in members])
        return {"members": members, "parsed": parsed}

    def build_block(plan: dict) -> dict:
        """Add the role fact (and a title fact when the title has its own line)."""
        members = [act[j] for j in plan["members"]]
        parsed = plan["parsed"]
        tl = parsed["title_line"]
        role_idx = [k for k in range(len(members)) if k != tl]
        text = ""
        for k in role_idx:
            piece = texts[plan["members"][k]]
            text = piece if not text else text + (" | " if " | " in text else ", ") + piece
        role = None
        title_fact = None
        for k, ln in enumerate(members):
            if k == tl:
                title_fact = add("title", ln, texts[plan["members"][k]])
            elif role is None:
                fields = dict(parsed["fields"])
                if len(role_idx) > 1:
                    fields["end_line"] = members[role_idx[-1]].no
                role = add("role", ln, text, fields)
        if title_fact is not None:
            title_fact["parent"] = role["id"]
        return role

    consumed: set[int] = set()
    for i, line in enumerate(act):
        if i in consumed:
            continue
        raw = line.text
        text = texts[i]
        prev_blank = gaps[i]
        kind_of_heading = None
        if line.heading in (1,):
            kind_of_heading = None
        elif line.heading == 2 or (line.heading is None and not line.is_list):
            kind_of_heading = section_kind(raw)
        if (kind_of_heading == "skill" and cur_kind == "skill" and line.heading is None
                and LABEL_END_RE.match(text) and i + 1 < len(act) and not gaps[i + 1]):
            kind_of_heading = None  # "Tools:" inside a skills table is a label, not a new section
        if line.heading == 2 and kind_of_heading is None:
            kind_of_heading = "other"
        if kind_of_heading:
            if cur_section:
                cur_section["end_line"] = last_line.no if last_line else line.no
            cur_section = {"name": text, "kind": kind_of_heading, "start_line": line.no, "end_line": line.no}
            sections.append(cur_section)
            cur_kind, parent = kind_of_heading, None
            last_fact, last_line = None, line
            continue

        md_h3 = source_kind == "markdown" and (line.heading or 0) >= 3
        fact: dict | None = None
        nm = None
        if not name_found:
            m_nm = CV_TITLE_NAME_RE.match(text) if cur_kind is None else None
            m_nm = m_nm or NAME_LABEL_RE.match(text)
            if m_nm:
                cand = re.sub(r"\s*\((?:male|female|[mf])\)\s*$", "", m_nm.group("n").strip(), flags=re.IGNORECASE)
                if looks_like_name(cand):
                    nm = cand
        if nm:
            name_done = name_found = True
            fact = add("contact", line, text, {"name": nm})
        elif not name_done and cur_kind is None:
            name_done = True
            if line.heading == 1 or looks_like_name(text):
                fact = add("contact", line, text, {"name": text})
                name_found = True
            elif text.lower() in TITLE_WORDS:
                fact = add("other", line, text)
                name_done = False
            elif is_contact_line(text):
                fact = add("contact", line, text)
            else:
                warnings.append(f"line {line.no}: the first line does not look like a name")
        if (fact is None and is_continuation(line, text)
                and not (cur_kind in (None, "experience") and not text[:1].islower() and plan_block(i))):
            merge(last_fact, line, text)
            last_line = line
            continue
        if fact is None and is_contact_line(text):
            fact = add("contact", line, text)
        if fact is None:
            k = cur_kind
            if k in (None, "experience"):
                plan = None if (md_h3 or (line.is_list and not dated_list_line(i))) else plan_block(i)
                if md_h3 and (k == "experience" or DATE_RANGE_RE.search(text)):
                    fact = add("role", line, text, role_fields(text, True))
                    parent = fact["id"]
                elif plan:
                    fact = build_block(plan)
                    parent = fact["id"]
                    consumed.update(plan["members"])
                    last_fact, last_line = fact, act[plan["members"][-1]]
                    continue
                elif line.is_list:
                    fact = add("bullet", line, text, par=parent)
                elif k is None:
                    fact = add("headline" if len(text.split()) <= 12 else "summary", line, text)
                else:
                    fact = add("other", line, text, par=parent)
            elif k == "education":
                if line.is_list and parent:
                    fact = add("bullet", line, text, par=parent)
                else:
                    fact = add("education", line, text, education_fields(text, md_h3))
                    parent = fact["id"]
            elif k == "project":
                if line.is_list and parent:
                    fact = add("bullet", line, text, par=parent)
                else:
                    fact = add("project", line, text)
                    parent = fact["id"]
            elif k == "achievements":
                fact = add("bullet", line, text)
            elif k in LIST_KINDS:
                lm = LABEL_END_RE.match(text) if k == "skill" else None
                if (lm and len(lm.group("label").split()) <= 6 and i + 1 < len(act) and not gaps[i + 1]
                        and not act[i + 1].heading and not section_kind(act[i + 1].text)
                        and not LABEL_END_RE.match(texts[i + 1]) and len(texts[i + 1].split()) <= 40):
                    # a skills-table cell: "Web Development -" then "React, Vite, ..." on the next line
                    label, end = lm.group("label").strip(), lm.group("end")
                    joined = f"{label}: {texts[i + 1]}" if end == ":" else f"{label} {end} {texts[i + 1]}"
                    fact = add("skill", line, joined, skill_fields(joined))
                    fact["fields"]["end_line"] = act[i + 1].no
                    consumed.add(i + 1)
                    last_fact, last_line = fact, act[i + 1]
                    continue
                fact = add(k, line, text, skill_fields(text) if k == "skill" else None)
            elif k == "summary":
                fact = add("summary", line, text)
            else:
                fact = add("bullet" if line.is_list else "other", line, text)
        last_fact, last_line = fact, line

    if cur_section and last_line:
        cur_section["end_line"] = last_line.no
    return facts, sections, warnings


# --------------------------------------------------------------------- quality

def quality_report(lines: list[Line], facts: list[dict], sections: list[dict], meta: dict,
                   pages: int | None, source_kind: str) -> dict:
    nonempty = [ln for ln in lines if ln.text.strip() and not is_divider(ln.text)]
    all_text = "\n".join(ln.text for ln in nonempty)
    weird = len(re.findall(r"\(cid:\d+\)", all_text)) * 6 + all_text.count("�") + len(
        re.findall(r"[-]", re.sub(r"(?m)^[]", "", all_text)))
    alpha = sum(c.isalpha() for c in all_text)
    garbage = bool(all_text) and (weird / max(len(all_text), 1) > 0.02 or alpha / max(len(all_text), 1) < 0.45)

    run, short_in_runs = 0, 0
    for ln in nonempty + [Line("x" * 80)]:
        t = GLYPH_RE.sub("", ln.text)
        if len(t) < 25:
            run += 1
        else:
            if run >= 5:
                short_in_runs += run
            run = 0
    short_ratio = short_in_runs / max(len(nonempty), 1)
    right_ratio = meta.get("right_column_lines", 0) / max(len(nonempty), 1) if source_kind == "pdf" else 0.0
    split_ratio = meta.get("split_lines", 0) / max(len(nonempty), 1) if source_kind == "pdf" else 0.0
    columns = source_kind == "pdf" and (right_ratio >= 0.2 or short_ratio >= 0.3 or split_ratio >= 0.15)

    contact_body = any(f["kind"] == "contact" and f["fields"].get("origin", "body") == "body"
                       and (EMAIL_RE.search(f["text"]) or find_phones(f["text"])) for f in facts)
    first = facts[0] if facts else None
    kinds: dict[str, int] = {}
    for f in facts:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    warnings = []
    if not contact_body:
        warnings.append("no email or phone number found in the body text; put contact details in the body, "
                        "not a header, footer or text box")
    if columns:
        warnings.append(f"possible multi-column layout: {right_ratio:.0%} of lines start mid-page and "
                        f"{short_ratio:.0%} sit in runs of short lines, and {split_ratio:.0%} look like two columns "
                        f"read across as one line; check the reading order in --text")
    if not any(s["kind"] == "experience" for s in sections):
        warnings.append("no Experience section heading recognised")
    if not kinds.get("role"):
        warnings.append("no job entries with date ranges found")
    if not nonempty:
        warnings.append("no text at all: probably a scanned image; OCR is not supported")
    return {
        "source_type": source_kind,
        "page_count": pages,
        "line_count": len(nonempty),
        "fact_count": len(facts),
        "facts_by_kind": kinds,
        "sections": [s["name"] for s in sections],
        "reading_order": {
            "name_first": any(f["kind"] == "contact" and "name" in f["fields"] for f in facts[:2]),
            "contact_in_body": contact_body,
            "columns_suspected": columns,
            "right_column_line_share": round(right_ratio, 2),
            "short_line_run_share": round(short_ratio, 2),
            "side_by_side_line_share": round(split_ratio, 2),
        },
        "garbage_suspected": garbage,
        "warnings": warnings,
    }


# ------------------------------------------------------------------------- CLI

def extract(path: Path) -> dict:
    """Run extraction; return {"lines", "facts", "sections", "report", "extractor"}."""
    ext = path.suffix.lower()
    warnings: list[str] = []
    meta: dict = {}
    pages: int | None = None
    if ext == ".pdf":
        lines, meta, warnings, extractor, pages = read_pdf(path)
        kind = "pdf"
    elif ext == ".docx":
        lines, meta, warnings, pages = read_docx_lines(path)
        extractor, kind = "python-docx", "docx"
    elif ext in (".md", ".markdown"):
        text, warnings = read_text_file(path)
        lines, extractor, kind = read_markdown(path, text), "markdown", "markdown"
    elif ext == ".txt":
        text, warnings = read_text_file(path)
        lines = [Line(_display(t)) for t in text.splitlines()]
        for ln in lines:
            ln.is_list = bool(GLYPH_RE.match(ln.text))
        extractor, kind = "text", "text"
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic"):
        raise ValueError(f"{ext} is a picture, and this skill cannot read text from pictures (no OCR). "
                         f"Ask for the PDF or DOCX, or paste the text")
    elif ext == ".doc":
        raise ValueError("old .doc files are not supported; save it as .docx or PDF first")
    else:
        raise ValueError(f"unsupported file type {ext!r}; use PDF, DOCX or markdown")
    for i, ln in enumerate(lines, start=1):
        ln.no = i
    facts, sections, cls_warnings = build_ledger(lines, kind)
    report = quality_report(lines, facts, sections, meta, pages, kind)
    if kind == "docx":
        report["page_count_estimated"] = True
    report["warnings"] = warnings + cls_warnings + report["warnings"]
    return {"lines": lines, "facts": facts, "sections": sections, "report": report, "extractor": extractor}


def _source_path_for_ledger(path: Path) -> str:
    try:
        return path.resolve().relative_to(user_dir().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="cv_extract.py")
    p.add_argument("file", help="CV file: .pdf, .docx, .md or .txt")
    p.add_argument("--out", help="write ledger.json here")
    p.add_argument("--text", help="write the numbered-line plain text here")
    p.add_argument("--force", action="store_true", help="overwrite an existing --out ledger (backs it up first)")
    p.add_argument("--fragment", action="store_true",
                   help="the input is part of a CV (e.g. one pasted role): no minimum line count")
    p.add_argument("--min-lines", type=int, default=10, metavar="N",
                   help="minimum non-empty lines for a trustworthy extraction (default 10)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args(argv)
    if a.min_lines < 1:
        p.error("--min-lines must be at least 1")

    path = Path(a.file)
    if not path.is_file():
        die(f"file not found: {path}")
    out = Path(a.out) if a.out else None
    if out and out.exists() and not a.force:
        die(f"{out} already exists. Fact IDs must stay stable and it may hold facts the user supplied. "
            f"Write to a new path, or pass --force to replace it (a backup is kept).")
    try:
        res = extract(path)
    except ValueError as exc:
        die(str(exc))
    lines, report = res["lines"], res["report"]
    min_lines = 1 if a.fragment else a.min_lines
    usable = report["line_count"] > 0 and report["fact_count"] > 0
    ok = usable and report["line_count"] >= min_lines and not report["garbage_suspected"]
    fragment = ok and (a.fragment or report["line_count"] < 10)
    report["fragment"] = fragment
    if fragment:
        expected = ("no email or phone number found", "no Experience section heading", "no job entries")
        report["warnings"] = [w for w in report["warnings"] if not w.startswith(expected)]
        report["warnings"].append("fragment: this is part of a CV, so the audit is partial; missing contact "
                                  "details, sections or roles are not reported")
    if not usable:
        report["warnings"].append("no usable text extracted")
    elif report["line_count"] < min_lines:
        report["warnings"].append(f"only {report['line_count']} lines extracted (need at least {min_lines}); "
                                  f"for a pasted part of a CV, rerun with --fragment")
    if report["garbage_suspected"]:
        report["warnings"].append("the text looks garbled (unmapped font glyphs or non-text); try another export")

    source = {"file": _source_path_for_ledger(path), "sha256": sha256_file(path),
              "extracted_at": now_iso(), "extractor": res["extractor"]}
    if fragment:
        source["fragment"] = True
    ledger = new_ledger(source)
    ledger["sections"] = [{"name": s["name"], "kind": s["kind"], "start_line": s["start_line"],
                           "end_line": s["end_line"]} for s in res["sections"]]
    ledger["facts"] = res["facts"]

    text_path = None
    if a.text:
        text_out = "\n".join(ln.text for ln in lines) + "\n"
        atomic_write_text(Path(a.text), text_out)
        text_path = str(Path(a.text))
    ledger_path = None
    if out and ok:
        if out.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = out.with_name(f"{out.stem}.bak-{stamp}{out.suffix}")
            shutil.copy2(out, backup)
            report["warnings"].append(f"previous ledger backed up to {backup}")
        save_ledger(ledger, out)
        ledger_path = str(out)

    if a.json:
        emit_json({"ok": ok, "report": report, "ledger_path": ledger_path, "text_path": text_path,
                   "ledger": ledger})
    else:
        ro = report["reading_order"]
        label = ("OK (fragment)" if fragment else "OK") if ok else "POOR"
        print(f"{label}  {path.name}: {report['source_type']}, pages {report['page_count']}, "
              f"{report['line_count']} lines, {report['fact_count']} facts")
        print(f"  sections: {', '.join(report['sections']) or '(none recognised)'}")
        print(f"  facts by kind: {report['facts_by_kind']}")
        print(f"  name first: {ro['name_first']} | contact in body: {ro['contact_in_body']} | "
              f"columns suspected: {ro['columns_suspected']}")
        for w in report["warnings"]:
            print(f"  warning: {w}")
        if ledger_path:
            print(f"  ledger written to {ledger_path}")
        elif out:
            print("  ledger NOT written: extraction too poor to trust")
        if text_path:
            print(f"  text written to {text_path} (line numbers match the ledger)")
    return EXIT_OK if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
