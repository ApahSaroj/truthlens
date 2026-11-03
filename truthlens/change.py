"""Change calculator (v0.4.1): claims about how a series moved between two periods.

A sentence such as "CPI inflation rose from 5.4 per cent in 2023-24 to 4.6 per cent in 2024-25" makes three
separate assertions, and each is checked on its own:

  (a) internal consistency: the direction word ("rose") against the sentence's own from -> to figures (5.4 -> 4.6 is
      a fall). A contradiction here needs no data at all.
  (b) endpoints: each figure against the official value for its period (done by the deterministic checker; the
      findings are passed in).
  (c) direction and size of the change, computed from the official values of both periods: up or down, by how many
      percentage points (absolute) and by how many per cent (relative). Confusing the two is flagged.

Recognised wording: rose / fell / grew / declined / increased / decreased / dropped / jumped / climbed / moderated /
slowed / accelerated / eased / cut / reduced (+ "from X to Y", "by N per cent | percentage points | pp | bps"),
"higher / lower than last year | the previous year | in <period>", "compared with <period>", "doubled / halved /
tripled", and trends ("every year", "consistently", "continuously", "year after year", "each year").
"Last year" / "the previous year" / "a year earlier" are resolved relative to the claim's own stated period.

The result is fail-closed: a period that is not in the official series makes the change UNVERIFIED (unless the
sentence contradicts itself, which is CONTRADICTED whatever the data say).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from .parsing import Number, find_numbers, find_periods

RISE = (r"rose|rise[sn]?|rising|increas(?:ed|es|ing|e)|grew|grow(?:n|s|ing)?|jump(?:ed|s|ing)?|climb(?:ed|s|ing)?|"
        r"accelerat(?:ed|es|ing)|surg(?:ed|es|ing)|went up|go(?:es)? up|picked up|improved|expanded|widened|"
        r"edged up|inched up|soared|spiked|hiked|raised")
FALL = (r"fell|fall(?:s|en|ing)?|declin(?:ed|es|ing|e)|decreas(?:ed|es|ing|e)|dropp(?:ed|ing)|drops?|moderat(?:ed|es|ing)|"
        r"slow(?:ed|s|ing)|eas(?:ed|es|ing)|cut|reduc(?:ed|es|ing)|went down|go(?:es)? down|dipp(?:ed|ing)|dips?|"
        r"slipp(?:ed|ing)|shr[ua]nk|narrow(?:ed|s|ing)|contract(?:ed|s|ing)|plunged|plummeted|tumbled|slid|softened|"
        r"edged down|inched down|lowered")
VERB_RX = re.compile(rf"\b(?:(?P<r>{RISE})|(?P<f>{FALL}))\b", re.I)
THAN_RX = re.compile(r"\b(?P<w>higher|lower|more|less|greater|smaller|up|down)\s+(?:than|from|compared\s+(?:with|to)|on)\b", re.I)
REL_YEAR_RX = re.compile(r"\b(?:last|the\s+previous|the\s+preceding|the\s+prior|a|one)\s+(?:financial\s+|fiscal\s+)?year"
                         r"(?:\s+(?:earlier|before|ago))?\b|\byear[- ]on[- ]year\b|\by-o-y\b|\byoy\b", re.I)
FACTOR_RX = re.compile(r"\b(?:(?P<q>more\s+than|over|nearly|almost|about|roughly|around|close\s+to|less\s+than)\s+)?"
                       r"(?P<w>doubled|doubling|halved|halving|tripled|trebled|quadrupled)\b", re.I)
FACTORS = {"doubl": 2.0, "halv": 0.5, "tripl": 3.0, "trebl": 3.0, "quadrupl": 4.0}
TREND_RX = re.compile(r"\b(?:every|each)\s+year\b|\byear\s+after\s+year\b|\bconsistently\b|\bcontinuously\b|"
                      r"\bsteadily\b|\bconsecutive(?:ly)?\b|\bwithout\s+(?:a\s+)?break\b|\bin\s+every\s+year\b", re.I)
SINCE_RX = re.compile(r"\b(?:since|from|between)\s+(?:FY\s*)?((?:19|20)\d{2}(?:[-–]\d{2,4})?)", re.I)


@dataclass
class Fig:
    raw: str
    value: float
    unit: str            # percent | pp | level
    decimals: int
    start: int
    end: int
    period: Optional[str] = None


@dataclass
class ChangeSpec:
    text: str
    direction: int = 0                 # +1 rise, -1 fall, 0 unknown (claimed sign of later/subject minus earlier)
    verb: str = ""
    from_fig: Optional[Fig] = None
    to_fig: Optional[Fig] = None
    by: Optional[Fig] = None
    factor: Optional[float] = None
    factor_word: str = ""
    factor_qual: str = ""              # more than | nearly | about ... ("more than halved")
    a_period: Optional[str] = None     # start / comparison period
    b_period: Optional[str] = None     # end / subject period
    relative: str = ""                 # "last year" wording that was resolved, if any
    trend: bool = False
    since: Optional[str] = None
    notes: list = field(default_factory=list)

    @property
    def kind(self) -> str:
        if self.trend:
            return "trend"
        if self.factor:
            return "factor"
        if self.from_fig and self.to_fig:
            return "from_to"
        if self.by:
            return "by"
        return "direction"

    def internal_conflict(self) -> Optional[str]:
        """The sentence contradicts itself: the direction word against its own from -> to figures, or a stated
        size of change that does not equal the difference between its own figures."""
        f, t = self.from_fig, self.to_fig
        if not (f and t) or f.unit != t.unit:
            return None
        # v0.5.3: '42,225 Million m3 ... 10 to 20 times' is not a from -> to pair: the scale words must agree
        if _scale_word(f.raw) != _scale_word(t.raw):
            return None
        d = t.value - f.value
        if self.direction and d and (d > 0) != (self.direction > 0):
            way = "a fall" if d < 0 else "a rise"
            size = f" of {abs(d):.{max(f.decimals, t.decimals)}f} percentage points" if f.unit == "percent" else ""
            return (f"Internal inconsistency: the sentence says ‘{self.verb}’, but its own figures go from {f.raw} to "
                    f"{t.raw}, which is {way}{size}.")
        if self.by is not None and f.unit == "percent":
            half = 0.5 * 10 ** (-self.by.decimals) + 1e-9
            if self.by.unit == "pp" and abs(abs(d) - self.by.value) > half:
                return (f"Internal inconsistency: {f.raw} to {t.raw} is a change of {abs(d):.2f} percentage points, "
                        f"not {self.by.raw}.")
        return None


def _figs(text: str) -> tuple[list[Fig], list]:
    periods = [p for p in find_periods(text) if not p.is_base]
    nums = find_numbers(text, [(p.start, p.end) for p in periods])
    out = []
    for n in nums:
        if n.unit_kind == "bare" and n.decimals == 0 and 1900 <= abs(n.value) <= 2100:
            continue
        unit = {"percent": "percent", "pp": "pp"}.get(n.unit_kind, "level")
        val = n.raw_value if unit != "level" else n.value
        out.append(Fig(raw=n.raw, value=val, unit=unit, decimals=n.decimals, start=n.start, end=n.end))
    return out, periods


def _period_of(fig: Fig, periods: list, text: str) -> Optional[str]:
    after = [p for p in periods if p.start >= fig.end and p.start - fig.end <= 25
             and not re.search(r"\bto\b|\bfrom\b", text[fig.end:p.start])]
    if after:
        return after[0].label
    before = [p for p in periods if p.end <= fig.start and fig.start - p.end <= 12]
    if before:
        return before[-1].label
    return None


def prev_period(label: str) -> Optional[str]:
    m = re.fullmatch(r"(\d{4})-(\d{2})", label or "")
    if m:
        y = int(m.group(1)) - 1
        return f"{y}-{str(y + 1)[-2:]}"
    m = re.fullmatch(r"\d{4}", label or "")
    if m:
        return str(int(label) - 1)
    return None


def _pkey(label: str) -> int:
    m = re.match(r"(\d{4})", label or "")
    return int(m.group(1)) if m else 0


def parse_change(text: str) -> Optional[ChangeSpec]:
    """Parse the change wording of one sentence; None when the sentence does not state a change."""
    t = text or ""
    figs, periods = _figs(t)
    spec = ChangeSpec(text=t)
    verbs = list(VERB_RX.finditer(t))
    than = THAN_RX.search(t)
    if verbs:
        v = verbs[0]
        spec.direction, spec.verb = (1 if v.group("r") else -1), v.group(0)
    if than and not verbs:
        w = than.group("w").lower()
        spec.direction = 1 if w in ("higher", "more", "greater", "up") else -1
        spec.verb = than.group(0)
    fm = FACTOR_RX.search(t)
    if fm:
        w = fm.group("w").lower()
        spec.factor = next(v for k, v in FACTORS.items() if w.startswith(k))
        spec.factor_word = fm.group(0)
        spec.factor_qual = re.sub(r"\s+", " ", (fm.group("q") or "").lower())
        spec.direction = 1 if spec.factor > 1 else -1
        spec.verb = spec.verb or fm.group(0)
    spec.trend = bool(TREND_RX.search(t)) and bool(spec.direction)
    # from X to Y
    mfrom = re.search(r"\bfrom\b", t, re.I)
    if mfrom:
        f = next((x for x in figs if x.start >= mfrom.end() and x.start - mfrom.end() <= 20), None)
        if f:
            mto = re.search(r"\bto\b", t[f.end:], re.I)
            if mto:
                pos = f.end + mto.end()
                g = next((x for x in figs if x.start >= pos and x.start - pos <= 20), None)
                if g:
                    spec.from_fig, spec.to_fig = f, g
    # "to Y from X" (reversed order)
    if not spec.from_fig:
        m = re.search(r"\bto\s+(?:about\s+|around\s+)?([\d.,]+)", t, re.I)
        m2 = re.search(r"\bfrom\s+(?:about\s+|around\s+)?([\d.,]+)", t, re.I)
        if m and m2 and m.start() < m2.start():
            g = next((x for x in figs if x.start >= m.start(1) - 1 and x.start <= m.end(1)), None)
            f = next((x for x in figs if x.start >= m2.start(1) - 1 and x.start <= m2.end(1)), None)
            if f and g:
                spec.from_fig, spec.to_fig = f, g
    # by N
    for x in figs:
        before = t[max(0, x.start - 45):x.start]
        if re.search(r"\bby\s+(?:about\s+|around\s+|nearly\s+|almost\s+|over\s+|some\s+)?$", before, re.I) and \
                (verbs or than) and x not in (spec.from_fig, spec.to_fig):
            spec.by = x
            break
        if x.unit == "pp" and x not in (spec.from_fig, spec.to_fig) and spec.by is None:
            spec.by = x
        if re.search(r"\b(?:an?\s+)?(?:increase|decrease|rise|fall|decline|drop|jump|gain|reduction|cut)\s+of\s*$",
                     before, re.I) and x not in (spec.from_fig, spec.to_fig):
            spec.by = x
            if not spec.direction:
                spec.direction = -1 if re.search(r"decrease|fall|decline|drop|reduction|cut", before, re.I) else 1
            break
    if spec.by is not None and than is not None and than.start() > spec.by.start and spec.by.unit in ("pp", "percent"):
        w = than.group("w").lower()          # "0.8 points lower than last year" -> the comparative is the direction
        spec.direction = 1 if w in ("higher", "more", "greater", "up") else -1
        spec.verb = than.group(0)
    # periods
    if spec.from_fig and spec.to_fig:
        spec.from_fig.period = _period_of(spec.from_fig, periods, t)
        spec.to_fig.period = _period_of(spec.to_fig, periods, t)
        labels = [p.label for p in periods]
        if (not spec.from_fig.period or not spec.to_fig.period) and len(labels) == 2:
            a, b = sorted(labels, key=_pkey)
            spec.from_fig.period = spec.from_fig.period or a
            spec.to_fig.period = spec.to_fig.period or b
        spec.a_period, spec.b_period = spec.from_fig.period, spec.to_fig.period
    else:
        labels = list(dict.fromkeys(p.label for p in periods))
        rel = REL_YEAR_RX.search(t)
        if than is not None and labels:
            # subject period (before 'than') against the comparison period (after it, or 'last year')
            subj = [p.label for p in periods if p.end <= than.start()]
            comp = [p.label for p in periods if p.start >= than.end()]
            if subj and comp:
                spec.b_period, spec.a_period = subj[-1], comp[0]
            elif subj and rel:
                spec.b_period, spec.a_period, spec.relative = subj[-1], prev_period(subj[-1]), rel.group(0)
            elif len(labels) >= 2:
                spec.a_period, spec.b_period = sorted(labels[:2], key=_pkey)
            elif rel:
                spec.b_period, spec.a_period, spec.relative = labels[0], prev_period(labels[0]), rel.group(0)
        elif len(labels) >= 2:
            spec.a_period, spec.b_period = sorted(labels[:2], key=_pkey)
            cw = re.search(r"\bcompared\s+(?:with|to)\b|\bover\b|\bagainst\b|\bfrom\b", t, re.I)
            if cw and not spec.trend:
                # "in 2024-25 compared with 2023-24": subject is the period before the comparison word
                subj = [p.label for p in periods if p.end <= cw.start()]
                comp = [p.label for p in periods if p.start >= cw.end()]
                if subj and comp and subj[-1] != comp[0]:
                    spec.b_period, spec.a_period = subj[-1], comp[0]
                    if _pkey(spec.b_period) < _pkey(spec.a_period):     # "from 2023-24 ... in 2024-25" reversed
                        spec.a_period, spec.b_period = spec.b_period, spec.a_period
        elif len(labels) == 1 and rel:
            spec.b_period, spec.a_period, spec.relative = labels[0], prev_period(labels[0]), rel.group(0)
        sm = SINCE_RX.search(t)
        if spec.trend and sm:
            spec.since = next((p.label for p in periods if p.start >= sm.start(1) - 3), None)
    # does the sentence state a change at all?
    stated = bool(spec.from_fig and spec.to_fig) or spec.by is not None or spec.factor is not None or spec.trend or \
        (than is not None and bool(spec.a_period) and bool(spec.b_period) and not figs)
    if not stated or not spec.direction and not (spec.from_fig and spec.to_fig):
        return None
    return spec


# ---------------------------------------------------------------------------------------------- checking
@dataclass
class Series:
    """What the change check needs from the official data: one value per period, plus labels."""
    indicator: str
    name: str
    unit: str                                    # percent | inr | count
    get: Callable[[str], Optional[dict]]         # period -> record {value, display, period, ...} or None
    periods: Callable[[], list]                  # all periods with a current value, oldest first


def _fmt(v: float, unit: str) -> str:
    if unit == "percent":
        return f"{v:g}%"
    from .parsing import human_count, human_inr
    return human_inr(v) if unit == "inr" else human_count(v)


def _close(claim: float, actual: float, decimals: int) -> bool:
    return abs(claim - actual) <= 0.5 * 10 ** (-decimals) + 1e-9


def check_change(spec: ChangeSpec, series: Optional[Series], findings: list[dict]) -> dict:
    """{'verdict', 'reason', 'failed_part', 'parts': [...], 'covers': [raw figures decided here]}."""
    parts: list[dict] = []
    covers: list[str] = []
    if series is not None and spec.kind == "by" and spec.by is not None and spec.by.unit == "percent" \
            and "growth" in series.indicator and not re.search(r"\b(?:growth|rate)\b[^.;]{0,30}$", spec.text[:spec.by.start], re.I):
        series = None        # "GDP grew by 7.2 per cent" states the growth rate itself, not a change in it
    name = series.name if series else "the series"

    def add(part, status, detail):
        parts.append({"part": part, "status": status, "detail": detail})

    conflict = spec.internal_conflict()
    if conflict:
        add("internal consistency", "contradicted", conflict)
    # (b) endpoints, as the deterministic checker found them
    for fig in (spec.from_fig, spec.to_fig):
        if fig is None:
            continue
        f = next((x for x in findings if x.get("claimed") == fig.raw), None)
        if f and f.get("verdict") in ("MISMATCH", "CLOSE"):
            off = (f.get("official") or {}).get("display")
            add(f"{fig.period or f.get('period')} figure", "contradicted",
                f"{fig.period or f.get('period')} {name}: draft {fig.raw}, official {off}.")
        elif f and f.get("verdict") == "MATCH":
            add(f"{fig.period or f.get('period')} figure", "supported", f"{fig.period or f.get('period')}: {fig.raw} matches.")
    # (c) direction and size from the official values
    if spec.kind == "trend":
        _check_trend(spec, series, add)
    elif series is not None and spec.a_period and spec.b_period:
        ra, rb = series.get(spec.a_period), series.get(spec.b_period)
        missing = [p for p, r in ((spec.a_period, ra), (spec.b_period, rb)) if r is None]
        if missing:
            avail = ", ".join(series.periods()) or "none"
            add("change", "unverified", f"No official value for {', '.join(missing)} in the {name} series "
                                        f"(available: {avail}), so the change cannot be computed.")
        else:
            va, vb = ra["value"], rb["value"]
            d = vb - va
            rel = d / va * 100 if va else float("nan")
            way = "rose" if d > 0 else ("fell" if d < 0 else "was unchanged")
            unit = series.unit
            ctx = (f"official {name} {way} from {_fmt(va, unit)} ({spec.a_period}) to {_fmt(vb, unit)} ({spec.b_period})"
                   + (f" = {d:+.2f} percentage points ({rel:+.1f}% relative)" if unit == "percent" else f" ({rel:+.1f}%)"))
            if spec.relative:
                ctx += f"; ‘{spec.relative}’ read as {spec.a_period}, the year before the claim's {spec.b_period}"
            if spec.direction and d and (d > 0) != (spec.direction > 0):
                add("direction", "contradicted", f"Direction: the draft says ‘{spec.verb}’, but {ctx}.")
            elif spec.direction and not d:
                add("direction", "contradicted", f"Direction: the draft says ‘{spec.verb}’, but {ctx}.")
            else:
                add("direction", "supported", f"Direction: {ctx}.")
            if spec.by is not None:
                covers.append(spec.by.raw)
                by = spec.by
                if by.unit == "pp" and unit == "percent":
                    ok = _close(by.value, abs(d), by.decimals)
                    if ok:
                        add("size", "supported", f"Size: {by.raw} matches the official change of {abs(d):.2f} percentage points.")
                    elif _close(by.value, abs(rel), by.decimals):
                        add("size", "contradicted", f"Size: {by.raw} is the relative change in per cent ({abs(rel):.1f}%); "
                                                    f"the change in percentage points is {abs(d):.2f}.")
                    else:
                        add("size", "contradicted", f"Size: draft {by.raw}, official change {abs(d):.2f} percentage points.")
                elif by.unit == "percent":
                    if _close(by.value, abs(rel), by.decimals):
                        msg = f"Size: {by.raw} matches the official relative change of {abs(rel):.1f}%."
                        if unit == "percent":
                            msg += f" (In percentage points the change is {abs(d):.2f}; say which you mean.)"
                        add("size", "supported", msg)
                    elif unit == "percent" and _close(by.value, abs(d), by.decimals):
                        add("size", "contradicted",
                            f"Size: {by.raw} confuses per cent with percentage points: the rate moved {abs(d):.1f} "
                            f"percentage points, a {abs(rel):.1f}% relative change. Write ‘{abs(d):.1f} percentage points’.")
                    else:
                        add("size", "contradicted", f"Size: draft {by.raw}, official change {abs(rel):.1f}%"
                                                    + (f" ({abs(d):.2f} percentage points)" if unit == "percent" else "") + ".")
                else:
                    covers.pop()
            if spec.factor:
                ratio = vb / va if va else float("nan")
                q, fct = spec.factor_qual, spec.factor
                if q in ("more than", "over"):        # "more than doubled" >= 2x; "more than halved" <= 0.5x
                    ok = ratio >= fct * 0.975 if fct > 1 else ratio <= fct * 1.025
                elif q == "less than":
                    ok = ratio < fct if fct > 1 else ratio > fct
                elif q:                                # nearly / almost / about: within 15%
                    ok = abs(ratio - fct) <= 0.15 * fct
                else:
                    ok = abs(ratio - fct) <= 0.075 * fct
                if ok:
                    add("factor", "supported", f"‘{spec.factor_word}’: official ratio {ratio:.2f}×.")
                else:
                    add("factor", "contradicted", f"‘{spec.factor_word}’: the official values give a ratio of {ratio:.2f}×, "
                                                  f"not {(spec.factor_qual + ' ') if spec.factor_qual else ''}{spec.factor:g}×.")
    bad = [p for p in parts if p["status"] == "contradicted"]
    unk = [p for p in parts if p["status"] == "unverified"]
    if bad:
        verdict = "CONTRADICTED"
    elif unk:
        verdict = "UNVERIFIED"
    elif parts and any(p["part"] in ("direction", "size", "factor", "trend") for p in parts):
        verdict = "SUPPORTED"
    else:
        verdict = None
    if not parts or verdict is None:
        return {"verdict": None, "reason": "", "failed_part": "", "parts": parts, "covers": covers, "kind": spec.kind}
    lead = bad or unk or parts
    reason = " ".join(p["detail"] for p in (bad + unk if (bad or unk) else parts))
    return {"verdict": verdict, "reason": reason, "failed_part": "; ".join(p["detail"].rstrip(". ") for p in (bad or unk)) if (bad or unk) else "",
            "parts": parts, "covers": covers if verdict != "UNVERIFIED" or not unk else [], "kind": spec.kind,
            "lead": lead[0]["part"]}


def _check_trend(spec: ChangeSpec, series: Optional[Series], add) -> None:
    if series is None:
        return             # no official series: the evidence judge decides (a trend claim is never skipped)
    ps = series.periods()
    if spec.since:
        ps = [p for p in ps if _pkey(p) >= _pkey(spec.since)]
    if spec.a_period and spec.b_period and not spec.since:
        ps = [p for p in ps if _pkey(spec.a_period) <= _pkey(p) <= _pkey(spec.b_period)]
    vals = [(p, series.get(p)) for p in ps]
    vals = [(p, r["value"]) for p, r in vals if r is not None]
    if len(vals) < 2:
        add("trend", "unverified", f"The official {series.name} series has fewer than two periods in this range, so the "
                                   "trend cannot be checked.")
        return
    breaks = [(a, b) for a, b in zip(vals, vals[1:]) if not ((b[1] - a[1]) * spec.direction > 0)]
    span = f"{vals[0][0]} to {vals[-1][0]}"
    seq = " → ".join(f"{_fmt(v, series.unit)} ({p})" for p, v in vals)
    if breaks:
        (pa, va), (pb, vb) = breaks[0]
        way = "rose" if vb > va else ("fell" if vb < va else "was unchanged")
        add("trend", "contradicted", f"Trend: the draft says ‘{spec.verb}’ every year, but official {series.name} {way} "
                                     f"from {_fmt(va, series.unit)} in {pa} to {_fmt(vb, series.unit)} in {pb} "
                                     f"(series {span}: {seq}).")
    else:
        add("trend", "supported", f"Trend: official {series.name} {('rose' if spec.direction > 0 else 'fell')} in every "
                                  f"year from {span} ({seq}).")


_SCALE_RX = re.compile(r"\b(thousand|lakh|lakhs|crore|crores|million|mn|billion|bn|trillion)\b|%|per ?cent", re.I)


def _scale_word(raw: str) -> str:
    """v0.5.3: the scale or unit word written with a figure ('' when none)."""
    m = _SCALE_RX.search(raw or "")
    w = (m.group(0) if m else "").lower()
    return {"lakhs": "lakh", "crores": "crore", "mn": "million", "bn": "billion", "per cent": "%", "percent": "%"}.get(w, w)
