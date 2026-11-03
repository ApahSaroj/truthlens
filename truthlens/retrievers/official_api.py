"""Shared plumbing for the v0.4 key-free ministry data sources (RBI, CEA, PPAC, JJM) and NDAP.

Each source is a *matcher*: given a numeric claim it returns v0.1-style findings built by `tables.match_rows`, so
the verdict engine treats it like MoSPI eSankhyiki (MATCH -> SUPPORTED, CLOSE/Superseded -> PARTLY, MISMATCH ->
CONTRADICTED only when exactly one well-fitting row disagrees; UNVERIFIED otherwise = fail closed).

Every outbound request goes through net.safe_get / net.safe_post (SSRF guard). Responses are cached on disk with a
TTL; when a source is down the stale cache is used and the failure is recorded in `errors` (never raised).
"""
from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache
from typing import Callable, Optional

from ..config import Config, redact
from ..net import DiskCache, make_session
from .base import terms
from .tables import dedupe_findings, match_rows

# Unit families: base unit -> {word in the claim: divisor applied to the base value}
UNIT_SCALES = {
    "count": [(r"\bcrore\b", 1e7, "crore"), (r"\blakh\b", 1e5, "lakh"), (r"\bmillion\b", 1e6, "million"),
              (r"\bbillion\b", 1e9, "billion")],
    "MW": [(r"\bGW\b|\bgigawatts?\b", 1000.0, "GW"), (r"\bMW\b|\bmegawatts?\b", 1.0, "MW")],
    "GW": [(r"\bMW\b|\bmegawatts?\b", 0.001, "MW"), (r"\bGW\b|\bgigawatts?\b", 1.0, "GW")],
    "TMT": [(r"\bmillion (?:metric )?tonnes?\b|\bMMT\b|\bmn tonnes?\b", 1000.0, "million tonnes"),
            (r"\blakh (?:metric )?tonnes?\b", 100.0, "lakh tonnes")],
    "USD_mn": [(r"\bbillion\b|\bbn\b", 1000.0, "US$ billion")],
    "lakh": [(r"\bcrore\b", 100.0, "crore"), (r"\bmillion\b", 10.0, "million")],
}


def unit_scale(claim_text: str, base: str) -> tuple[float, str]:
    """Divisor that converts a value in `base` units into the unit the claim is written in (1.0 when none named)."""
    for rx, div, label in UNIT_SCALES.get(base, []):
        if re.search(rx, claim_text or "", re.I if base not in ("MW", "GW") else re.I):
            return div, label
    return 1.0, base


def scaled(rows: list[dict], div: float) -> list[dict]:
    if div == 1.0:
        return rows
    out = []
    for r in rows:
        r2 = dict(r)
        try:
            r2["value"] = round(float(r["value"]) / div, 6)
        except (TypeError, ValueError, KeyError):
            continue
        out.append(r2)
    return out


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MONTH_RX = re.compile(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
                      r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?,?\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?((?:19|20)\d{2})\b", re.I)


def claim_month_years(text: str) -> set:
    return {f"{m.group(1)[:3].lower()} {m.group(2)}" for m in MONTH_RX.finditer(text or "")}


def month_period(month_label: str, claim_text: str) -> str:
    """Rows for a monthly snapshot carry 'sep 2026'. When the claim names that same month and year, the row's period
    becomes the bare year so the table matcher pairs them; any other named period leaves no match (fail closed)."""
    ml = (month_label or "").lower().strip()
    m = MONTH_RX.search(ml)
    norm = f"{m.group(1)[:3].lower()} {m.group(2)}" if m else ml
    if norm and norm in claim_month_years(claim_text):
        return norm.split()[-1]
    return norm


def kw_hits(text: str, keywords: list) -> int:
    low = (text or "").lower()
    return sum(1 for w in keywords if _kw_rx(w).search(low))


@lru_cache(maxsize=8192)
def _kw_rx(w: str):
    """v0.5.2: compiled once (dynamic patterns were evicting the re module's 512-entry cache in long documents)."""
    return re.compile(rf"\b{re.escape(w.lower())}\b")


class LiveSource:
    """Base class: cached transport + match()."""
    name = "live"
    badge = "Official data"
    publisher = ""
    portal = ""
    keywords: list = []
    ttl = 24 * 3600

    def __init__(self, cfg: Config, session=None):
        self.cfg = cfg
        self.session = session if session is not None else make_session()
        self.cache = DiskCache(cfg.cache_dir, self.name.replace("-", "_"), ttl=self.ttl)
        self.errors: list[str] = []
        self.offline = cfg.offline

    def unavailable(self) -> Optional[str]:
        return "skipped: offline" if self.offline else None

    def relevant(self, text: str) -> bool:
        return kw_hits(text, self.keywords) > 0

    def status(self) -> dict:
        return {"name": self.name, "configured": not self.offline, "detail": f"{self.publisher} ({self.portal}), no key"}

    def cached(self, key: str, fetch: Callable[[], object], ttl: Optional[int] = None):
        """Return (value, fetched_iso). Fresh cache -> live fetch -> stale cache; errors recorded, never raised."""
        cache = self.cache if ttl is None else DiskCache(self.cfg.cache_dir, self.name.replace("-", "_"), ttl=ttl)
        hit = cache.get(key)
        if hit is not None:
            return hit.get("v"), hit.get("t")
        if self.offline:
            st = cache.get(key, allow_stale=True)
            return (st.get("v"), st.get("t")) if st else (None, None)
        try:
            v = fetch()
            rec = {"v": v, "t": dt.date.today().isoformat()}
            cache.set(key, rec)
            return v, rec["t"]
        except Exception as e:
            self.errors.append(redact(f"{self.publisher or self.name}: {type(e).__name__}: {str(e)[:160]}"))
            st = cache.get(key, allow_stale=True)
            return (st.get("v"), st.get("t")) if st else (None, None)

    # subclasses return [(rows, source_dict, indicator_id, label)]
    def tables(self, claim_text: str) -> list[tuple]:  # pragma: no cover - interface
        raise NotImplementedError

    def match(self, claim_text: str, numbers: list) -> list[dict]:
        if not numbers or not self.relevant(claim_text):
            return []
        out = []
        for rows, src, ind_id, label in self.tables(claim_text):
            if not rows:
                continue
            src = dict(src)
            src.setdefault("retriever", self.name)
            src.setdefault("publisher", self.publisher)
            fs = match_rows(claim_text, numbers, rows, label=label, source=src, indicator_id=ind_id)
            out += fs
            if any(f["verdict"] != "UNVERIFIED" for f in fs):
                break
        return dedupe_findings(out)


GENERIC_WORDS = ("consumption import imports export exports rate rates total growth capacity power number share "
                 "per cent all billion units unit generation price connections connection year-on-year scheduled "
                 "commercial bank banks reserves energy fixed facility ratio deposits deposit "
                 "sum states supplied annual monthly latest current official data figure")


def _generic() -> set:
    out = set()
    for w in GENERIC_WORDS.split():
        out |= terms(w)
    return out


GENERIC = _generic()


def pick_indicator_rows(claim_text: str, groups: dict) -> list[tuple[str, list]]:
    """groups: {indicator label: rows}. The labels that share the most terms with the claim, best first. A label
    qualifies only when it shares at least one *specific* term with the claim (not 'consumption', 'rate', 'import'...),
    so 'diesel consumption' never falls back to 'petrol consumption'."""
    want = terms(claim_text)
    scored = []
    for label, rows in groups.items():
        lt = terms(label)
        common = want & lt
        if not (common - GENERIC):
            continue
        scored.append((len(common) / (len(lt) or 1) + 0.01 * len(common), label, rows))
    scored.sort(key=lambda x: -x[0])
    return [(lab, rows) for _s, lab, rows in scored]
