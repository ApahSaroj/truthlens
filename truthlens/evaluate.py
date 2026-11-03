"""Evaluate the checker on the labelled test set (data/testset.jsonl).

Each line: {"id", "text", "claim" (the number as written), "expected" verdict, "traps" (codes that must be raised)}.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

from .checker import Checker

VERDICTS = ["MATCH", "CLOSE", "MISMATCH", "UNVERIFIED"]


def load_testset(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(path: Path, checker: Optional[Checker] = None) -> dict:
    ck = checker or Checker(online=False)
    rows = []
    for item in load_testset(path):
        findings = ck.check_text(item["text"])
        pick = next((f for f in findings if f.claimed == item["claim"]), None)
        if pick is None:
            pick = next((f for f in findings if item["claim"] in f.claimed or f.claimed in item["claim"]), None)
        got = pick.verdict if pick else "NOT_EXTRACTED"
        codes = {w["code"] for w in pick.warnings} if pick else set()
        missing = [t for t in item.get("traps", []) if t not in codes]
        rows.append({"id": item["id"], "text": item["text"], "claim": item["claim"], "expected": item["expected"],
                     "got": got, "ok": got == item["expected"], "traps_expected": item.get("traps", []),
                     "traps_missing": missing, "traps_got": sorted(codes)})
    n = len(rows)
    correct = sum(r["ok"] for r in rows)
    trap_total = sum(len(r["traps_expected"]) for r in rows)
    trap_hit = trap_total - sum(len(r["traps_missing"]) for r in rows)
    confusion = Counter((r["expected"], r["got"]) for r in rows)
    per_class = {}
    for v in VERDICTS:
        tp = confusion.get((v, v), 0)
        pred = sum(c for (e, g), c in confusion.items() if g == v)
        true = sum(c for (e, g), c in confusion.items() if e == v)
        per_class[v] = {"precision": tp / pred if pred else None, "recall": tp / true if true else None, "support": true}
    return {"n": n, "correct": correct, "accuracy": correct / n if n else 0.0,
            "trap_recall": trap_hit / trap_total if trap_total else None, "trap_expected": trap_total, "trap_hit": trap_hit,
            "per_class": per_class, "confusion": {f"{e}->{g}": c for (e, g), c in sorted(confusion.items())}, "rows": rows}


def to_markdown(res: dict) -> str:
    lines = ["# TruthLens India v0.1 test-set results", "",
             f"- Sentences: {res['n']}",
             f"- Verdict accuracy: **{res['correct']}/{res['n']} = {res['accuracy']:.1%}**",
             f"- Trap recall (expected trap warnings raised): {res['trap_hit']}/{res['trap_expected']} = {res['trap_recall']:.1%}", "",
             "| Verdict | Precision | Recall | Support |", "|---|---|---|---|"]
    for v, m in res["per_class"].items():
        p = "—" if m["precision"] is None else f"{m['precision']:.2f}"
        r = "—" if m["recall"] is None else f"{m['recall']:.2f}"
        lines.append(f"| {v} | {p} | {r} | {m['support']} |")
    bad = [r for r in res["rows"] if not r["ok"] or r["traps_missing"]]
    lines += ["", "## Misses", ""]
    if not bad:
        lines.append("None.")
    for r in bad:
        lines.append(f"- #{r['id']} “{r['text']}” expected {r['expected']}, got {r['got']}"
                     + (f"; missing traps {r['traps_missing']}" if r["traps_missing"] else ""))
    lines += ["", "_The test set is small and was written by the developers alongside the rules, so it measures regressions, "
              "not real-world accuracy. A larger set of sentences taken from published Indian reports is on the roadmap._", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------- v0.2 (all claim types)
V2_VERDICTS = ["SUPPORTED", "PARTLY SUPPORTED", "CONTRADICTED", "UNVERIFIED", "SKIPPED"]


def evaluate_v2(path: Path, pipe, workers: int = 1) -> dict:
    """Each line: {"id", "text", "type", "expected"}. The sentence's verdict is the worst claim verdict."""
    from .readers import read_text
    items = load_testset(path)
    if workers > 1:
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            reps = list(ex.map(lambda it: pipe.run(read_text(it["text"]), f"#{it['id']}"), items))
    else:
        reps = [pipe.run(read_text(it["text"]), f"#{it['id']}") for it in items]
    rows = []
    for item, rep in zip(items, reps):
        claims = rep["claims"]
        got_type = claims[0]["claim"]["type"] if claims else "none"
        # an item can hold several sentences (an injected preamble before the claim): score the item as the reader
        # sees it, by its most severe sentence verdict, not by whichever sentence happens to come first
        from .model import SEVERITY
        judged = [s["verdict"] for s in rep["sentences"] if s.get("verdict")]
        got = max(judged, key=lambda v: SEVERITY.get(v, 0)) if judged else ("SKIPPED" if claims else "NOT_EXTRACTED")
        conf = claims[0]["confidence"] if claims else ""
        rows.append({"id": item["id"], "text": item["text"], "type": item["type"], "got_type": got_type,
                     "expected": item["expected"], "got": got, "ok": got == item["expected"],
                     "type_ok": got_type == item["type"], "confidence": conf,
                     "method": claims[0]["method"] if claims else ""})
    n = len(rows)
    correct = sum(r["ok"] for r in rows)
    conf = Counter((r["expected"], r["got"]) for r in rows)
    unsafe = [r for r in rows if r["got"] == "SUPPORTED" and r["expected"] in ("CONTRADICTED", "UNVERIFIED")]
    missed = [r for r in rows if r["expected"] == "CONTRADICTED" and r["got"] != "CONTRADICTED"]
    by_type: dict = {}
    for r in rows:
        t = by_type.setdefault(r["type"], {"n": 0, "correct": 0})
        t["n"] += 1
        t["correct"] += r["ok"]
    per_class = {}
    for v in V2_VERDICTS:
        tp = conf.get((v, v), 0)
        pred = sum(c for (e, g), c in conf.items() if g == v)
        true = sum(c for (e, g), c in conf.items() if e == v)
        per_class[v] = {"precision": tp / pred if pred else None, "recall": tp / true if true else None, "support": true}
    return {"n": n, "correct": correct, "accuracy": correct / n if n else 0.0,
            "type_accuracy": sum(r["type_ok"] for r in rows) / n if n else 0.0,
            "unsafe_supported": len(unsafe), "contradictions_missed": len(missed),
            "contradictions_total": sum(1 for r in rows if r["expected"] == "CONTRADICTED"),
            "by_type": by_type, "per_class": per_class,
            "confusion": {f"{e}->{g}": c for (e, g), c in sorted(conf.items())}, "rows": rows}


def to_markdown_v2(res: dict, title: str) -> str:
    lines = [f"## {title}", "",
             f"- Sentences: {res['n']}",
             f"- Verdict accuracy: **{res['correct']}/{res['n']} = {res['accuracy']:.1%}**",
             f"- Claim-type accuracy: {res['type_accuracy']:.1%}",
             f"- Unsafe SUPPORTED (expected CONTRADICTED or UNVERIFIED, got SUPPORTED): **{res['unsafe_supported']}**",
             f"- Contradictions caught: {res['contradictions_total'] - res['contradictions_missed']}/{res['contradictions_total']}", "",
             "| Claim type | Correct |", "|---|---|"]
    for t, m in sorted(res["by_type"].items()):
        lines.append(f"| {t} | {m['correct']}/{m['n']} |")
    lines += ["", "| Verdict | Precision | Recall | Support |", "|---|---|---|---|"]
    for v, m in res["per_class"].items():
        p = "—" if m["precision"] is None else f"{m['precision']:.2f}"
        r = "—" if m["recall"] is None else f"{m['recall']:.2f}"
        lines.append(f"| {v} | {p} | {r} | {m['support']} |")
    bad = [r for r in res["rows"] if not r["ok"]]
    lines += ["", "Misses:", ""]
    if not bad:
        lines.append("None.")
    for r in bad:
        lines.append(f"- #{r['id']} ({r['type']}) “{r['text'][:140]}” expected {r['expected']}, got {r['got']} [{r['method']}]")
    lines.append("")
    return "\n".join(lines)
