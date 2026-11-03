"""Low-level parsing of Indian numeric expressions and periods.

Handles Indian digit grouping (1,21,08,54,977), lakh / crore / lakh crore,
million / billion / trillion, ₹ / Rs / INR, per cent / percentage points,
and Indian period conventions (FY 2023-24, FY24, 2023-24, Q1 FY26, NFHS-5 ...).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

MULTIPLIERS = {
    "thousand": 1e3,
    "lakh": 1e5, "lac": 1e5, "lakhs": 1e5, "lacs": 1e5,
    "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "lakh crore": 1e12, "lakh crores": 1e12, "lac crore": 1e12, "lakh-crore": 1e12,
    "million": 1e6, "mn": 1e6,
    "billion": 1e9, "bn": 1e9,
    "trillion": 1e12, "tn": 1e12,
}
INDIAN_UNITS = {"lakh", "crore", "lakh crore"}
INTL_UNITS = {"thousand", "million", "billion", "trillion"}

_MULT_RE = (r"lakh[- ]crores?|lac crores?|lakhs?|lacs?|crores?|cr\b|thousand|million|mn\b|"
            r"billion|bn\b|trillion|tn\b")

NUMBER_RE = re.compile(
    r"(?P<cur>₹|\brs\.?|\binr\b|\bus\$|\$|\busd\b)?\s*"
    r"(?P<sign>\(-\)|−|-(?=\d))?"
    r"(?P<num>(?<![\w.,])\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|(?<![\w.,])\d+(?:\.\d+)?)"
    r"(?P<range>\s*(?:-|–|to)\s*\d+(?:\.\d+)?(?=\s*(?:%|per ?cent|percent)))?"
    r"(?:\s*(?P<mult>" + _MULT_RE + r"))?"
    r"(?:\s*(?P<pct>%|per ?cent\b|percent\b|pct\b|percentage points?\b|pp\b|p\.p\.|basis points?\b|bps\b))?",
    re.IGNORECASE,
)

MONTHS = ("jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|"
          "july|august|september|october|november|december")

PERIOD_PATTERNS = [
    ("plfs", re.compile(r"\bjuly[ ,]*(20\d{2})\s*(?:-|–|to)\s*june[ ,]*(20\d{2})\b", re.I)),
    ("nfhs", re.compile(r"\bnfhs[- ]?([3-6])\b", re.I)),
    ("quarter", re.compile(r"\bq([1-4])\s*(?:of\s*)?(?:fy\s*)?['’]?(\d{2,4}(?:\s*[-–/]\s*\d{2,4})?)", re.I)),
    ("fy", re.compile(r"\b(?:fy|f\.y\.|financial year|fiscal year|fiscal)\s*['’]?(\d{2,4})(?:\s*[-–/]\s*(\d{2,4}))?\b", re.I)),
    ("month", re.compile(r"\b(" + MONTHS + r")\.?,?\s+(20\d{2})\b", re.I)),
    ("range", re.compile(r"\b((?:19|20)\d{2})\s*[-–/]\s*(\d{2}|(?:19|20)\d{2})\b")),
    ("census", re.compile(r"\bcensus(?: of india)?[ ,]*(\d{4})\b|\b(\d{4}) census\b", re.I)),
    ("cy", re.compile(r"\b(?:cy|calendar year)?\s*((?:19|20)\d{2})\b", re.I)),
]

BASE_CONTEXT_AFTER = re.compile(r"^\s*(?:=\s*100|prices|base|series|-based)", re.I)
BASE_CONTEXT_BEFORE = re.compile(r"(?:base(?: year)?(?: of)?|at constant|at|constant \(?)\s*\(?$", re.I)


@dataclass
class Period:
    kind: str           # fy | cy | span | quarter | month | survey
    label: str          # canonical label, e.g. "2023-24", "2024", "2019-21", "Q1 2025-26"
    start: int
    end: int
    raw: str
    note: Optional[str] = None
    is_base: bool = False

    def to_dict(self):
        return asdict(self)


def fy_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _norm_year(y: str) -> int:
    y = int(y)
    if y < 100:
        y += 2000
    return y


def _fy_from_tokens(a: str, b: Optional[str]) -> tuple[str, Optional[str]]:
    if b:
        s = _norm_year(a)
        e = _norm_year(b) if len(b) == 4 else int(str(s)[:2] + b)
        if e - s == 1:
            return fy_label(s), None
        return f"{s}-{str(e)[-2:]}", "irregular financial-year range"
    y = _norm_year(a)
    # Indian convention: FY24 / FY2024 = the year ending March 2024 = 2023-24
    return fy_label(y - 1), f"'{a}' read as the financial year ending March {y} (FY {fy_label(y - 1)})"


NFHS_ROUNDS = {"3": "2005-06", "4": "2015-16", "5": "2019-21", "6": "2023-24"}


def find_periods(text: str) -> list[Period]:
    """Find period expressions. Earlier pattern types win on overlap."""
    taken: list[tuple[int, int]] = []
    out: list[Period] = []

    def free(s, e):
        return all(e <= a or s >= b for a, b in taken)

    for kind, rx in PERIOD_PATTERNS:
        for m in rx.finditer(text):
            s, e = m.span()
            raw = m.group(0).strip()
            # strip leading whitespace from span for cy pattern
            lead = len(m.group(0)) - len(m.group(0).lstrip())
            s += lead
            if not free(s, e):
                continue
            note = None
            if kind == "plfs":
                a, b = int(m.group(1)), int(m.group(2))
                if b - a != 1:
                    continue
                p = Period("fy", fy_label(a), s, e, raw, "PLFS survey year July-June")
            elif kind == "nfhs":
                lab = NFHS_ROUNDS.get(m.group(1))
                if not lab:
                    continue
                p = Period("survey", lab, s, e, raw, f"NFHS-{m.group(1)}")
            elif kind == "quarter":
                q = m.group(1)
                tok = re.split(r"\s*[-–/]\s*", m.group(2))
                lab, note = _fy_from_tokens(tok[0], tok[1] if len(tok) > 1 else None)
                p = Period("quarter", f"Q{q} {lab}", s, e, raw, note)
            elif kind == "fy":
                lab, note = _fy_from_tokens(m.group(1), m.group(2))
                p = Period("fy", lab, s, e, raw, note)
            elif kind == "month":
                p = Period("month", f"{m.group(1)[:3].title()} {m.group(2)}", s, e, raw)
            elif kind == "range":
                a = int(m.group(1))
                b = m.group(2)
                bb = int(b) if len(b) == 4 else int(str(a)[:2] + b)
                if bb <= a or bb - a > 5:
                    continue
                if bb - a == 1:
                    p = Period("fy", fy_label(a), s, e, raw)
                else:
                    p = Period("span", f"{a}-{str(bb)[-2:]}", s, e, raw)
            elif kind == "census":
                y = m.group(1) or m.group(2)
                p = Period("cy", y, s, e, raw, "census year")
            else:  # cy
                y = int(m.group(1))
                if not (1950 <= y <= 2100):
                    continue
                p = Period("cy", str(y), s, e, raw)
            # base-year mentions ("2011-12 prices", "2012=100", "base year 2022-23") are not claim periods
            after = text[e:e + 12]
            before = text[max(0, s - 25):s]
            if BASE_CONTEXT_AFTER.match(after) or BASE_CONTEXT_BEFORE.search(before):
                p.is_base = True
            taken.append((s, e))
            out.append(p)
    out.sort(key=lambda p: p.start)
    return out


@dataclass
class Number:
    value: float              # absolute value (multiplier applied)
    raw_value: float          # as written
    decimals: int
    unit_kind: str            # percent | pp | inr | usd | count | bare
    multiplier: Optional[str]
    multiplier_value: float
    currency: Optional[str]
    start: int
    end: int
    raw: str
    is_range: bool = False
    is_bps: bool = False

    def to_dict(self):
        return asdict(self)


def _parse_num(s: str) -> tuple[float, int]:
    s = s.replace(",", "")
    dec = len(s.split(".")[1]) if "." in s else 0
    return float(s), dec


def find_numbers(text: str, exclude_spans: list[tuple[int, int]] = ()) -> list[Number]:
    out = []
    masked = list(text)
    for a, b in exclude_spans:
        for i in range(a, min(b, len(masked))):
            masked[i] = " "
    masked = "".join(masked)
    for m in NUMBER_RE.finditer(masked):
        ns, ne = m.span("num")
        if any(not (ne <= a or ns >= b) for a, b in exclude_spans):
            continue
        raw_num = m.group("num")
        val, dec = _parse_num(raw_num)
        cur = (m.group("cur") or "").lower().strip() or None
        mult = (m.group("mult") or "").lower().strip() or None
        if mult:
            mult = re.sub(r"[- ]+", " ", mult)
            if mult.startswith("lakh crore") or mult.startswith("lac crore"):
                mult = "lakh crore"
            elif mult in ("lakhs", "lac", "lacs"):
                mult = "lakh"
            elif mult in ("crores", "cr"):
                mult = "crore"
            elif mult == "mn":
                mult = "million"
            elif mult == "bn":
                mult = "billion"
            elif mult == "tn":
                mult = "trillion"
        pct = (m.group("pct") or "").lower()
        sign = -1 if m.group("sign") else 1
        mv = MULTIPLIERS.get(mult, 1.0) if mult else 1.0
        is_bps = False
        if pct in ("%", "per cent", "percent", "pct", "percent"):
            kind = "percent"
        elif pct.startswith("percentage point") or pct in ("pp", "p.p."):
            kind = "pp"
        elif pct.startswith("basis point") or pct == "bps":
            kind, is_bps = "pp", True
            val = val / 100.0
            dec += 2
        elif cur in ("₹", "rs", "rs.", "inr"):
            kind = "inr"
        elif cur in ("$", "us$", "usd"):
            kind = "usd"
        elif mult:
            # "₹ ... crore" without symbol is common in Indian drafts: decide later from context
            kind = "count"
        else:
            kind = "bare"
        s = m.start("cur") if m.group("cur") else (m.start("sign") if m.group("sign") else ns)
        if pct.startswith("per") and pct.replace(" ", "") == "percent":
            kind = "percent"
        out.append(Number(
            value=sign * val * mv, raw_value=sign * val, decimals=dec, unit_kind=kind,
            multiplier=mult, multiplier_value=mv, currency=cur, start=s, end=m.end(),
            raw=text[m.start():m.end()].strip(), is_range=bool(m.group("range")), is_bps=is_bps,
        ))
    return out


def format_indian(n: float) -> str:
    """Format an integer with Indian digit grouping: 12108549 -> 1,21,08,549."""
    neg = n < 0
    s = str(int(round(abs(n))))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if neg else "") + s


def human_inr(v: float) -> str:
    if abs(v) >= 1e12:
        return f"₹{v / 1e12:,.2f} lakh crore"
    if abs(v) >= 1e7:
        return f"₹{v / 1e7:,.2f} crore"
    if abs(v) >= 1e5:
        return f"₹{v / 1e5:,.2f} lakh"
    return f"₹{format_indian(v)}"


def human_count(v: float) -> str:
    if abs(v) >= 1e7:
        return f"{format_indian(v)} ({v / 1e7:,.2f} crore)"
    if abs(v) >= 1e5:
        return f"{format_indian(v)} ({v / 1e5:,.2f} lakh)"
    return format_indian(v)
