"""Live MoSPI eSankhyiki lookups (PLFS and National Accounts), cached on disk.

Data path: the public MoSPI API behind the eSankhyiki portal (https://api.mospi.gov.in), the same
endpoints the official `mospi-esankhyiki` Python package calls (github.com/nso-india/mospi-esankhyiki):

  PLFS   /api/plfs/getFilterByIndicatorId  (valid states, years, codes)
         /api/plfs/getData                 indicator_code 1=LFPR 2=WPR 3=UR; frequency_code 1=annual;
                                           year_type_code 1=agricultural year (July-June) 2=calendar year;
                                           weekly_status_code 1=PS+SS (usual status) 2=CWS
  NAS    /api/nas/getNASData               indicator_code 5=GDP; base_year 2022-23; series Current;
                                           frequency_code 1=annual -> current_price / constant_price (₹ crore)

Two backends:
  rest        (default) direct HTTPS calls with certificate verification ON. The server still needs legacy
              TLS renegotiation, which `net.LegacyTLSAdapter` enables (also through proxies).
  esankhyiki  the official package (`pip install mospi-esankhyiki`). Its 0.2.1 release defaults to a private
              test address and turns certificate checks off, so TruthLens points it at the public server,
              turns verification back on and silences its debug printing.

`MospiStore` wraps the curated snapshot with the same interface as `CuratedStore`: curated, documented
values are used first; live values fill periods, variants and geographies the snapshot lacks, and a live
cross-check is attached to curated values when MoSPI is reachable.
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io
import re
from typing import Optional
from urllib.parse import urlencode

from ..config import Config, redact
from ..net import DiskCache, make_session, safe_get, with_params

PLFS_INDICATOR = {"unemployment_rate": 3, "lfpr": 1}
PLFS_VARIANTS = {  # variant -> overrides
    "usual_status": {"weekly_status_code": 1},
    "cws": {"weekly_status_code": 2},
    "youth_usual_status": {"weekly_status_code": 1, "age_code": 2},
    "female_usual_status": {"weekly_status_code": 1, "gender_code": 2},
    "default": {"weekly_status_code": 1},
}
NAS_INDICATORS = {"gdp_nominal": ("current_price", False), "gdp_real": ("constant_price", False),
                  "gdp_growth_nominal": ("current_price", True), "gdp_growth_real": ("constant_price", True)}
SUPPORTED = set(PLFS_INDICATOR) | set(NAS_INDICATORS)
PORTAL = "https://esankhyiki.mospi.gov.in"


def _today() -> str:
    return dt.date.today().isoformat()


class MospiClient:
    def __init__(self, cfg: Config, session=None):
        self.cfg = cfg
        self.base = cfg.mospi_base_url.rstrip("/")
        self.session = session or make_session(legacy_tls=True)
        self.cache = DiskCache(cfg.cache_dir, "mospi", ttl=7 * 24 * 3600)
        self.offline = cfg.offline or not cfg.mospi_enabled
        self.errors: list[str] = []
        self.calls = 0
        self._lib = None

    # ---------- transport ----------
    def _get(self, path: str, params: dict) -> Optional[dict]:
        url = f"{self.base}{path}?{urlencode(params)}"
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        if self.offline:
            return self.cache.get(url, allow_stale=True)
        try:
            self.calls += 1
            if self.cfg.mospi_backend == "esankhyiki" and path.endswith(("getData", "getNASData")):
                data = self._via_library(path, params)
            else:
                r = safe_get(self.session, with_params(f"{self.base}{path}", params), self.cfg.timeout, stream=False)
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = r.json()
            self.cache.set(url, data)
            return data
        except Exception as e:
            self.errors.append(redact(f"MoSPI {path}: {type(e).__name__}: {e}"))
            return self.cache.get(url, allow_stale=True)

    def _via_library(self, path: str, params: dict) -> dict:
        if self._lib is None:
            import esankhyiki  # type: ignore
            from ..net import LegacyTLSAdapter
            client = esankhyiki._client
            client.base_url = self.base
            client.session.verify = True
            client.session.mount("https://", LegacyTLSAdapter())
            self._lib = esankhyiki
        dataset = "PLFS" if "plfs" in path else "NAS"
        with contextlib.redirect_stdout(io.StringIO()):  # the package prints every raw response
            out = self._lib.get_data(dataset, dict(params))
        return {"data": out} if isinstance(out, list) else out

    @staticmethod
    def url(base: str, path: str, params: dict) -> str:
        return f"{base}{path}?{urlencode(params)}"

    # ---------- PLFS ----------
    def plfs_states(self) -> dict:
        data = self._get("/api/plfs/getFilterByIndicatorId", {"indicator_code": 3, "frequency_code": 1})
        out = {}
        for s in ((data or {}).get("data") or {}).get("state", []):
            out[s["description"].lower().replace("&", "and")] = s["state_code"]
        return out

    def plfs(self, indicator_code: int, year: str, state_code: int = 99, gender_code: int = 3, age_code: int = 1,
             sector_code: int = 3, weekly_status_code: int = 1) -> Optional[dict]:
        params = {"indicator_code": indicator_code, "frequency_code": 1,
                  "year_type_code": 1 if "-" in year else 2, "year": year, "state_code": state_code,
                  "gender_code": gender_code, "age_code": age_code, "sector_code": sector_code,
                  "weekly_status_code": weekly_status_code, "religion_code": 1, "social_category_code": 1,
                  "education_code": 0, "Format": "JSON"}
        data = self._get("/api/plfs/getData", params)
        rows = (data or {}).get("data") or []
        if not isinstance(rows, list) or len(rows) != 1:
            return None
        row = rows[0]
        try:
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            return None
        return {"value": value, "row": row, "url": self.url(self.base, "/api/plfs/getData", params)}

    # ---------- NAS ----------
    def nas_gdp(self, year: str, base_year: str = "2022-23") -> Optional[dict]:
        params = {"base_year": base_year, "series": "Current", "frequency_code": 1, "indicator_code": 5,
                  "year": year, "Format": "JSON"}
        data = self._get("/api/nas/getNASData", params)
        rows = (data or {}).get("data") or []
        if not isinstance(rows, list) or len(rows) != 1:
            return None
        row = rows[0]
        try:
            cur, con = float(row["current_price"]), float(row["constant_price"])
        except (KeyError, TypeError, ValueError):
            return None
        return {"current_price": cur, "constant_price": con, "revision": row.get("revision"),
                "unit": row.get("unit"), "row": row, "url": self.url(self.base, "/api/nas/getNASData", params)}


def _prev_fy(p: str) -> Optional[str]:
    m = re.fullmatch(r"(\d{4})-(\d{2})", p)
    if not m:
        return None
    a = int(m.group(1)) - 1
    return f"{a}-{str(a + 1)[2:]}"


class MospiStore:
    """CuratedStore-compatible view: curated first, MoSPI live for gaps (and as a cross-check)."""

    def __init__(self, curated, client: MospiClient, geography: str = "India"):
        self.curated = curated
        self.client = client
        self.geography = geography
        self._states = None
        self._memo: dict = {}

    # CuratedStore interface ---------------------------------------------------
    @property
    def meta(self):
        return self.curated.meta

    @property
    def records(self):
        return self.curated.records

    def for_geography(self, geography: str) -> "MospiStore":
        s = MospiStore(self.curated, self.client, geography)
        s._states = self._states
        s._memo = self._memo
        return s

    def supports_geography(self, indicator: str, geography: str) -> bool:
        return indicator in PLFS_INDICATOR and self._geo_params(geography) is not None

    def find(self, indicator: str, period: Optional[str] = None, variant: Optional[str] = None,
             status: Optional[str] = None, stage: Optional[str] = None) -> list[dict]:
        national = self.geography == "India"
        recs = self.curated.find(indicator, period=period, variant=variant, status=status, stage=stage) if national else []
        if period is None or indicator not in SUPPORTED or stage is not None:
            return recs
        if status not in (None, "current"):
            return recs
        live = self.live(indicator, period, variant or "default")
        if live is None:
            return recs
        if not recs:
            return [live]
        out = []
        for r in recs:
            if r["status"] == "current" and abs(float(r["value"]) - float(live["value"])) > 1e-9:
                r = copy.copy(r)
                r["live"] = {"value": live["value"], "url": live["source"]["url"],
                             "agrees": _agrees(indicator, r["value"], live["value"]),
                             "vintage": live.get("vintage")}
            elif r["status"] == "current":
                r = copy.copy(r)
                r["live"] = {"value": live["value"], "url": live["source"]["url"], "agrees": True,
                             "vintage": live.get("vintage")}
            out.append(r)
        return out

    def periods(self, indicator: str, variant: Optional[str] = None) -> list[str]:
        return self.curated.periods(indicator, variant) if self.geography == "India" else []

    def latest(self, indicator: str, variant: Optional[str] = None) -> Optional[dict]:
        return self.curated.latest(indicator, variant) if self.geography == "India" else None

    def coverage(self) -> dict:
        return self.curated.coverage()

    # live ----------------------------------------------------------------------
    def _geo_params(self, geography: str) -> Optional[dict]:
        g = geography.strip()
        if g == "India":
            return {"state_code": 99, "sector_code": 3}
        m = re.fullmatch(r"India \((rural|urban)\)", g)
        if m:
            return {"state_code": 99, "sector_code": 1 if m.group(1) == "rural" else 2}
        if self._states is None:
            self._states = self.client.plfs_states() or {}
        key = g.lower().replace("&", "and")
        aliases = {"orissa": "odisha", "jammu and kashmir": "jammu and kashmir"}
        key = aliases.get(key, key)
        for name, code in self._states.items():
            if name == key:
                return {"state_code": code, "sector_code": 3}
        return None

    def live(self, indicator: str, period: str, variant: str) -> Optional[dict]:
        key = (indicator, period, variant, self.geography)
        if key in self._memo:
            return self._memo[key]
        rec = None
        try:
            if indicator in PLFS_INDICATOR:
                rec = self._live_plfs(indicator, period, variant)
            elif indicator in NAS_INDICATORS and self.geography == "India":
                rec = self._live_nas(indicator, period)
        except Exception as e:  # never let a live source break a check
            self.client.errors.append(redact(f"MoSPI live {indicator} {period}: {e}"))
            rec = None
        self._memo[key] = rec
        return rec

    def _live_plfs(self, indicator: str, period: str, variant: str) -> Optional[dict]:
        if not re.fullmatch(r"\d{4}(-\d{2})?", period):
            return None
        geo = self._geo_params(self.geography)
        if geo is None or variant not in PLFS_VARIANTS:
            return None
        params = dict(geo)
        params.update(PLFS_VARIANTS[variant])
        got = self.client.plfs(PLFS_INDICATOR[indicator], period, **params)
        if not got:
            return None
        row = got["row"]
        label = (f"PLFS {row.get('year')} ({row.get('year_type')}), {row.get('indicator')}, {row.get('state')}, "
                 f"{row.get('sector')}, {row.get('gender')}, {row.get('AgeGroup')}, {row.get('weekly_status')}")
        return {
            "indicator": indicator, "variant": variant, "period": period, "value": got["value"], "unit": "percent",
            "base": None, "vintage": f"MoSPI eSankhyiki API, fetched {_today()}", "stage": None, "status": "current",
            "note": None, "display": None, "geography": self.geography, "live_source": True,
            "source": {"publisher": "MoSPI (NSO), eSankhyiki API", "title": label, "url": got["url"],
                       "published": "live API", "accessed": _today(), "key": "MOSPI-API-PLFS"},
        }

    def _live_nas(self, indicator: str, period: str) -> Optional[dict]:
        field, growth = NAS_INDICATORS[indicator]
        cur = self.client.nas_gdp(period)
        if not cur:
            return None
        val = cur[field] * 1e7  # ₹ crore -> ₹
        title = f"NAS (base 2022-23), GDP {period}, {cur.get('revision') or ''}, {field.replace('_', ' ')}"
        url = cur["url"]
        display = None
        if growth:
            prev_p = _prev_fy(period)
            prev = self.client.nas_gdp(prev_p) if prev_p else None
            if not prev or not prev[field]:
                return None
            val = (cur[field] / prev[field] - 1) * 100
            title = (f"NAS (base 2022-23), GDP growth {period} computed from {field.replace('_', ' ')} "
                     f"{cur[field]:,.0f} / {prev[field]:,.0f} ₹ crore ({cur.get('revision') or ''})")
            display = f"{val:.1f}%"
        return {
            "indicator": indicator, "variant": "default", "period": period, "value": val,
            "unit": "percent" if growth else "inr", "base": "2022-23",
            "vintage": f"{cur.get('revision') or 'latest'} via MoSPI eSankhyiki API, fetched {_today()}",
            "stage": None, "status": "current", "note": None, "display": display, "geography": "India",
            "live_source": True,
            "source": {"publisher": "MoSPI (NSO), eSankhyiki API", "title": title, "url": url,
                       "published": "live API", "accessed": _today(), "key": "MOSPI-API-NAS"},
        }


def _agrees(indicator: str, a: float, b: float) -> bool:
    if indicator in ("gdp_nominal", "gdp_real"):
        return abs(a - b) <= abs(a) * 0.0005
    return abs(round(a, 1) - round(b, 1)) < 0.05
