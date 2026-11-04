"""v0.5.2 bundled state and district data (truthlens/data/state_data.json, built by scripts/build_state_data.py).

  Census 2011 (Table A-1): population, households, inhabited villages, towns, area and density; total / rural /
      urban; every State/UT and district (2011 boundaries).
  CGWB Dynamic Ground Water Resources assessment 2025: state-wise recharge, extractable resource, extraction and
      stage of ground water extraction (%).
  NFHS-5 Karnataka (2019-21): household drinking water and sanitation figures from the state report (support only).

Works offline and in Quick mode (no request is ever sent). Fail-closed rules on top of the table matcher:
  * a figure is only contradicted when the draft names the period (for example "Census 2011", "2025 assessment");
    an undated figure that differs may be a newer estimate, so it stays "couldn't check" with the official value shown;
  * NFHS-5 figures (rounded household percentages) can support a figure, never contradict one;
  * a district-level figure is never contradicted (district names and boundaries change); it can be supported;
  * when the sentence names no State but the document is clearly about one (most State names in it are that State),
    the figure is compared with that State's row: a match is reported with the assumption stated, a difference is
    never called wrong;
  * Census 2011 rows for undivided Andhra Pradesh and Jammu and Kashmir (since reorganised) are not used to confirm
    or contradict (v0.6: an Andhra Pradesh figure that equals the undivided 2011 row is reported as DATED).

v0.6 additions:
  * share of India: "Uttar Pradesh accounts for 16.17% of the country's population ... 7.33% of the country's land
    area" is computed from the Census 2011 State row and the All India row (never from a sum of States);
  * areas in hectares (ha, mha, million/lakh ha, hectares) are converted to sq km (1 sq km = 100 ha);
  * DATED: a figure compared with official data for another year or other State boundaries is never called wrong.
    It is DATED when the figure equals the undivided State before a split (Uttarakhand from Uttar Pradesh
    9 Nov 2000, Jharkhand from Bihar 15 Nov 2000, Chhattisgarh from Madhya Pradesh 1 Nov 2000, Telangana from
    Andhra Pradesh 2 Jun 2014), when the sentence names an earlier year than the data (a 2009 groundwater figure
    against the CGWB 2025 assessment), or when the sentence gives no year and the document itself is older than
    the data (a 1999 policy against Census 2011).
"""
from __future__ import annotations

import contextvars
import json
import re
from functools import lru_cache
from importlib import resources
from typing import Optional

from .ministry import GroupedSource
from .tables import STATE_RX, claim_geo, claim_periods, norm_state

# the State a long document is about (set by Pipeline.run when one State dominates the document)
DOC_STATE: contextvars.ContextVar = contextvars.ContextVar("truthlens_doc_state", default=None)
# v0.6: the year of the document (from its title lines), set by Pipeline.run
DOC_YEAR: contextvars.ContextVar = contextvars.ContextVar("truthlens_doc_year", default=None)
# parent State -> (new State, its name, date it was formed, year)
BOUNDARY_CHANGES = {
    "uttar pradesh": ("uttarakhand", "Uttarakhand", "9 November 2000", 2000),
    "bihar": ("jharkhand", "Jharkhand", "15 November 2000", 2000),
    "madhya pradesh": ("chhattisgarh", "Chhattisgarh", "1 November 2000", 2000),
    "andhra pradesh": ("telangana", "Telangana", "2 June 2014", 2014),
}
DOC_YEAR_RX = re.compile(r"\b(?:policy|policies|draft|report|plan|act|rules|guidelines|vision|strategy|mission|order|"
                         r"notification|resolution|assessment|g\.?\s?o\.?)\b[^\n]{0,45}?(?<![\d.])((?:19|20)\d{2})(?![\d])", re.I)
NATIONAL_RX = re.compile(r"\b(india|all[- ]india|national(?:ly)?|country|nation|nationwide|across states)\b", re.I)
SKIP_CENSUS_STATES = {"andhra pradesh", "jammu and kashmir"}      # boundaries changed after 2011

# today's names -> the 2011 Census district names (Karnataka; extend as needed)
DISTRICT_ALIASES = {
    "belagavi": "belgaum", "vijayapura": "bijapur", "ballari": "bellary", "shivamogga": "shimoga",
    "chikkamagaluru": "chikmagalur", "tumakuru": "tumkur", "bengaluru urban": "bangalore", "bangalore urban": "bangalore",
    "bengaluru rural": "bangalore rural", "mysuru": "mysore", "kalaburagi": "gulbarga", "chamarajanagara": "chamarajanagar",
    "davangere": "davanagere", "chikkaballapur": "chikkaballapura", "ramanagaram": "ramanagara", "yadagiri": "yadgir",
}


@lru_cache(maxsize=1)
def load_state_data() -> dict:
    text = resources.files("truthlens.data").joinpath("state_data.json").read_text(encoding="utf-8")
    return json.loads(text)


def dominant_state(texts) -> Optional[str]:
    """The State a document is about: at least 3 mentions and at least 70% of all State mentions."""
    counts: dict = {}
    for t in texts:
        for m in STATE_RX.finditer(t or ""):
            s = norm_state(m.group(1))
            counts[s] = counts.get(s, 0) + 1
    if not counts:
        return None
    top, n = max(counts.items(), key=lambda kv: kv[1])
    return top if n >= 3 and n >= 0.7 * sum(counts.values()) else None


def document_year(texts, now_year: Optional[int] = None) -> Optional[int]:
    """v0.6: the year a document is from, read from its first lines (title, order number, cover date): the latest year
    that follows a word such as Policy, Draft, Report, Plan or Order in the first 12 blocks. None when not found."""
    import datetime as _dt
    now_year = now_year or _dt.date.today().year
    years = []
    for t in list(texts)[:12]:
        for m in DOC_YEAR_RX.finditer(t or ""):
            y = int(m.group(1))
            if 1947 <= y <= now_year:
                years.append(y)
    return max(years) if years else None


def census_total(state: str) -> Optional[dict]:
    """The Census 2011 'total' row of a State (norm_state name) or of All India ('india')."""
    want = "all india" if state in ("india", "all india") else state
    return next((r for r in load_state_data()["census2011_states"]
                 if r["tru"] == "total" and norm_state(r["state"]) == want), None)


def undivided(state: str, key: str) -> Optional[tuple]:
    """(value, explanation) of a Census 2011 measure for the State as it was before its split, or None."""
    bc = BOUNDARY_CHANGES.get(state)
    if not bc:
        return None
    parent = census_total(state)
    if parent is None or parent.get(key) in (None, ""):
        return None
    if state == "andhra pradesh":     # Census 2011 counted Andhra Pradesh before Telangana was formed
        return float(parent[key]), _n(parent[key])
    child = census_total(bc[0])
    if child is None or child.get(key) in (None, ""):
        return None
    v = float(parent[key]) + float(child[key])
    return v, f"{_n(parent[key])} ({parent['state']}) + {_n(child[key])} ({child['state']}) = {_n(v)}"


def _n(v) -> str:
    v = float(v)
    return f"{v:,.0f}" if abs(v - round(v)) < 1e-9 else f"{v:,.2f}"


def _eq(v: float, claimed: float, dec: int) -> bool:
    """Strict rounding, as in tables.match_rows: the official value rounded to the draft's decimals."""
    return abs(round(v, dec) - claimed) < 1e-9 or abs(v - claimed) < 0.5 * 10 ** (-dec) + 1e-9


SHARE_AFTER_RX = re.compile(
    r"^\s*(?:%|per\s?cent)?\s*(?:share\s+)?of\s+(?:the\s+)?(?:"
    r"(?P<n1>country|india|nation|all[- ]india)(?:['’]s)?\s+(?:total\s+)?(?P<m1>population|(?:geographical\s+|geographic\s+|"
    r"land\s+|total\s+)?(?:land\s+)?area|land(?:\s+mass)?)"
    r"|(?:total\s+)?(?P<m2>population|(?:geographical\s+|geographic\s+|land\s+)?area|land(?:\s+mass)?)\s+of\s+(?:the\s+)?"
    r"(?P<n2>country|india|nation))\b", re.I)
HA_U = r"(?:m\.?\s?ha\b\.?|ha\b\.?|hect(?:are)?s?\b\.?)"
SQKM_U = r"(?:sq\.?\s?kms?\b\.?|sq\.?\s?kilomet(?:re|er)s?\b|square\s+kilomet(?:re|er)s?\b|km2\b|km²)"
AREA_UNIT_RX = re.compile(rf"^\s*(?P<unit>{HA_U}|{SQKM_U})", re.I)
AREA_AFTER_RX = re.compile(r"^\s*[.,)]?\s*(?:of\s+(?:the\s+)?(?:total\s+)?(?:geographical|geographic|land|reporting)\s+area\b|"
                           r"of\s+(?:the\s+)?total\s+area\b|(?:total\s+)?geographical\s+area\b)", re.I)
AREA_BEFORE_RX = re.compile(r"(?:\b(?:geographical|geographic|land|total|reporting)\s+area|\bcovers\s+an\s+area|\bspread\s+over\s+an\s+area|"
                            r"\bspread\s+over|\bstate\s+area)\s*(?:of\s+(?:the\s+)?(?:state|country|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*)?"
                            r"(?:is\s+|of\s+|about\s+|around\s+|approximately\s+|nearly\s+|roughly\s+|some\s+|:\s*|-\s*)*\(?\s*$", re.I)
AREA_NOT_RX = re.compile(r"\b(?:irrigat\w*|flood\w*|forest\w*|cultur\w*|cultivab\w*|cropped|crop|command|sown|net|gross|under|"
                         r"prone|affected|wet\w*|basin|catchment|drainage|urban|rural|recharge|suitable|waterlogged|saline|"
                         r"degraded|stress\w*|protected|district|city|municipal)\b", re.I)


CENSUS_MEASURES = [
    # (key, label used to pick the table, unit base, words in the claim that select this measure)
    ("population", "population", "count", r"\b(population|people|persons|inhabitants)\b"),
    ("households", "households", "count", r"\bhouseholds?\b"),
    ("villages_inhabited", "inhabited villages", "count", r"\bvillages?\b"),
    ("towns", "towns", "count", r"\btowns?\b"),
    ("area_sq_km", "area sq km", None, r"\b(area|sq\.? ?km|square kilomet)"),
    ("density", "population density per sq km", None, r"\b(density|per sq\.? ?km|per square kilomet)"),
]
CGWB_MEASURES = [
    ("stage_pct", "stage of ground water extraction", None, "pct"),
    ("recharge_bcm", "total annual ground water recharge", None, "recharge"),
    ("extractable_bcm", "annual extractable ground water resource", None, "extractable"),
    ("extraction_bcm", "annual ground water extraction for all uses", None, "extraction"),
]
PCT_RX = re.compile(r"%|\bper ?cent\b|\bpercentage\b")
BCM_RX = re.compile(r"\bbcm\b|\bbillion cubic met")


PCT_CLAUSE_RX = re.compile(r"[^,;]*\d\s*(?:%|per ?cent\b)[^,;]*")


def census_measures(low: str) -> list:
    """The one Census measure a sentence is about (most specific wording first), so a population figure is never
    compared with a household count or a density. v0.5.3: clauses that carry a percentage are ignored when choosing
    (they used to switch the Census off for the whole sentence: 'Kerala ... (38,863 sq. km) covering 1.3 per cent of
    the area of the country')."""
    low = PCT_CLAUSE_RX.sub(" ", low)
    if not re.search(r"\d", low):
        return []
    # v0.5.3: one measure per clause that holds a figure ('population of 112.4 million (Census 2011) and area of 0.308
    # million sq km' -> population and area); each figure is then matched only to the measure its own clause names
    out = []
    for cl in re.split(r",(?!\d)|;|\band\b|\bwhile\b|\bwhereas\b", low):
        if not re.search(r"\d", cl):
            continue
        for key in ("density", "area_sq_km", "households", "villages_inhabited", "towns", "population"):
            m = next(x for x in CENSUS_MEASURES if x[0] == key)
            if re.search(m[3], cl):
                if m not in out:
                    out.append(m)
                break
    if not out:
        for key in ("density", "area_sq_km", "households", "villages_inhabited", "towns", "population"):
            m = next(x for x in CENSUS_MEASURES if x[0] == key)
            if re.search(m[3], low):
                return [m]
    return out


def cgwb_measures(low: str) -> list:
    if not re.search(r"ground ?water", low):
        return []
    if BCM_RX.search(low):
        if "recharge" in low:
            return [CGWB_MEASURES[1]]
        if "extractable" in low or "availab" in low:
            return [CGWB_MEASURES[2]]
        if re.search(r"\b(extraction|draft|use|uses|withdrawal)\b", low):
            return [CGWB_MEASURES[3]]
        return []
    if PCT_RX.search(low) and re.search(r"\bstage\b|\bextraction\b|\bexploitation\b", low):
        return [CGWB_MEASURES[0]]
    return []


DISTRICT_WORD_RX = re.compile(r"\bdistricts?\b|\bzilla\b")


@lru_cache(maxsize=64)
def _district_rx(state: str):
    """(one compiled alternation of the district names usable for this State, or for any State when '', {name: 2011 name}).
    A name found in two States is left out when no State is given (ambiguous)."""
    names: dict = {}
    for r in load_state_data()["census2011_districts"]:
        if state and norm_state(r["state"] or "") != state:
            continue
        names.setdefault(r["district"].lower(), set()).add(norm_state(r["state"] or ""))
    canon = {n: n for n, sts in names.items() if len(sts) == 1}
    for alias, real in DISTRICT_ALIASES.items():
        if real in canon:
            canon[alias] = real
    if not canon:
        return re.compile(r"(?!x)x"), {}
    alt = "|".join(re.escape(n) for n in sorted(canon, key=len, reverse=True))
    return re.compile(rf"\b({alt})\b(?!\s+(?:city|corporation|urban agglomeration|municipal))"), canon


class StateDataSource(GroupedSource):
    name = "state-data"
    badge = "Official data (bundled)"
    publisher = "Census 2011 / CGWB / NFHS-5 (bundled)"
    portal = "bundled with TruthLens"
    keywords = ["population", "people", "persons", "inhabitants", "households", "household", "villages", "village",
                "towns", "area", "density", "groundwater", "ground water", "extraction", "recharge", "aquifer",
                "drinking water", "piped", "tap", "toilet", "sanitation", "open defecation", "pucca", "electricity",
                "clean fuel", "census", "nfhs"]
    ttl = 0

    def __init__(self, cfg, session=None):
        super().__init__(cfg, session)
        self.offline = False          # bundled: works offline and in Quick mode
        self.unit_base = {}

    def unavailable(self) -> Optional[str]:
        return None

    def min_relevance(self, label: str) -> float:
        """v0.5.3: a Census table is only offered when the sentence names its measure in words (census_measures), and
        rows are already limited to the sentence's State, so the generic word-overlap cut-off is relaxed for it. Unit
        words are dropped by the term matcher, so 'The State of Karnataka covers an area of 1,91,791 Sq. Kms.' scored
        0.42 (under 0.5) and the pipeline reported 'no matching table' for the bundled Census area."""
        return 0.3 if "(Census 2011" in label else 0.5

    def status(self) -> dict:
        d = load_state_data()
        return {"name": self.name, "configured": True,
                "detail": f"bundled: Census 2011 ({len(d['census2011_states'])} State rows, {len(d['census2011_districts'])} "
                          f"district rows), CGWB groundwater 2025 ({len(d['cgwb2025_states'])} rows), NFHS-5 Karnataka"}

    # ------------------------------------------------------------------ data
    def _district(self, text: str, state: Optional[str]) -> Optional[str]:
        low = (text or "").lower()
        if not DISTRICT_WORD_RX.search(low):
            return None
        rx, canon = _district_rx(state or "")
        hits = list(dict.fromkeys(canon[m.group(1)] for m in rx.finditer(low)))
        return hits[0] if len(hits) == 1 else None

    def groups(self, claim_text: str):
        d = load_state_data()
        groups, sources = {}, {}
        geo = claim_geo(claim_text)
        state = None if geo == "india" else geo
        district = self._district(claim_text, state)
        csrc = dict(d["meta"]["sources"]["census2011"])
        if district:
            rows = [r for r in d["census2011_districts"] if r["district"].lower() == district]
            label_geo = f"{rows[0]['district']} district" if rows else ""
        else:
            rows = [r for r in d["census2011_states"] if norm_state(r["state"]) not in SKIP_CENSUS_STATES]
            label_geo = ""
        low = (claim_text or "").lower()
        for key, label, base, _rx in census_measures(low):
            out = []
            for r in rows:
                v = r.get(key)
                if v in (None, "") or (key in ("villages_inhabited",) and r["tru"] == "urban") or \
                        (key == "towns" and r["tru"] == "rural"):
                    continue
                area = {"total": "total", "rural": "rural", "urban": "urban"}.get(r["tru"], r["tru"])
                out.append({"state": r["state"], "year": "2011", "indicator": f"{label} {area}".strip(),
                            "area": area, "value": v})
            lab = f"{label} (Census 2011{', ' + label_geo if label_geo else ''})"
            groups[lab] = out
            sources[lab] = csrc
            if base:
                self.unit_base[lab] = base
        if not district:
            gsrc = dict(d["meta"]["sources"]["cgwb2025"])
            for key, label, base, _k in cgwb_measures(low):
                lab = f"{label} (CGWB assessment 2025)"
                groups[lab] = [{"state": r["state"], "year": "2025", "indicator": label, "value": r[key]}
                               for r in d["cgwb2025_states"]]
                sources[lab] = gsrc
            if PCT_RX.search(low):
                nsrc = dict(d["meta"]["sources"]["nfhs5_ka"])
                for r in d["nfhs5_states"]:
                    lab = f"NFHS-5 {r['indicator']}"
                    groups.setdefault(lab, []).append({"state": r["state"], "year": "2019-21", "indicator": r["indicator"],
                                                       "area": r["area"], "value": r["value"]})
                    sources[lab] = nsrc
        return groups, sources

    # ------------------------------------------------------------------ v0.6: share of India, hectares, DATED
    def _own_state(self, claim_text: str) -> tuple:
        """(State, assumed) for a share or area figure: the one State the sentence names, or the document's State when
        the sentence says 'the State'. (None, False) when it names several States or none."""
        names = {norm_state(m.group(1)) for m in STATE_RX.finditer(claim_text or "")}
        if len(names) == 1:
            return names.pop(), False
        if names:
            return None, False
        ds = DOC_STATE.get()
        if ds and re.search(r"\bstate(?:['’]s)?\b", claim_text or "", re.I):
            return ds, True
        return None, False

    def _finding(self, n, claim_text, verdict, reason, *, label, ind, value, display, period, state, snippet):
        src = dict(load_state_data()["meta"]["sources"]["census2011"])
        src["retriever"] = self.name
        return {
            "claim_id": "", "location": "", "sentence": claim_text, "claimed": n.raw, "claimed_value": n.value,
            "indicator": f"state-data:{ind}", "indicator_name": label, "period": period, "geography": state.title(),
            "verdict": verdict, "reason": reason, "negated": False, "direction": 0,
            "official": {"value": value, "display": display, "period": period, "variant": None, "stage": None,
                         "base": None, "vintage": src.get("published"), "status": None, "series_id": f"state-data:{ind}",
                         "series": label, "source": {k: src.get(k) for k in ("url", "title", "publisher", "published")},
                         "geography": state.title(), "live": False, "live_source": False, "bundled": True,
                         "retriever": self.name, "as_of": None, "snippet": f"{label}: {snippet}"},
            "citation": f"{label}: {snippet}. Source: {src.get('publisher')}, {src.get('title')} ({src.get('url')})",
            "warnings": [], "alternatives": [], "show_official": True,
        }

    @staticmethod
    def _years(periods: set) -> list:
        return sorted({int(p[:4]) for p in periods if re.match(r"(?:19|20)\d{2}", p)})

    def _decide(self, n, claim_text, *, kind, now, undiv, state, assumed, data_year=2011):
        """Verdict and reason for one figure against a Census 2011 value (now) and the undivided-State value (undiv).
        kind: 'share' (a percentage of India) or 'area'. Returns (verdict, reason)."""
        from ..polarity import negated
        from .tables import APPROX_RX
        claimed, dec = n.raw_value, n.decimals
        periods = claim_periods(claim_text)
        years = self._years(periods)
        named_data_year = any(p[:4] == str(data_year) for p in periods)
        earlier = bool(years) and not named_data_year and all(y < data_year for y in years)
        later = bool(years) and not named_data_year and all(y > data_year for y in years)
        doc_year = DOC_YEAR.get()
        bc = BOUNDARY_CHANGES.get(state)
        assume_note = (f" The sentence names no State; it was compared with {state.title()}, the State this document is "
                       "about." if assumed else "")
        year_note = ("" if years else f" The draft gives no year, so the comparison year is {data_year} (Census {data_year}).")
        i = claim_text.find(n.raw)
        if i >= 0 and negated(claim_text[:i]):
            return "UNVERIFIED", f"The draft denies the figure ({n.raw}); {now[1] if now else ''}"
        approx = i >= 0 and bool(APPROX_RX.search(claim_text[max(0, i - 30):i]))
        if now is not None and _eq(now[0], claimed, dec):
            if earlier and kind != "area":
                return "DATED", (f"Dated: the draft dates this figure {', '.join(map(str, years))}, but it equals the "
                                 f"Census {data_year} value ({now[1]}).{assume_note}")
            return "MATCH", f"Matches Census {data_year}: {now[1]}.{year_note if kind == 'share' else ''}{assume_note}"
        if undiv is not None and bc and _eq(undiv[0], claimed, dec):
            if state == "andhra pradesh" and doc_year and doc_year < bc[3]:
                return "MATCH", (f"Matches Census {data_year} for Andhra Pradesh as it was then ({undiv[1]}; Telangana was "
                                 f"formed on {bc[2]}).{assume_note}")
            return "DATED", (f"Dated (boundary): the figure matches undivided {state.title()}: {undiv[2]}. {bc[1]} was "
                             f"formed from {state.title()} on {bc[2]}, so this is the figure for the State before that "
                             f"change" + (f"; today's figure: {now[1]}" if now else "") + f".{assume_note}")
        if now is None:
            return "UNVERIFIED", ""
        if earlier and (kind != "area" or (bc and min(years) < bc[3])):
            return "DATED", (f"Dated: the draft's figure is for {', '.join(map(str, years))}; the bundled data is Census "
                             f"{data_year} ({now[1]}). A figure for an earlier year is not called wrong.{assume_note}")
        pre_split = bool(bc and doc_year and doc_year < bc[3] and undiv is not None)
        if not years and doc_year and doc_year < data_year and (kind != "area" or pre_split):
            extra = (f" The document predates the formation of {bc[1]} ({bc[2]}); undivided {state.title()}: {undiv[2]}."
                     if pre_split else "")
            return "DATED", (f"Dated: the document is from {doc_year}, before Census {data_year}; its figure is for an "
                             f"earlier year or boundary. Census {data_year}: {now[1]}.{extra}{assume_note}")
        if named_data_year and not assumed and not approx and kind == "share":
            # a share of India named as Census 2011 is computed from the same two Census rows, so a different figure is
            # wrong. A State area is never called wrong here: published areas differ by source (Survey of India,
            # Census, State records), so a different area stays open with the Census value shown
            return "MISMATCH", f"Census {data_year}: {now[1]}; the draft says {n.raw}.{assume_note}"
        if approx and now[0] and abs(now[0] - claimed) <= 0.10 * abs(now[0]):
            return "UNVERIFIED", (f"The draft gives an approximate figure ({n.raw}); Census {data_year}: {now[1]}."
                                  f"{year_note}{assume_note}")
        if later:
            return "UNVERIFIED", (f"Differs from Census {data_year} ({now[1]}), but the draft's figure is for "
                                  f"{', '.join(map(str, years))}, after the Census; not called wrong.{assume_note}")
        return "UNVERIFIED", (f"Differs: Census {data_year} gives {now[1]}; the draft says {n.raw}.{year_note} Its figure "
                              f"may be for another year (an earlier Census or an estimate), so it is not called wrong."
                              f"{assume_note}")

    def _share_findings(self, claim_text: str, numbers: list) -> list:
        """v0.6: 'X accounts for 16.17% of the country's population / 7.33% of the country's land area'."""
        out = []
        pct = [n for n in numbers if getattr(n, "unit_kind", "") == "percent" or "%" in n.raw or "per cent" in n.raw.lower()]
        if not pct:
            return out
        state, assumed = None, False
        india = census_total("india")
        for n in pct:
            i = claim_text.find(n.raw)
            if i < 0:
                continue
            m = SHARE_AFTER_RX.match(claim_text[i + len(n.raw): i + len(n.raw) + 90])
            if not m:
                continue
            if state is None:
                state, assumed = self._own_state(claim_text)
            if not state or state == "india" or india is None:
                return out
            meas = (m.group("m1") or m.group("m2") or "").lower()
            key = "population" if meas.startswith("population") else "area_sq_km"
            word = "population" if key == "population" else "area"
            unit = "" if key == "population" else " sq km"
            row = census_total(state) if state not in SKIP_CENSUS_STATES else None
            now = None
            if row is not None and row.get(key):
                v = 100.0 * float(row[key]) / float(india[key])
                now = (v, f"{row['state']} {word} {_n(row[key])}{unit} of All India {_n(india[key])}{unit} = {v:.2f}%")
            und = undivided(state, key)
            undiv = None
            if und is not None:
                v2 = 100.0 * und[0] / float(india[key])
                undiv = (v2, f"{und[1]}", f"{und[1]}{unit} of All India {_n(india[key])}{unit} = {v2:.2f}%")
            if now is None and undiv is None:
                continue
            verdict, reason = self._decide(n, claim_text, kind="share", now=now, undiv=undiv, state=state, assumed=assumed)
            if not reason:
                continue
            ref = now or undiv
            label = f"share of India's {word} (Census 2011)"
            out.append(self._finding(n, claim_text, verdict, reason, label=label, ind=f"share-{word}",
                                     value=round(ref[0], 4), display=f"{ref[0]:.2f}%", period="2011", state=state,
                                     snippet=ref[1] if ref is now else ref[2]))
        return out

    def _area_findings(self, claim_text: str, numbers: list) -> list:
        """v0.6: a State's geographical area in sq km or hectares (1 sq km = 100 ha) against Census 2011, with the
        undivided-State check."""
        out = []
        state, assumed = None, False
        for n in numbers:
            if getattr(n, "unit_kind", "") in ("percent", "pp") or "%" in n.raw:
                continue
            i = claim_text.find(n.raw)
            if i < 0:
                continue
            after = claim_text[i + len(n.raw): i + len(n.raw) + 80]
            um = AREA_UNIT_RX.match(after)
            if not um:
                continue
            unit_txt = um.group("unit")
            ha = not re.match(SQKM_U, unit_txt, re.I)
            mult = float(getattr(n, "multiplier_value", 1.0) or 1.0)
            if ha and re.match(r"m\.?\s?ha", unit_txt, re.I):
                mult *= 1e6                    # 'mha' = million hectares
            rest = after[um.end():]
            before = re.split(r"[;:]|(?<=\D)\.\s|\d", claim_text[max(0, i - 70):i])[-1]
            ctx = None
            am = AREA_AFTER_RX.match(rest)
            if am:
                ctx = rest[:am.end()]
            else:
                bm = AREA_BEFORE_RX.search(before)
                # the area words belong to an earlier figure ('29.44 million ha. of geographical area of the state 7.336
                # million ha has been recognised as flood prone'): not this one
                win = claim_text[max(0, i - 90):i]
                if bm and not re.search(rf"\d\s*(?:million|lakh|lac|crore|thousand)?\s*(?:{HA_U}|{SQKM_U})[\s.,)]*"
                                        rf"(?:of\s+)?(?:the\s+)?(?:total\s+)?(?:geographical|geographic|land|reporting|total)\s+area\b"
                                        rf"[^\d]*$", win, re.I):
                    ctx = before[max(0, bm.start() - 30):]
            if ctx is None or AREA_NOT_RX.search(ctx):
                continue
            if state is None:
                state, assumed = self._own_state(claim_text)
            if not state or state == "india":
                return out
            to_units = (100.0 if ha else 1.0) / mult      # sq km -> the draft's unit
            ulabel = (("million ha" if mult == 1e6 else "lakh ha" if mult == 1e5 else "ha") if ha else
                      ("million sq km" if mult == 1e6 else "lakh sq km" if mult == 1e5 else "sq km"))
            row = census_total(state) if state not in SKIP_CENSUS_STATES else None
            conv = " (1 sq km = 100 ha)" if ha else ""
            now = None
            if row is not None and row.get("area_sq_km"):
                a = float(row["area_sq_km"])
                now = (a * to_units, f"{row['state']} area {_n(a)} sq km" + (f" = {a * to_units:,.4g} {ulabel}{conv}"
                                                                             if to_units != 1 else ""))
            und = undivided(state, "area_sq_km")
            undiv = None
            if und is not None:
                undiv = (und[0] * to_units, und[1], f"{und[1]} sq km" + (f" = {und[0] * to_units:,.4g} {ulabel}{conv}"
                                                                         if to_units != 1 else "") + ", Census 2011 areas")
            if now is None and undiv is None:
                continue
            verdict, reason = self._decide(n, claim_text, kind="area", now=now, undiv=undiv, state=state, assumed=assumed)
            if not reason:
                continue
            if verdict == "UNVERIFIED" and not ha and mult == 1.0:
                continue        # a plain sq km figure that differs: the v0.5.3 table matcher decides it, as before
            ref = now if (now is not None and not reason.startswith("Dated (boundary)")) else (undiv or now)
            out.append(self._finding(n, claim_text, verdict, reason, label=f"area ({ulabel}; Census 2011)",
                                     ind="area-sq-km", value=round(ref[0], 6), display=f"{ref[0]:,.6g} {ulabel}",
                                     period="2011", state=state, snippet=ref[1] if ref is now else ref[2]))
        return out

    def _dated_by_year(self, text, numbers, years, label_ok, is_pct_table, pct, cnt) -> list:
        """v0.6: the sentence names a year the bundled data does not hold (a 2009 groundwater figure; the 2025 assessment
        is bundled): compare the figure with the bundled year anyway and report DATED when that year is later than every
        year the sentence names. A figure for a later year than the data is not compared."""
        stripped = _strip_years(text)
        fs = []
        if pct:
            fs += GroupedSource.match(self, stripped, pct, lambda k: is_pct_table(k) and (label_ok is None or label_ok(k)))
        if cnt:
            fs += GroupedSource.match(self, stripped, cnt, lambda k: not is_pct_table(k) and (label_ok is None or label_ok(k)))
        out = []
        for f in fs:
            try:
                data_year = int(str(f.get("period") or "")[:4])
            except ValueError:
                continue
            if "NFHS-5" in str(f.get("indicator_name") or "") or not all(y < data_year for y in years):
                continue
            definite = f["verdict"] in ("MATCH", "MISMATCH", "CLOSE") or (
                f["verdict"] == "UNVERIFIED" and str(f.get("reason") or "").startswith("The latest official value is"))
            if not definite or f.get("negated"):
                continue
            f["verdict"] = "DATED"
            f["reason"] = (f"Dated: the draft's figure is for {', '.join(map(str, years))}; the bundled official value is "
                           f"{f['official']['display']} ({f.get('period')}). A figure for an earlier year is not called wrong.")
            f["warnings"] = [w for w in f.get("warnings", []) if w.get("code") != "superseded"]
            out.append(f)
        return out

    # ------------------------------------------------------------------ match
    def match(self, claim_text: str, numbers: list, label_ok=None) -> list[dict]:
        if not numbers or not self.relevant(claim_text):
            return []
        # v0.6: share of India and State area (sq km or hectares) are decided here; those figures skip the table matcher
        special = []
        if label_ok is None or label_ok("area sq km (Census 2011)"):
            special = self._share_findings(claim_text, numbers)
            done = {f["claimed"] for f in special}
            special += self._area_findings(claim_text, [n for n in numbers if n.raw not in done])
        if special:
            done = {f["claimed"] for f in special}
            numbers = [n for n in numbers if n.raw not in done]
            if not numbers:
                return special
        return special + self._match_tables(claim_text, numbers, label_ok)

    def _match_tables(self, claim_text: str, numbers: list, label_ok=None) -> list[dict]:
        text, assumed = claim_text, None
        if not STATE_RX.search(claim_text or "") and not NATIONAL_RX.search(claim_text or ""):
            ds = DOC_STATE.get()
            if ds:
                assumed = ds
                text = f"{claim_text} ({ds.title()})"
        geo = claim_geo(text)
        district = self._district(text, None if geo == "india" else geo)
        if district and geo == "india":
            st = next((r["state"] for r in load_state_data()["census2011_districts"] if r["district"].lower() == district), None)
            if st:
                text = f"{text} ({st})"       # the district's own State, so the table matcher keeps its rows
                geo = norm_state(st)
        if geo == "india" and not NATIONAL_RX.search(claim_text or ""):
            return []           # no State named and none assumed: an all-India row would be a guess
        # v0.5.3: a percentage is only compared with a percentage table (NFHS-5, CGWB stage of extraction) and a count or
        # an area only with a count table: '1,91,791 sq km, i.e., 5.83% of India' compared 5.83% with the area
        pct = [n for n in numbers if getattr(n, "unit_kind", "") in ("percent", "pp") or "%" in n.raw
               or "per cent" in n.raw.lower()]
        cnt = [n for n in numbers if n not in pct]

        def is_pct_table(k: str) -> bool:
            return "NFHS-5" in k or "stage of ground water extraction" in k
        fs = []
        if pct:
            fs += GroupedSource.match(self, text, pct, lambda k: is_pct_table(k) and (label_ok is None or label_ok(k)))
        if cnt:
            fs += GroupedSource.match(self, text, cnt, lambda k: not is_pct_table(k) and (label_ok is None or label_ok(k)))
        periods = claim_periods(claim_text)
        dated = bool(periods)
        years = self._years(periods)
        if years and not fs:
            fs = self._dated_by_year(text, numbers, years, label_ok, is_pct_table, pct, cnt)
        doc_year = DOC_YEAR.get()
        for f in fs:
            f["sentence"] = claim_text
            nfhs = "NFHS-5" in str(f.get("indicator_name") or "")
            try:
                data_year = int(str(f.get("period") or "")[:4])
            except ValueError:
                data_year = None
            differs = f["verdict"] in ("MISMATCH", "CLOSE") or (
                f["verdict"] == "UNVERIFIED" and str(f.get("reason") or "").startswith("The latest official value is"))
            if differs and not dated and not nfhs and not district and doc_year and data_year and doc_year < data_year:
                # v0.6: an undated figure in a document older than the data is a figure for an earlier year
                f["verdict"] = "DATED"
                f["reason"] = (f"Dated: the document is from {doc_year}, before the {f.get('period')} data; its figure is "
                               f"for an earlier year. Official value: {f['official']['display']} ({f.get('period')})."
                               + (f" (The sentence names no State; compared with {assumed.title()}, the State this "
                                  "document is about.)" if assumed else ""))
                f["warnings"] = [w for w in f.get("warnings", []) if w.get("code") != "superseded"]
            if f["verdict"] in ("MISMATCH", "CLOSE"):
                why = None
                if nfhs:
                    why = "NFHS-5 figures are rounded household percentages; a different figure is not called wrong."
                elif district:
                    why = "District figures are only used to confirm a figure (district names and boundaries change)."
                elif assumed:
                    why = (f"The sentence names no State; it was compared with {assumed.title()}, the State this document "
                           "is about, so a different figure is not called wrong.")
                elif not dated:
                    why = "The draft gives no year, so its figure may be a newer estimate (not contradicted)."
                if why:
                    f["verdict"] = "UNVERIFIED"
                    f["reason"] = f"Official value: {f['official']['display']} ({f.get('period') or 'latest'}). {why}"
                    f["warnings"] = [w for w in f.get("warnings", []) if w.get("code") != "superseded"]
            if f["verdict"] == "MATCH" and assumed:
                f["reason"] = (f["reason"] + f" (The sentence names no State; compared with {assumed.title()}, the State "
                               "this document is about.)")
            if f["verdict"] == "MATCH" and district:
                f["reason"] = f["reason"] + f" ({district.title()} district, Census 2011 boundaries.)"
            off = f.get("official") or {}
            off["live"], off["live_source"] = False, False
            off["bundled"] = True
        return fs


def _strip_years(text: str) -> str:
    from .tables import FY_RX, YEAR_RX
    return YEAR_RX.sub(" ", FY_RX.sub(" ", text or ""))

