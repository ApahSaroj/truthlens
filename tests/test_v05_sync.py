"""v0.5 `truthlens sync` (self-updating knowledge). Offline: recorded responses via FixtureHTTP."""
import datetime as dt
import json
from pathlib import Path

import pytest

from fixture_http import FixtureHTTP
from truthlens import net, sync
from truthlens.config import Config


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"])


def _cfg(tmp_path, **kw):
    return Config.load(path="/nonexistent", cache_dir=Path(tmp_path) / "c", **kw)


def test_sync_records_state_log_and_whats_new(tmp_path):
    cfg = _cfg(tmp_path)
    s = FixtureHTTP()
    r1 = sync.run_sync(cfg, session=s, sources=["pib", "reports", "rbi", "mospi"], max_docs=1)
    assert {n: x["status"] for n, x in r1["sources"].items()} == {"pib": "ok", "reports": "ok", "rbi": "ok", "mospi": "ok"}
    # the first sync is a baseline, not "new"
    assert r1["new_total"] == 0 and "baseline" in r1["sources"]["pib"]["notes"][0]
    d = Path(sync.data_dir(cfg))
    st = json.loads((d / "sync_state.json").read_text())
    assert st["last_run"] and st["sources"]["rbi"]["last_synced"] and len(st["sources"]["pib"]["items"]) >= 10
    log = [json.loads(x) for x in (d / "sync_log.jsonl").read_text().splitlines()]
    assert len(log) == 1 and log[0]["sources"]["reports"]["items"] > 10
    # an item that was not there before is reported as new; a changed RBI rate supersedes the old one
    st["sources"]["pib"]["items"] = st["sources"]["pib"]["items"][1:]
    st["sources"]["rbi"]["items"] = [x if not x.startswith("Policy Repo Rate=") else "Policy Repo Rate=6.0"
                                     for x in st["sources"]["rbi"]["items"]]
    (d / "sync_state.json").write_text(json.dumps(st))
    r2 = sync.run_sync(cfg, session=s, sources=["pib", "rbi"], index_new=False)
    assert r2["sources"]["pib"]["new_count"] == 1
    assert any("Policy Repo Rate changed: 6.0% -> 5.5%" in x for x in r2["sources"]["rbi"]["new"])
    assert r2["superseded"] and r2["superseded"][0]["indicator"] == "rbi:Policy Repo Rate"
    text = sync.format_result(r2)
    assert "superseded" in text and "1 new" in text


def test_sync_source_failure_fails_closed_and_is_logged(tmp_path):
    cfg = _cfg(tmp_path)
    r = sync.run_sync(cfg, session=FixtureHTTP(), sources=["parliament"])
    assert r["sources"]["parliament"]["status"] == "error"
    st = sync.load_state(cfg)
    assert "last_run" not in st and st["sources"]["parliament"]["status"] == "error"
    assert sync.freshness(cfg)["stale"] is True


def test_offline_sync_does_nothing(tmp_path):
    r = sync.run_sync(_cfg(tmp_path, offline=True), session=FixtureHTTP())
    assert r["offline"] and not r["sources"]


def test_freshness_and_staleness_banner(tmp_path):
    cfg = _cfg(tmp_path)
    assert sync.freshness(cfg)["last_synced"] is None
    d = sync.data_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    old = (dt.datetime.now().astimezone() - dt.timedelta(days=9)).isoformat(timespec="seconds")
    (d / "sync_state.json").write_text(json.dumps({"last_run": old, "sources": {}}))
    f = sync.freshness(cfg)
    assert f["stale"] and "older than 7 days" in f["message"]
    from truthlens.report_v2 import banner_lines
    assert any("older than 7 days" in b for b in banner_lines({"summary": {"data_freshness": f}}))
    new = (dt.datetime.now().astimezone() - dt.timedelta(days=2)).isoformat(timespec="seconds")
    (d / "sync_state.json").write_text(json.dumps({"last_run": new, "sources": {}}))
    assert sync.freshness(cfg)["stale"] is False


def test_report_carries_data_freshness(tmp_path):
    from fixture_http import fixture_pipeline
    from truthlens.readers import read_text
    rep = fixture_pipeline(tmp_path).run(read_text("CPI inflation was 4.6 per cent in 2024-25."), "t")
    assert "data_freshness" in rep["summary"] and rep["summary"]["data_freshness"]["stale"] is True


def test_schedule_commands_are_printed_only():
    assert sync.schedule_command("daily", "unix").startswith("0 7 * * * ")
    assert sync.schedule_command("weekly", "unix").startswith("0 7 * * 1 ")
    w = sync.schedule_command("weekly", "windows")
    assert w.startswith("schtasks /Create /SC WEEKLY /D MON") and '"truthlens sync"' in w
    with pytest.raises(ValueError):
        sync.schedule_command("hourly")


def test_cli_sync_schedule_and_status(capsys, tmp_path):
    from truthlens.cli import main
    assert main(["sync", "--schedule", "daily", "--os", "windows"]) == 0
    out = capsys.readouterr().out
    assert "schtasks /Create /SC DAILY" in out and "does not install" in out
    assert main(["sync", "--status"]) == 0
    assert "never been updated" in capsys.readouterr().out


def test_plugin_sync_reports_new_periods_and_revisions(tmp_path, monkeypatch):
    import yaml
    from truthlens import plugins
    spec = {"name": "fake-sync", "kind": "rest", "trust": "official", "keywords": ["fakesync"],
            "request": {"url": "https://api.example.org/{indicator}"}, "indicators": [{"code": "A", "label": "alpha"}],
            "response": {"records": "$.rows[*]", "value": "$.v", "period": "$.y"}, "sync": {"requests": [{"indicator": "A"}]}}
    sd = tmp_path / "sd"
    sd.mkdir()
    (sd / "fake-sync.yaml").write_text(yaml.safe_dump(spec))
    monkeypatch.setenv("TRUTHLENS_SOURCES_DIR", str(sd))
    answers = [{"rows": [{"y": "2023", "v": 1.0}]}, {"rows": [{"y": "2023", "v": 1.5}, {"y": "2024", "v": 2.0}]}]
    monkeypatch.setattr(plugins.PluginSource, "fetch_doc", lambda self, v: (answers.pop(0), "https://example.org/A"))
    cfg = _cfg(tmp_path)
    r1 = sync.run_sync(cfg, sources=["plugins"])
    assert r1["sources"]["plugin:fake-sync"]["status"] == "ok"
    r2 = sync.run_sync(cfg, sources=["plugins"])
    new = r2["sources"]["plugin:fake-sync"]["new"]
    assert any("2024: 2.0 (new)" in x for x in new) and any("revised: 1.0 -> 1.5" in x for x in new)
    assert r2["superseded"][0]["kind"] == "revised"


def test_background_sync_runs_once(tmp_path, monkeypatch):
    import threading
    gate = threading.Event()
    calls = []

    def fake(cfg=None, **kw):
        calls.append(1)
        gate.wait(5)
        return {"finished": "now", "new_total": 3, "superseded": [], "sources": {}}
    monkeypatch.setattr(sync, "run_sync", fake)
    assert sync.run_in_background(_cfg(tmp_path)) is True
    assert sync.run_in_background(_cfg(tmp_path)) is False      # already running
    gate.set()
    for _ in range(50):
        if not sync.RUNNING["running"]:
            break
        import time
        time.sleep(0.05)
    assert sync.RUNNING["result"]["new_total"] == 3 and calls == [1]


def test_source_down_keeps_previous_state(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    s = FixtureHTTP()
    sync.run_sync(cfg, session=s, sources=["rbi"])
    before = sync.load_state(cfg)["sources"]["rbi"]["items"]
    from truthlens.retrievers import ministry
    monkeypatch.setattr(ministry, "parse_rbi_rates", lambda text: {"rates": {}, "fx": {}, "fx_as_of": None})
    r = sync.run_sync(cfg, session=s, sources=["rbi"])
    assert r["sources"]["rbi"]["status"] == "error"
    st = sync.load_state(cfg)["sources"]["rbi"]
    assert st["items"] == before and st["status"] == "error" and st["last_error"]


def test_rbi_empty_page_is_not_cached_over_good_data(tmp_path, monkeypatch):
    from truthlens.retrievers import ministry
    cfg = _cfg(tmp_path)
    src = ministry.RBISource(cfg, FixtureHTTP())
    good, _t = src._home()
    assert good["rates"]
    monkeypatch.setattr(ministry, "parse_rbi_rates", lambda text: {"rates": {}, "fx": {}, "fx_as_of": None})
    src2 = ministry.RBISource(cfg, FixtureHTTP())
    sync._force(src2)
    again, _t = src2._home()
    assert again["rates"] == good["rates"] and src2.errors
