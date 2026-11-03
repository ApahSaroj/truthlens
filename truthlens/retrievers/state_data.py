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
  * Census 2011 rows for undivided Andhra Pradesh and Jammu and Kashmir (since reorganised) are not used.
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

    # ------------------------------------------------------------------ match
    def match(self, claim_text: str, numbers: list, label_ok=None) -> list[dict]:
        if not numbers or not self.relevant(claim_text):
            return []
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
        dated = bool(claim_periods(claim_text))
        for f in fs:
            f["sentence"] = claim_text
            nfhs = "NFHS-5" in str(f.get("indicator_name") or "")
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
