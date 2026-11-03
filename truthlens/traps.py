"""India data-trap detectors. Each returns a list of warnings: {code, severity, message}.

Trap codes
  unit_scale          lakh/crore vs million/billion confusion (value off by a power of 10)
  fy_vs_cy            calendar year used for a financial-year series
  plfs_year           PLFS July-June rounds labelled as April-March FY
  budget_stage        Budget Estimate vs Revised Estimate vs Actuals
  plfs_status         PLFS usual status (ps+ss) vs current weekly status (CWS)
  old_base            figure from a superseded base-year series (GDP 2011-12, CPI 2012=100, IIP 2011-12)
  vintage             figure from an earlier, since-revised estimate of the same series
  wrong_year          value belongs to a different year of the same series
  registrations_vs_beneficiaries   enrolment counts described as people reached/benefited
  pct_vs_pp           change in a rate given in per cent instead of percentage points
  survey_vs_admin     NFHS survey figures mixed with administrative data (Poshan Tracker, HMIS)
"""
from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

from .parsing import fy_label

if TYPE_CHECKING:  # pragma: no cover
    from .checker import Checker
    from .extractor import Claim
    from .registry import Indicator


def fmt(r: dict) -> str:
    if r.get("display"):
        return r["display"]
    if r.get("unit", "percent") == "percent":
        return f"{r['value']:g}%"
    return str(r["value"])


def w(code: str, severity: str, message: str) -> dict:
    return {"code": code, "severity": severity, "message": message}


REG_RX = re.compile(r"\b(registered|registrations?|enrol(l)?ed|enrol(l)?ments?|accounts? (were )?opened|cards? (were )?issued|"
                    r"sanctioned|onboarded|sign[- ]?ups?)\b", re.I)
BEN_RX = re.compile(r"\b(beneficiar(y|ies)|benefit(ed|ted|ing)|received|reached|covered|households? (now )?(have|get)|"
                    r"people (now )?(have|get)|lives)\b", re.I)
ADMIN_RX = re.compile(r"\b(poshan tracker|hmis|anganwadi|administrative data|icds)\b", re.I)


def sentence_traps(c: "Claim") -> list[dict]:
    out = []
    s = c.sentence
    if REG_RX.search(s) and BEN_RX.search(s) and c.number.unit_kind in ("count", "bare", "percent"):
        out.append(w("registrations_vs_beneficiaries", "warn",
                     "The sentence mixes registrations/enrolments with beneficiaries or people reached. Registrations count sign-ups "
                     "(possibly duplicate or inactive), not people who received a benefit; check which one the source reports."))
    if c.indicator in ("child_stunting", "child_wasting", "child_underweight") and ADMIN_RX.search(s):
        out.append(w("survey_vs_admin", "warn",
                     "NFHS is a household survey; Poshan Tracker/HMIS figures are administrative and are not comparable with NFHS prevalence."))
    return out


def fy_vs_cy(store, ind: "Indicator", c: "Claim") -> list[dict]:
    y = int(c.period.label)
    alts = []
    for fy in (fy_label(y - 1), fy_label(y)):
        recs = [r for r in store.find(ind.id, period=fy, variant=c.variant or "default") if r["status"] == "current"]
        if recs:
            alts.append((fy, recs[0]))
    msg = (f"‘{c.period.raw}’ is a calendar year but {ind.name} is an April-March financial-year series. "
           f"Write ‘FY {fy_label(y - 1)}’ or ‘FY {fy_label(y)}’.")
    hit = None
    for fy, r in alts:
        if abs(c.number.raw_value - r["value"]) <= 0.05 + 0.5 * 10 ** (-c.number.decimals):
            hit = fy
    if alts:
        msg += " Official: " + "; ".join(f"FY {fy} = {r['value']:g}%" if ind.unit_kind == "percent" else f"FY {fy} = {fmt(r)}"
                                          for fy, r in alts) + "."
    if hit:
        msg += f" The draft's number matches FY {hit}."
    return [w("fy_vs_cy", "warn", msg)]


SCALE_EXPLAIN = "1 million = 10 lakh; 1 crore = 10 million; 1 billion = 100 crore; 1 lakh crore = 1 trillion"


def unit_scale(c: "Claim", ind: "Indicator", official: float) -> list[dict]:
    n = c.number
    if ind.unit_kind == "percent" or official == 0 or n.value == 0:
        return []
    ratio = official / n.value
    if ratio <= 0:
        return []
    k = round(math.log10(ratio))
    if k == 0 or abs(k) > 7:
        return []
    if abs(ratio / 10 ** k - 1) <= 0.03:
        unit = n.multiplier or "units"
        mixed = (n.multiplier in ("million", "billion", "trillion", "thousand") and True) or n.multiplier in ("lakh", "crore", "lakh crore")
        hint = f"Check the {unit} conversion ({SCALE_EXPLAIN})." if mixed else f"({SCALE_EXPLAIN})."
        return [w("unit_scale", "error",
                  f"The draft's figure is off by a factor of {10 ** abs(k):,} ({'too small' if k > 0 else 'too large'}): "
                  f"likely a lakh/crore vs million/billion slip. {hint}")]
    return []


def unit_scale_any(checker: "Checker", ind: "Indicator", c: "Claim") -> list[dict]:
    return []


def after_compare(checker: "Checker", c: "Claim", ind: "Indicator", ref: dict, verdict: str, cands: list[dict]) -> list[dict]:
    from .checker import MATCH, CLOSE, MISMATCH
    out: list[dict] = []
    store = checker.store
    n = c.number

    def matches(val: float) -> bool:
        v, _ = checker.compare(ind, c, val)
        return v == MATCH

    # old base / earlier vintage
    if c.base_hint == "old" and ref["status"] == "old_base":
        cur = [r for r in cands if r["status"] == "current"]
        msg = f"This figure is from the superseded base {ref.get('base')} series."
        if cur:
            msg += f" The current series (base {cur[0].get('base')}) gives {fmt(cur[0])} for {cur[0]['period']}; old and new series are not comparable."
        out.append(w("old_base", "warn", msg))
    elif verdict != MATCH:
        for r in cands:
            if r is ref:
                continue
            if r["status"] == "old_base" and matches(r["value"]):
                out.append(w("old_base", "error",
                             f"The draft's number matches the OLD base {r.get('base')} series ({fmt(r)}, {r['source']['publisher']}, {r['source']['published']}). "
                             f"MoSPI has replaced it with the base {ref.get('base')} series, which gives {fmt(ref)}. Update the figure and say which base you use."))
            elif r["status"] == "superseded_vintage" and matches(r["value"]):
                out.append(w("vintage", "warn",
                             f"The draft's number matches an earlier estimate ({r.get('vintage')}, published {r['source']['published']}), since revised to "
                             f"{fmt(ref)} ({ref.get('vintage') or 'latest'})."))
    # budget stage
    if ind.stage_priority:
        stages = {r.get("stage"): r for r in cands if r["status"] == "current"}
        if not c.stage:
            if len(stages) > 1:
                vals = "; ".join(f"{s}: {fmt(r)}" for s, r in stages.items())
                out.append(w("budget_stage", "warn",
                             f"Budget stage not stated. For {ref['period']} the Union Budget reports {vals}. Say whether this is the Budget Estimate (BE), Revised Estimate (RE) or Actuals; compared with {ref.get('stage')}."))
            elif ref.get("stage") == "BE":
                out.append(w("budget_stage", "info", f"{ref['period']} has only a Budget Estimate so far; describe it as a target (BE), not an outcome."))
        if verdict != MATCH:
            for s, r in stages.items():
                if r is not ref and matches(r["value"]):
                    out.append(w("budget_stage", "error",
                                 f"The draft's number is the {s} for {ref['period']}, but it was compared with {ref.get('stage')} ({fmt(ref)}). Label the stage correctly."))
        elif c.stage and ref.get("stage") != c.stage:
            out.append(w("budget_stage", "warn", f"The draft says {c.stage}, but the dataset only has {ref.get('stage')} for {ref['period']}."))
    # PLFS: did it match the other status?
    if ind.status_variants and verdict != MATCH:
        for v in ind.status_variants:
            if v == (c.variant or ind.default_variant):
                continue
            alt = [r for r in store.find(ind.id, period=ref["period"], variant=v) if r["status"] == "current"]
            if alt and matches(alt[0]["value"]):
                label = "current weekly status (CWS)" if v == "cws" else "usual status (ps+ss)"
                out.append(w("plfs_status", "error",
                             f"The draft's number is the {label} figure ({alt[0]['value']:g}%) for PLFS {ref['period']}. "
                             f"Say ‘{label}’; the {('usual status' if v == 'cws' else 'CWS')} figure is {ref['value']:g}%."))
    # wrong year
    if verdict == MISMATCH and not any(x["code"] in ("old_base", "vintage", "budget_stage", "plfs_status") and x["severity"] == "error" for x in out):
        others = [r for r in store.find(ind.id, variant=ref.get("variant")) if r["period"] != ref["period"] and r["status"] == "current"]
        hits = sorted({r["period"] for r in others if matches(r["value"])})
        if hits:
            out.append(w("wrong_year", "warn",
                         f"The draft's number matches the official value for {', '.join(hits)}, not {ref['period']}. Check the year."))
    # unit scale
    if verdict == MISMATCH:
        out.extend(unit_scale(c, ind, ref["value"]))
    return out
