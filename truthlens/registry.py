"""Indicator registry: loads data/indicators.yaml and finds indicator mentions in text."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Optional

import yaml


@dataclass
class Indicator:
    id: str
    name: str
    unit_kind: str
    period_type: str
    priority: int
    aliases: list
    exclude: list
    tolerance: dict
    traps: list
    series_id: str
    official_series: str
    variants: dict = field(default_factory=dict)
    default_variant: str = "default"
    status_variants: list = field(default_factory=list)
    stage_priority: list = field(default_factory=list)
    default_latest: bool = False
    worldbank: Optional[dict] = None
    generic_alias: Optional[str] = None

    def __post_init__(self):
        self._alias_rx = [re.compile(a, re.I) for a in self.aliases]
        self._excl_rx = [re.compile(a, re.I) for a in self.exclude]
        self._var_rx = {k: re.compile(v, re.I) for k, v in self.variants.items()}
        self._generic_rx = re.compile(self.generic_alias, re.I) if self.generic_alias else None

    def mentions(self, text: str):
        """Yield (start, end, generic) for alias matches."""
        for rx in self._alias_rx:
            for m in rx.finditer(text):
                generic = bool(self._generic_rx and self._generic_rx.fullmatch(m.group(0)))
                yield m.start(), m.end(), generic

    def excluded(self, window: str) -> bool:
        return any(rx.search(window) for rx in self._excl_rx)

    def detect_variant(self, window: str) -> Optional[str]:
        """The variant the text names. v0.5: a sub-group (female, male, rural, urban, youth) the text names must be the
        variant's own sub-group: such variants are tried first, and an all-persons indicator with no variant for that
        sub-group returns 'unmatched-<group>' (no official series -> the figure fails closed, never compared with
        the all-persons value). Held-out case 717: 'Female LFPR on usual status' was read as all persons."""
        named = named_subgroups(window)
        if named:
            # a status the text names (CWS) that the sub-group variant is not: no series (fail closed)
            other_status = [k for k, rx in self._var_rx.items() if not any(g in k for g in SUBGROUPS) and rx.search(window)]
            for k in self._var_rx:
                if any(g in k for g in named):
                    if other_status and not any(st in k for st in other_status):
                        return "unmatched-" + sorted(named)[0]
                    return k
            sex_age = named & {"female", "male", "youth"}     # rural/urban: handled by the live MoSPI sector lookup
            if sex_age and "persons" in self.name.lower():
                return "unmatched-" + sorted(sex_age)[0]
        for k, rx in self._var_rx.items():
            if any(g in k for g in SUBGROUPS) and not (named & {g for g in SUBGROUPS if g in k}):
                continue
            if rx.search(window):
                return k
        return None


SUBGROUPS = {"female": r"\b(female|women|woman|women's|girls?)\b", "male": r"\b(male|men|man|boys?)\b",
             "rural": r"\brural\b", "urban": r"\burban\b",
             "youth": r"\b(youth|young (?:people|persons)|15\s*[-–]\s*29)\b"}


def named_subgroups(text: str) -> set:
    low = (text or "").lower()
    out = {g for g, rx in SUBGROUPS.items() if re.search(rx, low)}
    if {"male", "female"} <= out:      # 'females per 1,000 males' is a ratio, not a sub-group
        out -= {"male", "female"}
    if {"rural", "urban"} <= out:
        out -= {"rural", "urban"}
    return out


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Indicator]:
    text = resources.files("truthlens.data").joinpath("indicators.yaml").read_text(encoding="utf-8")
    raw = yaml.safe_load(text)["indicators"]
    reg = {}
    for iid, d in raw.items():
        reg[iid] = Indicator(
            id=iid, name=d["name"], unit_kind=d["unit_kind"], period_type=d["period_type"],
            priority=d.get("priority", 50), aliases=d.get("aliases", []), exclude=d.get("exclude", []),
            tolerance=d.get("tolerance", {}), traps=d.get("traps", []), series_id=d.get("series_id", ""),
            official_series=d.get("official_series", ""), variants=d.get("variants", {}) or {},
            default_variant=d.get("default_variant", "default"), status_variants=d.get("status_variants", []),
            stage_priority=d.get("stage_priority", []), default_latest=d.get("default_latest", False),
            worldbank=d.get("worldbank"), generic_alias=d.get("generic_alias"),
        )
    return reg
