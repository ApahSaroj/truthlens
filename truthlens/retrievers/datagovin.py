"""data.gov.in Open Government Data (OGD) API: catalogue discovery, resource fetch and row matching.

v0.3 adds a local catalogue index (SQLite FTS5, BM25) built from the /lists listing by
`truthlens datagov sync`, so a claim can be routed to candidate resources without a hand-made map;
the hand-made map in truthlens.toml still works and takes precedence.

/lists parameters are the ones the community clients send (verified in their source code, 1 Nov 2026):
  datagovindia (Python) 1.0.2: format=json, notfilters[source]=visualize.data.gov.in, filters[active]=1,
                               sort[updated]=desc, offset, limit, optional api-key; record fields index_name,
                               title, desc, org_type, org[], sector[], source, field[{id,name,type}],
                               created_date, updated_date
  datagovindia (R), R/utils.R: the same URL for its server check
Not reachable from our test network (proxy 502 / Akamai 503), so this module is tested against fixtures
written in that format only. See docs/SOURCES.md.

Original v0.2 notes (bring your own free key: DATAGOVIN_API_KEY):

Endpoints (OGD Platform India, NIC):
  GET https://api.data.gov.in/resource/{resource_id}?api-key=KEY&format=json&offset=0&limit=100&filters[field]=value
      Per-resource data API. Each dataset's resource id is shown on its data.gov.in "API" page.
  GET https://api.data.gov.in/lists?format=json&filters[...]=...&offset=0&limit=...
      Resource listing used by community clients (datagovindia for R and Python) to sync metadata.
      data.gov.in does not document a full-text catalogue search API, so `search_catalog` is a
      best-effort title filter on this listing and is marked experimental.

Because resource ids are not discoverable reliably, retrieval is driven by a resource map in
truthlens.toml:

  [datagovin.resources.jjm_tap_connections]
  id = "<resource uuid from data.gov.in>"
  keywords = ["tap water", "jal jeevan"]
  title = "State-wise tap water connections (Jal Jeevan Mission)"
  filters = { }          # optional fixed filters[...]
  limit = 50

For each claim whose text contains one of an entry's keywords, the rows are fetched (cached for a day)
and the rows that best overlap the claim are returned as evidence snippets ("field: value; ...").
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlencode

from ..config import Config, redact
from ..model import Claim, Evidence
from ..net import DiskCache, make_session, safe_get, with_params
from .base import Retriever, terms

API = "https://api.data.gov.in"
# Published on data.gov.in's own API help pages and in the datagovindia R docs as a demo key. NOT verified
# from our network (unreachable). Used only when TRUTHLENS_DATAGOVIN_SAMPLE_KEY=1, never by default.
SAMPLE_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
LISTS_BASE = {"format": "json", "notfilters[source]": "visualize.data.gov.in", "filters[active]": 1, "sort[updated]": "desc"}


class DataGovInClient:
    def __init__(self, cfg: Config, session=None):
        self.cfg = cfg
        self.session = session or make_session()
        self.cache = DiskCache(cfg.cache_dir, "datagovin", ttl=24 * 3600)
        self.errors: list[str] = []

    @property
    def key(self) -> Optional[str]:
        k = self.cfg.secret("DATAGOVIN_API_KEY")
        if k:
            return k
        import os
        if os.environ.get("TRUTHLENS_DATAGOVIN_SAMPLE_KEY", "") in ("1", "true", "yes"):
            return SAMPLE_KEY
        return None

    @property
    def using_sample_key(self) -> bool:
        return self.key == SAMPLE_KEY

    def lists(self, offset: int = 0, limit: int = 1000) -> Optional[dict]:
        """One page of the resource listing (key optional: sent when configured)."""
        params = dict(LISTS_BASE, offset=offset, limit=limit)
        return self._get("/lists", params, key_optional=True)

    def _get(self, path: str, params: dict, key_optional: bool = False) -> Optional[dict]:
        public = f"{API}{path}?{urlencode(params)}"   # cache key and citation URL, without the key
        cached = self.cache.get(public)
        if cached is not None:
            return cached
        if self.cfg.offline or (not self.key and not key_optional):
            return self.cache.get(public, allow_stale=True)
        q = dict(params)
        if self.key:
            q["api-key"] = self.key
        try:
            r = safe_get(self.session, with_params(f"{API}{path}", q), self.cfg.timeout, stream=False)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            data = r.json()
            if isinstance(data, dict) and data.get("status") == "error":
                raise RuntimeError(str(data.get("message", "error"))[:200])
            self.cache.set(public, data)
            return data
        except Exception as e:
            self.errors.append(redact(f"data.gov.in {path}: {type(e).__name__}: {e}"))
            return self.cache.get(public, allow_stale=True)

    def resource(self, resource_id: str, filters: Optional[dict] = None, limit: int = 100, offset: int = 0) -> Optional[dict]:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", resource_id or ""):
            raise ValueError("data.gov.in resource ids are UUIDs")
        params = {"format": "json", "offset": offset, "limit": limit}
        for k, v in (filters or {}).items():
            params[f"filters[{k}]"] = v
        return self._get(f"/resource/{resource_id}", params)

    def search_catalog(self, query: str, limit: int = 10) -> list[dict]:
        """Experimental: title filter on the /lists resource listing (not a documented search API)."""
        data = self._get("/lists", {"format": "json", "filters[title]": query, "offset": 0, "limit": limit}) or {}
        out = []
        for r in data.get("records", []) or []:
            out.append({"id": r.get("index_name"), "title": r.get("title"), "org": r.get("org"),
                        "updated": r.get("updated_date"), "source": r.get("source")})
        return out


def _row_text(row: dict) -> str:
    return "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in row.items() if v not in (None, "") and k != "resource_uuid")


class DataGovInRetriever(Retriever):
    name = "datagovin"
    needs = ("DATAGOVIN_API_KEY",)

    def __init__(self, cfg: Config, session=None):
        super().__init__(cfg)
        self.client = DataGovInClient(cfg, session)

    def status(self) -> dict:
        n = len(self.cfg.datagovin_resources)
        if not self.client.key:
            return self._status(False, f"set DATAGOVIN_API_KEY (free at data.gov.in) and map resources in truthlens.toml ({n} mapped)")
        return self._status(True, f"{n} resource(s) mapped in truthlens.toml")

    def retrieve(self, claim: Claim, k: int = 3) -> list[Evidence]:
        text = claim.text.lower()
        out: list[Evidence] = []
        for name, res in (self.cfg.datagovin_resources or {}).items():
            kws = [w.lower() for w in res.get("keywords", [])]
            if not kws or not any(w in text for w in kws):
                continue
            try:
                data = self.client.resource(res["id"], res.get("filters"), int(res.get("limit", 100)))
            except ValueError:
                continue
            rows = (data or {}).get("records") or []
            want = terms(claim.text)
            scored = []
            for row in rows:
                rt = _row_text(row)
                st = terms(rt)
                score = len(want & st) / (len(want) or 1)
                scored.append((score, rt))
            scored.sort(reverse=True)
            for score, rt in scored[:k]:
                if score <= 0:
                    continue
                out.append(Evidence(retriever=self.name, source_url=f"https://www.data.gov.in/resource/{res['id']}",
                                    title=res.get("title") or (data or {}).get("title") or name, snippet=rt[:900],
                                    date=(data or {}).get("updated_date"), publisher=", ".join((data or {}).get("org") or [])
                                    or "data.gov.in (OGD Platform India)", official=True, score=score, kind="datapoint",
                                    meta={"resource_id": res["id"]}))
        return out


# ====================================================================== v0.3: catalogue index + matcher
import json  # noqa: E402
import sqlite3  # noqa: E402
import threading  # noqa: E402


class CatalogIndex:
    """Local index of data.gov.in resources (title, ministry/org, sector, fields, updated date) with FTS5/BM25."""

    def __init__(self, path):
        from pathlib import Path
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS res (id TEXT PRIMARY KEY, title TEXT, descr TEXT, org TEXT,
                               sector TEXT, source TEXT, fields TEXT, updated TEXT, created TEXT)""")
            self.db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS res_fts USING fts5(id UNINDEXED, title, descr, org, sector,
                               fields, tokenize='porter unicode61')""")
            self.db.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
            self.db.commit()

    def count(self) -> int:
        with self.lock:
            return self.db.execute("SELECT count(*) FROM res").fetchone()[0]

    def meta(self, k: str) -> Optional[str]:
        with self.lock:
            r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
            return r[0] if r else None

    def set_meta(self, k: str, v: str) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta(k,v) VALUES (?,?)", (k, v))
            self.db.commit()

    @staticmethod
    def _flat(x) -> str:
        if isinstance(x, list):
            return " | ".join(CatalogIndex._flat(i) for i in x if i)
        return str(x or "")

    def upsert(self, records: list[dict]) -> int:
        n = 0
        with self.lock:
            for r in records:
                rid = r.get("index_name")
                if not rid or not re.fullmatch(r"[0-9a-fA-F-]{36}", rid):
                    continue
                fields = " | ".join(f"{f.get('id', '')} {f.get('name', '')}".strip() for f in (r.get("field") or [])
                                    if isinstance(f, dict))
                row = (rid, r.get("title") or "", r.get("desc") or "", self._flat(r.get("org")), self._flat(r.get("sector")),
                       r.get("source") or "", fields, _iso_date(r.get("updated_date")), _iso_date(r.get("created_date")))
                self.db.execute("DELETE FROM res_fts WHERE id=?", (rid,))
                self.db.execute("INSERT OR REPLACE INTO res VALUES (?,?,?,?,?,?,?,?,?)", row)
                self.db.execute("INSERT INTO res_fts(id,title,descr,org,sector,fields) VALUES (?,?,?,?,?,?)",
                                (rid, row[1], row[2], row[3], row[4], row[6]))
                n += 1
            self.db.commit()
        return n

    def search(self, text: str, k: int = 5) -> list[dict]:
        want = [t for t in sorted(terms(text)) if re.fullmatch(r"[a-z\-]+", t)]
        if not want:
            return []
        q = " OR ".join(f'"{t}"' for t in want)
        with self.lock:
            try:
                rows = self.db.execute(
                    """SELECT r.id,r.title,r.descr,r.org,r.sector,r.fields,r.updated,bm25(res_fts, 0, 5.0, 1.0, 2.0, 1.0, 1.0) AS s
                       FROM res_fts JOIN res r ON r.id=res_fts.id WHERE res_fts MATCH ? ORDER BY s LIMIT ?""",
                    (q, k * 6)).fetchall()
            except sqlite3.OperationalError:
                return []
        out = []
        for rid, title, descr, org, sector, fields, updated, s in rows:
            tt = terms(f"{title} {fields}")
            cover = len(set(want) & tt) / len(want)
            out.append({"id": rid, "title": title, "org": org, "sector": sector, "fields": fields, "updated": updated,
                        "bm25": -s, "cover": cover})
        out = [o for o in out if o["cover"] >= 0.3]
        out.sort(key=lambda o: (-round(o["cover"], 1), -o["bm25"]))
        return out[:k]


def sync_catalog(client: DataGovInClient, index: CatalogIndex, max_records: int = 200000, page: int = 1000,
                 progress=None) -> dict:
    """Page through /lists (newest first) into the local index. Stops at max_records or an empty page."""
    done, total = 0, None
    for offset in range(0, max_records, page):
        data = client.lists(offset=offset, limit=page)
        if not data:
            break
        total = data.get("total", total)
        recs = data.get("records") or []
        if not recs:
            break
        done += index.upsert(recs)
        if progress:
            progress(done, total)
        if total is not None and offset + page >= int(total):
            break
    if done:
        index.set_meta("synced_at", __import__("datetime").datetime.now().isoformat(timespec="seconds"))
        index.set_meta("total_reported", str(total))
    return {"indexed": done, "total_reported": total, "errors": list(client.errors)}


def _iso_date(v) -> str:
    """data.gov.in dates as ISO text (epoch seconds/milliseconds are converted; other text is kept)."""
    import datetime as _dt
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit() and len(v) >= 9):
        x = float(v)
        x = x / 1000 if x > 1e11 else x
        return _dt.datetime.fromtimestamp(x, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(v or "")


def _with_title_period(rows: list[dict], title: str) -> list[dict]:
    """Resources that hold one snapshot ('... as on 31-03-2026') carry no year column: take the year from the title
    so a claim's period can still be matched. Rows that already name a period are left alone."""
    from .tables import row_period
    if any(row_period(r) for r in rows[:20]):
        return rows
    m = re.search(r"(?:as on|as of|for|in)\s+(?:\d{1,2}[-./]\d{1,2}[-./])?((?:19|20)\d{2}(?:\s*-\s*\d{2})?)", title or "", re.I)
    if not m:
        return rows
    y = re.sub(r"\s+", "", m.group(1))
    return [dict(r, year=y) for r in rows]


def _value_field(fields: str, claim_text: str) -> Optional[str]:
    """Pick the value column whose name best matches the claim (fields as indexed: 'id Name | id Name')."""
    best, score = None, 0
    want = terms(claim_text)
    for part in (fields or "").split(" | "):
        fid = part.split(" ", 1)[0]
        if not fid or fid.lower().startswith("state") or fid in ("year", "financial_year"):
            continue
        sc = len(want & terms(part.replace("_", " ")))
        if sc > score:
            best, score = fid, sc
    return best


def _title_sim(a: str, b: str) -> float:
    ta, tb = terms(a), terms(b)
    return len(ta & tb) / (len(ta | tb) or 1)


class DataGovInMatcher:
    """Claim -> candidate resources (catalogue index, newest first) -> rows -> tables.match_rows."""
    name = "datagovin-catalog"

    def __init__(self, cfg: Config, client: DataGovInClient, index: Optional[CatalogIndex] = None):
        self.cfg = cfg
        self.client = client
        self._index = index
        self.errors: list[str] = []

    @property
    def index(self) -> CatalogIndex:
        if self._index is None:
            self._index = CatalogIndex(self.cfg.cache_dir / "datagovin_catalog.sqlite")
        return self._index

    def status(self) -> dict:
        n = self.index.count()
        key = "free key set" if self.client.key and not self.client.using_sample_key else (
            "public sample key (opt-in, limited)" if self.client.key else "no key: catalogue search only, rows need a free key")
        return {"name": self.name, "configured": n > 0,
                "detail": f"{n} resources in the local catalogue index (truthlens datagov sync); {key}"}

    def unavailable(self) -> Optional[str]:
        if not self.client.key:
            return "skipped: needs a free data.gov.in key"
        if self.index.count() == 0:
            return "skipped: catalogue index empty (run truthlens datagov sync)"
        return None

    def candidates(self, text: str, k: int = 4) -> list[dict]:
        return self.index.search(text, k)

    def match(self, claim_text: str, numbers: list) -> list[dict]:
        from .tables import match_rows
        if not numbers or not self.client.key:
            return []
        cands = self.candidates(claim_text)
        cands.sort(key=lambda c: c["updated"] or "", reverse=True)        # freshness: newest release first
        results = []
        for c in cands:
            data = self.client.resource(c["id"], None, 1000 if not self.client.using_sample_key else 10)
            rows = (data or {}).get("records") or []
            if not rows:
                continue
            rows = _with_title_period(rows, (data or {}).get("title") or c["title"])
            updated = (data or {}).get("updated_date") or c["updated"]
            org = ", ".join((data or {}).get("org") or []) if isinstance((data or {}).get("org"), list) else (c["org"] or "")
            src = {"url": f"{API}/resource/{c['id']}?format=json", "title": (data or {}).get("title") or c["title"],
                   "publisher": f"{org or 'Government of India'} via data.gov.in (OGD Platform India)",
                   "published": str(updated or "")[:10] or None, "as_of": f"updated on {str(updated)[:10]}" if updated else None,
                   "retriever": "datagovin"}
            vk = _value_field(c.get("fields") or "", claim_text)
            if vk and not any(vk in r for r in rows[:5]):
                vk = None
            fs = match_rows(claim_text, numbers, rows, label=src["title"], source=src,
                            indicator_id=f"datagovin:{c['id']}", min_relevance=0.4, value_key=vk)
            results.append((c, fs))
        # freshness across releases: a match only in an older resource while a newer similar one differs
        from ..model import _human_date as _hd
        out = []
        newest = next(((c, fs) for c, fs in results if fs), None)
        for c, fs in results:
            for f in fs:
                if f["verdict"] == "MATCH" and newest and newest[0]["id"] != c["id"] and _title_sim(c["title"], newest[0]["title"]) >= 0.5:
                    nf = next((x for x in newest[1] if x["claimed"] == f["claimed"]), None)
                    if nf and nf["verdict"] in ("MISMATCH", "UNVERIFIED") and nf["official"]["value"] != f["official"]["value"]:
                        f = dict(f, verdict="CLOSE", official=nf["official"],
                                 reason=f"Matches an older release (updated {_hd(c['updated'][:10])}); the newer release "
                                        f"(updated {_hd(newest[0]['updated'][:10])}) says {nf['official']['display']}.")
                        from ..model import _human_date
                        f["warnings"] = f["warnings"] + [{"code": "superseded", "severity": "warn",
                                                          "message": f"Superseded: a newer release of this dataset (updated "
                                                                     f"{_human_date(newest[0]['updated'][:10])}) says "
                                                                     f"{nf['official']['display']}; the draft's {f['claimed']} "
                                                                     f"is from the release updated {_human_date(c['updated'][:10])}."}]
                out.append(f)
            if any(f["verdict"] in ("MATCH", "CLOSE") for f in out):
                break
        from .tables import dedupe_findings
        return dedupe_findings(out)
