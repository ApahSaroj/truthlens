"""NDAP (National Data and Analytics Platform, NITI Aayog): catalogue search without a key (pointers only).

Observed on 2 Nov 2026 by reading the calls ndap.niti.gov.in's own JavaScript makes (API base in its config chunk:
https://loadqa.ndapapi.com):

  catalogue  GET  https://loadqa.ndapapi.com/v1/search?query=<words>&search=Variables,DatasetInfo&domain=ndap
             public; needs the site's Origin/Referer headers (without them: {"Message": "Invalid Request"}).
             Returns Records.results[]: object_type (Dataset | Collection), id, name, details{ministry, sector,
             LastUpdatedDate, startingYear, endingYear, LocationGranularity, collectionName}, variable[{name}].
             This is not a documented public API: it is the call the NDAP site makes itself, on a host named
             "loadqa", and it can change or stop without notice. Re-checked live on 3 Nov 2026 (it answered a
             search for "ground water resources" with CGWB datasets).
  v0.5.3: the NDAP *data rows* path (a token from an "NDAP profile", NDAP_API_TOKEN) was removed. It was never
  verified: no token could be obtained and the row layout was only ever tested on a synthetic fixture.

Catalogue hits are *pointers*: evidence of kind "catalogue" that names the right dataset to cite (title, ministry,
years, last updated). They are never shown to the judge, so metadata alone can never make a claim SUPPORTED.
"""
from __future__ import annotations



from urllib.parse import urlencode

from ..config import Config, redact
from ..model import Claim, Evidence
from ..net import DiskCache, FetchError, get_json, make_session
from .base import Retriever, terms

NDAP_API = "https://loadqa.ndapapi.com"
NDAP_SITE = "https://ndap.niti.gov.in"
SITE_HEADERS = {"Origin": NDAP_SITE, "Referer": NDAP_SITE + "/", "Accept": "application/json, text/plain, */*"}


def dataset_url(ds_id) -> str:
    return f"{NDAP_SITE}/dataset/{ds_id}"


class NDAPCatalog(Retriever):
    """Retriever 'ndap': catalogue pointers for figures (no key)."""
    name = "ndap"

    def __init__(self, cfg: Config, session=None):
        super().__init__(cfg)
        self.session = session if session is not None else make_session()
        self.cache = DiskCache(cfg.cache_dir, "ndap", ttl=7 * 24 * 3600)

    def status(self) -> dict:
        return self._status(not self.cfg.offline, "NDAP catalogue search (loadqa.ndapapi.com/v1/search, undocumented; "
                                                  "names the dataset to cite, never used as evidence)")

    def search(self, query: str) -> list[dict]:
        url = f"{NDAP_API}/v1/search?" + urlencode({"query": query, "search": "Variables,DatasetInfo", "domain": "ndap"})
        hit = self.cache.get(url)
        if hit is not None:
            return hit
        if self.cfg.offline:
            return self.cache.get(url, allow_stale=True) or []
        try:
            d = get_json(self.session, url, self.cfg.timeout, SITE_HEADERS)
            recs = (d.get("Records") or {}) if isinstance(d, dict) else {}
            res = recs.get("results") if isinstance(recs, dict) else None
            if not isinstance(res, list):
                raise FetchError(str(d.get("Message") or "unexpected NDAP search response")[:80])
            keep = []
            for r in res[:25]:
                if not isinstance(r, dict) or r.get("object_type") != "Dataset":
                    continue
                det = r.get("details") or {}
                keep.append({"id": r.get("id"), "name": r.get("name") or "", "ministry": det.get("ministry") or "",
                             "sector": det.get("sector") or "", "updated": det.get("LastUpdatedDate") or "",
                             "from": det.get("startingYear"), "to": det.get("endingYear"),
                             "granularity": det.get("LocationGranularity") or "", "frequency": det.get("frequency") or "",
                             "collection": det.get("collectionName") or "",
                             "variables": [v.get("name") for v in (r.get("variable") or []) if isinstance(v, dict)][:20],
                             "matched": r.get("matched_interpretation") or ""})
            self.cache.set(url, keep)
            return keep
        except Exception as e:
            self.errors.append(redact(f"NDAP search: {type(e).__name__}: {str(e)[:120]}"))
            return self.cache.get(url, allow_stale=True) or []

    def best(self, text: str, k: int = 2) -> list[dict]:
        from .parliament import query_terms
        words = query_terms(text, 6)
        if len(words) < 2:
            return []
        want = terms(text)
        out = []
        for ds in self.search(" ".join(words)):
            dt_terms = terms(" ".join([ds["name"]] + ds["variables"]))
            cover = len(want & dt_terms) / (len(want) or 1)
            if cover >= 0.3 and len(want & terms(ds["name"])) >= 1:
                out.append(dict(ds, cover=round(cover, 2)))
        out.sort(key=lambda d: -d["cover"])
        return out[:k]

    def retrieve(self, claim: Claim, k: int = 2) -> list[Evidence]:
        out = []
        for ds in self.best(claim.text, k):
            years = f"{ds['from']}–{ds['to']}" if ds.get("from") else ""
            snippet = (f"NDAP dataset {ds['id']}: {ds['name']}. {ds['ministry']}; {ds['granularity']} {ds['frequency']} "
                       f"{years}; last updated {ds['updated'] or 'n.a.'}. Variables: {', '.join(ds['variables'][:6])}.")
            out.append(Evidence(retriever="ndap", source_url=dataset_url(ds["id"]), title=ds["name"], snippet=snippet,
                                date=ds["updated"] or None, publisher=f"NDAP (NITI Aayog); source: {ds['ministry']}",
                                official=False, score=ds["cover"], kind="catalogue", source_type="NDAP",
                                as_of=(f"updated {ds['updated']}" if ds["updated"] else None),
                                meta={"dataset_id": ds["id"], "collection": ds["collection"], "pointer": True}))
        return out
