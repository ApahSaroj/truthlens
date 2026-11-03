"""v0.5 corrections (human in the loop) and the web app's Update now / Last updated / This verdict is wrong."""
import json
from pathlib import Path

import pytest

from fixture_http import FixtureHTTP, fixture_pipeline
from truthlens import corrections as C
from truthlens import net, sync
from truthlens.config import Config

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
import truthlens.api as api  # noqa: E402


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"])


def _cfg(tmp_path):
    return Config.load(path="/nonexistent", cache_dir=Path(tmp_path) / "c")


def test_add_pending_validates_and_stores_locally(tmp_path):
    cfg = _cfg(tmp_path)
    rec = C.add_pending({"claim_text": "CPI inflation was 4.6 per cent in 2024-25.", "reported_verdict": "CONTRADICTED",
                         "correct_verdict": "SUPPORTED", "note": "<script>alert(1)</script>",
                         "source_url": "https://mospi.gov.in/x"}, cfg)
    assert rec["status"] == "pending" and len(rec["id"]) == 12
    lines = C.pending_path(cfg).read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["note"] == "<script>alert(1)</script>"   # stored as data, as is
    for bad in ({"claim_text": "x y z", "correct_verdict": "TRUE"},
                {"claim_text": "", "correct_verdict": "SUPPORTED"},
                {"claim_text": "abc def", "correct_verdict": "SUPPORTED", "source_url": "javascript:alert(1)"},
                {"claim_text": "abc def", "correct_verdict": "SUPPORTED", "source_url": "file:///etc/passwd"},
                {"claim_text": "abc def", "correct_verdict": "SUPPORTED", "source_url": "https://u:p@example.org/"},
                {"claim_text": "abc def", "correct_verdict": "SUPPORTED", "reported_verdict": "SUPPORTED"}):
        with pytest.raises(ValueError):
            C.add_pending(bad, cfg)
    big = C.add_pending({"claim_text": "a" * 9000 + "\x00\x07", "correct_verdict": "UNVERIFIED"}, cfg)
    assert len(big["claim_text"]) == C.MAX_TEXT and "\x00" not in big["claim_text"]


def test_review_never_auto_accepts_and_writes_labelled_case(tmp_path):
    cfg = _cfg(tmp_path)
    pipe = fixture_pipeline(tmp_path / "p")
    C.add_pending({"claim_text": "CPI inflation was 4.6 per cent in 2024-25.", "reported_verdict": "CONTRADICTED",
                   "correct_verdict": "SUPPORTED", "source_url": "https://example.com/blog"}, cfg)
    C.add_pending({"claim_text": "Real GDP grew 9.9% in 2024-25.", "reported_verdict": "CONTRADICTED",
                   "correct_verdict": "SUPPORTED"}, cfg)
    seen = []
    # a reviewer who answers nothing: everything stays pending
    done = C.review(cfg, pipe, decide=lambda rec, now: "", out=seen.append)
    assert done == {"accepted": 0, "rejected": 0, "skipped": 2, "sources_added": 0}
    assert len(C.load_pending(cfg)) == 2 and not C.testset_path(cfg).exists()
    assert any("now: SUPPORTED" in x for x in seen)          # the claim was re-run and shown
    answers = iter(["accept", "reject"])
    asked = []
    done = C.review(cfg, pipe, decide=lambda rec, now: next(answers),
                    approve_source=lambda rec: asked.append(rec["source_url"]) or False, out=lambda s: None)
    assert done["accepted"] == 1 and done["rejected"] == 1 and done["sources_added"] == 0
    assert asked == ["https://example.com/blog"]               # non-allow-listed: the reviewer was asked, said no
    case = [json.loads(x) for x in C.testset_path(cfg).read_text().splitlines()]
    assert len(case) == 1 and case[0]["expected"] == "SUPPORTED" and case[0]["category"] == "user_correction"
    assert C.load_pending(cfg) == [] and len(C.reviewed_path(cfg).read_text().splitlines()) == 2
    # the evaluator runs on the accepted cases
    from truthlens.evaluate import evaluate_v2
    res = evaluate_v2(C.testset_path(cfg), pipe)
    assert res["n"] == 1 and res["correct"] == 1


def test_add_source_allow_list_and_approval(tmp_path):
    cfg = _cfg(tmp_path)
    with pytest.raises(PermissionError):
        C.add_source("https://example.com/page", cfg, approved=False, session=FixtureHTTP())
    with pytest.raises(Exception):      # approved, but the SSRF guard still applies
        C.add_source("http://169.254.169.254/latest/meta-data/", cfg, approved=True, session=FixtureHTTP())


def test_cli_eval_and_corrections(tmp_path, capsys, monkeypatch):
    from truthlens.cli import main
    assert main(["eval", "--user-corrections", "--offline"]) == 1      # nothing accepted yet
    assert main(["corrections", "list"]) == 0
    assert "0 pending" in capsys.readouterr().out
    C.add_pending({"claim_text": "CPI inflation was 4.6 per cent in 2024-25.", "correct_verdict": "SUPPORTED"})
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["corrections", "review", "--offline"]) == 1           # no terminal: nothing decided
    assert len(C.load_pending()) == 1
    C.accept(C.load_pending()[0])
    assert main(["eval", "--user-corrections", "--offline", "--no-llm"]) == 0
    assert "1/1 correct" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------- web
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "ONLINE", False)
    monkeypatch.setattr(api, "_PIPE", None)
    return TestClient(api.app)


def test_page_has_update_now_last_updated_and_wrong_button(client):
    page = client.get("/").text
    assert 'id="updnow"' in page and "Update now" in page and 'id="fresh"' in page and "Last updated " in page
    assert "This verdict is wrong" in page and "Nothing changes until a person accepts it" in page


def test_api_corrections_endpoint(client):
    r = client.post("/corrections", json={"claim_text": "<img src=x onerror=alert(1)> GDP grew 7%.",
                                           "reported_verdict": "SUPPORTED", "correct_verdict": "CONTRADICTED",
                                           "note": "<script>x</script>"})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert client.post("/corrections", json={"claim_text": "abc def", "correct_verdict": "MAYBE"}).status_code == 422
    assert client.post("/corrections", json={"claim_text": "abc def", "correct_verdict": "SUPPORTED",
                                             "source_url": "javascript:alert(1)"}).status_code == 422
    assert client.post("/corrections", json={"claim_text": "x" * 5000, "correct_verdict": "SUPPORTED"}).status_code == 422
    assert len(C.load_pending()) == 1


def test_api_sync_status_and_update_now(client, monkeypatch):
    d = client.get("/sync/status").json()
    assert d["stale"] is True and d["last_synced"] is None and d["offline"] is True
    assert client.post("/sync").status_code == 409                       # offline server: nothing to update
    monkeypatch.setattr(api, "ONLINE", True)
    started = []
    monkeypatch.setattr(sync, "run_in_background", lambda cfg=None, **kw: started.append(1) or len(started) == 1)
    assert client.post("/sync").status_code == 202
    assert client.post("/sync").status_code == 409                       # one at a time
