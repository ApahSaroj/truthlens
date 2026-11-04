"""Corrected-draft export (.docx) with Word comments on every contradicted or partly supported sentence.

For a .docx input the original file is copied and annotated in place: the sentence's runs get a Word
comment (python-docx >= 1.2 `Document.add_comment`) with the verdict, the evidence and the suggested
correction, and the suggested text is added after the sentence as a coloured, underlined insertion
"[suggested: ...]" (tracked-change-like; Word's own revision marks are not produced). For other inputs a
new document is written with the draft's paragraphs and the same annotations. If the installed
python-docx has no comment support, only the inline suggestions are written.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

ANNOTATE = ("CONTRADICTED", "PARTLY SUPPORTED", "DATED")


def _comment_text(c: dict) -> str:
    lines = [f"TruthLens: {c['verdict']} ({c['confidence']} confidence)."]
    if c.get("rationale"):
        lines.append(c["rationale"][:400])
    quoted = {q["evidence_id"] for q in c.get("quotes", [])}
    for ev in c.get("evidence", [])[:2]:
        if ev["kind"] == "datapoint" or ev["id"] in quoted:
            lines.append(f"Evidence: “{ev['snippet'][:280]}” ({ev.get('publisher') or ''}, {ev['source_url']})")
    for w in c.get("warnings", [])[:2]:
        lines.append(f"{w['code']}: {w['message'][:220]}")
    if c.get("suggested_fix"):
        lines.append(f"Suggested: {c['suggested_fix']}")
    if c.get("fix_source"):
        lines.append(c["fix_source"][:300])
    return "\n".join(lines)


def _add_suggestion(paragraph, text: str):
    from docx.shared import RGBColor
    run = paragraph.add_run(f" [suggested: {text}]")
    run.font.color.rgb = RGBColor(0x1F, 0x7A, 0x3A)
    run.font.underline = True
    return run


def _annotate_paragraph(doc, paragraph, items: list[dict], can_comment: bool) -> int:
    n = 0
    for c in items:
        runs = [r for r in paragraph.runs if r.text]
        sent = c["claim"]["sentence"]
        target = [r for r in runs if sent[:40] and sent[:40] in r.text] or runs
        if can_comment and target:
            try:
                doc.add_comment(target, text=_comment_text(c), author="TruthLens", initials="TL")
            except Exception:
                can_comment = False
        if c.get("suggested_fix"):
            _add_suggestion(paragraph, c["suggested_fix"])
        n += 1
    return n


def export_docx(report: dict, out_path: str, source_path: Optional[str] = None) -> dict:
    import docx

    by_loc: dict = {}
    for c in report["claims"]:
        if c["verdict"] in ANNOTATE:
            by_loc.setdefault(c["claim"]["location"], []).append(c)
    src = Path(source_path) if source_path else None
    count = 0
    if src and src.suffix.lower() == ".docx" and src.exists():
        doc = docx.Document(str(src))
        can_comment = hasattr(doc, "add_comment")
        from docx.oxml.ns import qn
        para_no = table_no = 0
        for child in doc.element.body.iterchildren():
            if child.tag == qn("w:p"):
                text = "".join(t.text or "" for t in child.iter(qn("w:t"))).strip()
                if not text:
                    continue
                para_no += 1
                items = by_loc.get(f"para {para_no}")
                if items:
                    from docx.text.paragraph import Paragraph
                    count += _annotate_paragraph(doc, Paragraph(child, doc), items, can_comment)
            elif child.tag == qn("w:tbl"):
                table_no += 1
                table = docx.table.Table(child, doc)
                for r_i, row in enumerate(table.rows, start=1):
                    items = by_loc.get(f"table {table_no}, row {r_i}")
                    if not items:
                        continue
                    # annotate the first cell that holds a number the finding refers to
                    cell_para = None
                    for cell in row.cells:
                        for f in (items[0].get("numbers") or []):
                            if f["claimed"] in cell.text and f["verdict"] in ("MISMATCH", "CLOSE"):
                                cell_para = cell.paragraphs[0]
                    cell_para = cell_para or row.cells[0].paragraphs[0]
                    for c in items:
                        if can_comment and cell_para.runs:
                            try:
                                doc.add_comment(cell_para.runs, text=_comment_text(c), author="TruthLens", initials="TL")
                            except Exception:
                                can_comment = False
                        bad = [f for f in (c.get("numbers") or []) if f["verdict"] in ("MISMATCH", "CLOSE") and f.get("official")]
                        if bad:
                            _add_suggestion(cell_para, "; ".join(f"{f['claimed']} → {f['official']['display']}" for f in bad))
                        count += 1
    else:
        doc = docx.Document()
        can_comment = hasattr(doc, "add_comment")
        doc.add_heading(f"TruthLens corrected draft: {report['input']}", 1)
        by_block: dict = {}
        for s in report["sentences"]:
            by_block.setdefault(s["block"], []).append(s)
        claims_by_sid: dict = {}
        for c in report["claims"]:
            claims_by_sid.setdefault(c["claim"]["sentence_id"], []).append(c)
        for bi, b in enumerate(report["blocks"]):
            p = doc.add_paragraph()
            for s in by_block.get(bi, []):
                run = p.add_run(s["text"] + " ")
                for c in claims_by_sid.get(s["id"], []):
                    if c["verdict"] not in ANNOTATE:
                        continue
                    if can_comment:
                        try:
                            doc.add_comment([run], text=_comment_text(c), author="TruthLens", initials="TL")
                        except Exception:
                            can_comment = False
                    if c.get("suggested_fix"):
                        _add_suggestion(p, c["suggested_fix"])
                    count += 1
    s = report["summary"]
    note = doc.add_paragraph()
    from .report_v2 import headline_text
    r = note.add_run(f"TruthLens {report['version']}: {headline_text(s)}; verified score {s['verified_score']}% of "
                     f"{s.get('checked_claims', s['checkable_claims'])} checked claims (couldn't-check not counted); "
                     f"{count} sentence(s) annotated with comments and [suggested: ...] insertions. Review each suggestion against its source.")
    r.italic = True
    doc.save(out_path)
    return {"annotated": count, "comments": can_comment, "path": out_path}
