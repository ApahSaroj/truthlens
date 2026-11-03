"""Readers, World Bank cache, reports, CLI, API and MCP tool."""
import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def docx_path(tmp_path):
    import docx
    d = docx.Document()
    d.add_heading("Policy note", 1)
    d.add_paragraph("India's real GDP grew by 7.8% in FY 2025-26.")
    t = d.add_table(rows=3, cols=3)
    for i, row in enumerate([["Indicator", "2024-25", "2025-26"],
                             ["Fiscal deficit (% of GDP)", "4.8%", "4.4%"],
                             ["CPI inflation", "4.6%", "2.1%"]]):
        for j, v in enumerate(row):
            t.cell(i, j).text = v
    d.add_paragraph("The unemployment rate was 4.9% in 2023-24.")
    p = tmp_path / "draft.docx"
    d.save(p)
    return p


def test_read_docx_paragraphs_and_tables(docx_path):
    from truthlens.readers import read_docx
    blocks = read_docx(docx_path)
    locs = [b.location for b in blocks]
    assert "table 1, row 2" in locs
    row = next(b for b in blocks if b.location == "table 1, row 2")
    assert "2024-25: 4.8%" in row.text


def test_docx_table_cells_are_checked(checker, docx_path):
    from truthlens.readers import read_docx
    fs = checker.check_blocks(read_docx(docx_path))
    table = [f for f in fs if f.location.startswith("table")]
    assert {f.verdict for f in table} == {"MATCH"}
    assert {f.period for f in table} == {"2024-25", "2025-26"}


def test_read_pdf(checker):
    from truthlens.readers import read_pdf
    fs = checker.check_blocks(read_pdf(FIX / "sample.pdf"))
    assert [f.verdict for f in fs] == ["MATCH", "MISMATCH"]
    assert fs[0].location == "page 1"


def test_read_markdown_table():
    from truthlens.readers import read_text
    blocks = read_text("# Title\n\n| Indicator | Value |\n|---|---|\n| CPI inflation 2024-25 | 4.6% |\n")
    assert any("4.6%" in b.text for b in blocks)


def test_unsupported_file(tmp_path):
    from truthlens.readers import ReaderError, read_file
    p = tmp_path / "x.xlsx"
    p.write_text("x")
    with pytest.raises(ReaderError):
        read_file(p)


def test_worldbank_cache_roundtrip(wb, tmp_path):
    v, meta = wb.value("NY.GDP.MKTP.KD.ZG", "2024")
    assert v == pytest.approx(7.0993, abs=1e-3)
    assert (wb.cache_dir / "IND_NY.GDP.MKTP.KD.ZG.json").exists()
    calls = len(wb.session.calls)
    wb.value("NY.GDP.MKTP.KD.ZG", "2023")
    assert len(wb.session.calls) == calls  # served from cache


def test_worldbank_failure_falls_back_to_stale_cache(wb):
    wb.series("SP.POP.TOTL")
    wb.ttl = -1  # force refresh
    class Broken:
        calls = []
        def get(self, *a, **k):
            raise ConnectionError("down")
    wb.session = Broken()
    assert wb.series("SP.POP.TOTL") is not None
    assert wb.errors


def test_reports(checker, docx_path):
    from truthlens.readers import read_docx
    from truthlens.report import build_report, to_html, to_json, to_markdown
    rep = build_report(checker.check_blocks(read_docx(docx_path)), "draft.docx")
    assert rep["summary"]["numbers_checked"] == 6
    assert rep["summary"]["verdicts"]["MISMATCH"] == 1
    html = to_html(rep)
    assert html.startswith("<!doctype html>") and "<script" not in html and "@media print" in html
    md = to_markdown(rep)
    assert "| # | Where |" in md and "MISMATCH" in md
    json.loads(to_json(rep))


def test_cli_html(tmp_path, docx_path, monkeypatch):
    from truthlens.cli import main
    out = tmp_path / "report.html"
    assert main(["check", str(docx_path), "--format", "html", "-o", str(out), "--offline"]) == 0
    assert "TruthLens India" in out.read_text()
    assert main(["check", str(docx_path), "--offline", "--strict", "-o", str(tmp_path / "r.md")]) == 1


def test_cli_text_json(capsys):
    from truthlens.cli import main
    assert main(["check", "--text", "WPI inflation was 2.3% in 2024-25.", "-f", "json", "--offline"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["findings"][0]["verdict"] == "MATCH"


def test_cli_missing_file():
    from truthlens.cli import main
    assert main(["check", "nope.docx", "--offline"]) == 2


def test_api(monkeypatch, docx_path):
    from fastapi.testclient import TestClient
    import truthlens.api as api
    monkeypatch.setattr(api, "ONLINE", False)
    c = TestClient(api.app)
    assert c.get("/health").json()["status"] == "healthy"
    r = c.post("/check", json={"type": "text", "content": "Real GDP grew 6.5% in 2024-25."})
    assert r.status_code == 200 and r.json()["findings"][0]["verdict"] == "MISMATCH"
    r = c.post("/check", json={"type": "text", "content": "Real GDP grew 7.8% in 2025-26.", "format": "html"})
    assert r.headers["content-type"].startswith("text/html")
    with open(docx_path, "rb") as fh:
        r = c.post("/check/file", files={"file": ("draft.docx", fh, "application/octet-stream")})
    assert r.status_code == 200 and r.json()["input"] == "draft.docx"
    assert c.post("/check", json={"type": "text", "content": "  "}).status_code == 422
    r = c.post("/check/file", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415


def test_root_app_keeps_health_and_legacy_analyze():
    from fastapi.testclient import TestClient
    import sys
    sys.path.insert(0, str(ROOT))
    from app import app
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    r = c.post("/analyze", json={"type": "text", "content": "GDP grew 7.8% in 2025-26."})
    assert r.status_code == 200 and r.json()["claims_found"] >= 1


def test_mcp_tool_function(monkeypatch, wb):
    import truthlens.mcp_server as m
    from truthlens.checker import Checker
    monkeypatch.setattr(m, "_checker", Checker(worldbank=wb))
    out = m.verify_india_stat("India's real GDP grew by 7.8% in FY 2025-26.")
    assert out["findings"][0]["verdict"] == "MATCH"


def test_legacy_source_evaluator_path_independent(monkeypatch, tmp_path):
    import sys
    sys.path.insert(0, str(ROOT))
    monkeypatch.chdir(tmp_path)  # used to break when run outside the repo root
    from services.source_evaluator import evaluate_source
    assert evaluate_source("worldbank.org")["category"] == "international"


def test_report_labels_and_timestamp():
    from truthlens.report_v2 import _plural, _sentence, _when
    assert _when("2026-11-01T14:34:12+00:00") == "1 Nov 2026, 14:34 UTC"
    assert _when("2026-11-01T20:04:12+05:30") == "1 Nov 2026, 20:04 UTC+05:30"
    assert _when("yesterday") == "yesterday"
    assert _sentence("plfs_status") == "PLFS status" and _sentence("MISMATCH") == "Mismatch"
    assert _plural(1, "opinion skipped", "opinions skipped") == "1 opinion skipped"
