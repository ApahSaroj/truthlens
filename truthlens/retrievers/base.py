"""Retriever plug-in interface and shared text helpers.

A retriever turns a `Claim` into a list of `Evidence` items, each with a source URL, a verbatim snippet
and a date when the source gives one. Retrievers cache on disk under the TruthLens cache directory and
never raise: failures are recorded in `errors` and the retriever returns what it has (fail closed).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from ..config import Config
from ..model import Claim, Evidence

STOP = set("""a an the and or of in on at to for from by with as is are was were be been being this that these those it its
into over under than then there their which who whom whose what when where while about after before since during per
has have had not no nor but so such also more most less least very can could may might will would shall should
up down out new now all any each other some same only own just via within without between among across against
india indian india's government govt year years per cent percent""".split())

NUM_RX = re.compile(r"(?<![\w.])[-−]?\d[\d,]*(?:\.\d+)?")


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\u00a0", " ")).strip()


def stem(t: str) -> str:
    """Very light English stemmer (enough to match 'links'/'linking', 'released'/'release')."""
    for suf, keep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if t.endswith(suf) and len(t) - len(suf) >= 4 and not t.endswith("ss"):
            t = t[: len(t) - len(suf)] + keep
            break
    if t.endswith("e") and len(t) > 4:
        t = t[:-1]
    return t


# Indian official-statistics acronyms and their expansions (both directions are added to term sets)
ACRONYMS = {
    "iip": "index of industrial production", "cpi": "consumer price index", "wpi": "wholesale price index",
    "gdp": "gross domestic product", "gva": "gross value added", "plfs": "periodic labour force survey",
    "nas": "national accounts statistics", "nfhs": "national family health survey", "lfpr": "labour force participation rate",
    "cws": "current weekly status", "jjm": "jal jeevan mission", "mospi": "ministry of statistics and programme implementation",
    "nso": "national statistics office", "pib": "press information bureau", "rbi": "reserve bank of india",
    "dpiit": "department for promotion of industry and internal trade", "mcp": "model context protocol",
    "ai": "artificial intelligence", "ppi": "producer price index", "fhtc": "functional household tap connection",
    "hgj": "har ghar jal", "eli": "employment linked incentive", "ncs": "national career service",
    "nrdwp": "national rural drinking water programme", "mpce": "monthly per capita consumption expenditure",
    "hces": "household consumption expenditure survey", "aishe": "all india survey on higher education",
    "iip": "index of industrial production", "sut": "supply and use tables", "fre": "first revised estimates",
    # v0.5 (held-out 716): RBI rate acronyms, so 'the CRR' matches the 'cash reserve ratio' row
    "crr": "cash reserve ratio", "slr": "statutory liquidity ratio", "sdf": "standing deposit facility",
    "msf": "marginal standing facility",
}
IRREGULAR = {"grew": "grow", "growth": "grow", "rose": "rise", "fell": "fall", "risen": "rise", "fallen": "fall",
             "launch": "launch", "began": "begin", "begun": "begin", "contracted": "contract", "contraction": "contract",
             "declined": "decline", "decline": "decline", "jobless": "unemploy", "joblessness": "unemploy",
             "unemployment": "unemploy"}


_ACRX = {ac: re.compile(rf"\b{ac}\b") for ac in ACRONYMS}


def terms(text: str) -> set:
    """Content-word stems of a text (with acronym expansions). v0.5.2: memoised (a long document asked for the same
    catalogue labels' terms tens of thousands of times); a fresh set is returned so callers may change it."""
    return set(_terms_cached(text or ""))


@lru_cache(maxsize=65536)
def _terms_cached(text: str) -> frozenset:
    return frozenset(_terms(text))


def _terms(text: str) -> set:
    low = (text or "").lower().replace("’", "'")
    extra = []
    for ac, exp in ACRONYMS.items():
        if _ACRX[ac].search(low):
            extra.append(exp)
        if exp in low:
            extra.append(ac)
    toks = re.findall(r"[a-z][a-z\-]+", low + " " + " ".join(extra))
    out = set()
    for t in toks:
        t = t.strip("-")
        if t in IRREGULAR:
            out.add(IRREGULAR[t])
            continue
        if (len(t) < 3 and t not in ACRONYMS) or t in STOP:
            continue
        out.add(stem(t))
    return out


def numbers_in(text: str) -> list[float]:
    out = []
    for m in NUM_RX.finditer(text or ""):
        raw = m.group(0).replace(",", "").replace("−", "-")
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def number_tokens(text: str) -> list[str]:
    """Number strings as written, without thousands separators ('99,446' -> '99446', '-1.6' kept)."""
    return [m.group(0).replace(",", "").replace("−", "-") for m in NUM_RX.finditer(text or "")]


def contains_number(passage: str, raw: str) -> bool:
    """Does the passage contain this number (same digits, separators ignored)? '(-)1.6' matches '1.6'."""
    try:
        target = float(raw.replace(",", "").replace("−", "-").lstrip("+"))
    except ValueError:
        return False
    for v in numbers_in(passage):
        if abs(abs(v) - abs(target)) < 1e-9:
            return True
    return False


class Retriever:
    name = "base"
    needs: tuple = ()

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.errors: list[str] = []

    def _status(self, configured: bool, detail: str) -> dict:
        return {"name": self.name, "configured": configured, "detail": detail}

    def status(self) -> dict:
        return self._status(True, "")

    def retrieve(self, claim: Claim, k: int = 5) -> list[Evidence]:  # pragma: no cover - interface
        raise NotImplementedError


def best_window(text: str, want: set, numbers: list[str], width: int = 420) -> tuple[str, float]:
    """The sentence window of `text` that best covers the claim's terms and numbers (for quoting)."""
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(₹“\"])", norm_ws(text))
    best, best_s = "", -1.0
    for i in range(len(sents)):
        for span in (1, 2):
            chunk = " ".join(sents[i:i + span])
            if not chunk:
                continue
            ct = terms(chunk)
            s = len(want & ct) / (len(want) or 1)
            s += 0.5 * sum(1 for n in numbers if contains_number(chunk, n)) / (len(numbers) or 1)
            s -= 0.0005 * max(0, len(chunk) - width)
            if s > best_s:
                best, best_s = chunk, s
    return best[: width * 2], best_s


def short_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else s[:40]
