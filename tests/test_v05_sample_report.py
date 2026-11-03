"""v0.5: launchers and the web app's /sample-report open the v0.5 sample first, with the v0.4.1 sample as fallback."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_launchers_prefer_v05_sample_with_v041_fallback():
    sh = (ROOT / "start_truthlens.sh").read_text()
    bat = (ROOT / "start_truthlens.bat").read_bytes().decode()
    for t in (sh, bat):
        assert "sample_report_v05.html" in t and "sample_report_v041.html" in t
        assert t.index("sample_report_v05.html") < t.index("sample_report_v041.html")
    assert '[ -f "$SAMPLE" ] || SAMPLE=' in sh
    assert 'if not exist "%SAMPLE%" set "SAMPLE=' in bat
    assert "\r\n" in bat


def test_v05_sample_is_bundled():
    assert (ROOT / "samples" / "sample_report_v05.html").is_file()
    assert (ROOT / "samples" / "sample_report_v05.json").is_file()


def _client(monkeypatch, tmp_path, files):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import truthlens.api as api
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    monkeypatch.setattr(api, "SAMPLE_REPORT_DIR", tmp_path)
    monkeypatch.setattr(api, "ONLINE", False)
    return TestClient(api.app)


def test_sample_report_route_serves_v05_first(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, {"sample_report_v05.html": "<p>TruthLens v05</p>",
                                       "sample_report_v041.html": "<p>TruthLens v041</p>"})
    r = c.get("/sample-report")
    assert r.status_code == 200 and "v05" in r.text


def test_sample_report_route_falls_back_to_v041(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, {"sample_report_v041.html": "<p>TruthLens v041</p>"})
    r = c.get("/sample-report")
    assert r.status_code == 200 and "v041" in r.text


def test_sample_report_route_404_when_none_bundled(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, {})
    assert c.get("/sample-report").status_code == 404


def test_real_route_serves_bundled_v05(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import truthlens.api as api
    monkeypatch.setattr(api, "ONLINE", False)
    r = TestClient(api.app).get("/sample-report")
    want = (ROOT / "samples" / "sample_report_v05.html").read_text(encoding="utf-8")
    assert r.status_code == 200 and r.text == want
