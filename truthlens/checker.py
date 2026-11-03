"""Checker: resolve each claim to an official value and give a fail-closed verdict.

Verdicts
  MATCH       the claim equals the official value at the precision the claim is written in
  CLOSE       off by more than rounding but within the indicator's tolerance
  MISMATCH    beyond tolerance
  UNVERIFIED  no confident match to an official series and period (never a guess)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from .extractor import Claim, extract_claims
from .parsing import fy_label, human_count, human_inr
from .readers import Block
from .registry import Indicator, load_registry
from .sources.curated import CuratedStore
from .sources.worldbank import WorldBankClient
from . import traps as T

MATCH, CLOSE, MISMATCH, UNVERIFIED = "MATCH", "CLOSE", "MISMATCH", "UNVERIFIED"


@dataclass
class Finding:
    claim_id: str
    location: str
    sentence: str
    claimed: str
    claimed_value: float
    indicator: Optional[str]
    indicator_name: Optional[str]
    period: Optional[str]
    geography: str
    verdict: str
    reason: str
    official: Optional[dict] = None
    citation: Optional[str] = None
    warnings: list = field(default_factory=list)
    alternatives: list = field(default_factory=list)
    direction: int = 0          # -1/+1 when 'fell'/'rose' sets the sign of the figure (v0.3)
    negated: bool = False       # the clause denies the figure ('was not 4.6%') (v0.3)

    def to_dict(self):
        return asdict(self)


def display_value(rec_or_value, unit: str, decimals: int = 1) -> str:
    if isinstance(rec_or_value, dict):
        if rec_or_value.get("display"):
            return rec_or_value["display"]
        v, unit = rec_or_value["value"], rec_or_value.get("unit", unit)
    else:
        v = rec_or_value
    if unit == "percent":
        return f"{v:.{decimals}f}%"
    if unit == "inr":
        return human_inr(v)
    if unit in ("persons", "count"):
        return human_count(v)
    return str(v)


def citation_for(ind: Indicator, rec: dict) -> str:
    src = rec["source"]
    bits = [rec["period"]]
    if rec.get("variant") and rec["variant"] != "default":
        bits.append(rec["variant"].replace("_", " "))
    if rec.get("stage"):
        bits.append(rec["stage"])
    if rec.get("base"):
        bits.append(f"base {rec['base']}")
    val = display_value(rec, rec.get("unit", "percent"))
    return (f"{ind.name}: {val} ({', '.join(bits)}). Source: {src['publisher']}, “{src['title']}”, "
            f"published {src['published']}, {src['url']} (accessed {src['accessed']}).")


class Checker:
    def __init__(self, store: Optional[CuratedStore] = None, worldbank: Optional[WorldBankClient] = None,
                 online: bool = True, registry: Optional[dict] = None):
        self.reg = registry or load_registry()
        self.store = store or CuratedStore()
        if worldbank is None:
            worldbank = WorldBankClient(offline=not online)
        self.wb = worldbank

    # ---------- public API ----------
    def check_blocks(self, blocks: list[Block]) -> list[Finding]:
        return [self.check_claim(c) for c in extract_claims(blocks, self.reg)]

    def check_text(self, text: str) -> list[Finding]:
        from .readers import read_text
        return self.check_blocks(read_text(text))

    # ---------- core ----------
    def check_claim(self, c: Claim) -> Finding:
        f = self._check_claim(c)
        return _apply_negation(c, f)

    def _check_claim(self, c: Claim) -> Finding:
        n = c.number
        f = Finding(claim_id=c.id, location=c.location, sentence=c.sentence, claimed=n.raw,
                    claimed_value=n.value, indicator=c.indicator, indicator_name=c.indicator_name,
                    period=c.period.label if c.period else None, geography=c.geography,
                    verdict=UNVERIFIED, reason="")
        f.warnings.extend(T.sentence_traps(c))
        if c.skip_reason:
            f.reason = c.skip_reason
            return f
        if not c.indicator:
            f.reason = "No supported indicator recognised for this number."
            return f
        ind = self.reg[c.indicator]
        if any(x["code"] == "survey_vs_admin" for x in f.warnings):
            f.reason = "The figure is attributed to administrative data, which is not comparable with the NFHS survey series."
            return f
        if c.generic_mention and ind.id == "cpi_inflation":
            f.warnings.append(T.w("generic_inflation", "info",
                                  "‘Inflation’ is not qualified; compared with CPI (headline retail) inflation. Say ‘CPI inflation’ or ‘WPI inflation’."))
        if n.is_range:
            f.reason = "Ranges and projections are not checked."
            return f
        if c.geography != "India":
            supports = getattr(self.store, "supports_geography", None)
            if not (supports and supports(ind.id, c.geography)):
                f.reason = (f"Sub-national figure ({c.geography}); the curated dataset covers all-India values only "
                            "(state-level PLFS figures are checked when the live MoSPI source is enabled).")
                return f
            national = self.store
            self.store = national.for_geography(c.geography)
            try:
                return self._dispatch(c, ind, f)
            finally:
                self.store = national
        return self._dispatch(c, ind, f)

    def _dispatch(self, c: Claim, ind: Indicator, f: Finding) -> Finding:
        if c.claim_type == "change":
            return self._check_change(c, ind, f)
        period = self._resolve_period(c, ind, f)
        if period is None:
            return f
        return self._check_level(c, ind, f, period)

    # ---------- period handling ----------
    def _resolve_period(self, c: Claim, ind: Indicator, f: Finding) -> Optional[str]:
        p = c.period
        if p is None:
            if ind.default_latest:
                rec = self.store.latest(ind.id, c.variant)
                if rec:
                    f.warnings.append(T.w("period_missing", "warn",
                                          f"No survey round stated; compared with the latest round ({rec['period']}). Name the survey and year, e.g. ‘NFHS-5 (2019-21)’."))
                    f.period = rec["period"]
                    return rec["period"]
            f.reason = "No year or period stated next to this number, so it cannot be matched to an official value."
            if ind.period_type == "census":
                f.warnings.append(T.w("period_missing", "warn",
                                      "Population figures need a year. The curated dataset holds the Census 2011 count; later years are only World Bank estimates, not census counts."))
            return None
        if p.kind in ("quarter", "month"):
            f.reason = f"{'Quarterly' if p.kind == 'quarter' else 'Monthly'} figures ({p.label}) are not covered in v0.1; only annual values are checked."
            return None
        if ind.period_type == "fy" and p.kind == "cy":
            f.warnings.extend(T.fy_vs_cy(self.store, ind, c))
            if ind.worldbank and ind.worldbank.get("year_map") == "cy":
                return "CY:" + p.label
            f.reason = (f"{ind.name} is published for financial years (April-March); the draft says ‘{p.raw}’, "
                        "which could mean either of two financial years.")
            return None
        if ind.period_type == "fy" and p.kind == "span":
            f.reason = f"Period ‘{p.raw}’ is not a single financial year."
            return None
        if ind.period_type == "plfs":
            if p.raw.lower().startswith(("fy", "financial", "fiscal")):
                f.warnings.append(T.w("plfs_year", "warn",
                                      f"PLFS annual rounds run July-June (PLFS {p.label} = July {p.label[:4]} - June {int(p.label[:4]) + 1}), not April-March; avoid calling it ‘FY’."))
            return p.label
        if ind.period_type == "census":
            if p.kind != "cy":
                f.reason = "Population figures are checked for a calendar year."
                return None
            return p.label
        if ind.period_type == "survey":
            return p.label
        return p.label

    # ---------- reference selection ----------
    def _candidates(self, ind: Indicator, period: str, variant: str) -> list[dict]:
        return self.store.find(ind.id, period=period, variant=variant)

    def _pick_reference(self, c: Claim, ind: Indicator, cands: list[dict]) -> Optional[dict]:
        if not cands:
            return None
        pool = cands
        if c.base_hint == "old":
            old = [r for r in cands if r["status"] == "old_base"]
            pool = old or pool
        else:
            cur = [r for r in cands if r["status"] == "current"]
            pool = cur or pool
        if ind.stage_priority:
            if c.stage:
                st = [r for r in pool if r.get("stage") == c.stage]
                if st:
                    return st[-1]
            for s in ind.stage_priority:
                st = [r for r in pool if r.get("stage") == s]
                if st:
                    return st[-1]
        return pool[0]

    # ---------- comparison ----------
    def compare(self, ind: Indicator, c: Claim, official: float) -> tuple[str, float]:
        n = c.number
        scale = n.multiplier_value if ind.unit_kind != "percent" else 1.0
        claim = n.raw_value * _sign_from_words(c, ind)
        off = official / scale
        diff = claim - off
        half = 0.5 * 10 ** (-n.decimals) + 1e-9
        if ind.unit_kind == "percent":
            close_ok = abs(diff) <= ind.tolerance.get("close_abs", 0.2) + 1e-9
        else:
            close_ok = abs(diff) <= abs(off) * ind.tolerance.get("close_rel", 0.01) + 1e-9
        if c.comparator == "ge":
            if off >= claim - 1e-9:
                return MATCH, diff
        elif c.comparator == "le":
            if off <= claim + 1e-9:
                return MATCH, diff
        if abs(diff) <= half:
            return MATCH, diff
        if c.comparator == "approx":
            # 'about X' accepts anything inside the tolerance band as a match
            if close_ok:
                return MATCH, diff
            wider = (abs(diff) <= 2 * ind.tolerance.get("close_abs", 0.2)) if ind.unit_kind == "percent" \
                else (abs(diff) <= abs(off) * 2 * ind.tolerance.get("close_rel", 0.01))
            return (CLOSE if wider else MISMATCH), diff
        return (CLOSE if close_ok else MISMATCH), diff

    def _check_level(self, c: Claim, ind: Indicator, f: Finding, period: str) -> Finding:
        variant = c.variant or "default"
        if period.startswith("CY:"):
            return self._worldbank(c, ind, f, period[3:], "cy")
        cands = self._candidates(ind, period, variant)
        # PLFS: status not stated -> compare with usual status (headline) but test CWS too
        if ind.status_variants and not c.variant_explicit:
            f.warnings.append(T.w("plfs_status", "warn",
                                  "Activity status not stated. PLFS publishes both usual status (ps+ss, 365-day reference) and current weekly status (CWS, 7-day); "
                                  "headline comparisons use usual status. Name the one you mean."))
        if not cands:
            if ind.worldbank and ind.worldbank.get("year_map") == "fy_start" and re.fullmatch(r"\d{4}-\d{2}", period):
                return self._worldbank(c, ind, f, period[:4], "fy_start")
            if ind.worldbank and ind.worldbank.get("year_map") == "cy" and ind.period_type == "census":
                if period != "2011":
                    f.warnings.append(T.w("not_census", "info",
                                          "No census count exists for this year in the dataset; compared with a World Bank population estimate (not a census figure)."))
                    return self._worldbank(c, ind, f, period, "cy")
            avail = ", ".join(self.store.periods(ind.id, variant)) or "none"
            f.reason = f"No official value for {ind.name} ({variant.replace('_', ' ')}) for {period} in the dataset (available: {avail})."
            f.warnings.extend(T.unit_scale_any(self, ind, c))
            return f
        ref = self._pick_reference(c, ind, cands)
        verdict, diff = self.compare(ind, c, ref["value"])
        if _sign_from_words(c, ind) == -1:
            f.direction = -1
        elif ind.id in SIGNED_RATES and c.claim_type == "level" and _word_direction(c) == 1 and c.number.raw_value > 0:
            f.direction = 1
        f.verdict = verdict
        f.official = self._official(ind, ref)
        f.citation = citation_for(ind, ref)
        f.reason = self._reason(verdict, c, ind, ref, diff)
        f.warnings.extend(T.after_compare(self, c, ind, ref, verdict, cands))
        if verdict == CLOSE and c.comparator != "approx" and not _explained(f.warnings):
            # v0.4.1: a figure at the same (or finer) precision that differs from the official value is a mismatch,
            # not "likely rounding"; CLOSE stays only when the figure is a known earlier estimate or another budget stage
            verdict = f.verdict = MISMATCH
            f.reason = self._reason(verdict, c, ind, ref, diff)
        elif verdict == CLOSE:
            f.reason = self._reason(verdict, c, ind, ref, diff, explained=True)
        if ref.get("note"):
            f.warnings.append(T.w("source_note", "info", ref["note"]))
        live = ref.get("live")
        if live and not live.get("agrees"):
            f.warnings.append(T.w("live_differs", "warn",
                                  f"The live MoSPI eSankhyiki API currently gives {live['value']:g} for this series and period "
                                  f"({live.get('vintage') or 'live'}); the curated value is {ref['value']:g}. A revision may have been released."))
        return f

    def _worldbank(self, c: Claim, ind: Indicator, f: Finding, year: str, mode: str) -> Finding:
        wbcfg = ind.worldbank or {}
        got = self.wb.value(wbcfg["code"], year) if wbcfg else None
        if not got:
            f.reason = (f"No curated official value for {ind.name} for this period, and the World Bank fallback "
                        f"({wbcfg.get('code', 'n/a')}) returned nothing{' (offline)' if self.wb.offline else ''}.")
            return f
        val, meta = got
        label = year if mode == "cy" else fy_label(int(year))
        rec = {
            "indicator": ind.id, "variant": "default", "period": label, "value": val,
            "unit": "percent" if ind.unit_kind == "percent" else ("persons" if ind.unit_kind == "count" else "inr"),
            "status": "secondary", "stage": None, "base": None, "vintage": f"WDI last updated {meta.get('lastupdated')}",
            "display": None if ind.unit_kind != "percent" else f"{val:.2f}%",
            "source": {"publisher": "World Bank, World Development Indicators (secondary source)",
                       "title": f"{wbcfg['code']} for India (IND), {'calendar year' if mode == 'cy' else 'WDI year ' + year + ' = FY ' + label}",
                       "url": meta.get("url"), "published": meta.get("lastupdated"), "accessed": _today(),
                       "key": "WB:" + wbcfg["code"]},
        }
        verdict, diff = self.compare(ind, c, val)
        f.verdict = verdict
        f.official = self._official(ind, rec)
        f.official["series_id"] = wbcfg["code"]
        f.citation = citation_for(ind, rec)
        f.reason = self._reason(verdict, c, ind, rec, diff) + " (World Bank WDI, secondary source)"
        f.warnings.append(T.w("secondary_source", "info",
                              "Checked against the World Bank WDI, a secondary compilation; prefer citing the primary Indian release (MoSPI/RBI/RGI)."))
        if mode == "fy_start":
            f.warnings.append(T.w("secondary_source", "info",
                                  "World Bank national-accounts years for India are financial years labelled by their start year "
                                  f"(WDI {year} = FY {label}). WDI may lag MoSPI's latest revision and its years before 2022-23 "
                                  "may not equal MoSPI's own back series for the 2022-23 base."))
        if verdict == MISMATCH:
            f.warnings.extend(T.unit_scale(c, ind, val))
        return f

    def _check_change(self, c: Claim, ind: Indicator, f: Finding) -> Finding:
        n = c.number
        ps = [p for p in c.periods_in_sentence]
        variant = c.variant or "default"
        if len(ps) < 2:
            f.reason = "A change is stated without both start and end periods, so it cannot be checked."
            if n.unit_kind == "percent":
                f.warnings.append(T.w("pct_vs_pp", "warn",
                                      f"A change in a rate ({ind.name}) is ambiguous in per cent: say ‘percentage points’ for an absolute change, or give both levels."))
            return f
        p1, p2 = sorted(ps[:2])
        r1 = self._pick_reference(c, ind, self._candidates(ind, p1, variant))
        r2 = self._pick_reference(c, ind, self._candidates(ind, p2, variant))
        if not (r1 and r2):
            f.reason = f"Official values for both {p1} and {p2} are needed to check this change."
            return f
        pp = r2["value"] - r1["value"]
        rel = pp / r1["value"] * 100 if r1["value"] else float("nan")
        tol = ind.tolerance.get("close_abs", 0.2)
        claim = abs(n.raw_value)
        target, other = (abs(pp), abs(rel)) if n.unit_kind == "pp" else (abs(rel), abs(pp))
        half = 0.5 * 10 ** (-n.decimals) + 1e-9
        d = claim - target
        if abs(d) <= half:
            f.verdict = MATCH
        elif abs(d) <= tol:
            f.verdict = CLOSE
        else:
            f.verdict = MISMATCH
        unit_word = "percentage points" if n.unit_kind == "pp" else "per cent (relative)"
        f.reason = (f"Change {p1} → {p2}: official {r1['value']:g}% → {r2['value']:g}% = {pp:+.2f} percentage points "
                    f"({rel:+.1f}% relative). Claim read as {claim:g} {unit_word}.")
        if f.verdict == MISMATCH and abs(claim - other) <= max(half, 0.05):
            if n.unit_kind == "percent":
                f.warnings.append(T.w("pct_vs_pp", "error",
                                      f"{claim:g} is the change in percentage points, not per cent. Write ‘{abs(pp):.1f} percentage points’ "
                                      f"(a {abs(rel):.1f}% relative change)."))
            else:
                f.warnings.append(T.w("pct_vs_pp", "error",
                                      f"{claim:g} is the relative change in per cent; the change in percentage points is {abs(pp):.1f}."))
        f.official = self._official(ind, r2)
        f.official["display"] = f"{pp:+.1f} pp ({r1['value']:g}% → {r2['value']:g}%)"
        f.official["period"] = f"{p1} → {p2}"
        f.citation = citation_for(ind, r1) + " " + citation_for(ind, r2)
        f.period = f"{p1} → {p2}"
        return f

    # ---------- v0.4.1 change calculator ----------
    def series_for(self, text: str, findings: list[dict]):
        """The official series a change/trend sentence is about, as a change.Series, or None."""
        from .change import Series
        ind = None
        variant = None
        for f in findings:
            iid = f.get("indicator")
            if iid and iid in self.reg:
                ind = self.reg[iid]
                variant = (f.get("official") or {}).get("variant")
                if (f.get("geography") or "India") != "India":
                    return None
                break
        low = (text or "").lower()
        if ind is None:
            from .extractor import STATE_RX
            if STATE_RX.search(low):
                return None        # the curated series are all-India
            cands = []
            rupee = bool(re.search(r"₹|\brs\.?\b|\brupees?\b|\bcrore\b|\blakh\b", low))
            for i in self.reg.values():
                for s, e, generic in i.mentions(low):
                    if i.excluded(low[max(0, s - 15):e + 30]):
                        continue
                    pref = (i.unit_kind == "inr") == rupee or i.unit_kind not in ("inr", "percent")
                    cands.append((-(10 if generic else 0) + (5 if pref else 0) + i.priority * 0.01, s, i))
            if not cands:
                return None
            ind = max(cands, key=lambda x: x[0])[2]
        variant = variant or ind.detect_variant(low) or ind.default_variant
        shim = type("C", (), {"base_hint": "old" if re.search(r"2011[-–]12|old series", low) else None, "stage": None})()

        def get(period):
            cands = [r for r in self.store.find(ind.id, period=period, variant=variant)
                     if r.get("status") in ("current", "old_base")]
            ref = self._pick_reference(shim, ind, cands)
            if ref is None:
                return None
            return {"value": ref["value"], "period": ref["period"], "stage": ref.get("stage"),
                    "display": display_value(ref, ref.get("unit", "percent"))}

        def periods():
            out = []
            for p in self.store.periods(ind.id, variant):
                recs = [r for r in self.store.find(ind.id, period=p, variant=variant) if r.get("status") == "current"]
                if recs and not all(r.get("stage") == "BE" for r in recs) and re.fullmatch(r"\d{4}(?:-\d{2})?", p):
                    out.append(p)
            return out

        unit = "percent" if ind.unit_kind == "percent" else ("inr" if ind.unit_kind == "inr" else "count")
        name = re.sub(r"\s*\(.*?\)\s*$", "", ind.name)
        return Series(indicator=ind.id, name=name, unit=unit, get=get, periods=periods)

    # ---------- helpers ----------
    def _official(self, ind: Indicator, rec: dict) -> dict:
        return {
            "value": rec["value"], "display": display_value(rec, rec.get("unit", "percent")),
            "period": rec["period"], "variant": rec.get("variant"), "stage": rec.get("stage"),
            "base": rec.get("base"), "vintage": rec.get("vintage"), "status": rec.get("status"),
            "series_id": ind.series_id, "series": ind.official_series, "source": rec["source"],
            "geography": rec.get("geography", "India"), "live": rec.get("live"),
            "live_source": bool(rec.get("live_source")),
        }

    def _reason(self, verdict: str, c: Claim, ind: Indicator, ref: dict, diff: float, explained: bool = False) -> str:
        off = display_value(ref, ref.get("unit", "percent"))
        per = ref.get("period") or ""
        if verdict == MATCH:
            if c.comparator in ("ge", "le"):
                return f"Official value {off} is consistent with ‘{c.number.raw}’ as a bound."
            if _sign_from_words(c, ind) == -1:
                return f"Matches the official value {off} at the precision written (‘{_dir_word(c)} {c.number.raw}’ read as a negative change)."
            if ind.unit_kind == "percent" and is_rounding(c.number.raw, ref["value"]):
                return f"Matches the official value {off}, rounded to the precision written."
            return f"Matches the official value {off} at the precision written."
        if ind.unit_kind == "percent":
            delta = f"{diff:+.2f} percentage points"
        else:
            delta = f"{diff / (ref['value'] / c.number.multiplier_value) * 100:+.1f}%"
        if verdict == CLOSE:
            if explained:
                return (f"{per} {ind.name}: draft {c.number.raw}, official {off} (difference {delta}); the draft's figure is "
                        "an earlier estimate or another budget stage (see warnings).")
            return f"{per} {ind.name}: draft {c.number.raw}, official {off} (difference {delta}), within the approximate wording."
        return f"Official value is {off}; the draft differs by {delta}."


def _explained(warnings: list) -> bool:
    """A near-miss is explained when the draft's figure is itself an official figure: an earlier estimate of the same
    series (vintage) or another budget stage (BE/RE/Actual) for the same year."""
    return any(w.get("code") == "vintage" or (w.get("code") == "budget_stage" and w.get("severity") == "error")
               for w in warnings)


def _decimals(x) -> int:
    t = str(x).replace(",", "")
    m = re.search(r"\d+(?:\.(\d+))?", t)
    return len(m.group(1)) if m and m.group(1) else 0


def is_rounding(raw: str, official: float) -> bool:
    """v0.4.1 rounding rule: the draft's figure counts as a rounding of the official value only when it is written with
    fewer decimals than the official value and equals the official value rounded (half up) to those decimals:
    4.6 -> "5%", 4.56 -> "4.6". 4.5 vs 4.6 at the same precision is not rounding; it is a different figure."""
    from decimal import ROUND_HALF_UP, Decimal
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", raw or "")
    if not m:
        return False
    claim = Decimal(m.group(0).replace(",", ""))
    d_claim = _decimals(m.group(0))
    off = Decimal(repr(float(official)))
    d_off = _decimals(format(off.normalize(), "f"))
    if d_claim >= d_off:
        return False
    q = Decimal(1).scaleb(-d_claim)
    return off.quantize(q, rounding=ROUND_HALF_UP) == claim


SIGNED_RATES = {"gdp_growth_real", "gdp_growth_nominal", "cpi_inflation", "wpi_inflation", "iip_growth"}


def _num_start(c: Claim) -> int:
    n = c.number
    s = c.sentence or ""
    if s[n.start:n.end].strip() and n.raw and n.raw[:3] in s[n.start:n.end + 3]:
        return n.start
    i = s.find(n.raw)
    return i if i >= 0 else n.start


def _word_direction(c: Claim) -> int:
    from .polarity import direction
    return direction(c.sentence or "", _num_start(c))


def _dir_word(c: Claim) -> str:
    from .polarity import _DIR_RX
    before = (c.sentence or "")[max(0, _num_start(c) - 40):_num_start(c)]
    ms = list(_DIR_RX.finditer(before))
    return ms[-1].group(0) if ms else ""


def _sign_from_words(c: Claim, ind: Indicator) -> int:
    """'Wholesale inflation fell 0.7 per cent' states -0.7%: for growth and inflation rates a decline word
    directly before an unsigned figure makes it negative. Levels (unemployment rate 'fell to 3.2%') are untouched."""
    if ind.id not in SIGNED_RATES or c.claim_type != "level" or c.number.raw_value <= 0:
        return 1
    return -1 if _word_direction(c) == -1 else 1


def _number_clause(c: Claim) -> str:
    s = c.sentence or ""
    i = _num_start(c)
    head = re.split(r"[;,]|\b(?:while|whereas|but|although|though)\b", s[:i])[-1]
    tail = re.split(r"[;,]|\b(?:while|whereas|but|although|though)\b", s[i:])[0]
    return head + tail


def _apply_negation(c: Claim, f: Finding) -> Finding:
    """'CPI inflation was not 4.6 per cent': a denied figure that matches the official value is contradicted;
    a denied figure that differs is consistent but says nothing checkable, so it stays unverified."""
    from .polarity import negated
    clause = _number_clause(c)
    if not negated(clause.split(c.number.raw)[0] if c.number.raw in clause else clause):
        return f
    f.negated = True
    off = (f.official or {}).get("display")
    if f.verdict == MATCH:
        f.verdict = MISMATCH
        f.reason = f"The draft denies the figure ({c.number.raw}), but the official value is {off}."
    elif f.verdict in (CLOSE, MISMATCH):
        f.verdict = UNVERIFIED
        f.reason = (f"The draft says the figure was not {c.number.raw}; the official value is {off}, so the denial is "
                    "consistent but does not state the figure. Say what it was.")
    return f


def _today() -> str:
    import datetime as _dt
    return _dt.date.today().isoformat()
