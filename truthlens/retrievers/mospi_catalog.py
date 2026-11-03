"""MoSPI eSankhyiki: discovery across every dataset the public API lists, then a generic row matcher.

Discovery flow (the same one the official `mospi-esankhyiki` package exposes as list_datasets ->
get_indicators -> get_metadata -> get_data; endpoints read from its client.py and swagger files and
called live from our test network on 1 Nov 2026, see docs/SOURCES.md):

  1. indicator lists   GET https://api.mospi.gov.in/api/<ds>/get<Ds>IndicatorList           (cached 7 days)
  2. pick indicators   claim terms vs indicator labels (+ dataset keywords)
  3. rows              GET https://api.mospi.gov.in/api/<ds>/get<Ds>Records?indicator_code=N&Format=JSON&limit=200&page=..
                       (the API answers HTTP 400 "Limit cannot be greater than 200" above 200 rows per page)
                       (cached: 1 day for monthly/annual price and production series, 7 days for surveys)
  4. match             tables.match_rows: geography, period, rural/urban, sex, then the value at the precision written

PLFS and National Accounts keep their dedicated, curated-first path in retrievers/mospi.py.
"""
from __future__ import annotations

from .official_api import kw_hits  # noqa: E402  (v0.5.2: compiled keyword patterns)

import datetime as dt
import re
from typing import Optional
from urllib.parse import urlencode

from ..config import Config, redact
from ..net import DiskCache, make_session, safe_get, with_params
from .base import terms
from .tables import match_rows

API = "https://api.mospi.gov.in"
PORTAL = "https://esankhyiki.mospi.gov.in"

# dataset -> (title, indicator-list path, records path, label key, keywords that point to it, ttl seconds)
DATASETS = {
    "NFHS": ("National Family Health Survey (NFHS)", "/api/nfhs/getNfhsIndicatorList", "/api/nfhs/getNfhsRecords",
             ["nfhs", "stunting", "wasting", "underweight", "anaemia", "anemia", "fertility", "immunisation", "immunization",
              "institutional", "family planning", "sex ratio at birth", "mortality"], 7),
    "HCES": ("Household Consumption Expenditure Survey (HCES)", "/api/hces/getHcesIndicatorList", "/api/hces/getHcesRecords",
             ["mpce", "consumption expenditure", "hces", "per capita consumption", "household consumption"], 7),
    "GENDER": ("Women and Men in India (gender statistics)", "/api/gender/getGenderIndicatorList", "/api/gender/getGenderRecords",
               ["sex ratio", "women", "female", "gender", "literacy"], 7),
    "AISHE": ("All India Survey on Higher Education (AISHE)", "/api/aishe/getAisheIndicatorList", "/api/aishe/getAisheRecords",
              ["universities", "colleges", "higher education", "gross enrolment", "ger", "aishe"], 7),
    "UDISE": ("UDISE+ school education statistics", "/api/udise/getIndicatorList", "/api/udise/getUdiseRecords",
              ["schools", "school", "teachers", "udise", "enrolment", "pupil"], 7),
    "ENVSTATS": ("EnviStats India (environment statistics)", "/api/env/getEnvStatsIndicatorList", "/api/env/getEnvStatsRecords",
                 ["temperature", "rainfall", "forest", "emission", "environment", "envistats", "air quality"], 7),
    "TUS": ("Time Use Survey (TUS)", "/api/tus/getTusIndicatorList", "/api/tus/getTusRecords",
            ["time use", "unpaid", "minutes", "activity in a day"], 7),
}
# series without an indicator list: one pseudo-indicator each
STATIC = {
    "IIP_ANNUAL": ("Index of Industrial Production (IIP), annual, base 2022-23", "/api/iip/getIIPAnnual",
                   {"base_year": "2022-23", "Format": "JSON"},
                   ["iip", "industrial production", "industrial output", "manufacturing", "mining", "electricity"], 1,
                   "growth_rate"),
}
PUBLISHER = "MoSPI, National Statistics Office (eSankhyiki API)"


class MospiCatalog:
    name = "mospi-catalog"

    def __init__(self, cfg: Config, session=None, max_pages: int = 6, page_size: int = 200):
        self.cfg = cfg
        self.session = session or make_session(legacy_tls=True)
        self.lists = DiskCache(cfg.cache_dir, "mospi_catalog", ttl=7 * 24 * 3600)
        self.errors: list[str] = []
        self.max_pages = max_pages
        self.page_size = page_size
        self.offline = cfg.offline or not cfg.mospi_enabled

    def unavailable(self):
        return "skipped: offline or MoSPI disabled" if self.offline else None

    def status(self) -> dict:
        return {"name": self.name, "configured": not self.offline,
                "detail": f"MoSPI eSankhyiki discovery over {len(DATASETS) + len(STATIC)} datasets "
                          f"({', '.join(list(DATASETS) + list(STATIC))}), no key"}

    # ---------------------------------------------------------------- transport
    def _get(self, path: str, params: dict, ttl_days: int) -> Optional[dict]:
        url = f"{API}{path}?{urlencode(params)}" if params else f"{API}{path}"
        cache = DiskCache(self.cfg.cache_dir, "mospi_catalog", ttl=ttl_days * 24 * 3600)
        hit = cache.get(url)
        if hit is not None:
            return hit
        if self.offline:
            return cache.get(url, allow_stale=True)
        try:
            r = safe_get(self.session, with_params(f"{API}{path}", params), self.cfg.timeout, stream=False)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            data = r.json()
            data["_fetched"] = dt.date.today().isoformat()
            cache.set(url, data)
            return data
        except Exception as e:
            self.errors.append(redact(f"MoSPI {path}: {type(e).__name__}: {e}"))
            return cache.get(url, allow_stale=True)

    # ---------------------------------------------------------------- discovery
    def indicators(self) -> list[dict]:
        out = []
        for ds, (title, lpath, _rp, kws, ttl) in DATASETS.items():
            data = self._get(lpath, {}, 7) or {}
            items = data.get("data")
            if isinstance(items, dict):
                items = items.get("indicator") or []
            for it in items or []:
                label = (it.get("label") or it.get("description") or "").strip()
                if it.get("indicator_code") is not None and label:
                    out.append({"dataset": ds, "code": it["indicator_code"], "label": label, "title": title})
        for ds, (title, *_rest) in STATIC.items():
            out.append({"dataset": ds, "code": None, "label": title, "title": title})
        return out

    def candidates(self, text: str, k: int = 3) -> list[dict]:
        low = text.lower()
        want = terms(text)
        scored = []
        for ind in self.indicators():
            ds = ind["dataset"]
            kws = (DATASETS.get(ds) or STATIC.get(ds))[3 if ds in DATASETS else 3]
            lt = terms(ind["label"])
            overlap = len(want & lt)
            kw = kw_hits(low, kws)
            if not overlap and not kw:
                continue
            score = overlap / (len(lt) or 1) + 0.6 * min(kw, 2)
            if overlap == 0 and kw < 1:
                continue
            scored.append((score, ind))
        scored.sort(key=lambda x: -x[0])
        return [i for s, i in scored[:k] if s >= 0.6]

    def rows(self, ind: dict) -> tuple[list[dict], str, Optional[str]]:
        ds = ind["dataset"]
        if ds in STATIC:
            title, path, params, _kw, ttl, _vk = STATIC[ds]
            base = dict(params)
        else:
            title, _lp, path, _kw, ttl = DATASETS[ds]
            base = {"indicator_code": ind["code"], "Format": "JSON"}
        rows, fetched, url0 = [], None, None
        for page in range(1, self.max_pages + 1):
            params = dict(base, limit=self.page_size, page=page)
            data = self._get(path, params, ttl) or {}
            url0 = url0 or f"{API}{path}?{urlencode(params)}"
            fetched = fetched or data.get("_fetched")
            got = data.get("data") or []
            if not isinstance(got, list):
                break
            rows += got
            meta = data.get("meta_data") or {}
            if not got or page >= int(meta.get("totalPages") or 1):
                break
        return rows, url0 or "", fetched

    # ---------------------------------------------------------------- match
    def match(self, claim_text: str, numbers: list) -> list[dict]:
        if not numbers:
            return []
        out = []
        for ind in self.candidates(claim_text):
            rows, url, fetched = self.rows(ind)
            if not rows:
                continue
            ds = ind["dataset"]
            vk = STATIC[ds][5] if ds in STATIC else None
            title = (DATASETS.get(ds) or STATIC.get(ds))[0]
            label = f"{title}: {ind['label']}" if ds in DATASETS else title
            src = {"url": url, "title": f"{title} via eSankhyiki ({PORTAL})", "publisher": PUBLISHER,
                   "published": None, "as_of": f"retrieved {fetched}" if fetched else None, "retriever": "mospi"}
            fs = match_rows(claim_text, numbers, rows, label=label, source=src,
                            indicator_id=f"mospi:{ds}:{ind['code'] or 'all'}", value_key=vk)
            for f in fs:
                periods = sorted({str(r.get('year') or r.get('survey') or '') for r in rows if r})
                if periods:
                    f["official"]["as_of"] = (f["official"].get("as_of") or "") + f"; latest period in API: {periods[-1]}"
            out += fs
            if any(f["verdict"] != "UNVERIFIED" for f in fs):
                break
        from .tables import dedupe_findings
        return dedupe_findings(out)
