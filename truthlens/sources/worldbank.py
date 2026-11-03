"""World Bank WDI API connector (api.worldbank.org/v2) for India, with an on-disk cache.

Used only as a secondary fallback when the curated official dataset has no value.
WDI years for India's national accounts are financial years labelled by their
starting year (WDI "2024" = FY 2024-25); CPI and population are calendar years.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import requests  # noqa: F401  (kept for callers that pass a requests.Session)

from ..net import make_session, safe_get

API = "https://api.worldbank.org/v2/country/IND/indicator/{code}?format=json&per_page=200"
DEFAULT_TTL = 7 * 24 * 3600


def default_cache_dir() -> Path:
    base = os.environ.get("TRUTHLENS_CACHE") or os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "truthlens")
    return Path(base) / "worldbank"


class WorldBankClient:
    def __init__(self, cache_dir: Optional[Path] = None, timeout: float = 10.0, ttl: int = DEFAULT_TTL,
                 offline: bool = False, session: Optional[requests.Session] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.timeout = timeout
        self.ttl = ttl
        self.offline = offline
        self.session = session or make_session()
        self.errors: list[str] = []

    def _cache_path(self, code: str) -> Path:
        return self.cache_dir / f"IND_{code}.json"

    def _read_cache(self, code: str) -> Optional[dict]:
        p = self._cache_path(code)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except (OSError, ValueError):
                return None
        return None

    def series(self, code: str) -> Optional[dict]:
        """Return {"values": {year: value}, "lastupdated": str, "fetched_at": float, "url": str} or None."""
        cached = self._read_cache(code)
        fresh = cached and (time.time() - cached.get("fetched_at", 0) < self.ttl)
        if fresh or (cached and self.offline):
            return cached
        if self.offline:
            return None
        url = API.format(code=code)
        try:
            r = safe_get(self.session, url, self.timeout, {"User-Agent": "TruthLens/0.1"}, stream=False)
            r.raise_for_status()
            payload = r.json()
            meta, rows = payload[0], payload[1] or []
            values = {row["date"]: row["value"] for row in rows if row.get("value") is not None}
            out = {"code": code, "values": values, "lastupdated": meta.get("lastupdated"),
                   "fetched_at": time.time(), "url": url.replace("&per_page=200", "")}
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self._cache_path(code).write_text(json.dumps(out))
            except OSError:
                pass
            return out
        except Exception as e:  # network down, bad JSON, rate limit: fall back to stale cache
            self.errors.append(f"World Bank {code}: {e}")
            return cached

    def value(self, code: str, year: str) -> Optional[tuple[float, dict]]:
        s = self.series(code)
        if not s:
            return None
        v = s["values"].get(str(year))
        if v is None:
            return None
        return float(v), s
