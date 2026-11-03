"""Regenerates the sample reports from samples/sample_policy_note.docx with LIVE public sources and no keys:
MoSPI eSankhyiki API, World Bank, Crossref/OpenAlex, cited URLs, and an evidence index built by fetching
the official documents below (allow-listed domains). No LLM and no web search key: rule-based extraction
and the heuristic judge, so non-numeric verdicts carry 'low' confidence.

Outputs: samples/sample_report.{html,md,json}, samples/sample_corrected.docx, samples/sample_report.pdf (WeasyPrint)

`--from-json` re-renders only the HTML and PDF from the saved samples/sample_report.json (same findings, no network),
for when the report design changes but the check itself should stay comparable.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from truthlens.config import Config  # noqa: E402
from truthlens.docx_export import export_docx  # noqa: E402
from truthlens.pipeline import Pipeline  # noqa: E402
from truthlens.readers import read_file  # noqa: E402
from truthlens.report_v2 import to_html, to_json, to_markdown  # noqa: E402
from truthlens.retrievers.docs import DocFetcher, DocIndex, index_url  # noqa: E402

OFFICIAL_DOCS = [
    "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/aug/doc_9748_20260831_15530601.pdf",
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2299487",
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2243781",
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2196924",
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2278961",
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1685391",
]


def rerender():
    import json
    out = ROOT / "samples"
    rep = json.loads((out / "sample_report.json").read_text(encoding="utf-8"))
    (out / "sample_report.html").write_text(to_html(rep), encoding="utf-8")
    from weasyprint import HTML
    HTML(string=to_html(rep), base_url=str(out)).write_pdf(str(out / "sample_report.pdf"))
    print("re-rendered samples/sample_report.html and .pdf from sample_report.json")


def main():
    if "--from-json" in sys.argv:
        return rerender()
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="truthlens-sample-"))
    cfg = Config.load(path="/nonexistent", cache_dir=cache)
    cfg.llm_provider, cfg.search_provider = "none", "none"
    idx = DocIndex(cache / "index.sqlite")
    fetcher = DocFetcher(cfg)
    for u in OFFICIAL_DOCS:
        if not idx.has(u):
            r = index_url(idx, fetcher, u)
            print(f"indexed {r['passages']:4d} passages  {u}")
    pipe = Pipeline(cfg, llm=None, docs_index=idx)
    src = ROOT / "samples" / "sample_policy_note.docx"
    rep = pipe.run(read_file(src), src.name, {"source_path": src.name})
    out = ROOT / "samples"
    (out / "sample_report.html").write_text(to_html(rep), encoding="utf-8")
    (out / "sample_report.md").write_text(to_markdown(rep), encoding="utf-8")
    (out / "sample_report.json").write_text(to_json(rep), encoding="utf-8")
    export_docx(rep, str(out / "sample_corrected.docx"), str(src))
    try:
        from weasyprint import HTML
        HTML(string=to_html(rep), base_url=str(out)).write_pdf(str(out / "sample_report.pdf"))
    except ImportError:
        print("weasyprint not installed: skipped the PDF preview")
    s = rep["summary"]
    print(f"verified score {s['verified_score']}% · {s['verdicts']} · errors: {rep['meta'].get('errors')}")


if __name__ == "__main__":
    main()
