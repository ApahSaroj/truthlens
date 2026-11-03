"""Live document retrievers (v0.3): PIB press releases, OpenAlex research papers, government reports.

PIB      The English press-release feed (RssMain.aspx?ModId=6&reg=3&lang=1, cached 1 hour) is matched against the
         claim; the best-matching releases are fetched from pib.gov.in, indexed with their date, and searched.
         PIB has no usable key-free keyword/date search API: the date listing (allRel.aspx) is an ASP.NET
         postback form that ignored scripted filters in our tests, so older releases come from Parliament
         answers, web search (with a key) or `truthlens index --url`.
OpenAlex GET https://api.openalex.org/works?search=...&per-page=N&select=... (no key; `mailto` for the polite pool;
         an optional OPENALEX_API_KEY raises the shared daily budget). Abstracts (inverted index) are the evidence;
         cited with DOI, authors, year and venue. Used for claims that cite a study or state a research finding.
Reports  On-demand discovery of official reports: with a web-search key, a site-restricted search over the
         official allow-list; without one, the listing pages configured under [reports] listing_pages in
         truthlens.toml (defaults below) are read and PDFs whose link text matches the claim are fetched,
         extracted with page numbers and indexed.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional
from urllib.parse import urljoin

from ..config import Config, redact
from ..model import Claim, Evidence
from ..net import DiskCache, domain_allowed, fetch_bytes, FetchError, make_session, safe_get, with_params
from .base import Retriever, best_window, norm_ws, terms

# ------------------------------------------------------------------------------------------------ PIB


class PIBRetriever(Retriever):
    name = "pib"

    def __init__(self, cfg: Config, session=None, docs=None, fetcher=None, max_fetch: int = 2):
        super().__init__(cfg)
        self.session = session or make_session()
        self.cache = DiskCache(cfg.cache_dir, "pib", ttl=3600)
        self.docs = docs
        self.fetcher = fetcher
        self.max_fetch = max_fetch

    def status(self) -> dict:
        return self._status(not self.cfg.offline, "PIB English press-release feed (live, 1-hour cache) + release pages, no key")

    def feed(self) -> list[dict]:
        from .docs import pib_rss_items
        hit = self.cache.get("feed")
        if hit is not None:
            return hit
        if self.cfg.offline:
            return self.cache.get("feed", allow_stale=True) or []
        try:
            items, lang = pib_rss_items(self.session, self.cfg.timeout)
            items = [dict(it, lang=lang) for it in items]
            self.cache.set("feed", items)
            return items
        except Exception as e:
            self.errors.append(redact(f"PIB feed: {type(e).__name__}: {e}"))
            return self.cache.get("feed", allow_stale=True) or []

    def retrieve(self, claim: Claim, k: int = 3) -> list[Evidence]:
        if self.docs is None or self.fetcher is None:
            return []
        want = terms(claim.text)
        scored = sorted(((len(want & terms(it["title"])) / (len(want) or 1), it) for it in self.feed()), key=lambda x: -x[0])
        from .docs import index_bytes
        fetched = 0
        for score, it in scored:
            if score < 0.3 or fetched >= self.max_fetch:
                break
            url = it["link"]
            if self.docs.index.has(url):
                continue
            try:
                data, kind = self.fetcher.fetch(url)
                index_bytes(self.docs.index, url, data, kind, official=True)
                fetched += 1
            except Exception as e:
                self.errors.append(redact(f"PIB release: {type(e).__name__}: {str(e)[:120]}"))
        out = []
        for e in self.docs.retrieve(claim, k):
            if "pib.gov.in" in e.source_url:
                e.retriever, e.source_type, e.as_of = "pib", "PIB", e.date
                out.append(e)
        return out


# ------------------------------------------------------------------------------------------- OpenAlex
OPENALEX_WORKS = "https://api.openalex.org/works"
STUDY_RX = re.compile(r"\b(study|studies|research|survey(?:ed)?|paper|journal|evidence shows|researchers|"
                      r"meta-analysis|trial|et al\.?|according to (?:a|an|the) [a-z ]*(?:study|report|paper))\b", re.I)


def abstract_from_inverted(inv: Optional[dict]) -> str:
    if not inv:
        return ""
    pos = sorted((i, w) for w, idxs in inv.items() for i in idxs)
    return " ".join(w for _, w in pos)


class OpenAlexRetriever(Retriever):
    name = "openalex"

    def __init__(self, cfg: Config, session=None):
        super().__init__(cfg)
        self.session = session or make_session()
        self.cache = DiskCache(cfg.cache_dir, "openalex", ttl=7 * 24 * 3600)

    def status(self) -> dict:
        extra = "your OPENALEX_API_KEY" if self.cfg.secret("OPENALEX_API_KEY") else "no key (shared daily budget per IP)"
        return self._status(not self.cfg.offline, f"OpenAlex works search for research claims, {extra}")

    def search(self, q: str, n: int = 4) -> list[dict]:
        params = {"search": q, "per-page": n,
                  "select": "id,doi,title,publication_year,publication_date,authorships,primary_location,abstract_inverted_index"}
        if self.cfg.contact_email:
            params["mailto"] = self.cfg.contact_email
        from urllib.parse import urlencode
        ck = f"{OPENALEX_WORKS}?{urlencode(params)}"
        hit = self.cache.get(ck)
        if hit is not None:
            return hit
        if self.cfg.offline:
            return self.cache.get(ck, allow_stale=True) or []
        q2 = dict(params)
        key = self.cfg.secret("OPENALEX_API_KEY")
        if key:
            q2["api_key"] = key
        try:
            r = safe_get(self.session, with_params(OPENALEX_WORKS, q2), self.cfg.timeout, stream=False)
            if r.status_code == 429:
                raise RuntimeError("HTTP 429 (OpenAlex daily budget for this network used up; add OPENALEX_API_KEY)")
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            res = r.json().get("results") or []
            self.cache.set(ck, res)
            return res
        except Exception as e:
            self.errors.append(redact(f"OpenAlex: {type(e).__name__}: {e}"))
            return self.cache.get(ck, allow_stale=True) or []

    def retrieve(self, claim: Claim, k: int = 3) -> list[Evidence]:
        from .parliament import query_terms
        words = query_terms(claim.text, 6)
        if len(words) < 2:
            return []
        want = terms(claim.text)
        nums = [re.sub(r"[^\d.,]", "", n).strip(".,") for n in claim.numbers]
        out = []
        for w in self.search(" ".join(words)):
            abstract = abstract_from_inverted(w.get("abstract_inverted_index"))
            title = w.get("title") or ""
            if not abstract and not title:
                continue
            authors = [((a.get("author") or {}).get("display_name") or "") for a in (w.get("authorships") or [])][:4]
            venue = (((w.get("primary_location") or {}).get("source")) or {}).get("display_name") or ""
            window, _ = best_window(abstract, want, [n for n in nums if n]) if abstract else ("", 0)
            head = f"{title}. {', '.join(a for a in authors if a)} ({w.get('publication_year') or 'n.d.'}). {venue}."
            snippet = norm_ws(head + (" Abstract: " + window if window else ""))
            cover = len(want & terms(snippet)) / (len(want) or 1)
            if cover < 0.3:
                continue
            doi = w.get("doi") or ""
            out.append(Evidence(retriever=self.name, source_url=doi or w.get("id") or "", title=title, snippet=snippet,
                                date=w.get("publication_date") or str(w.get("publication_year") or ""), publisher=f"{venue} (via OpenAlex)",
                                official=False, score=round(cover, 3), kind="metadata", source_type="Paper",
                                as_of=w.get("publication_date"), meta={"doi": doi, "openalex": w.get("id"), "authors": authors}))
            if len(out) >= k:
                break
        return out


# -------------------------------------------------------------------------------------------- Reports
DEFAULT_LISTING_PAGES = [
    # Economic Survey and Union Budget documents (Ministry of Finance)
    "https://www.indiabudget.gov.in/economicsurvey/",
    "https://www.indiabudget.gov.in/",
    # MoSPI press releases and publications
    "https://www.mospi.gov.in/press-release",
]
REPORT_HINT_RX = re.compile(r"\b(report|survey|economic survey|budget|audit|cag|niti|white paper|annual report|"
                            r"bulletin|census|press note)\b", re.I)


class ReportsRetriever(Retriever):
    name = "reports"

    def __init__(self, cfg: Config, session=None, docs=None, fetcher=None, web=None, max_fetch: int = 2):
        super().__init__(cfg)
        self.session = session or make_session()
        self.cache = DiskCache(cfg.cache_dir, "reports", ttl=24 * 3600)
        self.docs, self.fetcher, self.web = docs, fetcher, web
        self.max_fetch = max_fetch
        self.pages = list((cfg.toml.get("reports") or {}).get("listing_pages") or DEFAULT_LISTING_PAGES) \
            if isinstance(getattr(cfg, "toml", None), dict) else list(DEFAULT_LISTING_PAGES)

    def status(self) -> dict:
        how = "site-restricted web search over official domains" if (self.web and self.web.provider) else \
            f"{len(self.pages)} official listing page(s) (no search key)"
        return self._status(not self.cfg.offline, f"Government reports discovered on demand: {how}; PDFs cited with page numbers")

    def links(self, page: str) -> list[dict]:
        hit = self.cache.get(page)
        if hit is not None:
            return hit
        if self.cfg.offline:
            return self.cache.get(page, allow_stale=True) or []
        try:
            data, _ct, final = fetch_bytes(self.session, page, self.cfg.timeout, 8 * 2 ** 20)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(data, "html.parser")
            out = []
            for a in soup.find_all("a", href=True):
                href = urljoin(final, a["href"])
                text = norm_ws(a.get_text(" ")) or norm_ws(a.get("title") or "")
                if href.lower().split("?")[0].endswith(".pdf") and domain_allowed(href, self.cfg.allowed_domains):
                    out.append({"url": href, "text": text[:200]})
            self.cache.set(page, out)
            return out
        except Exception as e:
            self.errors.append(redact(f"reports listing {page.split('/')[2]}: {type(e).__name__}: {str(e)[:100]}"))
            return self.cache.get(page, allow_stale=True) or []

    def retrieve(self, claim: Claim, k: int = 3) -> list[Evidence]:
        if self.docs is None or self.fetcher is None:
            return []
        want = terms(claim.text)
        cands: list[tuple] = []
        if self.web is not None and getattr(self.web, "provider", None):
            return []      # the web retriever already searches and indexes official pages when a key is set
        for page in self.pages:
            for ln in self.links(page):
                score = len(want & terms(ln["text"] + " " + ln["url"].rsplit("/", 1)[-1].replace("_", " "))) / (len(want) or 1)
                if score >= 0.25:
                    cands.append((score, ln["url"]))
        from .docs import index_bytes
        fetched = 0
        for score, url in sorted(cands, key=lambda x: -x[0]):
            if fetched >= self.max_fetch:
                break
            if self.docs.index.has(url):
                continue
            try:
                data, kind = self.fetcher.fetch(url)
                index_bytes(self.docs.index, url, data, kind, official=True)
                fetched += 1
            except Exception as e:
                self.errors.append(redact(f"report PDF: {type(e).__name__}: {str(e)[:120]}"))
        out = []
        for e in self.docs.retrieve(claim, k):
            if not e.source_url.startswith("file:") and "pib.gov.in" not in e.source_url:
                e.retriever, e.source_type, e.as_of = "reports", "Report", e.date
                out.append(e)
        return out


def today() -> str:
    return dt.date.today().isoformat()
