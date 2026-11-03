"""Input readers: .docx (paragraphs and tables), .pdf, .txt/.md, and URLs.

Each reader returns a list of Blocks: a chunk of text plus a human-readable location
("para 12", "table 1, row 3", "page 2") so findings point back into the draft.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Union
from urllib.parse import urlparse


@dataclass
class Block:
    text: str
    location: str

    def to_dict(self):
        return asdict(self)


class ReaderError(Exception):
    pass


def read_docx(path: Union[str, Path]) -> list[Block]:
    try:
        import docx  # python-docx
    except ImportError as e:  # pragma: no cover
        raise ReaderError("python-docx is required to read .docx files: pip install python-docx") from e
    from docx.oxml.ns import qn

    d = docx.Document(path if hasattr(path, "read") else str(path))
    blocks: list[Block] = []
    para_no = 0
    table_no = 0
    # walk the body in document order so tables appear where they are in the draft
    for child in d.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = "".join(t.text or "" for t in child.iter(qn("w:t"))).strip()
            if text:
                para_no += 1
                blocks.append(Block(text, f"para {para_no}"))
        elif child.tag == qn("w:tbl"):
            table_no += 1
            table = docx.table.Table(child, d)
            rows = table.rows
            header = None
            for r_i, row in enumerate(rows, start=1):
                cells = []
                for c in row.cells:
                    t = c.text.strip()
                    if not cells or cells[-1] != t:  # merged cells repeat
                        cells.append(t)
                if r_i == 1:
                    header = cells
                    line = " | ".join(cells)
                elif header and len(header) == len(cells):
                    # carry column headers into each row so "2024-25" / "%" headers give context
                    line = " | ".join(f"{h}: {c}" if h and h != c else c for h, c in zip(header, cells))
                else:
                    line = " | ".join(cells)
                if line.strip(" |"):
                    blocks.append(Block(line, f"table {table_no}, row {r_i}"))
    return blocks


def read_pdf(path: Union[str, Path]) -> list[Block]:
    """v0.5.3: reads each page line by line. Two-column pages are read one column at a time (they used to be read
    straight across, which glued half-sentences from both columns together); running headers and footers that repeat
    on many pages are dropped; a short line with no closing punctuation (a heading, a contents entry) is its own
    block, so it is never glued onto the sentence that follows."""
    blocks: list[Block] = []
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None
    if pdfplumber is not None:
        with pdfplumber.open(path if hasattr(path, "read") else str(path)) as pdf:
            pages = [_page_lines(page) for page in pdf.pages]
        repeated = _running_lines(pages)
        for i, lines in enumerate(pages, start=1):
            lines = [ln for ln in lines if _line_key(ln) not in repeated and not PAGE_NO_RX.fullmatch(ln.strip())]
            for para in _paragraphs_from_lines(lines):
                blocks.append(Block(para, f"page {i}"))
        return blocks
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise ReaderError("pdfplumber or pypdf is required to read PDFs") from e
    if hasattr(path, "seek"):
        path.seek(0)
    reader = PdfReader(path if hasattr(path, "read") else str(path))
    for i, page in enumerate(reader.pages, start=1):
        for para in _paragraphs(page.extract_text() or ""):
            blocks.append(Block(para, f"page {i}"))
    return blocks


PAGE_NO_RX = re.compile(r"(?:page\s*)?[-–(]?\s*\d{1,4}\s*[-–)]?|[ivxlc]{1,6}", re.I)
LIST_START_RX = re.compile(r"^\s*(?:[•▪●■◦\-–]\s|\(?[ivx]{1,5}\)\s|\(?[a-z]\)\s|\d{1,2}(?:\.\d{1,2}){0,3}\.?\s+[A-Z(]|"
                           r"[ivx]{1,5}\.\s|[A-Z]\.\s)")


def _page_lines(page) -> list[str]:
    """Text lines of one page; a two-column page is read left column first, then right column."""
    try:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    except Exception:
        words = []
    width = float(page.width or 0)
    split = _column_split(words, width) if words and width else None
    if split is None:
        return [ln for ln in (page.extract_text() or "").replace("\r", "").split("\n")]
    out = []
    for box in ((0, 0, split, page.height), (split, 0, width, page.height)):
        try:
            txt = page.crop(box).extract_text() or ""
        except Exception:
            txt = ""
        out += txt.replace("\r", "").split("\n")
        out.append("")          # a column end is a paragraph end
    return out


def _column_split(words: list, width: float):
    """x position of the gutter of a two-column page, or None. A gutter is a vertical strip in the middle third of
    the page that no word crosses, with enough text on both sides on the same lines (so a table or a single
    centred column is not split)."""
    if len(words) < 80:
        return None
    lo, hi = width * 0.3, width * 0.7
    step = width / 200.0
    best = None
    x = lo
    while x <= hi:
        g = width * 0.01            # a gutter is a strip at least 2% of the page wide, not a gap between two words
        crossing = sum(1 for w in words if w["x0"] < x + g and w["x1"] > x - g)
        if crossing <= max(1, len(words) // 200):
            left = sum(1 for w in words if w["x1"] <= x)
            right = sum(1 for w in words if w["x0"] >= x)
            if left >= 0.25 * len(words) and right >= 0.25 * len(words):
                # the strip must be a real gap: a line on the left and one on the right share the same baseline
                lt = {round(w["top"]) for w in words if w["x1"] <= x and w["x1"] > x - width * 0.2}
                rt = sorted({round(w["top"]) for w in words if w["x0"] >= x and w["x0"] < x + width * 0.2})
                shared = sum(1 for t in lt if any(abs(t - r) <= 3 for r in rt))
                if shared >= 5 and (best is None or crossing < best[1]):
                    best = (x, crossing)
        x += step
    return best[0] if best else None


def _line_key(line: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.strip().lower()))


def _running_lines(pages: list) -> set:
    """Lines (digits ignored) that appear among the first or last three lines of at least 3 pages and 30% of pages:
    running headers and footers such as 'STATE WATER POLICY (2019)  7' or 'Orissa Review * September-October 2007'."""
    if len(pages) < 3:
        return set()
    seen: dict = {}
    for lines in pages:
        ls = [ln for ln in lines if ln.strip()]
        for ln in set(ls[:3] + ls[-3:]):
            k = _line_key(ln)
            if len(k) >= 4:
                seen[k] = seen.get(k, 0) + 1
    need = max(3, int(0.3 * len(pages) + 0.999))
    return {k for k, n in seen.items() if n >= need}


def _paragraphs_from_lines(lines: list) -> list[str]:
    """Join wrapped lines into paragraphs. A paragraph ends at a blank line, before a list item or numbered heading,
    and after a short line without closing punctuation (a heading or a contents entry)."""
    widths = [len(ln.strip()) for ln in lines if ln.strip()]
    full = sorted(widths)[int(len(widths) * 0.8)] if widths else 0
    out, cur = [], []

    def flush():
        if cur:
            p = " ".join(cur)
            p = re.sub(r"\s+", " ", p).strip()
            if p:
                out.append(p)
            cur.clear()

    for ln in lines:
        t = ln.strip()
        if not t:
            flush()
            continue
        if cur and LIST_START_RX.match(t):
            flush()
        if cur and cur[-1].endswith("-") and not cur[-1].endswith(" -"):
            cur[-1] = cur[-1][:-1] + t       # word broken across lines
        else:
            cur.append(t)
        short = full and len(t) < 0.6 * full
        if short and not re.search(r"[,;(\-–]$|\b(?:and|or|of|the|to|in|for|with|by|a|an)$", t, re.I):
            flush()                          # a short line ends a paragraph or is a heading
    flush()
    return out


def _paragraphs(text: str) -> list[str]:
    # PDF text (pypdf fallback): join wrapped lines, split on blank lines or bullet starts
    text = text.replace("\r", "")
    parts = re.split(r"\n\s*\n|\n(?=\s*[•▪●\-–]\s)", text)
    out = []
    for p in parts:
        p = re.sub(r"(\w)-\n(\w)", r"\1\2", p)
        p = re.sub(r"\s*\n\s*", " ", p).strip()
        if p:
            out.append(p)
    return out


def read_text(text: str, label: str = "para") -> list[Block]:
    blocks = []
    paras = re.split(r"\n\s*\n", text.replace("\r", ""))
    n = 0
    for p in paras:
        lines = [ln.strip() for ln in p.split("\n") if ln.strip()]
        if not lines:
            continue
        # markdown tables / bullet lists: one block per line
        if all(ln.startswith(("|", "-", "*", "+")) or re.match(r"^\d+[.)]\s", ln) for ln in lines):
            for ln in lines:
                if re.fullmatch(r"\|?[\s:\-|]+\|?", ln):
                    continue
                n += 1
                blocks.append(Block(ln.strip("|-*+ ").replace("|", " | "), f"{label} {n}"))
        else:
            n += 1
            blocks.append(Block(" ".join(lines).lstrip("# ").strip(), f"{label} {n}"))
    return blocks


def read_file(path: Union[str, Path]) -> list[Block]:
    p = Path(path)
    if not p.exists():
        raise ReaderError(f"File not found: {p}")
    ext = p.suffix.lower()
    if ext == ".docx":
        return read_docx(p)
    if ext == ".pdf":
        return read_pdf(p)
    if ext in (".txt", ".md", ".markdown", ".text", ""):
        return read_text(p.read_text(encoding="utf-8", errors="replace"))
    if ext == ".doc":
        raise ReaderError("Legacy .doc is not supported; save the draft as .docx")
    raise ReaderError(f"Unsupported file type: {ext}")


def read_bytes(data: bytes, suffix: str) -> list[Block]:
    """v0.5.2: read an uploaded document from memory (never written to disk)."""
    import io
    ext = (suffix or "").lower()
    if ext == ".docx":
        try:
            return read_docx(io.BytesIO(data))
        except ReaderError:
            raise
        except Exception as e:
            raise ReaderError(f"could not read the .docx file ({type(e).__name__})") from None
    if ext == ".pdf":
        try:
            return read_pdf(io.BytesIO(data))
        except ReaderError:
            raise
        except Exception as e:
            raise ReaderError(f"could not read the PDF ({type(e).__name__})") from None
    if ext in (".txt", ".md", ".markdown", ".text", ""):
        return read_text(data.decode("utf-8", errors="replace"))
    if ext == ".doc":
        raise ReaderError("Legacy .doc is not supported; save the draft as .docx")
    raise ReaderError(f"Unsupported file type: {ext}")


def read_url(url: str, timeout: float = 15.0, session=None, max_bytes: int = 15 * 2 ** 20) -> tuple[list[Block], dict]:
    """Fetch a web page and return its text blocks (paragraphs, list items, table rows).

    All fetching goes through truthlens.net.fetch_bytes: only public http(s) hosts, redirects followed by
    hand with every hop validated before it is requested, size-capped."""
    from bs4 import BeautifulSoup

    from .net import FetchError, fetch_bytes, make_session

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ReaderError("Only http(s) URLs are supported")
    try:
        content, ctype, final = fetch_bytes(session or make_session(), url, timeout, max_bytes)
    except FetchError as e:
        raise ReaderError(f"Could not fetch {url[:120]}: {e}") from None
    if "pdf" in ctype or url.lower().endswith(".pdf") or content[:5] == b"%PDF-":
        import io        # v0.5.2: read in memory (was a temporary file that was never deleted)
        return read_pdf(io.BytesIO(content)), {"title": url, "domain": parsed.netloc}
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else url
    blocks = []
    n = 0
    for el in soup.find_all(["p", "li", "tr", "h1", "h2", "h3", "blockquote"]):
        if el.name == "tr":
            text = " | ".join(c.get_text(" ", strip=True) for c in el.find_all(["td", "th"]))
        else:
            if el.find_parent(["li", "p", "tr"]) is not None and el.name != "tr":
                continue
            text = el.get_text(" ", strip=True)
        if text and len(text) > 3:
            n += 1
            blocks.append(Block(text, f"block {n}"))
    return blocks, {"title": title, "domain": parsed.netloc}
