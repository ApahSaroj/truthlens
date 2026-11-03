"""Shared helpers for matching a numeric claim to rows of an official table (MoSPI eSankhyiki, data.gov.in).

A row is a flat dict ({"state": "Bihar", "year": "2023-24", "sector": "Rural", "value": "4122", ...}).
`match_rows` returns v0.1-style findings so the verdict engine treats them like the curated checker:
MATCH -> SUPPORTED, CLOSE -> PARTLY SUPPORTED (also used for "superseded": the figure matches an older
period/release but a newer one differs), MISMATCH -> CONTRADICTED, UNVERIFIED otherwise. It fails closed:
a mismatch is only reported when exactly one row fits the claim's geography, period and qualifiers well.
"""
from __future__ import annotations

import re
from typing import Optional

from .base import terms

STATES = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
          "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
          "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
          "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir", "Ladakh",
          "Puducherry", "Chandigarh", "Lakshadweep", "Andaman and Nicobar Islands",
          "Dadra and Nagar Haveli and Daman and Diu"]
STATE_ALIASES = {"orissa": "odisha", "j&k": "jammu and kashmir", "nct of delhi": "delhi", "pondicherry": "puducherry",
                 "uttaranchal": "uttarakhand", "a&n islands": "andaman and nicobar islands",
                 "andaman & n. islands": "andaman and nicobar islands"}
NATIONAL = {"all india", "india", "all-india", "total", "all india total", "national"}
STATE_RX = re.compile(r"\b(" + "|".join(re.escape(s) for s in sorted(STATES, key=len, reverse=True)) + r"|Orissa)\b", re.I)
FY_RX = re.compile(r"\b((?:19|20)\d{2})\s*[-–/]\s*(\d{2}|(?:19|20)\d{2})\b")
YEAR_RX = re.compile(r"\b((?:19|20)\d{2})\b")
NFHS_RX = re.compile(r"\bNFHS\s*[- ]?\s*([1-6])\b", re.I)
NFHS_YEARS = {"4": "2015-16", "5": "2019-21", "3": "2005-06", "6": "2023-24"}
GEO_KEYS = ("state", "state/ut", "state_ut", "state_name", "states_uts", "state_ut_name", "name_of_state_ut", "states", "state_uts",
            "_state", "state___ut", "state_ut_wise", "area")
VALUE_KEYS = ("value", "growth_rate", "index", "index_value", "percentage", "rate", "total")
QUALIFIERS = {"rural": "rural", "urban": "urban", "female": "female", "male": "male", "women": "female",
              "men": "male", "girls": "female", "boys": "male"}


def norm_state(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").lower().replace("&", "and")).strip(" .")
    return STATE_ALIASES.get(s, s)


def claim_geo(text: str) -> str:
    m = STATE_RX.search(text or "")
    return norm_state(m.group(1)) if m else "india"


def claim_periods(text: str) -> set:
    """Periods a claim names, in the forms official tables use ('2023-24', '2024', 'nfhs-5')."""
    out = set()
    for m in FY_RX.finditer(text or ""):
        a, b = m.group(1), m.group(2)
        b2 = b[-2:]
        out.add(f"{a}-{b2}")
    for m in NFHS_RX.finditer(text or ""):
        out.add(f"nfhs-{m.group(1)}")
        if m.group(1) in NFHS_YEARS:
            out.add(NFHS_YEARS[m.group(1)])
    if not out:
        out |= {m.group(1) for m in YEAR_RX.finditer(text or "")}
    return out


def row_period(row: dict) -> str:
    for k in PERIOD_KEYS:
        v = row.get(k)
        if v not in (None, ""):
            v = str(v).strip().lower()
            m = FY_RX.search(v)
            if m:
                return f"{m.group(1)}-{m.group(2)[-2:]}"
            return v
    return ""


def period_key(p: str) -> tuple:
    """Sort key: later periods last ('nfhs-5' > 'nfhs-4', '2024-25' > '2023-24')."""
    m = re.search(r"nfhs-(\d)", p or "")
    if m:
        return (int(NFHS_YEARS.get(m.group(1), "0")[:4] or 0), 0)
    m = re.search(r"((?:19|20)\d{2})", p or "")
    return (int(m.group(1)), 1) if m else (0, 0)


def row_geo(row: dict) -> Optional[str]:
    for k, v in row.items():
        kl = k.lower().replace(" ", "_")
        if kl in GEO_KEYS or kl.startswith("state"):
            return norm_state(str(v))
    return None


PERIOD_KEYS = ("year", "financial_year", "survey", "period_year", "fiscal_year", "years")


def _num(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def row_value(row: dict, prefer: Optional[str] = None) -> Optional[tuple]:
    keys = ([prefer] if prefer else []) + list(VALUE_KEYS)
    for k in keys:
        if k and row.get(k) not in (None, ""):
            v = _num(row[k])
            if v is not None:
                return k, v
    # tables with a named value column (data.gov.in: 'households_with_tap_water____'): use it only when it is the
    # row's single numeric column besides geography and period; with several, fail closed (no value)
    nums = [(k, _num(v)) for k, v in row.items()
            if k not in PERIOD_KEYS and k != "resource_uuid" and not (k.lower() in GEO_KEYS or k.lower().startswith("state"))
            and v not in (None, "") and _num(v) is not None]
    return nums[0] if len(nums) == 1 else None


def row_text(row: dict) -> str:
    return "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in row.items() if v not in (None, "") and k != "resource_uuid")


def _named_qualifiers(text_low: str) -> set:
    named = {v for k, v in QUALIFIERS.items() if re.search(rf"\b{k}s?\b", text_low)}
    if {"male", "female"} <= named:      # 'females per 1,000 males' is a ratio, not a sub-group
        named -= {"male", "female"}
    if {"rural", "urban"} <= named:
        named -= {"rural", "urban"}
    return named


def _qualifier_ok(claim_low: str, row: dict) -> tuple[bool, float]:
    """Rural/urban and male/female: a qualifier named in the claim must be in the row; rows for a sub-group are
    penalised when the claim names none."""
    rtxt = " ".join(str(v).lower() for v in row.values() if v is not None)
    named = _named_qualifiers(claim_low)
    row_has = {v for k, v in QUALIFIERS.items() if re.search(rf"\b{k}\b", rtxt)}
    if named:
        return (named <= row_has), 0.0
    if row_has and not re.search(r"\b(total|combined|all|person|persons)\b", rtxt):
        return True, -0.3
    return True, 0.0


def match_rows(claim_text: str, numbers: list, rows: list[dict], *, label: str, source: dict, indicator_id: str,
               value_key: Optional[str] = None, min_relevance: float = 0.5,
               relevance_text: Optional[str] = None) -> list[dict]:
    """Return findings for the claim's numbers against table rows (see module doc).

    numbers: parsed numbers from claims.checkable_numbers (need .raw, .raw_value, .decimals).
    source: {url, title, publisher, published (release/updated date), as_of}.
    """
    if not rows or not numbers:
        return []
    # relevance_text: the figure's own clause, when a sentence carries figures for several indicators
    want = terms(relevance_text or claim_text)
    geo = claim_geo(claim_text)
    periods = claim_periods(claim_text)
    findings = []
    for n in numbers:
        i = claim_text.find(n.raw)
        clause = claim_text
        if i >= 0:
            head = re.split(r";|,(?!\d)|\bthan\b|\bwhile\b|\bwhereas\b|\bcompared\b", claim_text[:i])[-1]
            tail = re.split(r";|,(?!\d)|\bthan\b|\bwhile\b|\bwhereas\b|\bcompared\b", claim_text[i:])[0]
            clause = head + tail
        low = (clause if _named_qualifiers(clause.lower()) else claim_text).lower()
        findings += _match_number(n, claim_text, low, want, geo, periods, rows, label, source, indicator_id, value_key,
                                  min_relevance)
    return findings


def _match_number(n, claim_text, low, want, geo, periods, rows, label, source, indicator_id, value_key, min_relevance):
    scored = []
    for row in rows:
        g = row_geo(row)
        if g is not None:
            if geo == "india" and g not in NATIONAL:
                continue
            if geo != "india" and g != geo:
                continue
        elif geo != "india":
            continue
        ok, pen = _qualifier_ok(low, row)
        if not ok:
            continue
        rv = row_value(row, value_key)
        if rv is None:
            continue
        text_terms = terms(" ".join(str(v) for k, v in row.items() if isinstance(v, str) and not re.fullmatch(r"[\d.,\-]+", v)))
        ind_terms = terms(" ".join([label.split(": ", 1)[-1]] + [str(v) for k, v in row.items()
                                              if k.lower() in ("indicator", "sub_indicator", "category", "sub_category", "item")
                                              and isinstance(v, str)]))
        cover_claim = len(want & (text_terms | ind_terms)) / (len(want) or 1)
        cover_ind = len(want & ind_terms) / (len(ind_terms) or 1)
        rel = 0.5 * cover_claim + 0.5 * cover_ind
        scored.append({"row": row, "period": row_period(row), "rel": rel + pen, "key": rv[0], "value": rv[1]})
    if not scored:
        return []
    findings = []
    for n in [n]:
        claimed = n.raw_value
        dec = n.decimals

        def eq(v: float) -> bool:
            return abs(round(v, dec) - claimed) < 1e-9 or abs(v - claimed) < 0.5 * 10 ** (-dec) + 1e-9

        pool = [s for s in scored if not periods or s["period"] in periods or s["period"] in {p.split("-")[0] for p in periods}]
        if not pool:
            continue
        top = max(s["rel"] for s in pool)
        if top < min_relevance:
            continue
        best = [s for s in pool if s["rel"] >= top - 0.05]
        hit = next((s for s in sorted(best, key=lambda s: -s["rel"]) if eq(s["value"])), None)
        if hit is None:
            hit_any = next((s for s in pool if eq(s["value"]) and s["rel"] >= min_relevance), None)
        else:
            hit_any = hit
        # freshness: when the claim names no period, the latest period is the reference
        latest = None
        if not periods:
            same_series = [s for s in scored if s["rel"] >= top - 0.05 and (hit_any is None or _same_series(s["row"], hit_any["row"]))]
            if same_series:
                latest = max(same_series, key=lambda s: period_key(s["period"]))
        if hit_any is not None:
            ref = hit_any
            verdict, reason = "MATCH", f"Matches the official value {_fmt(ref['value'])} ({ref['period'] or 'latest'})."
            warns = []
            if latest is not None and period_key(latest["period"]) > period_key(ref["period"]) and not eq(latest["value"]):
                verdict = "CLOSE"
                reason = (f"Superseded: the figure matches the older period {ref['period']} ({_fmt(ref['value'])}); "
                          f"the newer {latest['period']} figure is {_fmt(latest['value'])}.")
                warns.append({"code": "superseded", "severity": "warn",
                              "message": f"Superseded: newer data ({latest['period']}) says {_fmt(latest['value'])}; "
                                         f"the draft's {n.raw} is the {ref['period']} figure."})
                ref = latest
            findings.append(_finding(n, verdict, reason, ref, label, source, indicator_id, warns, claim_text))
            continue
        # mismatch only when the rows that fit well all say something clearly different and agree with each other
        vals = [s["value"] for s in best]
        far = all(abs(v - claimed) > max(0.03 * abs(v), 0.5 * 10 ** (-dec)) for v in vals)
        tight = (max(vals) - min(vals)) <= 0.10 * max(abs(max(vals)), 1e-9)
        if (len(best) == 1 or (far and tight and len(best) <= 4)) and top >= max(min_relevance, 0.6) and (periods or latest is not None):
            ref = (min(best, key=lambda s: abs(s["value"] - claimed)) if periods else latest)
            others = sorted({_fmt(v) for v in vals if v != ref["value"]})
            # v0.5.2: "around 70 per cent" is an approximate figure: within 10% of the official value it is not wrong
            i = claim_text.find(n.raw)
            if i >= 0 and APPROX_RX.search(claim_text[max(0, i - 30):i]) and ref["value"] and \
                    abs(ref["value"] - claimed) <= 0.10 * abs(ref["value"]):
                findings.append(_finding(n, "UNVERIFIED", f"The draft gives an approximate figure ({n.raw}); the official value "
                                         f"is {_fmt(ref['value'])} ({ref['period'] or 'latest'}).", ref, label, source,
                                         indicator_id, [], claim_text))
                continue
            findings.append(_finding(n, "MISMATCH", f"Official value is {_fmt(ref['value'])} ({ref['period'] or 'latest'})"
                                     + (f"; other variants of the series give {', '.join(others)}." if others else "."),
                                     ref, label, source, indicator_id, [], claim_text))
        else:
            ref = sorted(best, key=lambda s: -period_key(s["period"])[0])[0]
            findings.append(_finding(n, "UNVERIFIED", "Several official rows could match; none states this figure.",
                                     ref, label, source, indicator_id, [], claim_text))
    return findings


APPROX_RX = re.compile(r"\b(?:around|about|approximately|approx\.?|nearly|roughly|close to|almost|some|over|more than|"
                       r"less than|under|upwards of|in excess of|at least|at most)\s*$|~\s*$", re.I)


def dedupe_findings(fs: list[dict]) -> list[dict]:
    """One finding per claimed figure: a decided finding (MATCH / CLOSE / MISMATCH) beats UNVERIFIED ones, and only the
    first UNVERIFIED is kept when nothing decided it."""
    decided = {f["claimed"] for f in fs if f["verdict"] != "UNVERIFIED"}
    out, seen = [], set()
    for f in fs:
        if f["verdict"] == "UNVERIFIED":
            if f["claimed"] in decided or f["claimed"] in seen:
                continue
            seen.add(f["claimed"])
        out.append(f)
    return out


def _same_series(a: dict, b: dict) -> bool:
    ignore = {"year", "survey", "financial_year", "period_year", "fiscal_year", "years"} | set(VALUE_KEYS) | {"unit"}
    return all(str(a.get(k)) == str(b.get(k)) for k in set(a) | set(b) if k not in ignore)


def _fmt(v: float) -> str:
    return f"{v:,.2f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else f"{v:,.0f}"


def _finding(n, verdict, reason, ref, label, source, indicator_id, warns, claim_text) -> dict:
    from ..polarity import negated
    row = ref["row"]
    snippet = f"{label}: {row_text(row)}"
    neg = negated(claim_text.split(n.raw)[0] if n.raw in claim_text else claim_text)
    if neg and verdict == "MATCH":
        verdict, reason = "MISMATCH", f"The draft denies the figure ({n.raw}), but the official value is {_fmt(ref['value'])}."
    elif neg and verdict in ("CLOSE", "MISMATCH"):
        verdict, reason = "UNVERIFIED", f"The draft says the figure was not {n.raw}; the official value is {_fmt(ref['value'])}."
    return {
        "claim_id": "", "location": "", "sentence": claim_text, "claimed": n.raw, "claimed_value": n.value,
        "indicator": indicator_id, "indicator_name": label, "period": ref["period"], "geography": row_geo(row) or "India",
        "verdict": verdict, "reason": reason, "negated": neg, "direction": 0,
        "official": {"value": ref["value"], "display": _fmt(ref["value"]), "period": ref["period"], "variant": None,
                     "stage": None, "base": None, "vintage": source.get("published"), "status": None, "series_id": indicator_id,
                     "series": label, "source": {k: source.get(k) for k in ("url", "title", "publisher", "published")},
                     "geography": row_geo(row) or "India", "live": True, "live_source": True,
                     "retriever": source.get("retriever"), "as_of": source.get("as_of"), "snippet": snippet},
        "citation": f"{snippet}. Source: {source.get('publisher')}, {source.get('title')} ({source.get('url')})",
        "warnings": warns, "alternatives": [],
    }
