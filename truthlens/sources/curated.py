"""Curated offline dataset of official Indian statistics (data/india_official.json)."""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Optional


@lru_cache(maxsize=1)
def load_curated() -> dict:
    text = resources.files("truthlens.data").joinpath("india_official.json").read_text(encoding="utf-8")
    return json.loads(text)


class CuratedStore:
    def __init__(self, data: Optional[dict] = None):
        self.data = data or load_curated()
        self.records = self.data["records"]

    @property
    def meta(self):
        return self.data["meta"]

    def find(self, indicator: str, period: Optional[str] = None, variant: Optional[str] = None,
             status: Optional[str] = None, stage: Optional[str] = None, geography: Optional[str] = None) -> list[dict]:
        if geography not in (None, "India"):
            return []  # the curated snapshot is all-India only
        out = []
        for r in self.records:
            if r["indicator"] != indicator:
                continue
            if period is not None and r["period"] != period:
                continue
            if variant is not None and r["variant"] != variant:
                continue
            if status is not None and r["status"] != status:
                continue
            if stage is not None and r.get("stage") != stage:
                continue
            out.append(r)
        return out

    def periods(self, indicator: str, variant: Optional[str] = None) -> list[str]:
        return sorted({r["period"] for r in self.find(indicator, variant=variant)})

    def latest(self, indicator: str, variant: Optional[str] = None) -> Optional[dict]:
        recs = [r for r in self.find(indicator, variant=variant) if r["status"] == "current"]
        if not recs:
            return None
        return sorted(recs, key=lambda r: r["period"])[-1]

    def coverage(self) -> dict:
        cov: dict = {}
        for r in self.records:
            key = r["indicator"] + ("" if r["variant"] == "default" else f" [{r['variant']}]")
            cov.setdefault(key, set()).add(r["period"])
        return {k: sorted(v) for k, v in sorted(cov.items())}
