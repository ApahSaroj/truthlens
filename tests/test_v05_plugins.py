"""v0.5 plug-in sources (REST + MCP). Fully offline: fake servers on 127.0.0.1 in the test process only."""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests
import yaml

from conftest import REAL_SESSION_GET
from truthlens import plugins
from truthlens.config import Config
from truthlens.readers import read_text

FIX = Path(__file__).parent / "fixtures" / "plugins"


# ----------------------------------------------------------------------------------------------- fake REST server
class _H(BaseHTTPRequestHandler):
    log = []
    delay = 0.0

    def log_message(self, *a):
        pass

    def do_GET(self):
        _H.log.append({"path": self.path, "headers": dict(self.headers)})
        if _H.delay:
            time.sleep(_H.delay)
        if "/redirect" in self.path:
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()
            return
        ind = self.path.split("/indicator/")[1].split("?")[0] if "/indicator/" in self.path else "X"
        data = {"LIFE": [("2022", 71.7), ("2023", 72.0)], "FOREST": [("2023", 24.3)],
                "EVIL": [("2023", 50.0)]}.get(ind, [])
        body = [{"page": 1, "lastupdated": "2026-10-08"},
                [{"indicator": {"id": ind, "value": "<script>alert(1)</script> " + ind}, "country": {"value": "India"},
                  "date": d, "value": v} for d, v in data]]
        out = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


@pytest.fixture
def rest_server(monkeypatch):
    monkeypatch.setattr(requests.Session, "get", REAL_SESSION_GET)      # allow the local fake server only
    _H.log, _H.delay = [], 0.0
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _spec(base, **over):
    s = {
        "name": "fake-wdi", "kind": "rest", "publisher": "Fake Bank", "badge": "FakeBank", "trust": "official",
        "allow_local": True, "timeout": 3, "keywords": ["fakebank"],
        "request": {"url": base + "/v2/country/{place}/indicator/{indicator}?format=json&date={period}"},
        "places": {"india": "IND"}, "period": {"format": "year", "default": "2010:2030"},
        "indicators": [{"code": "LIFE", "label": "life expectancy at birth", "unit": "years", "keywords": ["life expectancy"]},
                       {"code": "FOREST", "label": "forest area share of land area", "unit": "%", "keywords": ["forest area"]}],
        "response": {"records": "$[1][*]", "value": "$.value", "period": "$.date", "place": "$.country.value",
                     "title": "$.indicator.value", "as_of_root": "$[0].lastupdated"},
        "test": {"claim": "Life expectancy at birth in India was 72.0 years in 2023."},
    }
    s.update(over)
    return s


def _install(tmp_path, monkeypatch, *specs):
    d = tmp_path / "sd"
    d.mkdir(exist_ok=True)
    for s in specs:
        (d / f"{s['name']}.yaml").write_text(yaml.safe_dump(s), encoding="utf-8")
    monkeypatch.setenv("TRUTHLENS_SOURCES_DIR", str(d))
    return d


def _pipe(tmp_path):
    from truthlens.pipeline import Pipeline
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path / "c", retrievers=["curated", "docs", "plugins"])
    cfg.llm_provider, cfg.search_provider = "none", "none"
    return Pipeline(cfg, llm=None)


def _claim(pipe, text):
    rep = pipe.run(read_text(text), "t")
    return rep, rep["claims"][0]


# ----------------------------------------------------------------------------------------------- config + jsonpath
def test_jsonpath_subset():
    from truthlens import jsonpath as jp
    doc = [{"lastupdated": "2026-10-08"}, [{"a": {"b": 1}}, {"a": {"b": 2}}]]
    assert jp.find(doc, "$[1][*].a.b") == [1, 2]
    assert jp.first(doc, "$[0].lastupdated") == "2026-10-08"
    assert jp.find({"v": {"X": {"IND": {"2023": 7}}}}, "$.v.*.IND") == [{"2023": 7}]
    assert jp.find({"k": [1]}, "$['k'][-1]") == [1]
    with pytest.raises(ValueError):
        jp.parse("$..deep")


def test_validate_rejects_literal_keys_and_bad_configs():
    good = _spec("https://api.example.org")
    assert plugins.validate(good) == []
    bad = dict(good, auth={"env": "X", "key": "sk-123"})
    assert any("never put the key" in e for e in plugins.validate(bad))
    assert any("name" in e for e in plugins.validate(dict(good, name="Bad Name")))
    assert any("trust" in e for e in plugins.validate(dict(good, trust="gospel")))
    assert any("JSONPath" in e or "jsonpath" in e.lower() for e in plugins.validate(dict(good, response={"value": "value"})))
    no_kw = dict(good, keywords=[], indicators=[{"code": "A", "label": "a"}])
    assert any("keywords" in e for e in plugins.validate(no_kw))
    assert any("server" in e for e in plugins.validate({"name": "m-x", "kind": "mcp", "keywords": ["x"],
                                                         "response": {"value": "$.v"}}))


def test_bundled_examples_are_valid_and_key_free():
    ex = plugins.examples()
    assert {"worldbank-wdi", "imf-datamapper"} <= set(ex)
    for name, text in ex.items():
        spec = yaml.safe_load(text)
        assert plugins.validate(spec) == [], name
        assert not spec.get("auth") and not spec.get("allow_local")


# ----------------------------------------------------------------------------------------------- REST end to end
def test_rest_plugin_supports_and_contradicts_like_an_official_table(tmp_path, monkeypatch, rest_server):
    _install(tmp_path, monkeypatch, _spec(rest_server))
    pipe = _pipe(tmp_path)
    rep, c = _claim(pipe, "Life expectancy at birth in India was 72.0 years in 2023.")
    assert "plugin:fake-wdi" in c["plan"]["data_matchers"]
    assert c["verdict"] == "SUPPORTED" and c["method"] == "live-official-data" and c["confidence"] == "high", c["rationale"]
    ev = c["evidence"][0]
    assert ev["source_type"] == "FakeBank" and ev["official"] is True and "2023" in ev["quote"]
    assert ev["data_as_of"].startswith("8 October 2026")
    _rep, c2 = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 75.0 years in 2023.")
    assert c2["verdict"] == "CONTRADICTED" and "72" in c2["rationale"]
    # polarity: the draft denies the official figure
    _rep, c3 = _claim(_pipe(tmp_path), "Life expectancy at birth in India was not 72.0 years in 2023.")
    assert c3["verdict"] == "CONTRADICTED"


def test_rest_plugin_routes_by_keywords_only(tmp_path, monkeypatch, rest_server):
    _install(tmp_path, monkeypatch, _spec(rest_server))
    _rep, c = _claim(_pipe(tmp_path), "Steel output was 140 million tonnes in 2023.")
    assert not any(m.startswith("plugin:") for m in c["plan"].get("data_matchers", []))
    assert not _H.log


def test_unit_gate_and_place_gate(tmp_path, monkeypatch, rest_server):
    _install(tmp_path, monkeypatch, _spec(rest_server))
    # a % figure is never judged against a 'years' series
    _rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 72.0% in 2023.")
    assert c["verdict"] != "SUPPORTED"
    # a state the config has no place code for: no request, fail closed
    _H.log.clear()
    _rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in Kerala was 75.0 years in 2023.")
    assert c["verdict"] == "UNVERIFIED" and not _H.log


def test_local_address_refused_without_allow_local_and_shown_in_banner(tmp_path, monkeypatch, rest_server):
    _install(tmp_path, monkeypatch, _spec(rest_server, allow_local=False))
    rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 72.0 years in 2023.")
    assert c["verdict"] == "UNVERIFIED" and not _H.log
    assert any(u["source"] == "plugin:fake-wdi" for u in rep["summary"]["unreachable_sources"]), rep["summary"]
    assert any("private or local" in e for e in rep["meta"]["errors"])


def test_redirect_to_metadata_address_is_not_followed(tmp_path, rest_server):
    # allow_local covers the configured local host only: its redirect to 169.254.169.254 is refused before any request
    spec = _spec(rest_server, request={"url": rest_server + "/redirect/{indicator}"}, allow_local=True)
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    src = plugins.PluginSource(cfg, spec)
    from truthlens import net
    with pytest.raises(net.FetchError, match="private or local"):
        src.fetch_doc({"indicator": "LIFE", "period": "2023", "place": "IND", "query": ""})
    assert len(_H.log) == 1 and "/redirect/" in _H.log[0]["path"]


def test_auth_key_from_env_never_stored(tmp_path, monkeypatch, rest_server):
    monkeypatch.setenv("FAKE_BANK_KEY", "sekret-abc-123456")
    _install(tmp_path, monkeypatch, _spec(rest_server, auth={"env": "FAKE_BANK_KEY", "in": "query", "name": "apikey"}))
    rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 72.0 years in 2023.")
    assert c["verdict"] == "SUPPORTED"
    assert any("apikey=sekret-abc-123456" in h["path"] for h in _H.log)
    blob = json.dumps(rep)
    assert "sekret-abc-123456" not in blob
    for f in (tmp_path / "c").rglob("*.json"):
        assert "sekret-abc-123456" not in f.read_text(encoding="utf-8")
    # header placement
    _H.log.clear()
    _install(tmp_path, monkeypatch, _spec(rest_server, auth={"env": "FAKE_BANK_KEY", "in": "header", "name": "X-Key"}))
    pipe = _pipe(tmp_path / "2")
    _claim(pipe, "Forest area was 24.3% of land area in India in 2023.")
    assert _H.log and _H.log[0]["headers"].get("X-Key") == "sekret-abc-123456"
    assert "sekret" not in _H.log[0]["path"]


def test_missing_key_skips_the_source(tmp_path, monkeypatch, rest_server):
    _install(tmp_path, monkeypatch, _spec(rest_server, auth={"env": "NOT_SET_KEY_XYZ", "in": "header", "name": "X-Key"}))
    _rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 72.0 years in 2023.")
    assert c["verdict"] == "UNVERIFIED" and not _H.log
    assert any("needs the key" in str(x.get("status")) for x in c["consulted"])


def test_trust_other_is_at_most_partly_low_and_never_contradicts(tmp_path, monkeypatch, rest_server):
    _install(tmp_path, monkeypatch, _spec(rest_server, trust="other"))
    _rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 72.0 years in 2023.")
    assert c["verdict"] == "PARTLY SUPPORTED" and c["confidence"] == "low", (c["verdict"], c["confidence"])
    assert c["evidence"][0]["official"] is False
    _rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 75.0 years in 2023.")
    assert c["verdict"] != "CONTRADICTED"


def test_per_source_timeout_fails_closed(tmp_path, monkeypatch, rest_server):
    _H.delay = 2.5
    _install(tmp_path, monkeypatch, _spec(rest_server, timeout=0.5))
    rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 72.0 years in 2023.")
    assert c["verdict"] == "UNVERIFIED"
    assert any(u["source"] == "plugin:fake-wdi" for u in rep["summary"]["unreachable_sources"])


def test_plugin_output_is_escaped_in_html(tmp_path, monkeypatch, rest_server):
    from truthlens.report_v2 import to_html
    _install(tmp_path, monkeypatch, _spec(rest_server))
    rep, c = _claim(_pipe(tmp_path), "Life expectancy at birth in India was 72.0 years in 2023.")
    assert "<script>" in json.dumps(rep["claims"][0]["evidence"])     # the raw title came back ...
    html = to_html(rep)
    assert "<script>alert(1)</script>" not in html                   # ... and is escaped on the page
    assert "&lt;script&gt;" in html


def test_broken_config_is_reported_not_loaded(tmp_path, monkeypatch, rest_server):
    d = _install(tmp_path, monkeypatch, _spec(rest_server))
    (d / "broken.yaml").write_text("name: Broken Name\nkind: rest\n", encoding="utf-8")
    pipe = _pipe(tmp_path)
    assert "plugin:fake-wdi" in pipe.matchers and len(pipe.plugin_problems) == 1
    assert any("plugin config" in e for e in pipe.errors())


def test_offline_skips_plugins(tmp_path, monkeypatch, rest_server):
    from truthlens.pipeline import Pipeline
    _install(tmp_path, monkeypatch, _spec(rest_server))
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path / "c", retrievers=["curated", "docs", "plugins"], offline=True)
    cfg.llm_provider, cfg.search_provider = "none", "none"
    rep = Pipeline(cfg, llm=None).run(read_text("Life expectancy at birth in India was 72.0 years in 2023."), "t")
    assert rep["claims"][0]["verdict"] == "UNVERIFIED" and not _H.log


# ----------------------------------------------------------------------------------------------- CLI
def test_cli_sources_list_add_test(tmp_path, monkeypatch, rest_server, capsys):
    from truthlens.cli import main
    d = tmp_path / "sd"
    monkeypatch.setenv("TRUTHLENS_SOURCES_DIR", str(d))
    f = tmp_path / "fake.yaml"
    f.write_text(yaml.safe_dump(_spec(rest_server)), encoding="utf-8")
    assert main(["sources", "add", str(f)]) == 0
    assert (d / "fake-wdi.yaml").exists()
    assert main(["sources", "add", "worldbank-wdi"]) == 0
    capsys.readouterr()
    assert main(["sources", "list"]) == 0
    out = capsys.readouterr().out
    assert "plugin:fake-wdi" in out and "plugin:worldbank-wdi" in out
    assert main(["sources", "test", "fake-wdi"]) == 0
    out = capsys.readouterr().out
    assert "MATCH" in out and "life expectancy" in out
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: x\n", encoding="utf-8")
    assert main(["sources", "add", str(bad)]) == 2


# ----------------------------------------------------------------------------------------------- MCP
def _mcp_spec(**over):
    s = {"name": "fake-mcp", "kind": "mcp", "publisher": "Fake Stats (MCP)", "badge": "FakeMCP", "trust": "official",
         "timeout": 30, "keywords": ["fakestat unemployment"],
         "server": {"command": [sys.executable, str(FIX / "fake_mcp_server.py"), "stdio"]},
         "tool": "get_indicator", "arguments": {"indicator": "{indicator}", "place": "{place}"},
         "indicators": [{"code": "unemployment", "label": "fakestat unemployment rate", "unit": "%",
                         "keywords": ["fakestat unemployment"]}],
         "response": {"records": "$.data[*]", "value": "$.value", "period": "$.year", "place": "$.country",
                      "title": "$.title", "as_of_root": "$.source.updated"},
         "source_url": "https://stats.example.org/{indicator}"}
    s.update(over)
    return s


import importlib.util  # noqa: E402
needs_mcp = pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="the optional 'mcp' package is not installed")


@needs_mcp
def test_mcp_stdio_plugin(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, _mcp_spec())
    _rep, c = _claim(_pipe(tmp_path), "The fakestat unemployment rate in India was 3.2% in 2023.")
    assert c["verdict"] == "SUPPORTED", (c["verdict"], c["rationale"], c["consulted"])
    assert c["evidence"][0]["source_type"] == "FakeMCP"
    assert c["evidence"][0]["source_url"] == "https://stats.example.org/unemployment"
    _rep, c = _claim(_pipe(tmp_path / "b"), "The fakestat unemployment rate in India was 4.0% in 2023.")
    assert c["verdict"] == "CONTRADICTED"


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def mcp_http():
    import subprocess
    port = _free_port()
    proc = subprocess.Popen([sys.executable, str(FIX / "fake_mcp_server.py"), "http", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import socket
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/mcp"
    proc.terminate()
    proc.wait(5)


@needs_mcp
def test_mcp_streamable_http_plugin_and_ssrf_guard(tmp_path, monkeypatch, mcp_http):
    spec = _mcp_spec(server={"url": mcp_http}, allow_local=True)
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    doc = plugins.call_mcp(spec, {"indicator": "unemployment", "place": "IND"}, 20)
    assert doc["data"][-1]["value"] == 3.2
    from truthlens.net import FetchError
    with pytest.raises(FetchError, match="private or local"):
        plugins.call_mcp(dict(spec, allow_local=False), {"indicator": "unemployment", "place": "IND"}, 5)
    with pytest.raises(FetchError):
        plugins.call_mcp(dict(spec, server={"url": "http://169.254.169.254/mcp"}, allow_local=False), {}, 5)
    _install(tmp_path, monkeypatch, spec)
    _rep, c = _claim(_pipe(tmp_path), "The fakestat unemployment rate in India was 3.2% in 2023.")
    assert c["verdict"] == "SUPPORTED", c["consulted"]


def test_max_offset_drops_projection_years():
    import datetime as dt
    y = dt.date.today().year
    spec = _spec("https://api.example.org", period={"format": "year", "default": "", "max_offset": -1},
                 response={"records": "$.r[*]", "value": "$.v", "period": "$.y"})
    rows, _m = plugins.to_rows(spec, {"r": [{"y": str(y - 1), "v": 1}, {"y": str(y), "v": 2}, {"y": str(y + 3), "v": 3}]},
                               "x")
    assert [r["year"] for r in rows] == [str(y - 1)]


@needs_mcp
def test_mcp_stdio_child_gets_only_its_own_key(monkeypatch):
    monkeypatch.setenv("SECRET_PROBE_XYZ", "should-not-leak")
    monkeypatch.setenv("FAKE_MCP_KEY", "k-123456789")
    spec = _mcp_spec(tool="env_probe")
    got = plugins.call_mcp(spec, {"name": "SECRET_PROBE_XYZ"}, 30)
    assert got["data"][0]["value"] == 0                      # other secrets are not passed to the server
    spec_auth = dict(spec, auth={"env": "FAKE_MCP_KEY", "in": "env"})
    assert plugins.validate(spec_auth) == []
    got = plugins.call_mcp(spec_auth, {"name": "FAKE_MCP_KEY"}, 30)
    assert got["data"][0]["value"] == 1
