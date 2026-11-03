"""Web search retriever (bring your own key): Brave, Tavily or Serper, re-ranked by source trust.

Endpoints (from each provider's API docs):
  Brave   GET  https://api.search.brave.com/res/v1/web/search?q=...      header X-Subscription-Token: KEY
          results: web.results[] {title, url, description, page_age|age}
  Tavily  POST https://api.tavily.com/search  {"query", "max_results"}   header Authorization: Bearer KEY
          results: results[] {title, url, content, published_date?}
          Keyless mode (header X-Tavily-Access-Mode: keyless) is supported for search but is OFF unless
          TRUTHLENS_TAVILY_KEYLESS=1, because it sends claim text to Tavily without an account.
  Serper  POST https://google.serper.dev/search {"q", "num", "gl"}       header X-API-KEY: KEY
          results: organic[] {title, link, snippet, date?}

Search snippets are short and written by the search engine, so they are marked `kind="search_snippet"`.
For the top official (allow-listed) results TruthLens also fetches the page itself, indexes it, and
returns the matching passage verbatim, which is the evidence the judge prefers.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Optional

from ..config import Config, redact
from ..model import Claim, Evidence
from ..net import DiskCache, domain_allowed, host_of, make_session, safe_get, safe_post, with_params
from .base import Retriever, short_date

ENDPOINTS = {"brave": "https://api.search.brave.com/res/v1/web/search", "tavily": "https://api.tavily.com/search",
             "serper": "https://google.serper.dev/search"}
KEYS = {"brave": "BRAVE_API_KEY", "tavily": "TAVILY_API_KEY", "serper": "SERPER_API_KEY"}


@lru_cache(maxsize=1)
def trusted_weights() -> list[tuple[str, int, str]]:
    data = json.loads(resources.files("truthlens.data").joinpath("trusted_sources.json").read_text(encoding="utf-8"))
    out = []
    for cat, info in data.items():
        if cat.startswith("_"):
            continue
        for d in info["domains"]:
            out.append((d, int(info["weight"]), cat))
    out.sort(key=lambda x: -len(x[0]))  # most specific first
    return out


def trust(url: str) -> tuple[int, str]:
    h = host_of(url)
    for d, w, cat in trusted_weights():
        if h == d or h.endswith("." + d):
            return w, cat
    return 10, "unknown"


class WebSearchRetriever(Retriever):
    name = "web"

    def __init__(self, cfg: Config, session=None, docs=None, fetcher=None):
        super().__init__(cfg)
        self.provider = cfg.resolved_search()
        self.session = session or make_session()
        self.cache = DiskCache(cfg.cache_dir, "websearch", ttl=3 * 24 * 3600)
        self.docs = docs          # DocsRetriever (to index fetched official pages)
        self.fetcher = fetcher    # DocFetcher
        self.calls = 0

    def status(self) -> dict:
        if not self.provider:
            return self._status(False, "set BRAVE_API_KEY, TAVILY_API_KEY or SERPER_API_KEY (or TRUTHLENS_TAVILY_KEYLESS=1)")
        keyless = self.provider == "tavily" and not self.cfg.secret("TAVILY_API_KEY")
        return self._status(True, f"{self.provider}{' (keyless mode)' if keyless else ''}")

    # -------------------------------------------------------------- providers
    def search(self, query: str, n: int = 8) -> list[dict]:
        if not self.provider:
            return []
        ckey = f"{self.provider}|{n}|{query}"
        cached = self.cache.get(ckey)
        if cached is not None:
            return cached
        if self.cfg.offline:
            return self.cache.get(ckey, allow_stale=True) or []
        try:
            self.calls += 1
            res = getattr(self, f"_{self.provider}")(query, n)
            self.cache.set(ckey, res)
            return res
        except Exception as e:
            self.errors.append(redact(f"{self.provider} search: {type(e).__name__}: {e}"))
            return self.cache.get(ckey, allow_stale=True) or []

    def _brave(self, q: str, n: int) -> list[dict]:
        r = safe_get(self.session, with_params(ENDPOINTS["brave"], {"q": q, "count": min(n, 20), "country": "IN"}),
                     self.cfg.timeout, {"Accept": "application/json", "X-Subscription-Token": self.cfg.secret("BRAVE_API_KEY") or ""},
                     stream=False)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}")
        rows = (r.json().get("web") or {}).get("results") or []
        return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("description", ""),
                 "date": x.get("page_age") or x.get("age")} for x in rows]

    def _tavily(self, q: str, n: int) -> list[dict]:
        key = self.cfg.secret("TAVILY_API_KEY")
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        elif self.cfg.tavily_keyless:
            headers["X-Tavily-Access-Mode"] = "keyless"
        else:
            return []
        r = safe_post(self.session, ENDPOINTS["tavily"], self.cfg.timeout, headers,
                      json_body={"query": q[:400], "max_results": min(n, 20)})
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}")
        rows = r.json().get("results") or []
        return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", ""),
                 "date": x.get("published_date")} for x in rows]

    def _serper(self, q: str, n: int) -> list[dict]:
        r = safe_post(self.session, ENDPOINTS["serper"], self.cfg.timeout,
                      {"X-API-KEY": self.cfg.secret("SERPER_API_KEY") or "", "Content-Type": "application/json"},
                      json_body={"q": q, "num": min(n, 20), "gl": "in"})
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}")
        rows = r.json().get("organic") or []
        return [{"title": x.get("title", ""), "url": x.get("link", ""), "snippet": x.get("snippet", ""),
                 "date": x.get("date")} for x in rows]

    # -------------------------------------------------------------- retrieval
    def retrieve(self, claim: Claim, k: int = 4) -> list[Evidence]:
        if not self.provider:
            return []
        query = claim.text if len(claim.text) < 300 else claim.text[:300]
        if "india" not in query.lower():
            query += " India"
        results = self.search(query)
        ranked = []
        for pos, r in enumerate(results):
            if not r.get("url"):
                continue
            w, cat = trust(r["url"])
            official = domain_allowed(r["url"], self.cfg.allowed_domains)
            score = w / 100 + (0.2 if official else 0) - pos * 0.03
            ranked.append((score, r, cat, official))
        ranked.sort(key=lambda x: -x[0])
        out: list[Evidence] = []
        fetched = 0
        for score, r, cat, official in ranked:
            if official and self.fetcher is not None and self.docs is not None and fetched < self.cfg.web_fetch_top:
                fetched += 1
                try:
                    from .docs import index_url
                    if not self.docs.index.has(r["url"]):
                        index_url(self.docs.index, self.fetcher, r["url"])
                    hits = self.docs.index.search(claim.text, claim.numbers, k=2, url=r["url"])
                    for h in hits:
                        from .base import best_window, terms
                        snip, _ = best_window(h["text"], terms(claim.text), claim.numbers)
                        out.append(Evidence(retriever=self.name, source_url=r["url"], title=h["title"] or r["title"],
                                            snippet=snip or h["text"], date=h["date"] or short_date(r.get("date")),
                                            publisher=h["publisher"], page=h["page"], official=True,
                                            score=round(score + h["score"], 3), kind="passage",
                                            meta={"via": f"{self.provider} search, page fetched", "trust": cat}))
                    if hits:
                        continue
                except Exception as e:
                    self.errors.append(redact(f"fetch {host_of(r['url'])}: {e}"))
            out.append(Evidence(retriever=self.name, source_url=r["url"], title=r.get("title", ""),
                                snippet=(r.get("snippet") or "")[:700], date=short_date(r.get("date")),
                                publisher=host_of(r["url"]), official=official, score=round(score, 3),
                                kind="search_snippet", meta={"via": f"{self.provider} search", "trust": cat}))
        out.sort(key=lambda e: -e.score)
        return out[:k]
