"""Suggested corrections.

Deterministic for numbers resolved against official series (the official value replaces the draft's
number, with the unit written the way the draft writes it, and the source is appended). For other
claims the LLM judge's corrected sentence is used when a key is configured; without a key a heuristic
replacement is offered only when the evidence passage holds exactly one candidate figure or date.
"""
from __future__ import annotations

import re
from typing import Optional

NUM_HEAD = re.compile(r"[-−]?\d[\d,]*(?:\.\d+)?")


def _source_note(src: dict) -> str:
    if not src:
        return ""
    bits = [src.get("publisher", "").split(" (")[0]]
    if src.get("title"):
        bits.append(f"“{src['title'][:90]}{'…' if len(src['title']) > 90 else ''}”")
    pub = src.get("published")
    if pub and pub != "live API":
        bits.append(pub)
    return "Source: " + ", ".join(b for b in bits if b)


def replace_number(raw: str, new_value: float, decimals: int) -> str:
    """'4.9 per cent' + 3.2 -> '3.2 per cent'; keeps the draft's unit wording."""
    m = NUM_HEAD.search(raw)
    if not m:
        return raw
    d = max(decimals, 1) if abs(new_value) < 1000 else decimals
    num = f"{new_value:,.{d}f}" if "," in m.group(0) else f"{new_value:.{d}f}"
    return raw[:m.start()] + num + raw[m.end():]


def numeric_fix(sentence: str, findings: list[dict]) -> tuple[Optional[str], Optional[str]]:
    """Return (corrected sentence, source note) for MISMATCH/CLOSE numeric findings."""
    out = sentence
    sources = []
    changed = False
    for f in findings:
        if f["verdict"] not in ("MISMATCH", "CLOSE") or not f.get("official"):
            continue
        off = f["official"]
        raw = f["claimed"]
        if f.get("negated"):
            continue                      # a denial is not corrected by swapping the number
        if f.get("direction"):
            # 'fell 1.2 per cent' vs official -0.7: write 'fell 0.7 per cent'; a sign flip needs a new verb
            if (off.get("value") or 0) * f["direction"] < 0:
                continue
        if raw not in out:
            continue
        codes = {w["code"]: w for w in f.get("warnings", [])}
        head = NUM_HEAD.search(raw)
        if not head:
            continue
        decimals = len(head.group(0).split(".")[1]) if "." in head.group(0) else 0
        if "pct_vs_pp" in codes and "→" in str(off.get("period", "")):
            m = re.search(r"([+-]?\d+(?:\.\d+)?) pp", off.get("display", ""))
            if m:
                new = f"{abs(float(m.group(1))):.1f} percentage points"
                out = out.replace(raw, new, 1)
                changed = True
                sources.append(_source_note(off.get("source")))
                continue
        if f.get("indicator") and off.get("value") is not None and re.search(r"%|per ?cent|pp|percentage", raw, re.I):
            val = float(off["value"])
            new = replace_number(raw, abs(val) if f.get("direction") else val, decimals)
        else:
            new = off.get("display") or raw
            # keep "about/over" wording outside the raw string; the display already carries the unit
        if new != raw:
            out = out.replace(raw, new, 1)
            changed = True
            note = _source_note(off.get("source"))
            if "old_base" in codes:
                note += " (current base 2022-23 series)"
            sources.append(note)
    if not changed:
        return None, None
    return out, "; ".join(dict.fromkeys(s for s in sources if s))


def heuristic_fix(sentence: str, claim_numbers: list[str], passage: str, kind: str) -> Optional[str]:
    """Replace the single claimed figure with the single same-kind figure in the passage."""
    if len(claim_numbers) != 1:
        return None
    raw = claim_numbers[0]
    if raw not in sentence:
        return None
    if kind == "percent":
        cands = re.findall(r"(\d+(?:\.\d+)?)\s*(?:%|per ?cent)", passage)
    elif kind == "crore":
        cands = re.findall(r"(\d+(?:\.\d+)?)\s*(?:crore|Crore)", passage)
    else:
        cands = re.findall(r"(?<![\d.])(\d[\d,]*(?:\.\d+)?)(?![\d.])", passage)
    cands = list(dict.fromkeys(cands))
    if len(cands) != 1:
        return None
    m = NUM_HEAD.search(raw)
    return sentence.replace(raw, raw[:m.start()] + cands[0] + raw[m.end():], 1)


def date_fix(sentence: str, claim_date: str, passage_dates: list[str]) -> Optional[str]:
    if len(set(passage_dates)) != 1 or claim_date not in sentence:
        return None
    return sentence.replace(claim_date, passage_dates[0], 1)
