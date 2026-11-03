"""The single-page web app: three states, the sample endpoint, re-rendering a JSON report, and XSS hygiene."""
import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import truthlens.api as api  # noqa: E402
from truthlens.webui import PAGE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "ONLINE", False)
    monkeypatch.setattr(api, "_PIPE", None)
    return TestClient(api.app)


def test_page_has_three_states_and_no_cdn(client):
    page = client.get("/").text
    for sid in ('id="start"', 'id="checking"', 'id="results"'):
        assert sid in page
    assert "Try the sample" in page and "Reading the document" in page and "Writing the report" in page
    assert "Copy corrected text" in page and "Download report" in page and "(HTML)" in page and "Accept fix" in page
    assert "prefers-reduced-motion" in page and ":focus-visible" in page
    # works offline: no external scripts, stylesheets or fonts
    assert "<script src" not in page and 'rel="stylesheet"' not in page and "fonts.googleapis" not in page
    assert all('href="data:' in ln for ln in page.splitlines() if "<link" in ln)
    assert "used for this one check only" in page and "never stored" in page


def test_page_never_puts_report_text_in_innerhtml():
    # the only innerHTML assignments are the constant SVG icon map
    lines = [ln for ln in PAGE.splitlines() if "innerHTML" in ln]
    assert lines and all("ICON[" in ln for ln in lines)
    assert "document.write" not in PAGE and "insertAdjacentHTML" not in PAGE and "eval(" not in PAGE


def test_sample_endpoint(client):
    r = client.get("/sample")
    assert r.status_code == 200
    assert r.content == (ROOT / "samples" / "sample_policy_note.docx").read_bytes()
    assert "wordprocessingml" in r.headers["content-type"]


def test_sample_runs_end_to_end(client):
    data = client.get("/sample").content
    r = client.post("/check/file?format=json", files={"file": ("sample_policy_note.docx", data)})
    j = r.json()
    assert r.status_code == 200 and j["summary"]["claims"] > 5 and j["sentences"] and j["blocks"]
    assert any(c["verdict"] == "CONTRADICTED" and c.get("suggested_fix") for c in j["claims"])


def test_render_endpoint_matches_static_report(client):
    rep = json.loads((ROOT / "samples" / "sample_report.json").read_text())
    r = client.post("/render?format=html", json=rep)
    from truthlens.report_v2 import to_html
    assert r.status_code == 200 and r.text == to_html(rep)
    assert client.post("/render", json={"hello": 1}).status_code == 422


def test_render_escapes_hostile_text(client):
    rep = json.loads((ROOT / "samples" / "sample_report.json").read_text())
    rep["input"] = "<script>alert(1)</script>.docx"
    rep["sentences"][1]["text"] = "<img src=x onerror=alert(1)>"
    r = client.post("/render?format=html", json=rep)
    assert "<script>alert(1)" not in r.text and "<img src=x" not in r.text


# ------------------------------------------------------------------------------------------- v0.3 UI
def test_page_v03_source_badges_freshness_and_keys(client):
    page = client.get("/").text
    for s in ("Copy citation", "Data as of ", "Superseded. ", "stype(e)", "Deep check asks: MoSPI, RBI",   # v0.5.3 live line
              "Untested (never answered our test network",
              'id="dgkey"', "datagovin_key", "low confidence", "Rajya Sabha", "Lok Sabha"):
        assert s in page, s
    assert page.count('type="password"') == 2      # AI key, data.gov.in key (v0.5.3: NDAP token removed)


def test_api_datagovin_key_per_check_only(monkeypatch):
    from truthlens.config import SECRET_ENV, Config
    for k in SECRET_ENV:
        monkeypatch.delenv(k, raising=False)
    seen = []

    class FakePipe:
        def __init__(self, cfg):
            seen.append({"dg": Config.secret("DATAGOVIN_API_KEY"), "llm": cfg.llm_provider})

        def run(self, blocks, name, meta=None, **kw):     # v0.5.2: mode=
            return {"tool": "TruthLens", "input": name, "summary": {}}

    import truthlens.pipeline as pl
    monkeypatch.setattr(pl, "Pipeline", FakePipe)
    c = TestClient(api.app)
    r = c.post("/check", json={"type": "text", "content": "x 5%", "datagovin_key": "abc123def456"})
    assert r.status_code == 200 and "abc123def456" not in r.text
    r = c.post("/check", json={"type": "text", "content": "x 5%"}, headers={"X-DataGovIn-Key": "hdr999key000"})
    assert r.status_code == 200
    r = c.post("/check/file?format=json", files={"file": ("a.txt", b"GDP grew 7.2%.")}, data={"datagovin_key": "form111key222"})
    assert r.status_code == 200
    assert [s["dg"] for s in seen] == ["abc123def456", "hdr999key000", "form111key222"]
    assert seen[0]["llm"] != "openai" and Config.secret("DATAGOVIN_API_KEY") is None
    assert c.post("/check", json={"type": "text", "content": "x", "datagovin_key": "bad key<>"}).status_code == 422


def test_report_shows_source_type_and_data_as_of():
    from truthlens.report_v2 import to_html, to_markdown
    rep = json.loads((ROOT / "samples" / "sample_report.json").read_text())
    c = next(c for c in rep["claims"] if c["evidence"])
    c["evidence"][0].update({"source_type": "Rajya Sabha", "as_of": "2025-03-17", "data_as_of": "",
                             "source_url": "javascript:alert(1)", "snippet": "<b>x</b>"})
    c["evidence"] = c["evidence"][:1]
    c["quotes"] = []
    html = to_html(rep)
    assert '<span class="st">Rajya Sabha</span>' in html and "Data as of 17 March 2025" in html
    assert 'href="javascript:' not in html and "<b>x</b>" not in html
    assert "[Rajya Sabha]" in to_markdown(rep) and "data as of 17 March 2025" in to_markdown(rep)


def test_data_as_of_labels():
    from truthlens.model import data_as_of
    assert data_as_of({"as_of": "retrieved 2026-11-01; latest period in API: 2023-24"}) == \
        "1 November 2026 (retrieved live; latest period 2023-24)"
    assert data_as_of({"as_of": "updated on 2026-04-10"}) == "10 April 2026 (dataset updated)"
    assert data_as_of({"as_of": None, "date": "2026-08-06"}) == "6 August 2026"
    assert data_as_of({}) == ""
