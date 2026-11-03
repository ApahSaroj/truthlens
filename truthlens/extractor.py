"""Numeric claim extraction: sentence split, numbers, indicator, variant, period, geography.

Rule-based by design (deterministic, testable). spaCy is used for sentence splitting
when the `en_core_web_sm` model is installed; otherwise a regex splitter is used.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from typing import Optional

from .parsing import Number, Period, find_numbers, find_periods
from .readers import Block
from .registry import Indicator, load_registry

STATES = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana",
    "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur",
    "meghalaya", "mizoram", "nagaland", "odisha", "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal", "delhi", "jammu and kashmir",
    "jammu & kashmir", "ladakh", "puducherry", "chandigarh", "andaman", "lakshadweep", "dadra",
]
STATE_RX = re.compile(r"\b(" + "|".join(re.escape(s) for s in STATES) + r")\b", re.I)
SUBSTATE_RX = re.compile(r"\b(district|districts|taluks?|taluka|tehsil|mandal|gram panchayats?|panchayats?|"
                         r"municipal(?:ity| corporation)|zilla parishad)\b", re.I)
CLAUSE_RX = re.compile(r";|,\s*(?:and|while|whereas|but)\b|\bwhile\b|\bwhereas\b|\bbut\b|,\s*(?=[a-z]+'s\b)")
URBAN_RURAL_RX = re.compile(r"\b(urban|rural)\b", re.I)
NATIONAL_WORD_RX = re.compile(r"\b(india|india's|all[- ]india|national(?:ly)?|nationwide|the country|country's|across (?:the )?states|"
                              r"union government|centre|central government)\b", re.I)
LOCAL_RX = re.compile(r"\b(?:corporation|city|cities|town|towns|municipalit(?:y|ies)|ward|wards|block|blocks|village|villages|"
                      r"habitations?|basin|catchment)\b", re.I)
OWN_STATE_RX = re.compile(r"\b(?:the|this|our) state\b|\bstate['’]s\b|\blargest state\b|\bsmallest state\b", re.I)


def _sentence_geography(low: str) -> str:
    """v0.5.3: the place a sentence is about when the number's own clause names none ('' = all India)."""
    m = STATE_RX.search(low)
    if m:
        return m.group(1).title()
    m = SUBSTATE_RX.search(low) or LOCAL_RX.search(low)
    if m:
        return "Sub-national (" + m.group(0).lower() + ")"
    try:
        from .retrievers.state_data import DOC_STATE
        ds = DOC_STATE.get()
    except Exception:
        ds = None
    if ds:
        return ds.title()
    if OWN_STATE_RX.search(low):
        return "Sub-national (state)"
    return ""

STAGE_RX = [
    ("BE", re.compile(r"\bbudget(ed)? estimates?\b|\bBE\b|\bbudgeted\b|\btarget(ed)?\b|\bbudget target\b|\bprojected\b")),
    ("RE", re.compile(r"\brevised estimates?\b|\bRE\b|\brevised\b")),
    ("Provisional Actual", re.compile(r"\bprovisional actuals?\b|\bCGA\b")),
    ("Actual", re.compile(r"\bactuals?\b|\baccounts\b")),
]
OLD_BASE_RX = re.compile(r"2011[-–]12\s*(prices|base|series)|base(\s*year)?\s*(of\s*)?2011[-–]12|\bold (gdp |cpi |iip )?series\b|2012\s*=\s*100|\b2012 base\b|\bbase 2012\b", re.I)
NEW_BASE_RX = re.compile(r"2022[-–]23\s*(prices|base|series)|base(\s*year)?\s*(of\s*)?2022[-–]23|\bnew (gdp |cpi |iip )?series\b|2024\s*=\s*100", re.I)

COMPARATORS = [
    ("ge", re.compile(r"(\bover|\bcrossed|\bcrossing|\bsurpassed|\bmore than|\babove|\bexceed(ed|ing|s)?|\bat least|\bupwards of|>)\s*$", re.I)),
    ("le", re.compile(r"(\bunder|\bless than|\bbelow|\bat most|\bup to|<)\s*$", re.I)),
    ("approx", re.compile(r"(\babout|\baround|\bnearly|\balmost|\bapproximately|\broughly|\bclose to|\bsome|~|\bapprox\.?)\s*$", re.I)),
]
CHANGE_OF_RX = re.compile(r"\b(an? )?(increase|decrease|rise|fall|decline|drop|jump|gain|reduction|improvement)\s+of\s*$", re.I)
CHANGE_RX = re.compile(r"\b(rose|rise[sn]?|increase[sd]?|grew|jump(ed|s)?|climb(ed|s)?|fell|fall(en|s)?|decline[sd]?|"
                       r"drop(ped|s)?|decrease[sd]?|reduce[sd]?|improve[sd]?|went (up|down)|up|down)\b[^.;%]{0,25}\bby\s*$", re.I)
CURRENCY_CONTEXT_RX = re.compile(r"₹|\brs\.?\b|\brupees?\b|\binr\b", re.I)


@dataclass
class Claim:
    id: str
    sentence: str
    location: str
    number: Number
    indicator: Optional[str] = None
    indicator_name: Optional[str] = None
    mention: Optional[str] = None
    generic_mention: bool = False
    variant: Optional[str] = None
    variant_explicit: bool = False
    stage: Optional[str] = None
    base_hint: Optional[str] = None
    period: Optional[Period] = None
    periods_in_sentence: list = field(default_factory=list)
    comparator: Optional[str] = None
    claim_type: str = "level"
    geography: str = "India"
    skip_reason: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        return d


@lru_cache(maxsize=1)
def _spacy():
    try:
        import spacy  # noqa
        return spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "tagger", "attribute_ruler"])
    except Exception:
        return None


ABBREV = (r"(?<!\bal\.)(?<!\bRs\.)(?<!\brs\.)(?<!\bNo\.)(?<!\bno\.)(?<!\bvs\.)(?<!e\.g\.)(?<!i\.e\.)(?<!\bDr\.)(?<!\bMr\.)"
          r"(?<!\bMs\.)(?<!\bSt\.)(?<!\bp\.)(?<!\bpp\.)(?<!\bviz\.)(?<!\bapprox\.)(?<!\bLtd\.)(?<!\bCo\.)"
          # v0.5.3: abbreviations common in Indian government documents ('1,91,791 Sq. Kms.', 'Govt. of', 'Dt. 12.3.2024')
          r"(?<!\bSq\.)(?<!\bsq\.)(?<!\bGovt\.)(?<!\bDept\.)(?<!\bDeptt\.)(?<!\bDt\.)(?<!\bNos\.)(?<!\bnos\.)"
          r"(?<!\bHa\.)(?<!\bKm\.)(?<!\bAnr\.)(?<!\bSmt\.)(?<!\bShri\.)(?<!\bHon\.)(?<!\bProf\.)")
SENT_SPLIT = re.compile(r"(?<=[.!?])" + ABBREV + r"\s+(?=[A-Z0-9₹“\"(\[])")


def split_sentences(text: str) -> list[tuple[int, str]]:
    """Return (offset, sentence) pairs."""
    nlp = _spacy()
    if nlp is not None and len(text) < 100000:
        try:
            return [(s.start_char, s.text) for s in nlp(text).sents if s.text.strip()]
        except Exception:
            pass
    out, pos = [], 0
    for part in SENT_SPLIT.split(text):
        idx = text.find(part, pos)
        if part.strip():
            out.append((idx, part))
        pos = idx + len(part)
    return out


def _compatible(ind: Indicator, n: Number, sentence: str) -> bool:
    if ind.unit_kind == "percent":
        return n.unit_kind in ("percent", "pp")
    if ind.unit_kind == "inr":
        if n.unit_kind == "inr":
            return True
        return n.unit_kind == "count" and n.multiplier in ("crore", "lakh crore", "lakh", "trillion", "billion", "million") \
            and bool(CURRENCY_CONTEXT_RX.search(sentence))
    if ind.unit_kind == "count":
        if n.unit_kind == "count":
            return not CURRENCY_CONTEXT_RX.search(sentence[max(0, n.start - 3):n.end + 1])
        return n.unit_kind == "bare" and abs(n.value) >= 10000
    return False


def _is_claim_number(n: Number, sentence: str) -> Optional[str]:
    """Return None if the number should be checked, else a reason to ignore it."""
    if n.unit_kind == "bare":
        if abs(n.value) < 10000:
            return "bare small number"
        if 1900 <= n.value <= 2100 and n.decimals == 0:
            return "year"
    before = sentence[max(0, n.start - 12):n.start].lower()
    after = sentence[n.end:n.end + 12].lower()
    if re.search(r"\b(aged?|ages)\s*$", before) or re.match(r"\s*(years?|yrs|months?)\b", after):
        if n.unit_kind in ("bare", "count"):
            return "age or duration"
    if re.search(r"(table|figure|fig\.|section|annex|page|statement|no\.)\s*$", before):
        return "reference number"
    return None


def extract_claims(blocks: list[Block], registry: Optional[dict] = None) -> list[Claim]:
    reg = registry or load_registry()
    claims: list[Claim] = []
    for block in blocks:
        for _, sent in split_sentences(block.text):
            claims.extend(_claims_in_sentence(sent, block.location, reg, start_id=len(claims)))
    return claims


def _claims_in_sentence(sent: str, location: str, reg: dict, start_id: int = 0) -> list[Claim]:
    periods = find_periods(sent)
    numbers = find_numbers(sent, [(p.start, p.end) for p in periods])
    low = sent.lower()
    mentions = []  # (start, end, indicator, generic)
    for ind in reg.values():
        for s, e, generic in ind.mentions(low):
            mentions.append((s, e, ind, generic))

    out: list[Claim] = []
    claim_periods = [p for p in periods if not p.is_base]
    for n in numbers:
        reason = _is_claim_number(n, sent)
        if reason:
            continue
        c = Claim(id=f"c{start_id + len(out) + 1}", sentence=sent.strip(), location=location, number=n,
                  periods_in_sentence=[p.label for p in claim_periods])
        # indicator association
        best = None
        for s, e, ind, generic in mentions:
            if not _compatible(ind, n, sent):
                continue
            if e <= n.start:
                dist = n.start - e
            elif s >= n.end:
                dist = (s - n.end) * 1.6 + 5
            else:
                dist = 0
            if dist > 160:
                continue
            lo, hi = min(s, n.start), max(e, n.end)
            between = low[lo:hi]
            if ";" in between:
                dist += 60
            after = low[hi:hi + 12]
            cut = re.search(r"[,;]|\bwhile\b|\band\b", after)
            win = low[max(0, lo - 15):hi] + (after[:cut.start()] if cut else after)
            if ind.excluded(win):
                continue
            score = -dist + ind.priority * 0.5 - (15 if generic else 0)
            if best is None or score > best[0]:
                best = (score, s, e, ind, generic)
        if n.unit_kind == "usd":
            c.skip_reason = "Values in US dollars are not checked in v0.1 (official Indian series are in ₹)."
        if best:
            _, s, e, ind, generic = best
            c.indicator, c.indicator_name = ind.id, ind.name
            c.mention, c.generic_mention = sent[s:e], generic
            lo, hi = min(s, n.start), max(e, n.end)
            local = low[max(0, lo - 40):min(len(low), hi + 40)]
            v = ind.detect_variant(local)
            c.variant_explicit = v is not None
            c.variant = v or ind.default_variant
            prev_end = max([m.end for m in numbers if m.end <= n.start] + [0])
            next_start = min([m.start for m in numbers if m.start >= n.end] + [len(sent)])
            tail = sent[n.end:min(next_start, n.end + 35)]
            cut = re.search(r"\band\b|;|,|\bwhile\b|\bbut\b|\bwhereas\b", tail)
            if cut:
                tail = tail[:cut.start()]
            stage_win = sent[max(prev_end, lo - 30):n.end] + tail
            for stage, rx in STAGE_RX:
                if rx.search(stage_win):
                    c.stage = stage
                    break
            if OLD_BASE_RX.search(sent):
                c.base_hint = "old"
            elif NEW_BASE_RX.search(sent):
                c.base_hint = "new"
            # geography: only within the clause that holds the number and its indicator
            gstart = max(0, lo - 40)
            gend = min(len(low), hi + 40)
            seps = list(CLAUSE_RX.finditer(low))
            for m in seps:
                if m.end() <= lo:
                    gstart = max(gstart, m.end())
                elif m.start() >= hi:
                    gend = min(gend, m.start())
                    break
            gwin = low[gstart:gend]
            geo = STATE_RX.search(gwin)
            if geo:
                c.geography = geo.group(1).title()
            elif SUBSTATE_RX.search(gwin):
                # v0.5.2: a district, block, village or city figure is never compared with an all-India value
                c.geography = "Sub-national (" + SUBSTATE_RX.search(gwin).group(1).lower() + ")"
            elif URBAN_RURAL_RX.search(gwin) and ind.id in ("unemployment_rate", "lfpr", "cpi_inflation",
                                                             "child_stunting", "child_wasting", "child_underweight"):
                c.geography = "India (" + URBAN_RURAL_RX.search(gwin).group(1).lower() + ")"
            elif not NATIONAL_WORD_RX.search(low):
                # v0.5.3: the clause names no place, but the sentence (or the document) is about a State, a city or a
                # district: a state figure is never compared with an all-India value (real policy documents: "Maharashtra
                # ... population of 112.4 million (Census 2011)" was called wrong against India's 121 crore)
                c.geography = _sentence_geography(low) or c.geography
        # period: nearest after the number (within 45 chars), else nearest before, else any after
        c.period = _nearest_period(n, claim_periods, sent)
        # comparator and change wording
        before = sent[max(0, n.start - 30):n.start]
        for name, rx in COMPARATORS:
            if rx.search(before):
                c.comparator = name
                break
        if n.unit_kind == "pp":
            c.claim_type = "change"
        elif c.indicator and "growth" not in c.indicator and (CHANGE_RX.search(sent[max(0, n.start - 60):n.start])
                                                            or CHANGE_OF_RX.search(sent[max(0, n.start - 30):n.start])):
            c.claim_type = "change"
        out.append(c)
    _fix_from_to(out, claim_periods)
    return out


def _nearest_period(n: Number, periods: list[Period], sent: str = "") -> Optional[Period]:
    if not periods:
        return None
    # "2024-25: 4.8%" (table cells with column headers) -> the label directly before wins
    for p in periods:
        if p.end <= n.start and re.fullmatch(r"[\s:=–\-(]*", sent[p.end:n.start] or ""):
            return p
    after = [p for p in periods if p.start >= n.end and p.start - n.end <= 45 and "|" not in sent[n.end:p.start]]
    if after:
        return min(after, key=lambda p: p.start - n.end)
    before = [p for p in periods if p.end <= n.start]
    if before:
        return max(before, key=lambda p: p.end)
    return min(periods, key=lambda p: abs(p.start - n.end))


def _fix_from_to(claims: list[Claim], periods: list[Period]):
    """'Between 2017-18 and 2023-24, X fell from 6.0% to 3.2%': assign periods in order."""
    lv = [c for c in claims if c.indicator and c.claim_type == "level"]
    if len(lv) != 2 or len(periods) != 2 or lv[0].indicator != lv[1].indicator:
        return
    a, b = lv
    if a.period is b.period and a.period is not None:
        s = a.sentence.lower()
        if re.search(r"\bfrom\b", s) and re.search(r"\bto\b", s):
            a.period, b.period = periods[0], periods[1]
