"""Official documents: allow-listed fetcher + local searchable index with page-level citations.

* `DocFetcher` downloads HTML pages and PDFs **only** from allow-listed official domains (pib.gov.in,
  *.gov.in, *.nic.in, rbi.org.in, worldbank.org, who.int, un.org, ...; extend in truthlens.toml
  `[docs] allowed_domains`). Files are cached under <cache>/docs/.
* `extract_passages` turns a document into passages with page numbers: PDF text per page plus every
  table row (pdfplumber), HTML paragraphs/list items/table rows (PIB release body when present),
  DOCX paragraphs and tables, plain text.
* `DocIndex` is a SQLite FTS5 index (BM25 ranking, built into Python's sqlite3; no server, no extra
  dependency). `truthlens index ./reports` adds your own folder; `truthlens index --url URL` adds an
  allow-listed page; `truthlens index --pib-rss` adds the current PIB press-release feed.
* `DocsRetriever` searches the index for each claim and returns the best passages with page numbers.

PIB RSS: https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3 (listed on https://www.pib.gov.in/ViewRss.aspx).
The feed has titles and links only (no dates or text), so each linked release is fetched and indexed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import re
import sqlite3
import threading
from pathlib import Path
from typing import Iterable, Optional

from ..config import Config, redact
from ..model import Claim, Evidence
from ..net import FetchError, domain_allowed, fetch_bytes, host_of, make_session
from .base import Retriever, best_window, contains_number, norm_ws, terms

# English press-release feed. `Lang=1&Regid=3` (the link on PIB's RSS page) is served in Hindi from some
# networks; `reg=3&lang=1` (the query PIB's own region/language switcher uses) returned English on 1 Nov 2026.
PIB_RSS = "https://pib.gov.in/RssMain.aspx?ModId=6&reg=3&lang=1"
PUBLISHERS = {
    "pib.gov.in": "Press Information Bureau (PIB), Government of India", "mospi.gov.in": "MoSPI (NSO)",
    "rbi.org.in": "Reserve Bank of India", "indiabudget.gov.in": "Ministry of Finance (Union Budget)",
    "worldbank.org": "World Bank", "who.int": "World Health Organization", "un.org": "United Nations",
    "niti.gov.in": "NITI Aayog", "censusindia.gov.in": "Office of the Registrar General, India",
    "data.gov.in": "OGD Platform India", "dhsprogram.com": "IIPS/MoHFW (NFHS) via DHS Program",
    "imf.org": "International Monetary Fund", "unicef.org": "UNICEF",
}
PIB_BODY = "innner-page-main-about-us-content-right-part"
DATE_PATTERNS = [
    (re.compile(r"Posted On:\s*(\d{1,2}) ([A-Z]{3}) (\d{4})"), "%d %b %Y"),
    (re.compile(r"\b(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December),? (\d{4})\b"), "%d %B %Y"),
    (re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}),? (\d{4})\b"), "%B %d %Y"),
]


def publisher_for(url: str) -> str:
    h = host_of(url)
    for d, name in PUBLISHERS.items():
        if h == d or h.endswith("." + d):
            return name
    return h or "local file"


def find_date(text: str) -> Optional[str]:
    head = text[:3000]
    for rx, fmt in DATE_PATTERNS:
        m = rx.search(head)
        if m:
            try:
                return dt.datetime.strptime(" ".join(m.groups()).title(), fmt).date().isoformat()
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------- extraction
def _chunk(text: str, max_len: int = 700) -> list[str]:
    text = norm_ws(text)
    if len(text) <= max_len:
        return [text] if text else []
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(₹“\"])", text)
    out, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) + 1 > max_len:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def extract_pdf(data: bytes) -> tuple[str, list[dict]]:
    import pdfplumber
    passages: list[dict] = []
    title = ""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        meta_title = (pdf.metadata or {}).get("Title") or ""
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if i == 1:
                lines = [ln.strip() for ln in text.splitlines()[:15] if len(ln.strip().split()) >= 3]
                skip = re.compile(r"^(government of india|ministry of|department of|dated|press release|\d)", re.I)
                good = [ln for ln in lines if not skip.match(ln)]
                title = meta_title.strip() or (good[0][:200] if good else (lines[0][:200] if lines else ""))
            from ..readers import _paragraphs
            for para in _paragraphs(text):
                for ch in _chunk(para):
                    passages.append({"text": ch, "page": i, "kind": "text"})
            try:
                for t_i, table in enumerate(page.extract_tables() or [], start=1):
                    header = None
                    for row in table:
                        cells = [norm_ws(c or "") for c in row]
                        if not any(cells):
                            continue
                        if header is None:
                            header = cells
                        line = " | ".join(c for c in cells if c)
                        passages.append({"text": line, "page": i, "kind": f"table {t_i}"})
            except Exception:
                pass
    return title, passages


def extract_html(data: bytes, url: str = "") -> tuple[str, list[dict], Optional[str]]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):  # (ASP.NET pages wrap everything in <form>)
        tag.decompose()
    body = soup.find(class_=PIB_BODY) or soup.find("article") or soup.find("main") or soup.body or soup
    title = ""
    h = body.find(["h1", "h2"]) if hasattr(body, "find") else None
    if h and h.get_text(strip=True):
        title = h.get_text(" ", strip=True)
    elif soup.title:
        title = soup.title.get_text(" ", strip=True)
    full = body.get_text(" ", strip=True)
    date = find_date(full)
    for meta in ("article:published_time", "dc.date", "date"):
        m = soup.find("meta", attrs={"property": meta}) or soup.find("meta", attrs={"name": meta})
        if m and m.get("content"):
            date = date or m["content"][:10]
    passages = []
    seen = set()
    for el in body.find_all(["p", "li", "tr", "h1", "h2", "h3", "h4", "blockquote", "div"]):
        if el.name == "div":
            if el.find(["p", "li", "tr", "div", "table"]):
                continue
            t = el.get_text(" ", strip=True)
        elif el.name == "tr":
            t = " | ".join(c.get_text(" ", strip=True) for c in el.find_all(["td", "th"]))
        else:
            if el.find_parent(["li", "p", "tr"]) is not None:
                continue
            t = el.get_text(" ", strip=True)
        t = norm_ws(t)
        if len(t) < 15 or t in seen:
            continue
        seen.add(t)
        for ch in _chunk(t):
            passages.append({"text": ch, "page": None, "kind": "table row" if el.name == "tr" else "text"})
    if not passages and full:
        passages = [{"text": ch, "page": None, "kind": "text"} for ch in _chunk(full, 600)]
    return title, passages, date


def extract_docx(path: Path) -> tuple[str, list[dict]]:
    from ..readers import read_docx
    blocks = read_docx(path)
    title = blocks[0].text[:200] if blocks else path.name
    return title, [{"text": b.text, "page": None, "kind": b.location} for b in blocks for _ in [0] if b.text.strip()]


# ---------------------------------------------------------------- index
class DocIndex:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # the API serves requests from a thread pool; one connection guarded by a lock
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.lock = threading.RLock()
        self.db.execute("""CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY, url TEXT UNIQUE, title TEXT,
                           publisher TEXT, date TEXT, official INTEGER, sha TEXT, added TEXT)""")
        self.db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(
                           text, doc_id UNINDEXED, page UNINDEXED, kind UNINDEXED, tokenize='porter unicode61')""")
        self.db.commit()

    def close(self):
        self.db.close()

    def has(self, url: str) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM docs WHERE url=?", (url,)).fetchone() is not None

    def add(self, url: str, title: str, passages: list[dict], publisher: str = "", date: Optional[str] = None,
            official: bool = False, sha: str = "") -> int:
        with self.lock:
            return self._add(url, title, passages, publisher, date, official, sha)

    def _add(self, url, title, passages, publisher, date, official, sha) -> int:
        cur = self.db.execute("SELECT id FROM docs WHERE url=?", (url,)).fetchone()
        if cur:
            self.db.execute("DELETE FROM passages WHERE doc_id=?", (cur[0],))
            self.db.execute("DELETE FROM docs WHERE id=?", (cur[0],))
        c = self.db.execute("INSERT INTO docs(url,title,publisher,date,official,sha,added) VALUES (?,?,?,?,?,?,?)",
                            (url, title, publisher, date, int(official), sha, dt.date.today().isoformat()))
        doc_id = c.lastrowid
        self.db.executemany("INSERT INTO passages(text,doc_id,page,kind) VALUES (?,?,?,?)",
                            [(p["text"], doc_id, p.get("page"), p.get("kind", "text")) for p in passages if p["text"]])
        self.db.commit()
        return doc_id

    def docs(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("""SELECT d.url,d.title,d.publisher,d.date,d.official,d.added,
                                      (SELECT count(*) FROM passages p WHERE p.doc_id=d.id) FROM docs d ORDER BY d.id""").fetchall()
        return [dict(zip(("url", "title", "publisher", "date", "official", "added", "passages"), r)) for r in rows]

    def passages_for(self, url: str) -> list[dict]:
        with self.lock:
            rows = self.db.execute("""SELECT p.text,p.page,p.kind FROM passages p JOIN docs d ON d.id=p.doc_id
                                      WHERE d.url=?""", (url,)).fetchall()
        return [{"text": t, "page": pg, "kind": k} for t, pg, k in rows]

    def doc(self, url: str) -> Optional[dict]:
        with self.lock:
            r = self.db.execute("SELECT url,title,publisher,date,official FROM docs WHERE url=?", (url,)).fetchone()
        return dict(zip(("url", "title", "publisher", "date", "official"), r)) if r else None

    def search(self, text: str, numbers: Iterable[str] = (), k: int = 8, url: Optional[str] = None) -> list[dict]:
        with self.lock:
            return self._search(text, numbers, k, url)

    def _search(self, text: str, numbers: Iterable[str] = (), k: int = 8, url: Optional[str] = None) -> list[dict]:
        want = sorted(terms(text))
        toks = [f'"{t}"' for t in want if re.fullmatch(r"[a-z\-]+", t)]
        nums = [n for n in numbers if re.fullmatch(r"[\d.,]+", n)]
        toks += [f'"{n.replace(",", "")}"' for n in nums]
        if not toks:
            return []
        q = " OR ".join(toks)
        sql = """SELECT p.text,p.page,p.kind,bm25(passages) AS s,d.url,d.title,d.publisher,d.date,d.official
                 FROM passages p JOIN docs d ON d.id=p.doc_id WHERE passages MATCH ?"""
        args: list = [q]
        if url:
            sql += " AND d.url=?"
            args.append(url)
        sql += " ORDER BY s LIMIT ?"
        args.append(max(k * 6, 30))
        try:
            with self.lock:
                rows = self.db.execute(sql, args).fetchall()
        except sqlite3.OperationalError:
            return []
        out = []
        wset = set(want)
        for t, page, kind, s, u, title, pub, date, off in rows:
            pt = terms(t)
            cover = len(wset & pt) / (len(wset) or 1)
            nhit = sum(1 for n in nums if contains_number(t, n)) / (len(nums) or 1) if nums else 0.0
            score = cover + 0.6 * nhit + (0.05 if off else 0)
            out.append({"text": t, "page": page, "kind": kind, "bm25": s, "url": u, "title": title, "publisher": pub,
                        "date": date, "official": bool(off), "score": score, "cover": cover, "num_hit": nhit})
        out.sort(key=lambda r: -r["score"])
        return out[:k]


# ---------------------------------------------------------------- fetching and indexing
class DocFetcher:
    def __init__(self, cfg: Config, session=None):
        self.cfg = cfg
        self.session = session or make_session()
        self.dir = cfg.cache_dir / "docs"
        self.errors: list[str] = []

    def allowed(self, url: str) -> bool:
        return domain_allowed(url, self.cfg.allowed_domains)

    def fetch(self, url: str, any_domain: bool = False) -> tuple[bytes, str]:
        """Return (content, kind) where kind is 'pdf' or 'html'. Cached by URL."""
        if not any_domain and not domain_allowed(url, self.cfg.allowed_domains):
            raise FetchError(f"{host_of(url)} is not on the official-domain allow-list")
        key = hashlib.sha256(url.encode()).hexdigest()[:32]
        for ext in ("pdf", "html"):
            p = self.dir / f"{key}.{ext}"
            if p.exists():
                return p.read_bytes(), ext
        if self.cfg.offline:
            raise FetchError("offline: document not in cache")
        data, ctype, final = fetch_bytes(self.session, url, self.cfg.timeout, int(self.cfg.max_doc_mb * 2 ** 20))
        if not any_domain and not domain_allowed(final, self.cfg.allowed_domains):
            raise FetchError(f"redirected off the allow-list to {host_of(final)}")
        kind = "pdf" if ("pdf" in ctype.lower() or data[:5] == b"%PDF-") else "html"
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{key}.{kind}").write_bytes(data)
        return data, kind


def index_bytes(index: DocIndex, url: str, data: bytes, kind: str, official: bool) -> dict:
    if kind == "pdf":
        title, passages = extract_pdf(data)
        date = find_date(" ".join(p["text"] for p in passages[:6]))
    else:
        title, passages, date = extract_html(data, url)
    index.add(url, title or url, passages, publisher_for(url), date, official, hashlib.sha256(data).hexdigest()[:16])
    return {"url": url, "title": title, "passages": len(passages), "date": date}


def index_url(index: DocIndex, fetcher: DocFetcher, url: str) -> dict:
    data, kind = fetcher.fetch(url)
    return index_bytes(index, url, data, kind, official=True)


def index_path(index: DocIndex, path: Path, official: bool = False) -> list[dict]:
    path = Path(path)
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    done = []
    for f in files:
        ext = f.suffix.lower()
        url = f.resolve().as_uri()
        try:
            if ext == ".pdf":
                title, passages = extract_pdf(f.read_bytes())
                date = find_date(" ".join(p["text"] for p in passages[:6]))
            elif ext in (".html", ".htm"):
                title, passages, date = extract_html(f.read_bytes())
            elif ext == ".docx":
                title, passages = extract_docx(f)
                date = None
            elif ext in (".txt", ".md"):
                text = f.read_text(encoding="utf-8", errors="replace")
                title = text.strip().splitlines()[0][:200] if text.strip() else f.name
                passages = [{"text": ch, "page": None, "kind": "text"} for para in re.split(r"\n\s*\n", text)
                            for ch in _chunk(para)]
                date = find_date(text)
            else:
                continue
        except Exception as e:
            done.append({"url": url, "error": redact(f"{type(e).__name__}: {e}")})
            continue
        index.add(url, title or f.name, passages, "local file: " + f.name, date, official)
        done.append({"url": url, "title": title, "passages": len(passages), "date": date})
    return done


def pib_rss_items(session, timeout: float = 20.0) -> tuple[list[dict], str]:
    """Return (items, language) from the PIB press-release feed. PIB sometimes redirects Lang=1 to the
    Hindi feed (Lang=2) based on session/region; the language actually served is reported."""
    data, ctype, final = fetch_bytes(session, PIB_RSS, timeout)
    text = data.decode("utf-8-sig", errors="replace")
    items = []
    for m in re.finditer(r"<item>(.*?)</item>", text, re.S):
        body = m.group(1)
        t = re.search(r"<title>(.*?)</title>", body, re.S)
        ln = re.search(r"<link>(.*?)</link>", body, re.S)
        if t and ln:
            items.append({"title": norm_ws(t.group(1)), "link": ln.group(1).strip().replace("PressReleaseIframePage",
                                                                                           "PressReleasePage")})
    devanagari = sum(1 for it in items if re.search(r"[\u0900-\u097F]", it["title"]))
    lang = "hi" if items and devanagari > len(items) / 2 else "en"
    if "Lang=2" in final:
        lang = "hi"
    return items, lang


class DocsRetriever(Retriever):
    name = "docs"

    def __init__(self, cfg: Config, index: Optional[DocIndex] = None):
        super().__init__(cfg)
        self._index = index

    @property
    def index(self) -> DocIndex:
        if self._index is None:
            self._index = DocIndex(self.cfg.cache_dir / "index.sqlite")
        return self._index

    def status(self) -> dict:
        n = len(self.index.docs())
        where = str(self.index.path).replace(str(Path.home()), "~", 1)     # no home path in shared reports
        return self._status(True, f"{n} document(s) in the local index ({where})")

    def retrieve(self, claim: Claim, k: int = 4) -> list[Evidence]:
        from ..claims import NUMREF_RX, _strip_citations
        body = NUMREF_RX.sub(" ", _strip_citations(claim.text))
        nums = [d for d in (re.sub(r"[^\d.,]", "", n).strip(".,") for n in claim.numbers) if d]
        hits = self.index.search(body, nums, k=k * 3)
        out = []
        want = terms(body)
        for h in hits:
            if h["cover"] < 0.2:
                continue
            snippet, _ = best_window(h["text"], want, nums)
            out.append(Evidence(retriever=self.name, source_url=h["url"], title=h["title"], snippet=snippet or h["text"],
                                date=h["date"], publisher=h["publisher"], page=h["page"], official=h["official"],
                                score=round(h["score"], 3), kind="passage",
                                meta={"passage_kind": h["kind"], "cover": round(h["cover"], 2), "num_hit": h["num_hit"]}))
            if len(out) >= k:
                break
        return out
