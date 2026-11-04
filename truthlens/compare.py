"""v0.6: compare two versions of a document (an old policy and its new draft).

What it reports, all computed locally (no network, no AI):
  * near-copied sentences: a sentence of the new version whose text is at least 85% the same as a sentence of the
    old version (difflib ratio on lower-cased text without list markers or section numbers; each old sentence is used
    at most once, best pairs first);
  * numbers that changed between matched sentences (similarity at least 60%): '20 mha' -> '19.13 mha';
  * sentences of the old version with no match in the new one (similarity under 60%), and the subset that state a
    commitment (shall, will, should, must, ensure, target ...): "commitments dropped";
  * new sections: headings of the new version that are not in the old one, with how many of the sentences under them
    are new.

Limits: sentence splitting follows the PDF text, so a sentence broken across lines or pages in one file and not the
other can miss its match; a reordered or merged sentence counts as reworded or new; the similarity is about wording,
not meaning.
"""
from __future__ import annotations

import datetime as dt
import difflib
import html
import json
import re
from typing import Optional

from . import __version__
from .claims import non_claim_reason, segment, strip_marks

NEAR_COPY = 0.85
MATCHED = 0.60
MIN_WORDS = 6
COMMIT_RX = re.compile(r"\b(?:shall|will|should|must|ensure[sd]?|commit\w*|endeavou?r\w*|undertake[sn]?|target\w*|"
                       r"guarantee\w*|mandatory|obligat\w*|priorit\w*|aim\w*\s+to|is\s+to\s+be|are\s+to\s+be)\b", re.I)
WORD_RX = re.compile(r"[a-z]+|\d+(?:\.\d+)?")
HEAD_NUM_RX = re.compile(r"^\s*(?:chapter\s+)?(?:\d{1,2}(?:\.\d{1,2}){0,2}\.?|[ivxlc]{1,6}[.)]|[a-z][.)])\s+", re.I)
TOC_RX = re.compile(r"(?:\.{4,}|…{2,}|_{4,})\s*\d*\s*$")


def _norm(text: str) -> str:
    t = strip_marks(text or "").lower()
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[^\w%.'\s-]", " ", t)
    return re.sub(r"\s+", " ", t).strip(" .")


def _words(text: str) -> set:
    return set(WORD_RX.findall(text))


def _sentences(blocks) -> list:
    out = []
    for s in segment(blocks):
        txt = (s.text or "").strip()
        if len(txt.split()) < MIN_WORDS or TOC_RX.search(txt):
            continue
        why = non_claim_reason(txt)
        if why in ("heading", "table", "contact"):
            continue
        n = _norm(txt)
        out.append({"id": s.id, "text": txt, "location": s.location, "block": s.block, "norm": n, "words": _words(n)})
    return out


def _ratio(a: str, b: str, floor: float) -> float:
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < floor or sm.quick_ratio() < floor:
        return 0.0
    return sm.ratio()


def _pairs(old: list, new: list) -> list:
    """One-to-one pairs (similarity >= MATCHED), best first."""
    index: dict = {}
    for i, s in enumerate(old):
        for w in s["words"]:
            index.setdefault(w, []).append(i)
    cand = []
    for j, s in enumerate(new):
        hits: dict = {}
        for w in s["words"]:
            if len(index.get(w, ())) > 0.5 * len(old) and len(old) > 20:
                continue            # very common words do not pick candidates
            for i in index.get(w, ()):
                hits[i] = hits.get(i, 0) + 1
        for i, h in hits.items():
            o = old[i]
            if h < 0.3 * min(len(o["words"]), len(s["words"])):
                continue
            r = _ratio(o["norm"], s["norm"], MATCHED)
            if r >= MATCHED:
                cand.append((r, i, j))
    cand.sort(key=lambda x: (-x[0], x[1], x[2]))
    used_o, used_n, out = set(), set(), []
    for r, i, j in cand:
        if i in used_o or j in used_n:
            continue
        used_o.add(i)
        used_n.add(j)
        out.append((r, i, j))
    return out


def _merged(old: list, new: list, pairs: list, near_copy: float) -> list:
    """Two adjacent old sentences that the new version joined into one (or one old sentence the new version split in
    two), when the joined text is a near-copy and the parts are not already near-copies elsewhere."""
    best_n = {j: r for r, i, j in pairs}
    best_o = {i: r for r, i, j in pairs}
    used_o = {i for r, i, j in pairs if r >= near_copy}
    used_n = {j for r, i, j in pairs if r >= near_copy}
    out = []
    for j, s in enumerate(new):
        if j in used_n:
            continue
        for i in range(len(old) - 1):
            if i in used_o or i + 1 in used_o or old[i]["block"] > old[i + 1]["block"] + 1:
                continue
            joined = old[i]["norm"] + " " + old[i + 1]["norm"]
            if len(_words(joined) & s["words"]) < 0.5 * len(s["words"]):
                continue
            r = _ratio(joined, s["norm"], near_copy)
            if r >= near_copy and r > best_n.get(j, 0):
                out.append(("join", r, (i, i + 1), (j,)))
                used_o |= {i, i + 1}
                used_n.add(j)
                break
    for i, o in enumerate(old):
        if i in used_o:
            continue
        for j in range(len(new) - 1):
            if j in used_n or j + 1 in used_n:
                continue
            joined = new[j]["norm"] + " " + new[j + 1]["norm"]
            if len(_words(joined) & o["words"]) < 0.5 * len(o["words"]):
                continue
            r = _ratio(o["norm"], joined, near_copy)
            if r >= near_copy and r > best_o.get(i, 0):
                out.append(("split", r, (i,), (j, j + 1)))
                used_o.add(i)
                used_n |= {j, j + 1}
                break
    return out


LEAD_SECTION_RX = re.compile(r"^\s*(?:\(?[ivxlc]{1,5}[.)]|\(?[a-z][.)]|\d{1,2}(?:\.\d{1,2}){0,3}\.?|[-–•*])\s+(?=[A-Z](?:[a-z]|\s)|\()")
UNIT = (r"%|per\s?cent|bcm|mcm|m\.?a\.?f\.?|maf|mha|m\.?\s?ha|lakh\s+ha|lac\s+ha|ha\b|hectares?|lakh|lac|crores?|"
        r"million|billion|thousand|sq\.?\s?kms?|km|mw|gw|kwh|tmc|cumecs?|cusecs?|mm|t/ha|tonnes?|tones|lpcd|mld|rs\.?|₹")
FIG_RX = re.compile(rf"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*({UNIT})?(?![\w])", re.I)
YEARISH_RX = re.compile(r"^(?:19|20)\d{2}$")


def _figures(text: str) -> list:
    """(value, unit, raw) for each figure, without a leading section number ('4.3 State has ...') or bare years; a
    leading figure with a unit ('27.8 BCM of surface water ...') is kept. A unit-less figure inside a range or list
    is kept too, so a changed count shows."""
    m = LEAD_SECTION_RX.match(text or "")
    t = text[m.end():] if m else (text or "")
    out = []
    for f in FIG_RX.finditer(t):
        num, unit = f.group(1).rstrip(","), (f.group(2) or "").lower().replace(" ", "").replace(".", "")
        if not unit and YEARISH_RX.match(num):
            continue
        try:
            v = float(num.replace(",", ""))
        except ValueError:
            continue
        unit = {"percent": "%", "crores": "crore", "hectare": "ha", "hectares": "ha", "lacha": "lakhha", "lac": "lakh",
                "tones": "tonne", "tonnes": "tonne", "maf": "maf", "mha": "mha", "sqkms": "sqkm"}.get(unit, unit)
        out.append((v, unit, (num + (" " + f.group(2) if f.group(2) else "")).strip()))
    return out


def number_changes(old_text: str, new_text: str) -> dict:
    """Figures that differ between two matched sentences: {'changed': [{old, new}], 'removed': [...], 'added': [...]}.
    A changed figure is one with the same unit at the same place in the sentence and a different value."""
    a, b = _figures(old_text), _figures(new_text)
    ka, kb = [f"{v:.6g}|{u}" for v, u, _r in a], [f"{v:.6g}|{u}" for v, u, _r in b]
    out = {"changed": [], "removed": [], "added": []}
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ka, kb, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        left, right = list(a[i1:i2]), list(b[j1:j2])
        for x in list(left):
            y = next((y for y in right if y[1] == x[1]), None)
            if y is not None:
                out["changed"].append({"old": x[2], "new": y[2]})
                left.remove(x)
                right.remove(y)
        out["removed"] += [x[2] for x in left]
        out["added"] += [y[2] for y in right]
    return out


def _headings(blocks) -> list:
    out = []
    for i, b in enumerate(blocks):
        t = re.sub(r"\s+", " ", (b.text or "")).strip()
        if not t or TOC_RX.search(t) or len(t) > 110:
            continue
        words = re.findall(r"[A-Za-z][A-Za-z'’\-]*", t)
        if not (1 <= len(words) <= 12) or t.endswith((".", ",", ";")) and not HEAD_NUM_RX.match(t):
            continue
        if re.search(r"\d{3,}", HEAD_NUM_RX.sub("", t)):
            continue
        numbered = bool(HEAD_NUM_RX.match(t))
        caps = sum(1 for w in words if w.isupper() and len(w) > 1) >= 0.6 * len(words)
        if not (numbered or caps):
            continue
        if t.endswith(".") and len(words) > 8:
            continue
        out.append({"block": i, "text": t, "location": b.location, "norm": _norm(HEAD_NUM_RX.sub("", t))})
    return out


def compare_blocks(old_blocks, new_blocks, old_name: str = "old", new_name: str = "new",
                   near_copy: float = NEAR_COPY) -> dict:
    old, new = _sentences(old_blocks), _sentences(new_blocks)
    pairs = _pairs(old, new)
    near, reworded, num_rows = [], [], []
    matched_o, matched_n = set(), set()
    for r, i, j in sorted(pairs, key=lambda p: p[2]):
        o, n = old[i], new[j]
        matched_o.add(i)
        matched_n.add(j)
        ch = number_changes(o["text"], n["text"])
        row = {"similarity": round(r, 3), "old": o["text"], "new": n["text"], "old_location": o["location"],
               "new_location": n["location"], "numbers": ch, "_i": i, "_j": j}
        (near if r >= near_copy else reworded).append(row)
        if ch["changed"] or ch["removed"] or ch["added"]:
            num_rows.append(row)
    for kind, r, ii, jj in _merged(old, new, pairs, near_copy):
        # replace any weaker single-sentence pairing of these sentences with the joined / split near-copy
        reworded = [x for x in reworded if not (x.get("_i") in ii or x.get("_j") in jj)]
        num_rows = [x for x in num_rows if not (x.get("_i") in ii or x.get("_j") in jj)]
        o_txt = " ".join(old[i]["text"] for i in ii)
        n_txt = " ".join(new[j]["text"] for j in jj)
        ch = number_changes(o_txt, n_txt)
        row = {"similarity": round(r, 3), "old": o_txt, "new": n_txt, "old_location": old[ii[0]]["location"],
               "new_location": new[jj[0]]["location"], "numbers": ch,
               "note": "two old sentences joined into one" if kind == "join" else "one old sentence split in two",
               "_order": jj[0]}
        near.append(row)
        if ch["changed"] or ch["removed"] or ch["added"]:
            num_rows.append(row)
        matched_o |= set(ii)
        matched_n |= set(jj)
    near.sort(key=lambda x: x.get("_order", x.get("_j", 0)))
    num_rows.sort(key=lambda x: x.get("_order", x.get("_j", 0)))
    for x in near + reworded + num_rows:
        for k in ("_i", "_j", "_order"):
            x.pop(k, None)
    dropped = [{"text": o["text"], "location": o["location"], "commitment": bool(COMMIT_RX.search(o["text"]))}
               for i, o in enumerate(old) if i not in matched_o]
    added = [{"text": n["text"], "location": n["location"], "block": n["block"]}
             for j, n in enumerate(new) if j not in matched_n]
    # new sections: headings of the new version not found among the old version's headings or sentences
    old_heads = [h["norm"] for h in _headings(old_blocks)]
    old_norms = [o["norm"] for o in old]
    nh = _headings(new_blocks)
    sections = []
    for k, h in enumerate(nh):
        if not h["norm"] or len(h["norm"]) < 4:
            continue
        if any(_ratio(h["norm"], x, 0.8) >= 0.8 for x in old_heads) or any(h["norm"] in x for x in old_norms):
            continue
        end = nh[k + 1]["block"] if k + 1 < len(nh) else len(new_blocks)
        under = [n for n in new if h["block"] <= n["block"] < end]
        matched_ids = {new[j]["id"] for j in matched_n}
        fresh = [n for n in under if n["id"] not in matched_ids]
        sections.append({"heading": h["text"], "location": h["location"], "sentences": len(under),
                         "new_sentences": len(fresh)})
    changed_figs = sum(len(r["numbers"]["changed"]) for r in num_rows)
    return {
        "tool": "TruthLens", "version": __version__, "kind": "compare",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "old": {"name": old_name, "blocks": len(old_blocks), "sentences_compared": len(old)},
        "new": {"name": new_name, "blocks": len(new_blocks), "sentences_compared": len(new)},
        "method": {"near_copy_threshold": near_copy, "matched_threshold": MATCHED, "min_words": MIN_WORDS,
                   "similarity": "difflib SequenceMatcher ratio on lower-cased sentences without list markers or "
                                 "section numbers; each old sentence matched at most once, best pairs first"},
        "summary": {"near_copies": len(near), "reworded": len(reworded), "sentences_with_changed_numbers": len(num_rows),
                    "figures_changed": changed_figs, "dropped": len(dropped),
                    "dropped_commitments": sum(1 for d in dropped if d["commitment"]), "added": len(added),
                    "new_sections": len(sections),
                    "near_copy_share_of_new": round(len(near) / len(new), 3) if new else 0.0},
        "near_copies": near,
        "reworded": reworded,
        "number_changes": num_rows,
        "dropped": dropped,
        "added": added,
        "new_sections": sections,
    }


def add_meaning(rep: dict, old_blocks, new_blocks, embedder=None, topics: str = "auto",
                threshold: Optional[float] = None, model: Optional[str] = None, llm=None) -> dict:
    """v0.7: add the meaning comparison (rep['meaning']). When the optional model is not installed or cannot be
    loaded, rep['meaning'] = {'unavailable': why} and the wording comparison stands on its own."""
    from .meaning import MATCH, FastEmbedder, MeaningUnavailable, ai_summaries, compare_meaning
    try:
        m = compare_meaning(old_blocks, new_blocks, embedder or FastEmbedder(model),
                            MATCH if threshold is None else threshold, topics)
    except MeaningUnavailable as e:
        rep["meaning"] = {"unavailable": str(e)}
        return rep
    if llm is not None:
        ai_summaries(m, llm)
    rep["meaning"] = m
    return rep


def compare_paths(old_path, new_path, near_copy: float = NEAR_COPY, meaning: bool = False, **mopts) -> dict:
    from pathlib import Path
    from .readers import read_file
    ob, nb = read_file(old_path), read_file(new_path)
    rep = compare_blocks(ob, nb, Path(old_path).name, Path(new_path).name, near_copy)
    return add_meaning(rep, ob, nb, **mopts) if meaning else rep


def compare_bytes(old: bytes, old_suffix: str, old_name: str, new: bytes, new_suffix: str, new_name: str,
                  near_copy: float = NEAR_COPY, meaning: bool = False, **mopts) -> dict:
    from .readers import read_bytes
    ob, nb = read_bytes(old, old_suffix), read_bytes(new, new_suffix)
    rep = compare_blocks(ob, nb, old_name, new_name, near_copy)
    return add_meaning(rep, ob, nb, **mopts) if meaning else rep


# ---------------------------------------------------------------------------------------------- reports
def summary_line(rep: dict) -> str:
    s = rep["summary"]
    return (f"{s['near_copies']} near-copied sentences · {s['figures_changed']} figures changed (old → new) in "
            f"{s['sentences_with_changed_numbers']} matched sentences with different figures · {s['dropped']} old "
            f"sentences with no match ({s['dropped_commitments']} commitments) · {s['added']} new sentences · "
            f"{s['new_sections']} new section headings")


def _nums_text(ch: dict) -> str:
    bits = [f"{c['old']} → {c['new']}" for c in ch.get("changed") or []]
    bits += [f"removed {x}" for x in ch.get("removed") or []]
    bits += [f"added {x}" for x in ch.get("added") or []]
    return "; ".join(bits)


def _md(s) -> str:
    return (str(s) if s is not None else "").replace("|", "\\|").replace("\n", " ")


LABEL_COLS = ("kept", "strengthened", "weakened", "changed figure", "new", "dropped")


def meaning_line(m: dict) -> str:
    s = m["summary"]
    return " · ".join(f"{s.get(k, 0)} {k}" for k in LABEL_COLS)


def _loc(q: Optional[dict]) -> str:
    if not q:
        return ""
    bits = [str(q.get("location") or ""), (f"para {q['para']}" if q.get("para") else "")]
    return ", ".join(b for b in bits if b)


def _meaning_md(m: dict, per_topic: int = 40) -> list:
    if m.get("unavailable"):
        return ["## Match by meaning", "", f"_Not run: {_md(m['unavailable'])}_", ""]
    out = ["## Match by meaning", "", f"**{meaning_line(m)}**", "",
           f"Model: {_md(m.get('model_note') or m.get('model'))}. Match score threshold {m['threshold']:.3f}; topics from "
           f"{_md(m['topic_source'])}. {_md(m['method'])}", "",
           f"_{_md(m['caveat'])} Labels are rules, not AI; reasons are only quotes from the new version._", "",
           "| Topic | kept | strengthened | weakened | changed figure | new | dropped |", "|---|---|---|---|---|---|---|"]
    for t in m["topics"]:
        c = t["counts"]
        out.append(f"| {_md(t['topic'])} | " + " | ".join(str(c.get(k, 0)) for k in LABEL_COLS) + " |")
    for t in m["topics"]:
        out += ["", f"### {_md(t['topic'])}", ""]
        if t.get("why"):
            for w in t["why"]:
                out.append(f"- **Reason the document gives** ({_md(_loc(w))}; linked by similarity, check): “{_md(w['text'])}”")
        else:
            out.append("- Reason not stated in the document")
        ai = t.get("ai_summary")
        if ai:
            if ai["status"] == "ok":
                out.append(f"- **{ai['label']}:** {_md(ai['text'])}")
            else:
                out.append(f"- {ai['label']}: not shown ({ai['status']}: {_md('; '.join(ai.get('problems') or []))})")
        shown = 0
        for it in t["items"]:
            if shown >= per_topic:
                out.append(f"- … {len(t['items']) - shown} more in the JSON or HTML report")
                break
            shown += 1
            old = f"Old ({_md(_loc(it['old']))}): “{_md(it['old']['text'])}”" if it.get("old") else ""
            news = " / ".join(f"New ({_md(_loc(n))}): “{_md(n['text'])}”" for n in it.get("new") or [])
            rule = f" _({_md('; '.join(it['rule']))})_" if it.get("rule") else ""
            if it["label"] == "dropped":
                near = it.get("nearest_new")
                hint = (f" Possible match (weak, score {it['match_score']:.3f}): “{_md(near['text'])}”"
                        if it.get("possible_match") and near else "")
                out.append(f"- **dropped** {old}.{hint}")
            elif it["label"] == "new":
                out.append(f"- **new** {news}")
            else:
                out.append(f"- **{it['label']}** (score {it['match_score']:.3f}) {old} → {news}{rule}")
    out += ["", "## Wording comparison", ""]
    return out


def to_markdown(rep: dict, limit: int = 200) -> str:
    s = rep["summary"]
    out = [f"# TruthLens compare: {rep['old']['name']} → {rep['new']['name']}", "",
           f"Generated {rep['generated_at']} by TruthLens {rep['version']}. Local comparison; "
           f"{'no network except the one-time model download' if rep.get('meaning') else 'no network'}.", ""]
    if rep.get("meaning"):
        out += _meaning_md(rep["meaning"])
    out += [f"**{summary_line(rep)}**", "",
           f"Sentences compared: {rep['old']['sentences_compared']} (old), {rep['new']['sentences_compared']} (new); "
           f"sentences of {MIN_WORDS}+ words, headings and table rows left out. Near-copy: similarity ≥ "
           f"{rep['method']['near_copy_threshold']:.2f}; matched: ≥ {rep['method']['matched_threshold']:.2f}.", "",
           f"## Near-copied sentences ({s['near_copies']})", "", "| # | Similarity | Old | New | Figures changed |",
           "|---|---|---|---|---|"]
    for i, r in enumerate(rep["near_copies"][:limit], 1):
        out.append(f"| {i} | {r['similarity']:.2f} | {_md(r['old'][:180])} | {_md(r['new'][:180])} | {_md(_nums_text(r['numbers']))} |")
    out += ["", f"## Numbers changed between matched sentences ({s['sentences_with_changed_numbers']} sentences)", "",
            "| # | Similarity | Old | New | Change |", "|---|---|---|---|---|"]
    for i, r in enumerate(rep["number_changes"][:limit], 1):
        out.append(f"| {i} | {r['similarity']:.2f} | {_md(r['old'][:160])} | {_md(r['new'][:160])} | {_md(_nums_text(r['numbers']))} |")
    out += ["", f"## Commitments dropped ({s['dropped_commitments']} of {s['dropped']} old sentences with no match)", ""]
    out += [f"- {_md(d['text'][:240])} _({_md(d['location'])})_" for d in rep["dropped"] if d["commitment"]][:limit]
    out += ["", f"## Other old sentences with no match ({s['dropped'] - s['dropped_commitments']})", ""]
    out += [f"- {_md(d['text'][:240])}" for d in rep["dropped"] if not d["commitment"]][:limit]
    out += ["", f"## New sections ({s['new_sections']})", "", "| Heading | Sentences under it | Of which new |", "|---|---|---|"]
    out += [f"| {_md(x['heading'])} | {x['sentences']} | {x['new_sentences']} |" for x in rep["new_sections"][:limit]]
    out += ["", "_Similarity is about wording, not meaning. A sentence split differently by the PDF text in one file can "
            "miss its match. Check the pairs before relying on them._", ""]
    return "\n".join(out)


def to_json(rep: dict) -> str:
    return json.dumps(rep, indent=2, ensure_ascii=False, default=str)


CSS = """body{font:15px/1.5 Georgia,'Times New Roman',serif;color:#211d18;background:#f7f4ee;margin:0}
header,main{max-width:1100px;margin:0 auto;padding:24px}h1{font:600 22px/1.3 system-ui,sans-serif}h2{font:600 17px/1.3 system-ui,sans-serif;margin-top:28px}
.sum{font:600 16px/1.5 system-ui,sans-serif}.sub{font:13px/1.5 system-ui,sans-serif;color:#5e564b}
table{border-collapse:collapse;width:100%;font-size:13px;background:#fffdf9}td,th{border-top:1px solid #e3ddd2;padding:6px 8px;vertical-align:top;text-align:left}
th{font:600 12px system-ui,sans-serif;color:#5e564b}td.n{font-family:ui-monospace,monospace;white-space:nowrap}del{color:#b42318}ins{color:#1d6b3a;text-decoration:none;font-weight:600}
li{margin:4px 0}details{margin:6px 0;background:#fffdf9;border:1px solid #e3ddd2;padding:6px 10px}summary{cursor:pointer;font:600 14px system-ui,sans-serif}
.lab{font:600 11px system-ui,sans-serif;padding:1px 6px;border-radius:8px;background:#ece6da;white-space:nowrap}.lab.strengthened{background:#d8eedd}.lab.weakened{background:#f6dcd6}
.lab.dropped{background:#f1e2c8}.lab.new{background:#dce8f6}.lab.changed{background:#efe0f4}.why{font-size:13px;color:#3d372f}.ai{font-size:13px;border-left:3px solid #c9b98f;padding-left:8px}"""


def to_html(rep: dict, limit: int = 300) -> str:
    e = html.escape
    s = rep["summary"]

    def diff_html(a: str, b: str) -> tuple:
        sa, sb = a.split(), b.split()
        oa, ob = [], []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sa, sb, autojunk=False).get_opcodes():
            if op == "equal":
                oa.append(e(" ".join(sa[i1:i2])))
                ob.append(e(" ".join(sb[j1:j2])))
            else:
                if i2 > i1:
                    oa.append("<del>" + e(" ".join(sa[i1:i2])) + "</del>")
                if j2 > j1:
                    ob.append("<ins>" + e(" ".join(sb[j1:j2])) + "</ins>")
        return " ".join(oa), " ".join(ob)

    def rows(items):
        out = []
        for i, r in enumerate(items[:limit], 1):
            a, b = diff_html(r["old"], r["new"])
            out.append(f"<tr><td class=n>{i}</td><td class=n>{r['similarity']:.2f}</td><td>{a}</td><td>{b}</td>"
                       f"<td class=n>{e(_nums_text(r['numbers']))}</td></tr>")
        return "".join(out)
    head = "<tr><th>#</th><th>Similarity</th><th>Old</th><th>New</th><th>Figures</th></tr>"
    meaning_html = _meaning_html(rep["meaning"]) if rep.get("meaning") else ""
    drops = "".join(f"<li>{e(d['text'])} <span class=sub>({e(str(d['location']))})</span></li>"
                    for d in rep["dropped"] if d["commitment"])
    others = "".join(f"<li>{e(d['text'])}</li>" for d in rep["dropped"] if not d["commitment"])
    secs = "".join(f"<tr><td>{e(x['heading'])}</td><td class=n>{x['sentences']}</td><td class=n>{x['new_sentences']}</td></tr>"
                   for x in rep["new_sections"][:limit])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TruthLens compare: {e(rep['old']['name'])} → {e(rep['new']['name'])}</title><style>{CSS}</style></head><body>
<header><p class=sub><b>TruthLens</b> · compare two versions · {e(rep['version'])} · {e(rep['generated_at'])}</p>
<h1>{e(rep['old']['name'])} → {e(rep['new']['name'])}</h1><p class=sum>{e(summary_line(rep))}</p>
<p class=sub>Sentences compared: {rep['old']['sentences_compared']} (old), {rep['new']['sentences_compared']} (new). Near-copy:
similarity ≥ {rep['method']['near_copy_threshold']:.2f}; matched: ≥ {rep['method']['matched_threshold']:.2f}. Local text comparison
(no network). Similarity is about wording, not meaning.</p></header><main>
{meaning_html}<h2>Near-copied sentences ({s['near_copies']})</h2><table>{head}{rows(rep['near_copies'])}</table>
<h2>Numbers changed between matched sentences ({s['sentences_with_changed_numbers']})</h2><table>{head}{rows(rep['number_changes'])}</table>
<h2>Commitments dropped ({s['dropped_commitments']})</h2><ul>{drops or '<li>none</li>'}</ul>
<h2>New sections ({s['new_sections']})</h2><table><tr><th>Heading</th><th>Sentences</th><th>Of which new</th></tr>{secs}</table>
<details><summary>Other old sentences with no match ({s['dropped'] - s['dropped_commitments']})</summary><ul>{others}</ul></details>
</main></body></html>"""


def _meaning_html(m: dict) -> str:
    e = html.escape
    if m.get("unavailable"):
        return f"<h2>Match by meaning</h2><p class=sub>Not run: {e(m['unavailable'])}</p><h2>Wording comparison</h2>"
    rows = "".join(f"<tr><td><a href='#t{k}'>{e(t['topic'])}</a></td>" + "".join(
        f"<td class=n>{t['counts'].get(c, 0)}</td>" for c in LABEL_COLS) + "</tr>" for k, t in enumerate(m["topics"]))
    parts = [f"<h2>Match by meaning</h2><p class=sum>{e(meaning_line(m))}</p>",
             f"<p class=sub>Model: {e(m.get('model_note') or m.get('model'))}. Match score threshold {m['threshold']:.3f}; "
             f"topics from {e(m['topic_source'])}. {e(m['method'])} <b>{e(m['caveat'])}</b> Labels are rules, not AI; "
             "reasons are only quotes from the new version.</p>",
             "<table><tr><th>Topic</th>" + "".join(f"<th>{c}</th>" for c in LABEL_COLS) + f"</tr>{rows}</table>"]

    def q(x):
        return f"“{e(x['text'])}” <span class=sub>({e(_loc(x))})</span>" if x else ""
    for k, t in enumerate(m["topics"]):
        c = t["counts"]
        why = "".join(f"<p class=why><b>Reason the document gives</b> (linked by similarity, check): {q(w)}</p>"
                      for w in t.get("why") or []) or "<p class=why>Reason not stated in the document</p>"
        ai = t.get("ai_summary")
        if ai and ai["status"] == "ok":
            why += f"<p class=ai><b>{e(ai['label'])}:</b> {e(ai['text'])}</p>"
        elif ai:
            why += f"<p class=ai>{e(ai['label'])}: not shown ({e(ai['status'])}: {e('; '.join(ai.get('problems') or []))})</p>"
        trs = []
        for it in t["items"]:
            lab = it["label"]
            new = "<br>".join(q(n) for n in it.get("new") or [])
            if lab == "dropped" and it.get("possible_match") and it.get("nearest_new"):
                new = f"<span class=sub>Possible match (weak, score {it['match_score']:.3f}):</span> {q(it['nearest_new'])}"
            note = e("; ".join(it.get("rule") or []))
            score = f"{it['match_score']:.3f}" if lab not in ("new",) else ""
            trs.append(f"<tr><td><span class='lab {lab.split()[0]}'>{e(lab)}</span></td><td class=n>{score}</td>"
                       f"<td>{q(it.get('old'))}</td><td>{new}</td><td class=sub>{note}</td></tr>")
        counts = ", ".join(f"{c.get(x, 0)} {x}" for x in LABEL_COLS if c.get(x))
        parts.append(f"<details id='t{k}'><summary>{e(t['topic'])} <span class=sub>({e(counts)})</span></summary>{why}"
                     "<table><tr><th>Label</th><th>Score</th><th>Old</th><th>New</th><th>Why this label</th></tr>"
                     + "".join(trs) + "</table></details>")
    parts.append("<h2>Wording comparison</h2>")
    return "".join(parts)


def render(rep: dict, fmt: str) -> str:
    return {"json": to_json, "md": to_markdown, "markdown": to_markdown, "html": to_html}[fmt](rep)
