"""v0.2 reports: Turnitin-style HTML (self-contained, printable, no JavaScript), Markdown and JSON."""
from __future__ import annotations

import difflib
import html
import json
import re

VCLASS = {"SUPPORTED": "sup", "PARTLY SUPPORTED": "part", "CONTRADICTED": "con", "UNVERIFIED": "unv", "SKIPPED": "op"}
VLABEL = {"SUPPORTED": "Supported", "PARTLY SUPPORTED": "Partly supported", "CONTRADICTED": "Contradicted",
          "UNVERIFIED": "Needs a source / couldn't check", "SKIPPED": "Opinion (not checked)"}
TYPE_LABEL = {"numeric": "number/statistic", "citation": "cited claim", "entity": "factual claim", "opinion": "opinion"}
RETRIEVER_LABEL = {"curated": "TruthLens curated official dataset", "mospi": "MoSPI eSankhyiki API (live)",
                   "worldbank": "World Bank WDI (secondary)", "docs": "Official document index", "web": "Web search",
                   "citation": "Cited source", "datagovin": "data.gov.in OGD API"}
def _stype(ev: dict) -> str:
    """Source-type badge text for one evidence item (reports written before v0.3 carry no source_type)."""
    from types import SimpleNamespace
    from .model import source_type_for
    t = ev.get("source_type") or ""
    if t and t != "Parliament":
        return t
    return source_type_for(SimpleNamespace(retriever=ev.get("retriever") or "", source_url=ev.get("source_url") or "",
                                           kind=ev.get("kind") or "", meta=ev.get("meta") or {}))


def _safe_url(u) -> str:
    """Only http(s) links are written as links (a report posted to /render could carry javascript: URLs)."""
    u = str(u or "")
    return u if u.lower().startswith(("https://", "http://")) else ""


def _asof(ev: dict) -> str:
    from .model import data_as_of
    return ev.get("data_as_of") or data_as_of(ev)


def split_counts(s: dict) -> dict:
    """v0.4.1 split figures; reports written before v0.4.1 carry only `verdicts`."""
    v = s.get("verdicts") or {}
    return {"contradicted": s.get("contradicted", v.get("CONTRADICTED", 0)), "partly": s.get("partly", v.get("PARTLY SUPPORTED", 0)),
            "supported": s.get("supported", v.get("SUPPORTED", 0)), "couldnt_check": s.get("couldnt_check", v.get("UNVERIFIED", 0)),
            "skipped": s.get("skipped", s.get("skipped_opinions", 0))}


def headline_text(s: dict) -> str:
    if s.get("headline"):
        return s["headline"]
    from .pipeline import headline
    return headline(split_counts(s))


def cite_rows(report: dict) -> list:
    """v0.5.3: claims to cite (reports written before v0.5.3 are rebuilt from their couldn't-check claims)."""
    rows = report.get("claims_to_cite")
    if rows is not None:
        return rows
    from .verdict import UNCHECKED_REASONS
    return [{"claim_id": c["claim"]["id"], "location": c["claim"]["location"], "text": c["claim"]["text"],
             "why": UNCHECKED_REASONS.get(c.get("unchecked_reason") or "no_data", "no data"),
             "reason": c.get("unchecked_reason") or "no_data", "numbers": c["claim"].get("numbers") or []}
            for c in report.get("claims") or [] if c.get("verdict") == "UNVERIFIED"]


def to_cite_csv(report: dict) -> str:
    """v0.5.3: 'claims to cite' as CSV (UTF-8 with a BOM so Excel shows Indian scripts and ₹ correctly). Cells that
    begin with = + - @ are prefixed with ' so a spreadsheet never runs them as formulas."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["#", "Where", "Claim", "Figures", "Why it needs a source", "Source you will cite"])

    def safe(x):
        x = str(x or "")
        return "'" + x if x[:1] in ("=", "+", "-", "@", "\t", "\r") else x
    for i, r in enumerate(cite_rows(report), 1):
        w.writerow([i, safe(r.get("location")), safe(r.get("text")), safe("; ".join(r.get("numbers") or [])),
                    safe(r.get("why")), ""])
    return "\ufeff" + buf.getvalue()


def banner_lines(report: dict) -> list[str]:
    """v0.4.1: which sources were unreachable this run, how many claims that affected; offline runs say so.
    v0.5.2: short and plain: one line with the top reasons claims couldn't be checked (the per-source detail is in
    banner_details, shown collapsed)."""
    s = report.get("summary") or {}
    out = []
    if s.get("offline"):
        out.append("Offline run: live official sources, citation registries and research indexes were not consulted. "
                   "Figures were checked only against the bundled official snapshot, the offline citation cache and your "
                   "own indexed documents, so more claims show as “couldn't check”.")
    b = s.get("banner")
    if b is not None:
        if b.get("text"):
            out.append(b["text"] + (" Couldn't check is not the same as wrong." if b.get("text") else ""))
        if b.get("sources_down"):
            out.append("Sources that didn't respond: " + ", ".join(b["sources_down"]) + ".")
    else:
        un = s.get("unreachable_sources") or []
        if un:
            out.append("Unreachable this run: " + "; ".join(
                f"{u['source']} ({u['status']}, {u['claims_affected']} claim{'s' if u['claims_affected'] != 1 else ''} affected)"
                if u.get("claims_affected") else (f"{u['source']} ({u['status']} during the run; {u.get('claims_asked', 0)} "
                                                   f"claim{'s' if u.get('claims_asked', 0) != 1 else ''} asked it)")
                for u in un) + ". Claims that needed them show as “couldn't check”, not as wrong.")
        dl = s.get("live_deadline") or {}
        if dl.get("claims_hit_deadline"):
            out.append(dl.get("note") or f"{dl['claims_hit_deadline']} claim(s) ran out of time.")
    fr = s.get("data_freshness") or {}
    if fr.get("stale") and fr.get("last_synced"):
        out.append(fr.get("message") or "Local data is more than 7 days old: run Update now.")
    return out


def banner_details(report: dict) -> list[str]:
    """v0.5.2: the per-source and per-reason detail behind the short banner (collapsed in the HTML report)."""
    s = report.get("summary") or {}
    out = []
    for k, v in (s.get("couldnt_check_reasons") or {}).items():
        if v.get("claims"):
            out.append(f"{v['label']}: {v['claims']} claim{'s' if v['claims'] != 1 else ''}")
    for u in s.get("unreachable_sources") or []:
        if u.get("claims_affected"):
            out.append(f"{u['source']}: {u['status']}, {u['claims_affected']} claim{'s' if u['claims_affected'] != 1 else ''} affected")
    dl = s.get("live_deadline") or {}
    if dl.get("claims_hit_deadline") and dl.get("note"):
        out.append(dl["note"])
    return out


def mode_line(s: dict) -> str:
    """'Quick check · 27 claims not checked in Quick mode — Deep check (about 1 min)' / 'Deep check'."""
    mode = s.get("mode")
    if not mode:
        return ""
    q = ((s.get("couldnt_check_reasons") or {}).get("quick") or {}).get("claims", 0)
    if mode == "quick":
        return "Quick check" + (f" · {q} claim{'s' if q != 1 else ''} not checked in Quick mode — Deep check (about 1 min)"
                                if q else " · every claim that needs a live source was answered from saved data")
    return "Deep check (live sources asked)"


ORDER = {"CONTRADICTED": 0, "PARTLY SUPPORTED": 1, "UNVERIFIED": 2, "SUPPORTED": 3, "SKIPPED": 4}


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, default=str)


def _md(s) -> str:
    return (str(s) if s is not None else "").replace("|", "\\|").replace("\n", " ")


def to_markdown(report: dict) -> str:
    s = report["summary"]
    v = s["verdicts"]
    score = "n/a" if s["verified_score"] is None else f"{s['verified_score']:.0f}%"
    sp = split_counts(s)
    checked = s.get("checked_claims", sp["supported"] + sp["partly"] + sp["contradicted"])
    out = [f"# TruthLens hallucination check: {report['input']}", "",
           f"Generated {report['generated_at']} by TruthLens {report['version']} "
           f"(extractor: {report['meta'].get('extractor', '?')}, judge: {report['meta'].get('judge', '?')}).", "",
           f"**{headline_text(s)}**", "",
           *([f"_{s['split_line']}_", ""] if s.get("split_line") else []),
           "| Wrong (contradicted) | Partly supported | Supported | Couldn't check | Skipped (opinion) |",
           "|---|---|---|---|---|",
           f"| {sp['contradicted']} | {sp['partly']} | {sp['supported']} | {sp['couldnt_check']} | {sp['skipped']} |", ""]
    if mode_line(s):
        out += [f"_{mode_line(s)}_", ""]
    if s.get("statements") is not None:
        out += [f"{s['statements']} statements · {s.get('checkable', 0)} checkable claims"
                + (f" · {s['not_checkable']} not checkable facts (descriptions, procedures)" if s.get("not_checkable") else ""), ""]
    out += [f"> ⚠ {b}" for b in banner_lines(report)] + ([""] if banner_lines(report) else [])
    out += [f"Verified score: {score} (confidence-weighted: high 1.0, medium 0.6, low 0.3) over {checked} checked claims; "
           f"{sp['couldnt_check']} couldn't check are not in the score. {s.get('couldnt_check_note', '')} "
           f"{s.get('low_confidence_supported', 0)} of the supported claims are low-confidence (heuristic match, no AI judge). "
           f"Citations checked: {s['citations_checked']} ({s['citations_not_found']} not found). "
           f"Suggested fixes: {s['suggested_fixes']}.", "",
           "| # | Where | Type | Verdict | Claim | Suggested fix |", "|---|---|---|---|---|---|"]
    for i, c in enumerate(report["claims"], 1):
        cl = c["claim"]
        out.append(f"| {i} | {_md(cl['location'])} | {_md(TYPE_LABEL.get(cl['type'], cl['type']))} | **{c['verdict']}** "
                   f"| {_md(cl['text'][:160])} | {_md(c.get('suggested_fix') or '')} |")
    out += ["", "## Details", ""]
    for i, c in enumerate(report["claims"], 1):
        cl = c["claim"]
        if c["verdict"] == "SKIPPED":
            continue
        out.append(f"### {i}. {c['verdict']} ({c['confidence']} confidence, {c['method']}): {cl['location']}")
        out.append(f"> {cl['sentence']}")
        out.append("")
        if cl.get("hedged"):
            out.append(f"- Opinion wording, but {cl.get('note') or 'contains a factual claim'}: checked “{cl['text']}”.")
        if c.get("failed_part"):
            out.append(f"- **Failed part:** {c['failed_part']}")
        if c.get("rationale"):
            out.append(f"- {c['rationale']}")
        for f in c.get("numbers", []):
            off = f.get("official") or {}
            out.append(f"- Number {f['claimed']}: {f['verdict']}. {f['reason']}"
                       + (f" Official: {off.get('display')} ({off.get('period')})." if off else ""))
        for w in c.get("warnings", []):
            out.append(f"- ⚠ **{w['code']}**: {w['message']}")
        ev_by = {e["id"]: e for e in c["evidence"]}
        quoted = [q["evidence_id"] for q in c.get("quotes", [])]
        for e in c["evidence"][:4]:
            mark = " (quoted)" if e["id"] in quoted else ""
            loc = f", p. {e['page']}" if e.get("page") else ""
            asof = _asof(e)
            tag = " [unverified source: not live-verified]" if e.get("not_live_verified") else ""
            out.append(f"- Evidence {e['id']}{mark} [{_stype(e)}]{tag}: "
                       f"“{_md((e.get('quote') or e['snippet'])[:220])}” ({e.get('publisher') or ''}{loc}{'; data as of ' + asof if asof else ''}) {e['source_url']}")
        for q in c.get("quotes", []):
            if q["evidence_id"] not in ev_by:
                continue
        for cc in c.get("citation_checks", []):
            out.append(f"- Citation {cc.get('citation')}: {cc.get('status')}"
                       + (f", {cc.get('support')}" if cc.get("support") else "")
                       + (f" ({cc.get('title')})" if cc.get("title") else ""))
        if c.get("suggested_fix"):
            out.append(f"- **Suggested:** {c['suggested_fix']}" + (f" ({c['fix_source']})" if c.get("fix_source") else ""))
        out.append("")
    out += ["## Sources", ""]
    for src in report["sources"]:
        out.append(f"- {src.get('publisher') or ''}: {src.get('title') or ''} {src['url']}"
                   + (f" ({src['date']})" if src.get("date") else ""))
    out += ["", "_SUPPORTED: the evidence states the claim. PARTLY SUPPORTED: part of it, or close but not exact. "
            "CONTRADICTED (wrong): the evidence says something different. COULDN'T CHECK (UNVERIFIED): no evidence good enough to "
            "decide; TruthLens fails closed. This is not a finding that the claim is wrong. "
            "The verified score counts SUPPORTED claims among checked claims (supported, partly, contradicted), weighted by "
            "confidence (high 1.0, medium 0.6, low 0.3)._", ""]
    return "\n".join(out)


CSS = """.cite{max-width:1080px;margin:24px auto;padding:0 24px}.cite table{border-collapse:collapse;width:100%;font-size:13px}
.cite th,.cite td{border-top:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}

:root{--bg:#f6f4ef;--paper:#fff;--raised:#f1ede5;--line:rgba(31,27,22,.12);--line2:rgba(31,27,22,.07);
--ink:#1f1b16;--ink2:#564e44;--muted:#6f675c;--accent:#1f4e79;
--sup:#1d6b3a;--supbg:#e2f0e5;--part:#8a5300;--partbg:#fbedcf;--con:#b42318;--conbg:#fadcd6;--unv:#5e564b;--unvbg:#ebe6dc;--op:#6f675c;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI","IBM Plex Sans",Roboto,"Helvetica Neue",Arial,sans-serif;
--serif:Charter,"Bitstream Charter","Iowan Old Style","Source Serif 4",Georgia,"Noto Serif",serif;
--mono:ui-monospace,"SF Mono","JetBrains Mono","IBM Plex Mono",Menlo,Consolas,"Liberation Mono",monospace}
*{box-sizing:border-box}html,body{margin:0}
body{font:14px/20px var(--sans);color:var(--ink);background:var(--bg);font-variant-numeric:tabular-nums}
a{color:var(--accent);text-underline-offset:2px}a:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}
header{padding:24px 32px 28px;border-bottom:1px solid var(--line);background:var(--paper)}
.brand{display:flex;align-items:baseline;gap:12px;margin:0 0 16px;font-size:13px;color:var(--muted)}
.brand b{font-size:16px;font-weight:600;color:var(--ink);letter-spacing:0}
h1{font-size:28px;line-height:36px;font-weight:500;margin:0;overflow-wrap:anywhere}
h2{font-size:13px;line-height:20px;font-weight:500;color:var(--ink2);margin:0 0 12px}
.sub{color:var(--muted);margin:4px 0 0;font-size:13px}
.top{display:flex;flex-wrap:wrap;gap:32px;align-items:flex-start;margin-top:24px}
.score{flex:0 0 240px}.score .lbl{display:block;font-size:13px;color:var(--ink2)}
.score b{display:block;font-size:48px;line-height:52px;font-weight:500;letter-spacing:-.02em;margin:4px 0}
.score .of{display:block;font-size:13px;color:var(--muted)}
.bar{display:flex;gap:2px;height:8px;margin:12px 0 0;background:var(--unvbg);border-radius:2px;overflow:hidden}
.bar i{display:block;height:100%}
.tally{flex:1 1 360px;min-width:0}
.counts{display:flex;flex-wrap:wrap;gap:8px 32px;margin:0;padding:0;list-style:none}
.counts li{display:flex;align-items:baseline;gap:8px;font-size:14px;color:var(--ink2);white-space:nowrap}
.counts li b{font-size:24px;line-height:32px;font-weight:500;color:var(--ink)}
.counts li.con b{color:var(--con)}.counts li.part b{color:var(--part)}.counts li.sup b{color:var(--sup)}.counts li.unv b{color:var(--unv)}
.headline{margin:16px 0 0;font-size:20px;line-height:28px;font-weight:600;color:var(--ink)}
.banner{margin:12px 0 0;padding:8px 12px;border-radius:8px;background:var(--partbg);color:var(--ink);font-size:13px;line-height:20px;max-width:1080px}
.counts li.op b{color:var(--op)}.tag{display:inline-block;padding:0 6px;margin-right:6px;border-radius:999px;background:var(--raised);border:1px solid var(--line);font:600 11px/18px var(--sans);color:var(--ink2)}
.why.fail b{color:var(--con)}blockquote .st.nlv{font-weight:500;color:var(--part);border-color:var(--part)}
.stats{margin:12px 0 0;font-size:13px;line-height:20px;color:var(--muted)}
.legend{font-size:12px;line-height:24px;color:var(--muted);margin-top:12px}.legend mark{padding:1px 4px}
main{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:32px;padding:32px 32px 48px;max-width:1600px}
section,aside{min-width:0}
.draft{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:32px 40px;overflow-wrap:anywhere}
.panel{position:sticky;top:0;max-height:100vh;overflow:auto;padding:0 4px 0 0}
.draft p{margin:0 0 16px;font:16px/28px var(--serif)}.draft p:last-child{margin-bottom:0}
.draft p.row{font:13px/24px var(--mono);color:var(--ink2);border-left:2px solid var(--line);padding-left:12px;margin-bottom:8px}
.draft .loc{display:none}
mark{background:none;color:inherit;padding:2px 1px;border-radius:2px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
mark.sup{background:var(--supbg)}mark.part{background:var(--partbg)}
mark.con{background:var(--conbg);text-decoration:underline wavy var(--con) 1px;text-underline-offset:4px;text-decoration-skip-ink:none}
mark.unv{background:var(--unvbg)}mark.op{color:var(--op);text-decoration:underline dotted var(--muted) 1px;text-underline-offset:4px}
mark a{color:inherit;text-decoration:none}
sup.n{font:500 10px/1 var(--mono);margin-left:2px;vertical-align:super}sup.n a{text-decoration:none}
sup.n.sup a{color:var(--sup)}sup.n.part a{color:var(--part)}sup.n.con a{color:var(--con)}sup.n.unv a{color:var(--unv)}
.card,blockquote,.fix,.warn{overflow-wrap:anywhere}
.card{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:0 0 12px}
.card.op{background:transparent}
.ch{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline}
.ch .no{font:500 13px/20px var(--mono);color:var(--unv)}
.verdict{font-size:14px;font-weight:600;color:var(--unv)}
.sup .no,.sup .verdict{color:var(--sup)}.part .no,.part .verdict{color:var(--part)}.con .no,.con .verdict{color:var(--con)}.op .no,.op .verdict{color:var(--op);font-weight:500}
.meta{color:var(--muted);font-size:12px;line-height:20px}
.claim{margin:8px 0 0;font:14px/22px var(--serif)}.why{font-size:13px;line-height:20px;margin:8px 0 0;color:var(--ink)}
table.nums{width:100%;border-collapse:collapse;font-size:12px;line-height:16px;margin:12px 0 4px}
table.nums td,table.nums th{border-bottom:1px solid var(--line2);padding:6px 8px 6px 0;text-align:left;vertical-align:top}
table.nums th{color:var(--muted);font-weight:500;border-bottom-color:var(--line)}
table.nums th,table.nums td.f,table.nums td.bad,table.nums td.ok,table.nums td:nth-child(4){white-space:nowrap}
table.nums td.f{font-family:var(--mono);color:var(--ink)}table.nums td.bad{color:var(--con)}table.nums td.ok{color:var(--sup)}
.warn{font-size:12px;line-height:18px;margin:8px 0 0;padding:8px 12px;border-radius:8px;background:var(--partbg);color:var(--ink)}
.warn b{font-weight:600;color:var(--part)}.warn.error{background:var(--conbg)}.warn.error b{color:var(--con)}
blockquote{margin:8px 0 0;padding:8px 12px;border-left:2px solid var(--line);background:var(--raised);border-radius:0 8px 8px 0;font:13px/20px var(--serif);color:var(--ink)}
blockquote.q{border-left-color:var(--ink)}
blockquote .src{display:block;color:var(--muted);font:11px/16px var(--sans);margin-top:4px;overflow-wrap:anywhere}
blockquote .src b{font-weight:600;color:var(--ink)}
blockquote .st{display:inline-block;padding:0 6px;margin-right:4px;border:1px solid var(--line);border-radius:999px;background:var(--paper);color:var(--ink);font-weight:700;white-space:nowrap}
.cite{margin-top:8px}
.fix{margin:12px 0 0;padding:12px;border:1px solid var(--line);border-radius:8px;font:14px/22px var(--serif)}
.fix>b{display:block;font:600 12px/16px var(--sans);color:var(--ink2);margin-bottom:4px}
.fix ins{text-decoration:underline 2px var(--sup);text-underline-offset:3px;color:var(--sup);font-weight:600;background:var(--supbg)}
.fix del{color:var(--con);text-decoration:line-through 1.5px}
.fix .src{display:block;color:var(--muted);font:11px/16px var(--sans);margin-top:8px}
footer{padding:0 32px 48px;color:var(--ink2);font-size:13px;line-height:20px;max-width:1080px}
footer p{margin:12px 0 0}footer h2{margin-top:0}
.srcs{font-size:12px;line-height:18px;color:var(--muted);padding-left:24px;margin:0}.srcs li{margin:0 0 4px;word-break:break-all}
@page{size:A4;margin:14mm 12mm 14mm 12mm}
@media print{body{background:#fff;font-size:10.5px;line-height:15px}
header{padding:0 0 12px;border-bottom:1px solid var(--line);background:none}.brand{margin-bottom:8px}
h1{font-size:18px;line-height:24px}.top{margin-top:12px;gap:24px}.score{flex-basis:160px}.score b{font-size:34px;line-height:38px}
.counts li{font-size:11px}.counts li b{font-size:16px;line-height:22px}.counts{gap:4px 16px}
main{display:block;padding:12px 0 0}.panel{position:static;max-height:none;overflow:visible;padding:0}
.draft{border:0;border-radius:0;padding:0 0 8px;margin-bottom:12px}.draft p{font-size:11px;line-height:18px;margin-bottom:8px}
.draft p.row{font-size:9.5px;line-height:15px}
.card{break-inside:auto;padding:8px 12px;margin-bottom:8px;border-radius:8px}.ch,.ch+.why{break-after:avoid;page-break-after:avoid}table.nums{font-size:9.5px;line-height:13px;margin-top:8px}table.nums td,table.nums th{padding:4px 8px 4px 0}.stats{font-size:10px;line-height:15px;margin-top:8px}.legend{font-size:10px;line-height:20px}blockquote,.fix,.warn,table.nums,.ch{break-inside:avoid;page-break-inside:avoid}
blockquote,.claim,.fix{font-size:10px;line-height:15px}.warn,.why{font-size:10px;line-height:14px}
h2{margin-top:12px;break-after:avoid;page-break-after:avoid}footer{padding:0}.verdict{font-size:11px}.ch .no{font-size:10px;line-height:16px}.meta{font-size:9.5px;line-height:14px}.fix>b{font-size:9.5px;line-height:14px}blockquote .src,.fix .src{font-size:9px;line-height:13px}a{color:inherit;text-decoration:none}}
@media (max-width:900px){main{grid-template-columns:minmax(0,1fr);gap:24px;padding:24px 16px 40px}.panel{position:static;max-height:none;overflow:visible}
header{padding:20px 16px 24px}footer{padding:0 16px 40px}.draft{padding:20px 16px}.card{padding:12px 16px}.score{flex-basis:100%}.top{gap:20px}
h1{font-size:22px;line-height:28px}.draft p{font-size:15px;line-height:26px}}
"""


_ACRONYMS = {"plfs": "PLFS", "pp": "pp", "pct": "%", "cpi": "CPI", "gdp": "GDP", "iip": "IIP"}


def _sentence(code: str) -> str:
    """'old_base' -> 'Old base', 'MISMATCH' -> 'Mismatch', 'plfs_status' -> 'PLFS status'."""
    words = str(code).replace("_", " ").lower().split()
    words = [_ACRONYMS.get(w, w) for w in words]
    out = " ".join(words)
    return out[:1].upper() + out[1:] if out and not out[0].isupper() else out


def _when(stamp) -> str:
    """'2026-11-01T14:34:12+00:00' -> '1 Nov 2026, 14:34 UTC'. Anything unparseable is shown as given."""
    import datetime as dt
    try:
        d = dt.datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return str(stamp)
    off = d.utcoffset()
    if off is None:
        zone = ""
    elif not off:
        zone = " UTC"
    else:
        mins = int(off.total_seconds() // 60)
        zone = f" UTC{'+' if mins >= 0 else '-'}{abs(mins) // 60:02d}:{abs(mins) % 60:02d}"
    return f"{d.day} {d:%b %Y}, {d:%H:%M}{zone}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _diff(old: str, new: str) -> str:
    e = html.escape
    a, b = re.findall(r"\S+|\s+", old), re.findall(r"\S+|\s+", new)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(e("".join(a[i1:i2])))
        else:
            if i2 > i1 and "".join(a[i1:i2]).strip():
                out.append(f"<del>{e(''.join(a[i1:i2]))}</del>")
            if j2 > j1:
                out.append(f"<ins>{e(''.join(b[j1:j2]))}</ins>")
    return "".join(out)


def _card(i: int, c: dict) -> str:
    e = html.escape
    cl = c["claim"]
    vc = VCLASS.get(c["verdict"], "unv")
    parts = [f'<div class="card {vc}" id="{e(cl["id"])}"><div class="ch"><span class="no">[{i}]</span>'
             f'<span class="verdict">{e(VLABEL.get(c["verdict"], c["verdict"]))}</span>'
             f'<span class="meta">{e(TYPE_LABEL.get(cl["type"], cl["type"]))} · {e(cl["location"])}'
             f'{" · confidence " + e(c["confidence"]) if c["confidence"] not in ("n/a", "") else ""}'
             f'{" · " + e(c["method"]) if c["method"] and c["method"] != "skipped" else ""}</span></div>']
    if cl.get("hedged"):
        parts.append(f'<div class="claim"><span class="tag">contains a factual claim</span> Opinion wording set aside; checked: “{e(cl["text"])}”</div>')
    elif cl["text"] != cl["sentence"]:
        parts.append(f'<div class="claim">Claim: “{e(cl["text"])}”</div>')
    if c.get("failed_part"):
        parts.append(f'<div class="why fail"><b>Failed part:</b> {e(c["failed_part"])}</div>')
    if c.get("rationale"):
        parts.append(f'<div class="why">{e(c["rationale"])}</div>')
    if c.get("numbers"):
        rows = []
        for f in c["numbers"]:
            off = f.get("official") or {}
            src = off.get("source") or {}
            link = f'<a href="{e(src["url"])}">{e((src.get("publisher") or "source").split(" (")[0])}</a>' if _safe_url(src.get("url")) else ""
            chk = str(f["verdict"])
            tone = {"MATCH": "ok", "MISMATCH": "bad"}.get(chk, "")
            rows.append(f'<tr><td class="f">{e(f["claimed"])}</td><td>{e(f.get("indicator_name") or "—")}</td>'
                        f'<td class="f">{e(str(f.get("period") or "—"))}</td><td class="{tone}">{e(_sentence(chk))}</td>'
                        f'<td><span class="f">{e(off.get("display", "—"))}</span> {link}</td></tr>')
        parts.append('<table class="nums"><tr><th>Number</th><th>Series</th><th>Period</th><th>Check</th><th>Official</th></tr>'
                     + "".join(rows) + "</table>")
    for w in c.get("warnings", [])[:6]:
        parts.append(f'<div class="warn {e(w["severity"])}"><b>{e(_sentence(w["code"]))}</b> · {e(w["message"])}</div>')
    quoted = {q["evidence_id"]: q["quote"] for q in c.get("quotes", [])}
    shown = 0
    for ev in sorted(c["evidence"], key=lambda x: (x["id"] not in quoted, x["kind"] != "datapoint")):
        if shown >= 3:
            break
        if c["verdict"] == "UNVERIFIED" and ev["kind"] != "datapoint" and ev["id"] not in quoted and shown >= 2:
            continue
        shown += 1
        text = quoted.get(ev["id"]) or ev.get("quote") or ev["snippet"]
        loc = f", page {ev['page']}" if ev.get("page") else ""
        asof = _asof(ev)
        url = ev.get("source_url") or ""
        link = f'<a href="{e(url)}">{e(url[:110])}</a>' if _safe_url(url) else e(url[:110])
        nlv = '<span class="st nlv" title="This source has only been tested on synthetic or rate-limited fixtures">unverified source</span>' if ev.get("not_live_verified") else ""
        parts.append(f'<blockquote class="{"q" if ev["id"] in quoted else ""}">“{e(text[:240])}{"…" if len(text) > 240 else ""}”'
                     f'<span class="src"><span class="st">{e(_stype(ev))}</span>{nlv} {e(ev["id"])} · {e(ev.get("publisher") or "")}{e(loc)}'
                     f'{" · <b>Data as of " + e(asof) + "</b>" if asof else ""}'
                     f'{" · dataset to cite, not used as evidence" if ev.get("kind") == "catalogue" else ""} · {link}</span></blockquote>')
    for cc in c.get("citation_checks", []):
        st = cc.get("status")
        txt = {"found": "found", "not_found": "does not exist", "unreachable": "could not be read",
               "unresolved": "not resolvable", "empty": "no text"}.get(st, st)
        sup = {"supports": "contains the claim", "partial": "partly matches", "number_missing": "does not contain the figure",
               "not_in_source": "does not mention the claim"}.get(cc.get("support"), "")
        parts.append(f'<div class="meta cite">Cited source {e(cc.get("citation", ""))}: <b>{e(txt)}</b>'
                     f'{" — " + e(sup) if sup else ""}{" · " + e(cc["title"][:120]) if cc.get("title") else ""}</div>')
    if c.get("suggested_fix"):
        parts.append(f'<div class="fix"><b>Suggested:</b>{_diff(cl["sentence"], c["suggested_fix"])}'
                     f'{"<span class=src>" + e(c["fix_source"]) + "</span>" if c.get("fix_source") else ""}</div>')
    parts.append("</div>")
    return "".join(parts)


def _draft(report: dict, numbering: dict) -> str:
    e = html.escape
    by_block: dict = {}
    for s in report["sentences"]:
        by_block.setdefault(s["block"], []).append(s)
    claims_by_sid: dict = {}
    for c in report["claims"]:
        claims_by_sid.setdefault(c["claim"]["sentence_id"], []).append(c)
    out = []
    for bi, b in enumerate(report["blocks"]):
        sents = by_block.get(bi, [])
        segs = []
        for s in sents:
            cs = claims_by_sid.get(s["id"], [])
            text = e(s["text"])
            if s.get("verdict") and cs:
                vc = VCLASS.get(s["verdict"], "unv")
                first = cs[0]["claim"]["id"]
                nums = "".join(f'<sup class="n {VCLASS.get(c["verdict"], "unv")}"><a href="#{e(c["claim"]["id"])}">{numbering[c["claim"]["id"]]}</a></sup>'
                               for c in cs)
                segs.append(f'<mark class="{vc}" title="{e(VLABEL.get(s["verdict"], ""))}"><a href="#{e(first)}">{text}</a></mark>{nums}')
            else:
                segs.append(text)
        is_row = b["location"].startswith("table")
        tag = "p class=\"row\"" if is_row else "p"
        out.append(f"<{tag}>{' '.join(segs) or e(b['text'])}</p>")
    return "".join(out)


def _cite_section(report: dict) -> str:
    rows = cite_rows(report)
    if not rows:
        return ""
    e = html.escape
    body = "".join(f"<tr><td>{i}</td><td>{e(str(r.get('location') or ''))}</td><td>{e(str(r.get('text') or ''))}</td>"
                   f"<td>{e(str(r.get('why') or ''))}</td></tr>" for i, r in enumerate(rows, 1))
    return (f'<section class="cite"><h2>Claims to cite ({len(rows)})</h2><p>TruthLens has no official dataset for these '
            "claims yet, or a source did not answer in this run. They are not wrong; give each one a source. "
            "<code>truthlens check FILE -f cite</code> writes this list as a spreadsheet (CSV).</p>"
            f"<table><thead><tr><th>#</th><th>Where</th><th>Claim</th><th>Why</th></tr></thead><tbody>{body}</tbody></table></section>")


def to_html(report: dict) -> str:
    e = html.escape
    s = report["summary"]
    v = s["verdicts"]
    sp = split_counts(s)
    checked = s.get("checked_claims", sp["supported"] + sp["partly"] + sp["contradicted"])
    n = s["checkable_claims"] or 1
    score = "—" if s["verified_score"] is None else f"{s['verified_score']:.0f}%"
    banners = "".join(f'<p class="banner">{e(b)}</p>' for b in banner_lines(report))
    det = banner_details(report)
    if det:
        banners += ('<details class="banner-details"><summary>Details</summary><ul>' +
                    "".join(f"<li>{e(d)}</li>" for d in det) + "</ul></details>")
    ml = mode_line(s)
    if ml:
        banners = f'<p class="mode">{e(ml)}</p>' + banners
    if s.get("statements") is not None:
        banners += (f'<p class="sub">{s["statements"]} statements · {s.get("checkable", 0)} checkable claims'
                    f'{" · " + str(s["not_checkable"]) + " not checkable facts (descriptions, procedures)" if s.get("not_checkable") else ""}</p>')
    numbering = {c["claim"]["id"]: i for i, c in enumerate(report["claims"], 1)}
    bar = "".join(f'<i style="width:{100 * v[k] / n:.2f}%;background:var(--{cls})"></i>'
                  for k, cls in (("SUPPORTED", "sup"), ("PARTLY SUPPORTED", "part"), ("CONTRADICTED", "con")) if v[k])
    cards = sorted(report["claims"], key=lambda c: (ORDER.get(c["verdict"], 9), numbering[c["claim"]["id"]]))
    cards_html = "".join(_card(numbering[c["claim"]["id"]], c) for c in cards)
    meta = report["meta"]
    status = meta.get("sources_status") or []
    used = ", ".join(f"{x['name']}{'' if x['configured'] else ' (off)'}" for x in status)
    srcs = "".join(f'<li>{e(x.get("publisher") or "")}: {e((x.get("title") or "")[:140])} '
                   f'{("(" + e(str(x["date"])) + ") ") if x.get("date") else ""}'
                   f'{("<a href=" + chr(34) + e(x["url"]) + chr(34) + ">" + e(x["url"]) + "</a>") if _safe_url(x.get("url")) else e(x.get("url") or "")}</li>'
                   for x in report["sources"])
    errs = meta.get("errors") or []
    err_html = f'<p>Source errors during this run: {e("; ".join(errs[:6]))}</p>' if errs else ""
    counts = "".join(f'<li class="{cls}"><b>{sp[k]}</b>{label}</li>' for k, cls, label in (
        ("contradicted", "con", "wrong (contradicted)"), ("partly", "part", "partly supported"),
        ("supported", "sup", "supported"), ("couldnt_check", "unv", "couldn't check"), ("skipped", "op", "skipped (opinion or not a checkable fact)")))
    stats = " · ".join([
        _plural(s.get("hedged_factual", 0), "opinion-worded sentence checked for its factual claim",
                "opinion-worded sentences checked for their factual claims"),
        f"{_plural(s['citations_checked'], 'citation', 'citations')} checked, {s['citations_not_found']} not found",
        f"{_plural(s['numbers_checked'], 'number', 'numbers')} checked",
        _plural(s["warnings"], "data-trap or citation warning", "data-trap and citation warnings"),
        _plural(s["suggested_fixes"], "suggested fix", "suggested fixes")])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TruthLens check: {e(report['input'])}</title><style>{CSS}</style></head>
<body><header>
<p class="brand"><b>TruthLens</b><span>Hallucination check</span></p>
<h1>{e(report['input'])}</h1>
<p class="sub">Generated {e(_when(report['generated_at']))} · TruthLens {e(report['version'])} ·
claims by {e(meta.get('extractor', '?'))} · judged by {e(meta.get('judge', '?'))}</p>
<p class="headline">{e(headline_text(s))}</p>{('<p class="sub">' + e(s["split_line"]) + '</p>') if s.get("split_line") else ""}{banners}
<div class="top"><div class="score"><span class="lbl">Verified score (of checked claims)</span><b>{score}</b>
<span class="of">{sp['supported']} of {checked} checked claims supported{(" · " + str(s.get("low_confidence_supported")) + " low-confidence") if s.get("low_confidence_supported") else ""} · {sp['couldnt_check']} couldn't check (not in the score) · {sp['skipped']} skipped</span><div class="bar">{bar}</div></div>
<div class="tally"><ul class="counts">{counts}</ul>
<p class="stats">{e(s.get("couldnt_check_note") or "“Couldn't check” means no source answered for that claim; it is not a finding that the claim is wrong.")}</p>
<p class="stats">{e(stats)}</p>
<div class="legend">Highlights: <mark class="sup">supported</mark> <mark class="part">partly supported</mark> <mark class="con">contradicted</mark>
<mark class="unv">couldn't check</mark> <mark class="op">opinion</mark> · plain text has no checkable claim. Select a sentence to jump to its evidence</div></div></div>
</header>
<main><section><h2>Draft</h2><div class="draft">{_draft(report, numbering)}</div></section>
<aside class="panel"><h2>Findings, evidence and fixes</h2>{cards_html or '<p>No checkable claims found.</p>'}</aside></main>
{_cite_section(report)}<footer><h2>Sources</h2><ol class="srcs">{srcs or '<li>none</li>'}</ol>
<p><b>How to read this.</b> SUPPORTED: the evidence states the claim. PARTLY SUPPORTED: part of it is supported, or a figure is close but not exact.
CONTRADICTED (wrong): the evidence says something different. COULDN'T CHECK (UNVERIFIED): no evidence good enough to decide; TruthLens fails closed and never guesses, and this is not a finding that the claim is wrong.
The verified score counts SUPPORTED claims among checked claims (supported, partly supported, contradicted; couldn't-check and opinions excluded), weighted by confidence: high 1.0, medium 0.6, low 0.3, so heuristic matches alone can never reach 100%. Numbers matched to an official series are checked
deterministically (TruthLens India statistics pack: curated official values, live MoSPI data, World Bank); other claims are judged only against the quoted evidence.
Confidence “low” means a lexical heuristic decided (no LLM key configured). Retrievers: {e(used)}.</p>{err_html}
<p>TruthLens is a checking aid, not an authority. Open the linked source before relying on a verdict.</p></footer>
</body></html>"""
