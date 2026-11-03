"""Report builders: JSON, Markdown and a self-contained, printable one-page HTML."""
from __future__ import annotations

import datetime as dt
import html
import json
from collections import Counter
from typing import Optional

from . import __version__
from .checker import Finding

VERDICTS = ["MISMATCH", "CLOSE", "MATCH", "UNVERIFIED"]


def build_report(findings: list[Finding], source_name: str, meta: Optional[dict] = None) -> dict:
    counts = Counter(f.verdict for f in findings)
    trap_counts = Counter(w["code"] for f in findings for w in f.warnings if w["severity"] in ("warn", "error"))
    sources = {}
    for f in findings:
        if f.official:
            s = f.official["source"]
            sources[s["url"]] = s
    return {
        "tool": "TruthLens India",
        "version": __version__,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "input": source_name,
        "meta": meta or {},
        "summary": {
            "numbers_checked": len(findings),
            "verdicts": {v: counts.get(v, 0) for v in VERDICTS},
            "warnings": sum(1 for f in findings for w in f.warnings if w["severity"] in ("warn", "error")),
            "traps": dict(trap_counts.most_common()),
        },
        "findings": [f.to_dict() for f in findings],
        "sources": list(sources.values()),
    }


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, default=str)


def _md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def to_markdown(report: dict) -> str:
    s = report["summary"]
    v = s["verdicts"]
    lines = [
        f"# TruthLens India stat audit: {report['input']}",
        "",
        f"Generated {report['generated_at']} by TruthLens {report['version']}.",
        "",
        f"**{s['numbers_checked']} numbers checked:** {v['MISMATCH']} mismatch, {v['CLOSE']} close, "
        f"{v['MATCH']} match, {v['UNVERIFIED']} unverified. **{s['warnings']} data-trap warnings.**",
        "",
        "| # | Where | Claim | Verdict | Official value | Period | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, f in enumerate(report["findings"], 1):
        off = f.get("official") or {}
        src = off.get("source") or {}
        link = f"[{src.get('publisher', '')}]({src['url']})" if src.get("url") else ""
        lines.append(f"| {i} | {_md_escape(f['location'])} | {_md_escape(f['claimed'])} ({_md_escape(f.get('indicator_name') or 'not recognised')}) "
                     f"| **{f['verdict']}** | {_md_escape(off.get('display', ''))} | {_md_escape(off.get('period') or f.get('period') or '')} | {link} |")
    lines += ["", "## Details", ""]
    for i, f in enumerate(report["findings"], 1):
        lines.append(f"### {i}. {f['verdict']}: {f['claimed']} ({f['location']})")
        lines.append(f"> {f['sentence']}")
        lines.append("")
        lines.append(f"- {f['reason']}")
        off = f.get("official")
        if off:
            lines.append(f"- Series: {off.get('series')} (TruthLens id `{off.get('series_id')}`)")
            if off.get("vintage"):
                lines.append(f"- Vintage: {off['vintage']}")
        for wn in f["warnings"]:
            lines.append(f"- ⚠ **{wn['code']}** ({wn['severity']}): {wn['message']}")
        if f.get("citation"):
            lines.append(f"- Citation: {f['citation']}")
        lines.append("")
    lines += ["## Sources", ""]
    for src in report["sources"]:
        lines.append(f"- {src['publisher']}, “{src['title']}”, published {src['published']}. {src['url']} (accessed {src['accessed']})")
    lines += ["", "_Verdicts: MATCH = equals the official value at the precision written; CLOSE = within the indicator's tolerance; "
              "MISMATCH = beyond tolerance; UNVERIFIED = no confident match (TruthLens never guesses)._", ""]
    return "\n".join(lines)


CSS = """
:root{--ink:#1d1d1f;--muted:#5f6368;--line:#e3e3e3;--bg:#fafaf7;--mis:#b3261e;--close:#b26a00;--ok:#1e7d32;--unv:#5f6368}
*{box-sizing:border-box}body{font:14px/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);margin:0}
main{max-width:1060px;margin:0 auto;padding:28px 24px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 10px}
.sub{color:var(--muted);margin:0 0 18px}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:14px 0 6px}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.card b{display:block;font-size:22px}.card span{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.MISMATCH b{color:var(--mis)}.CLOSE b{color:var(--close)}.MATCH b{color:var(--ok)}.UNVERIFIED b{color:var(--unv)}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
th{background:#f3f3ef;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
tr:last-child td{border-bottom:0}\ntd{font-size:12.5px}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;color:#fff;white-space:nowrap}
.p-MISMATCH{background:var(--mis)}.p-CLOSE{background:var(--close)}.p-MATCH{background:var(--ok)}.p-UNVERIFIED{background:var(--unv)}
.sent{color:var(--muted);font-size:12.5px;margin-top:3px}
.warn{margin:6px 0 0;padding:6px 8px;border-left:3px solid var(--close);background:#fff8ec;font-size:12.5px}
.warn.error{border-color:var(--mis);background:#fdeeee}.warn.info{border-color:#9aa0a6;background:#f4f4f4}
.cite{margin-top:6px;font-size:12px;color:var(--muted)}
.cite code{font-size:11.5px;background:#f3f3ef;padding:1px 4px;border-radius:4px}
a{color:#0b57d0}
.foot{color:var(--muted);font-size:12px;margin-top:22px}
.traps{display:flex;flex-wrap:wrap;gap:6px}.traps span{background:#fff;border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:12px}
.item{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:0 0 8px}
.ih{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}.muted{color:var(--muted);font-size:12.5px}
.reason{margin-top:4px}.off{margin-top:4px;font-size:13px}
.cite span{font-weight:600;color:var(--ink)}.wn{color:var(--close);font-size:11px;font-weight:700}
.srcs{font-size:12px;color:var(--muted);padding-left:18px}.srcs a{word-break:break-all}
@page{size:A4;margin:12mm}
@media print{body{background:#fff;font-size:11px}main{padding:0;max-width:none}.item,.card,tr{break-inside:avoid}
a{color:inherit;text-decoration:none}h2{margin:14px 0 6px}.cite{font-size:10px}th,td{padding:4px 6px}td{font-size:10.5px}}
@media (max-width:720px){.cards{grid-template-columns:repeat(2,1fr)}}
"""


TRAP_NAMES = {
    "unit_scale": "lakh/crore vs million", "fy_vs_cy": "FY vs calendar year", "plfs_year": "PLFS year",
    "budget_stage": "BE vs RE vs Actuals", "plfs_status": "usual status vs CWS", "old_base": "old base series",
    "vintage": "revised estimate", "wrong_year": "wrong year", "registrations_vs_beneficiaries": "registrations vs beneficiaries",
    "pct_vs_pp": "% vs percentage points", "survey_vs_admin": "survey vs admin data", "period_missing": "no period",
    "generic_inflation": "unqualified ‘inflation’", "secondary_source": "secondary source", "not_census": "not a census count",
    "source_note": "source note",
}


def _needs_attention(f: dict) -> bool:
    return f["verdict"] in ("MISMATCH", "CLOSE") or any(w["severity"] in ("warn", "error") for w in f["warnings"])


def to_html(report: dict) -> str:
    e = html.escape
    s = report["summary"]
    v = s["verdicts"]
    findings = report["findings"]
    order = {"MISMATCH": 0, "CLOSE": 1, "UNVERIFIED": 2, "MATCH": 3}
    attention = sorted([(i, f) for i, f in enumerate(findings, 1) if _needs_attention(f)],
                       key=lambda x: (order[x[1]["verdict"]], x[0]))
    cards = []
    for i, f in attention:
        off = f.get("official") or {}
        warns = "".join(
            f'<div class="warn {e(w["severity"])}"><b>{e(TRAP_NAMES.get(w["code"], w["code"]))}:</b> {e(w["message"])}</div>'
            for w in f["warnings"])
        official = (f'<div class="off">Official: <b>{e(off.get("display", ""))}</b> · {e(str(off.get("period") or ""))}'
                    f'{(" · " + e(off["stage"])) if off.get("stage") else ""}'
                    f'{(" · base " + e(off["base"])) if off.get("base") else ""}'
                    f' · <a href="{e(off["source"]["url"])}">{e(off["source"]["publisher"])}</a></div>') if off else ""
        cite = f'<div class="cite"><span>Paste-ready citation</span> {e(f["citation"])}</div>' if f.get("citation") else ""
        cards.append(
            f'<div class="item"><div class="ih"><span class="pill p-{e(f["verdict"])}">{e(f["verdict"])}</span>'
            f'<b>#{i} {e(f["claimed"])}</b> <span class="muted">{e(f.get("indicator_name") or "not recognised")} · {e(f["location"])}</span></div>'
            f'<div class="sent">“{e(f["sentence"])}”</div><div class="reason">{e(f["reason"])}</div>{official}{warns}{cite}</div>')
    rows = []
    for i, f in enumerate(findings, 1):
        off = f.get("official") or {}
        src = off.get("source") or {}
        link = f'<a href="{e(src["url"])}">{e(src.get("publisher", "source").split(" (")[0])}</a>' if src.get("url") else "—"
        nw = sum(1 for w in f["warnings"] if w["severity"] in ("warn", "error"))
        wn = ' <span class="wn">⚠' + str(nw) + '</span>' if nw else ''
        rows.append(
            f"<tr><td>{i}</td><td>{e(f['location'])}</td><td><b>{e(f['claimed'])}</b></td>"
            f"<td>{e(f.get('indicator_name') or '—')}</td><td>{e(str(f.get('period') or '—'))}</td>"
            f"<td><span class=\"pill p-{e(f['verdict'])}\">{e(f['verdict'])}</span>{wn}</td>"
            f"<td>{e(off.get('display', '—'))}</td><td>{link}</td></tr>")
    traps = "".join(f"<span>{e(TRAP_NAMES.get(k, k))} × {n}</span>" for k, n in s["traps"].items()) or "<span>none</span>"
    srcs = "".join(f"<li>{e(x['publisher'])}, “{e(x['title'])}”, published {e(str(x['published']))}. "
                   f"<a href=\"{e(x['url'])}\">{e(x['url'])}</a> (accessed {e(str(x['accessed']))})</li>" for x in report["sources"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TruthLens stat audit: {e(report['input'])}</title><style>{CSS}</style></head>
<body><main>
<h1>TruthLens India · stat audit</h1>
<p class="sub">{e(report['input'])} · generated {e(report['generated_at'])} · TruthLens {e(report['version'])}</p>
<div class="cards">
<div class="card"><span>Numbers checked</span><b>{s['numbers_checked']}</b></div>
<div class="card MISMATCH"><span>Mismatch</span><b>{v['MISMATCH']}</b></div>
<div class="card CLOSE"><span>Close</span><b>{v['CLOSE']}</b></div>
<div class="card MATCH"><span>Match</span><b>{v['MATCH']}</b></div>
<div class="card UNVERIFIED"><span>Unverified</span><b>{v['UNVERIFIED']}</b></div>
</div>
<h2>Data traps found ({s['warnings']})</h2><div class="traps">{traps}</div>
<h2>Needs attention ({len(attention)})</h2>
{''.join(cards) or '<p class="muted">Nothing to fix.</p>'}
<h2>All numbers</h2>
<table><thead><tr><th>#</th><th>Where</th><th>Claim</th><th>Indicator</th><th>Period</th><th>Verdict</th><th>Official</th><th>Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<h2>Sources</h2><ol class="srcs">{srcs}</ol>
<p class="foot">MATCH = equals the official value at the precision written · CLOSE = within the indicator's tolerance (rounding, earlier estimate) ·
MISMATCH = beyond tolerance · UNVERIFIED = no confident match to an official series and period; TruthLens never guesses.
Official values come from a curated dataset in which every figure was read from the linked official document; World Bank WDI values, when used, are marked as a secondary source.</p>
</main></body></html>"""
