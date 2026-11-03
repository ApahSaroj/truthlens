"""v0.4 research sources: Semantic Scholar, arXiv and Shodhganga (Indian PhD theses).

Semantic Scholar  GET https://api.semanticscholar.org/graph/v1/paper/search?query=..&limit=N&fields=title,abstract,year,
                  venue,authors,externalIds,publicationDate,url   (key-free; optional S2_API_KEY sent as x-api-key)
                  GET https://api.semanticscholar.org/graph/v1/paper/DOI:<doi>?fields=...   (citation existence check)
                  The shared key-free pool answers HTTP 429 often (it did on every call from our network on 2 Nov 2026):
                  we back off (1 s, 2 s; Retry-After honoured, capped) and then fail closed with the 429 recorded.
arXiv             GET https://export.arxiv.org/api/query?search_query=all:..&max_results=N   (Atom XML, key-free; arXiv
                  asks for at most one request every 3 seconds, so calls are serialised and spaced)
                  GET https://export.arxiv.org/api/query?id_list=<id>   (citation check for arXiv:NNNN.NNNNN)
Shodhganga        GET https://shodhganga.inflibnet.ac.in/open-search/?query=..&format=atom&rpp=N  (DSpace OpenSearch, the
                  documented keyword search of DSpace 6 JSPUI repositories; /oai/request answers OAI-PMH but has no
                  keyword search). On 2 Nov 2026 every URL on the host, including /oai/request?verb=Identify, answered
                  an "Anubis" proof-of-work bot-challenge page (JavaScript), so no record could be read. The retriever
                  detects that page and fails closed. Tests use a SYNTHETIC OpenSearch Atom fixture.

Papers are evidence of kind "metadata" with the badge Paper (or Thesis). A paper can support a *research* claim only
through a verbatim abstract quote that passes the same figure/date/name/polarity checks as any other quote; it is
never used to support an official-statistics claim (see verdict.py: papers_cannot_decide_official_figures).
"""
from __future__ import annotations

import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import quote, urlencode

from ..config import Config, redact
from ..model import Claim, Evidence
from ..net import DiskCache, FetchError, fetch_bytes, make_session, safe_get
from .base import Retriever, best_window, norm_ws, terms

S2 = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = "title,abstract,year,venue,authors,externalIds,publicationDate,url"
ARXIV = "https://export.arxiv.org/api/query"
SHODH = "https://shodhganga.inflibnet.ac.in"
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _paper_evidence(retriever: str, badge: str, title: str, authors: list, year, venue: str, abstract: str, url: str,
                    date: Optional[str], claim_text: str, nums: list, meta: dict) -> Optional[Evidence]:
    want = terms(claim_text)
    window, _ = best_window(abstract, want, [n for n in nums if n]) if abstract else ("", 0)
    head = f"{title}. {', '.join(a for a in authors[:4] if a)} ({year or 'n.d.'}). {venue}."
    snippet = norm_ws(head + (" Abstract: " + window if window else ""))
    cover = len(want & terms(snippet)) / (len(want) or 1)
    if cover < 0.3:
        return None
    return Evidence(retriever=retriever, source_url=url, title=title, snippet=snippet, date=date or (str(year) if year else None),
                    publisher=f"{venue} (via {meta.get('via', retriever)})".strip(), official=False, score=round(cover, 3),
                    kind="metadata", source_type=badge, as_of=date or (str(year) if year else None), meta=meta)


class SemanticScholarRetriever(Retriever):
    name = "semanticscholar"
    backoff = (1.0, 2.0)

    def __init__(self, cfg: Config, session=None):
        super().__init__(cfg)
        self.session = session if session is not None else make_session()
        self.cache = DiskCache(cfg.cache_dir, "semanticscholar", ttl=7 * 24 * 3600)
        self._lock = threading.Lock()      # one request at a time (the key-free pool is shared and rate-limited)

    def status(self) -> dict:
        k = "your S2_API_KEY" if self.cfg.secret("S2_API_KEY") else "no key (shared pool, often HTTP 429)"
        return self._status(not self.cfg.offline, f"Semantic Scholar Graph API paper search and DOI lookup, {k}")

    def _get(self, url: str):
        hit = self.cache.get(url)
        if hit is not None:
            return hit
        if self.cfg.offline:
            return self.cache.get(url, allow_stale=True)
        headers = {"Accept": "application/json"}
        key = self.cfg.secret("S2_API_KEY")
        if key:
            headers["x-api-key"] = key
        last = None
        with self._lock:
            for attempt in range(len(self.backoff) + 1):
                try:
                    r = safe_get(self.session, url, self.cfg.timeout, headers)
                except FetchError as e:
                    last = str(e)
                    break
                st = getattr(r, "status_code", 200)
                if st == 429 and attempt < len(self.backoff):
                    ra = (getattr(r, "headers", {}) or {}).get("retry-after")
                    try:
                        wait = min(float(ra), 5.0) if ra else self.backoff[attempt]
                    except ValueError:
                        wait = self.backoff[attempt]
                    time.sleep(wait)
                    continue
                if st == 404:
                    self.cache.set(url, {"_status": 404})
                    return {"_status": 404}
                if st >= 400:
                    last = f"HTTP {st}" + (" (rate-limited; add S2_API_KEY)" if st == 429 else "")
                    break
                try:
                    data = r.json()
                except Exception:
                    last = "not JSON"
                    break
                self.cache.set(url, data)
                return data
        self.errors.append(redact(f"Semantic Scholar: {last}"))
        return self.cache.get(url, allow_stale=True)

    def search(self, q: str, n: int = 4) -> list[dict]:
        d = self._get(f"{S2}/paper/search?" + urlencode({"query": q, "limit": n, "fields": S2_FIELDS}))
        return (d or {}).get("data") or [] if isinstance(d, dict) else []

    def by_doi(self, doi: str) -> Optional[dict]:
        """Paper record, {"_status": 404} when Semantic Scholar does not know the DOI, None when it could not be asked."""
        return self._get(f"{S2}/paper/DOI:{quote(doi, safe='/:;()')}?fields={S2_FIELDS}")

    def retrieve(self, claim: Claim, k: int = 3) -> list[Evidence]:
        from .parliament import query_terms
        words = query_terms(claim.text, 6)
        if len(words) < 2:
            return []
        nums = [re.sub(r"[^\d.,]", "", n).strip(".,") for n in claim.numbers]
        out = []
        for p in self.search(" ".join(words)):
            ext = p.get("externalIds") or {}
            doi = ext.get("DOI")
            url = f"https://doi.org/{doi}" if doi else (p.get("url") or "")
            ev = _paper_evidence(self.name, "Paper", p.get("title") or "", [a.get("name") or "" for a in p.get("authors") or []],
                                 p.get("year"), p.get("venue") or "", p.get("abstract") or "", url, p.get("publicationDate"),
                                 claim.text, nums, {"doi": doi, "s2": p.get("paperId"), "via": "Semantic Scholar"})
            if ev:
                out.append(ev)
            if len(out) >= k:
                break
        return out


class ArxivRetriever(Retriever):
    name = "arxiv"
    _lock = threading.Lock()
    _last = [0.0]
    spacing = 3.0

    def __init__(self, cfg: Config, session=None):
        super().__init__(cfg)
        self.session = session if session is not None else make_session()
        self.cache = DiskCache(cfg.cache_dir, "arxiv", ttl=7 * 24 * 3600)

    def status(self) -> dict:
        return self._status(not self.cfg.offline, "arXiv API (Atom), key-free; one request per 3 s")

    def _get(self, url: str) -> Optional[str]:
        hit = self.cache.get(url)
        if hit is not None:
            return hit
        if self.cfg.offline:
            return self.cache.get(url, allow_stale=True)
        with self._lock:
            wait = self.spacing - (time.time() - self._last[0])
            if wait > 0:
                time.sleep(min(wait, self.spacing))
            try:
                data, _ct, _u = fetch_bytes(self.session, url, self.cfg.timeout, 4 * 2 ** 20)
                self._last[0] = time.time()      # spacing counts requests that reached arXiv
                txt = data.decode("utf-8", "replace")
                self.cache.set(url, txt)
                return txt
            except Exception as e:
                if "HTTP" in str(e):
                    self._last[0] = time.time()
                self.errors.append(redact(f"arXiv: {type(e).__name__}: {str(e)[:120]}"))
                return self.cache.get(url, allow_stale=True)

    @staticmethod
    def parse(xml_text: str) -> list[dict]:
        out = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return out
        for e in root.findall("a:entry", ATOM):
            def t(tag):
                x = e.find(f"a:{tag}", ATOM)
                return norm_ws(x.text) if x is not None and x.text else ""
            aid = t("id")
            if not aid or "/abs/" not in aid:
                continue
            out.append({"id": aid.replace("http://", "https://"), "title": t("title"), "summary": t("summary"),
                        "published": t("published")[:10], "authors": [norm_ws(a.findtext("a:name", "", ATOM))
                                                                       for a in e.findall("a:author", ATOM)]})
        return out

    def search(self, q: str, n: int = 4) -> list[dict]:
        sq = " AND ".join(f"all:{w}" for w in q.split()[:5])
        txt = self._get(f"{ARXIV}?" + urlencode({"search_query": sq, "start": 0, "max_results": n}))
        return self.parse(txt or "")

    def by_id(self, arxiv_id: str) -> Optional[list]:
        txt = self._get(f"{ARXIV}?" + urlencode({"id_list": arxiv_id}))
        return None if txt is None else self.parse(txt)

    def retrieve(self, claim: Claim, k: int = 2) -> list[Evidence]:
        from .parliament import query_terms
        words = query_terms(claim.text, 5)
        if len(words) < 2:
            return []
        nums = [re.sub(r"[^\d.,]", "", n).strip(".,") for n in claim.numbers]
        out = []
        for p in self.search(" ".join(words)):
            ev = _paper_evidence(self.name, "Paper", p["title"], p["authors"], p["published"][:4], "arXiv preprint",
                                 p["summary"], p["id"], p["published"], claim.text, nums, {"arxiv": p["id"], "via": "arXiv",
                                                                                          "preprint": True})
            if ev:
                out.append(ev)
            if len(out) >= k:
                break
        return out


ANUBIS_RX = re.compile(r"Making sure you(?:&#39;|')re not a bot|within\.website", re.I)
THESIS_RX = re.compile(r"\b(thesis|theses|ph\.?\s?d|doctoral|dissertation|shodhganga)\b", re.I)


class ShodhgangaRetriever(Retriever):
    name = "shodhganga"

    def __init__(self, cfg: Config, session=None):
        super().__init__(cfg)
        self.session = session if session is not None else make_session()
        self.cache = DiskCache(cfg.cache_dir, "shodhganga", ttl=7 * 24 * 3600)

    def status(self) -> dict:
        return self._status(not self.cfg.offline, "Shodhganga (INFLIBNET) Indian theses via DSpace OpenSearch; on 2 Nov 2026 "
                                                  "the host served a JavaScript bot challenge, so this source fails closed")

    @staticmethod
    def parse_atom(xml_text: str) -> list[dict]:
        out = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return out
        for e in root.findall("a:entry", ATOM):
            link = next((l.get("href") for l in e.findall("a:link", ATOM) if l.get("href", "").startswith("http")), "")
            out.append({"title": norm_ws(e.findtext("a:title", "", ATOM)),
                        "creators": [norm_ws(a.findtext("a:name", "", ATOM)) for a in e.findall("a:author", ATOM)],
                        "date": (e.findtext("a:published", "", ATOM) or e.findtext("a:updated", "", ATOM) or "")[:10],
                        "description": norm_ws(e.findtext("a:summary", "", ATOM) or e.findtext("a:content", "", ATOM)),
                        "url": link, "publisher": "Shodhganga, INFLIBNET"})
        return out

    def search(self, q: str, n: int = 5) -> list[dict]:
        url = f"{SHODH}/open-search/?" + urlencode({"query": q, "format": "atom", "rpp": n})
        hit = self.cache.get(url)
        if hit is not None:
            return hit
        if self.cfg.offline:
            return self.cache.get(url, allow_stale=True) or []
        try:
            data, _ct, _u = fetch_bytes(self.session, url, self.cfg.timeout, 4 * 2 ** 20)
            txt = data.decode("utf-8", "replace")
            if ANUBIS_RX.search(txt[:5000]):
                raise FetchError("Shodhganga answered a JavaScript bot-challenge page (Anubis); no records readable")
            recs = self.parse_atom(txt)
            self.cache.set(url, recs)
            return recs
        except Exception as e:
            self.errors.append(redact(f"Shodhganga: {type(e).__name__}: {str(e)[:140]}"))
            return self.cache.get(url, allow_stale=True) or []

    def retrieve(self, claim: Claim, k: int = 2) -> list[Evidence]:
        from .parliament import query_terms
        words = query_terms(claim.text, 6)
        if len(words) < 2:
            return []
        nums = [re.sub(r"[^\d.,]", "", n).strip(".,") for n in claim.numbers]
        out = []
        for r in self.search(" ".join(words)):
            ev = _paper_evidence(self.name, "Thesis", r["title"], r["creators"], (r["date"] or "")[:4],
                                 f"PhD thesis, {r['publisher'] or 'Shodhganga'}", r["description"], r["url"], r["date"] or None,
                                 claim.text, nums, {"via": "Shodhganga", "thesis": True})
            if ev:
                out.append(ev)
            if len(out) >= k:
                break
        return out
