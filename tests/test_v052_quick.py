"""v0.5.2: Quick mode (no network), Deep re-run of unchecked claims, the persistent live-answer cache, claim selection
and routing, honest couldn't-check reasons, bundled state data, and the hosted-server limits."""
import socket
import time
from pathlib import Path

import pytest
import requests

from truthlens.readers import read_file, read_text

ROOT = Path(__file__).resolve().parent.parent
LONG = ROOT / "tests" / "fixtures" / "long_policy_draft.docx"


@pytest.fixture
def no_sockets(monkeypatch):
    """Any attempt to open a connection or resolve a name is recorded and refused."""
    seen = []

    def connect(self, addr):
        seen.append(("connect", addr))
        raise OSError("network blocked by test")

    def gai(*a, **k):
        seen.append(("dns", a[0] if a else None))
        raise OSError("dns blocked by test")
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", gai)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (seen.append(("create", a[0])), (_ for _ in ()).throw(OSError("blocked")))[1])
    return seen


def _real_pipeline(**over):
    from truthlens.config import Config
    from truthlens.pipeline import Pipeline
    cfg = Config.load(offline=False)
    for k, v in over.items():
        setattr(cfg, k, v)
    return Pipeline(cfg, llm=None)       # real requests sessions: Quick mode must not use them


# ------------------------------------------------------------------------------------------------ Quick mode
def test_quick_mode_makes_zero_network_calls(no_sockets, monkeypatch):
    sent = []
    orig = requests.Session.send
    monkeypatch.setattr(requests.Session, "send", lambda self, req, **kw: (sent.append(req.url), orig(self, req, **kw))[1])
    pipe = _real_pipeline()
    t0 = time.monotonic()
    rep = pipe.run(read_file(LONG), "long", mode="quick")
    dt = time.monotonic() - t0
    assert no_sockets == [] and sent == []
    s = rep["summary"]
    assert s["mode"] == "quick" and rep["meta"]["live_checks"]["mode"] == "quick"
    assert s["claims"] == 51 and dt < 10
    assert s["couldnt_check_reasons"]["quick"]["claims"] > 0


def test_quick_mode_never_supported_without_evidence(no_sockets):
    rep = _real_pipeline().run(read_file(LONG), "long", mode="quick")
    for c in rep["claims"]:
        if c["verdict"] == "SUPPORTED":
            assert c["evidence"], c["claim"]["text"]
        if c["verdict"] == "UNVERIFIED" and c["unchecked_reason"] == "quick":
            assert "Not checked in Quick mode" in c["rationale"]


def test_quick_mode_with_fixture_sessions_sends_nothing(tmp_path):
    from fixture_http import FixtureHTTP, fixture_pipeline
    http = FixtureHTTP()
    pipe = fixture_pipeline(tmp_path, session=http, preload_docs=False)
    rep = pipe.run(read_text("The repo rate is 5.5%. Lok Sabha was told 15 crore households have tap water. "
                             "A 2019 study by Kumar et al. found groundwater fell 30% (doi:10.1234/abcd.5678)."), "t",
                   mode="quick")
    assert http.calls == []
    assert all(c["verdict"] != "SUPPORTED" or c["evidence"] for c in rep["claims"])


# ------------------------------------------------------------------------------------------------ Deep re-run
def test_deep_rerun_evaluates_only_claims_quick_left_unchecked(tmp_path, monkeypatch):
    from fixture_http import fixture_pipeline
    pipe = fixture_pipeline(tmp_path)
    blocks = read_file(LONG)
    state = {}
    quick = pipe.run(blocks, "long", mode="quick", state_out=state)
    unchecked = {c["claim"]["id"] for c in quick["claims"] if c.get("unchecked_reason") == "quick"}
    assert unchecked
    evaluated = []
    orig = pipe.engine.evaluate

    def spy(claim, findings):
        evaluated.append(claim.id)
        return orig(claim, findings)
    monkeypatch.setattr(pipe.engine, "evaluate", spy)
    deep = pipe.run(blocks, "long", mode="deep", prior=state)
    dedup_skipped = len(unchecked) - len(set(evaluated))
    assert set(evaluated) <= unchecked and len(evaluated) >= len(unchecked) - dedup_skipped
    assert deep["summary"]["mode"] == "deep" and deep["meta"]["deep_rerun_of_unchecked"] == len(evaluated)
    before = {c["claim"]["id"]: c["verdict"] for c in quick["claims"]}
    after = {c["claim"]["id"]: c["verdict"] for c in deep["claims"]}
    assert before.keys() == after.keys()
    for cid in before:
        if cid not in unchecked:
            assert after[cid] == before[cid]
    assert deep["summary"]["couldnt_check_reasons"]["quick"]["claims"] == 0


# ------------------------------------------------------------------------------------------------ live cache
class _FakeSession(requests.Session):
    """A real requests.Session whose transport is a counter (no network)."""

    def __init__(self, status=200, body=b'{"ok": 1}'):
        super().__init__()
        self.status, self.body, self.sent = status, body, 0

    def get(self, url, **kw):
        self.sent += 1
        r = requests.Response()
        r.status_code = self.status
        r._content = self.body
        r._content_consumed = True
        r.headers["content-type"] = "application/json"
        r.url = url
        return r


@pytest.fixture
def public_dns(monkeypatch, tmp_path):
    from truthlens import net
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"])
    monkeypatch.setenv("TRUTHLENS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("TRUTHLENS_LIVE_CACHE", raising=False)


def _guarded_get(sess, url, mode="deep", headers=None):
    from truthlens import net, runguard
    g = runguard.RunGuard(budget=30, mode=mode)
    tok = runguard.CURRENT.set(g)
    try:
        return net.safe_get(sess, url, 5, headers)
    finally:
        runguard.CURRENT.reset(tok)


def test_live_cache_stores_answers_and_serves_quick_mode(public_dns):
    from truthlens import net
    s = _FakeSession()
    url = "https://api.example.org/data?q=tap+water"
    assert _guarded_get(s, url).content == b'{"ok": 1}' and s.sent == 1
    assert _guarded_get(s, url).content == b'{"ok": 1}' and s.sent == 1        # second Deep check: from disk
    r = _guarded_get(s, url, mode="quick")                                       # Quick mode reads the cache too
    assert r.content == b'{"ok": 1}' and r.headers.get("x-truthlens-cache") == "hit" and s.sent == 1
    with pytest.raises(net.QuickModeSkip):
        _guarded_get(s, "https://api.example.org/data?q=other", mode="quick")   # not cached: never sent
    assert s.sent == 1


def test_live_cache_never_caches_failures(public_dns):
    s = _FakeSession(status=503, body=b"busy")
    url = "https://api.example.org/x"
    _guarded_get(s, url)
    s2 = _FakeSession(status=503)
    _guarded_get(s2, url)
    assert s2.sent == 1                       # the 503 was not stored as an answer
    s3 = _FakeSession(status=404, body=b"no")
    _guarded_get(s3, "https://api.example.org/y")
    s4 = _FakeSession(status=404)
    _guarded_get(s4, "https://api.example.org/y")
    assert s4.sent == 1


def test_live_cache_skips_credentials_and_keeps_no_plain_text(public_dns, tmp_path):
    from truthlens import livecache
    assert not livecache.cacheable_request("GET", "https://api.x.org/a?api_key=SECRET", {})
    assert not livecache.cacheable_request("GET", "https://api.x.org/a", {"Authorization": "Bearer x"})
    assert not livecache.cacheable_request("POST", "https://api.anthropic.com/v1/messages", {})
    assert livecache.cacheable_request("GET", "https://api.openalex.org/works?search=groundwater+karnataka", {})
    s = _FakeSession()
    _guarded_get(s, "https://api.example.org/q?search=Karnataka+rural+tap+connections+2024")
    files = list((tmp_path / "data" / "live_cache").rglob("*.json"))
    assert len(files) == 1
    assert "Karnataka" not in files[0].read_text() and "search=" not in files[0].read_text()
    s2 = _FakeSession()
    _guarded_get(s2, "https://api.example.org/q?token=abc")
    assert len(list((tmp_path / "data" / "live_cache").rglob("*.json"))) == 1


def test_live_cache_ttl_and_size_cap(tmp_path):
    from truthlens.livecache import LiveCache
    lc = LiveCache(tmp_path, ttl_days=1, max_mb=0.001)
    assert lc.put("h", ("GET", "u1"), 200, b"x" * 600, "text/plain", "u1")
    assert lc.get("h", ("GET", "u1"))["status"] == 200
    assert not lc.put("h", ("GET", "bad"), 500, b"err", "text/plain", "bad")
    assert lc.get("h", ("GET", "bad")) is None
    old = LiveCache(tmp_path, ttl_days=0.0000001)
    time.sleep(0.05)
    assert old.get("h", ("GET", "u1")) is None and old.get("h", ("GET", "u1"), allow_stale=True) is not None
    lc.put("h", ("GET", "u2"), 200, b"y" * 600, "text/plain", "u2")
    st = lc.prune()
    assert st["bytes"] <= lc.max_bytes


def test_disk_cache_does_not_store_query_text(tmp_path):
    from truthlens.net import DiskCache
    c = DiskCache(tmp_path, "ns")
    c.set("search:Karnataka district secret phrase", {"v": 1})
    txt = next((tmp_path / "ns").glob("*.json")).read_text()
    assert "secret phrase" not in txt and c.get("search:Karnataka district secret phrase") == {"v": 1}


# ------------------------------------------------------------------------------------------------ claim selection
def test_descriptive_text_is_not_a_claim_and_repeats_are_checked_once(tmp_path):
    from fixture_http import fixture_pipeline
    pipe = fixture_pipeline(tmp_path)
    text = ("The Rural Drinking Water and Sanitation Department shall prepare village water security plans.\n\n"
            "The Gram Panchayat is responsible for operation and maintenance of the Jal Jeevan Mission schemes.\n\n"
            "The Jal Jeevan Mission was launched in August 2019.\n\n"
            "CPI inflation was 4.6 percent in 2024-25.\n\nCPI inflation was 4.6 percent in 2024-25.")
    rep = pipe.run(read_text(text), "t")
    nc = [c for c in rep["claims"] if c["method"] == "not-checkable"]
    assert len(nc) == 2 and all(c["verdict"] == "SKIPPED" for c in nc)
    jjm = next(c for c in rep["claims"] if c["claim"]["text"].startswith("The Jal Jeevan Mission was launched"))
    assert jjm["method"] != "not-checkable"
    cpi = [c for c in rep["claims"] if c["claim"]["text"].startswith("CPI")]
    assert len(cpi) == 2 and cpi[0]["verdict"] == cpi[1]["verdict"] == "SUPPORTED"
    assert any(w["code"] == "repeated_claim" for w in cpi[1]["warnings"])
    assert rep["summary"]["not_checkable"] == 2 and rep["summary"]["statements"] == 5


def test_slow_fallbacks_only_for_top_claims(tmp_path):
    from fixture_http import fixture_pipeline
    pipe = fixture_pipeline(tmp_path, fallback_claims=2)
    text = "\n\n".join(f"The Jal Jeevan Mission scheme in Assam covered {100 + i} villages in 2023-24." for i in range(5))
    rep = pipe.run(read_text(text), "t", mode="quick")
    with_fb = [c for c in rep["claims"] if "parliament" in (c["plan"].get("routes") or [])]
    assert len(with_fb) == 2
    for c in rep["claims"]:
        if c not in with_fb:
            assert not {"pib", "parliament", "ndap", "reports"} & set(c["plan"].get("routes") or [])


def test_study_search_only_for_studies(tmp_path):
    from fixture_http import fixture_pipeline
    rep = fixture_pipeline(tmp_path).run(read_text("Karnataka has 27,397 inhabited villages as per Census 2011."), "t",
                                         mode="quick")
    assert not {"openalex", "semanticscholar", "arxiv"} & set(rep["claims"][0]["plan"]["routes"])


# ------------------------------------------------------------------------------------------------ reasons and banner
def test_couldnt_check_reasons_and_short_banner(no_sockets):
    rep = _real_pipeline().run(read_file(LONG), "long", mode="quick")
    s = rep["summary"]
    total = sum(v["claims"] for v in s["couldnt_check_reasons"].values())
    assert total == s["couldnt_check"]
    assert set(s["couldnt_check_reasons"]) >= {"no_data", "no_response", "quick", "deadline"}
    b = s["banner"]
    assert b["text"].startswith(f"{total} claims not checked against data") and len(b["top"]) <= 3     # v0.5.3 wording
    assert "Deep check" in b["deep_hint"]
    from truthlens.report_v2 import banner_lines, to_html
    lines = banner_lines(rep)
    assert len(lines) <= 3 and all(len(x) < 400 for x in lines)
    html = to_html(rep)
    assert "Quick check" in html and "not checked in Quick mode — Deep check (about 1 min)" in html and "<details" in html


# ------------------------------------------------------------------------------------------------ bundled state data
def _q(text):
    return _real_pipeline().run(read_text(text), "t", mode="quick")["claims"]


def test_state_data_census_and_groundwater(no_sockets):
    cs = _q("Karnataka had a population of 6.11 crore as per Census 2011.\n\n"
            "As per Census 2011, Karnataka had 79.47 lakh rural households.\n\n"
            "As per Census 2011, Karnataka had 85 lakh rural households.\n\n"
            "The stage of ground water extraction in Karnataka was 66.49 per cent in the 2025 assessment.\n\n"
            "Karnataka has 92 lakh rural households.")
    v = [c["verdict"] for c in cs]
    assert v[:4] == ["SUPPORTED", "SUPPORTED", "CONTRADICTED", "SUPPORTED"]
    assert v[4] != "CONTRADICTED"          # undated: may be a newer estimate, never called wrong
    assert any("censusindia.gov.in" in (e.get("source_url") or "") for e in cs[0]["evidence"])


def test_state_data_fail_closed_rules(no_sockets):
    cs = _q("In Karnataka, 90 per cent of households use an improved source of drinking water (NFHS-5).\n\n"
            "As per Census 2011, Tumakuru district had a population of 30 lakh.\n\n"
            "As per Census 2011, Tumakuru district had a population of 26.79 lakh.")
    assert cs[0]["verdict"] != "CONTRADICTED" and cs[1]["verdict"] != "CONTRADICTED"
    assert cs[2]["verdict"] == "SUPPORTED"


def test_document_state_assumption_supports_but_never_contradicts(no_sockets):
    intro = "\n\n".join(["Karnataka rural water supply policy.", "Karnataka has 30 districts.",
                         "This policy covers rural Karnataka.", "Karnataka's villages depend on groundwater.",
                         "Rural households in Karnataka need safe water."])
    cs = _q(intro + "\n\nThe State had 79.47 lakh rural households as per Census 2011.\n\n"
                    "The State had 99 lakh rural households as per Census 2011.")
    a, b = cs[-2], cs[-1]
    assert a["verdict"] == "SUPPORTED" and "compared with Karnataka" in a["rationale"]
    assert b["verdict"] != "CONTRADICTED"


def test_curated_all_india_figures_never_used_for_a_district(no_sockets):
    cs = _q("As per Census 2011, Tumakuru district had a population of 12 lakh.")
    assert cs[0]["verdict"] != "CONTRADICTED"


# ------------------------------------------------------------------------------------------------ hosted server
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import truthlens.api as api  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "ONLINE", False)
    monkeypatch.setattr(api, "_PIPE", None)
    api.JOBS.clear()
    api.LIMITER.hits.clear()
    return TestClient(api.app)


def _wait(c, jid, timeout=60):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        st = c.get(f"/jobs/{jid}").json()
        if st["status"] != "running":
            return st
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_jobs_default_to_quick_and_deep_endpoint_reruns_unchecked(client):
    data = LONG.read_bytes()
    r = client.post("/jobs/file", files={"file": ("long.docx", data)})
    assert r.status_code == 202 and r.json()["mode"] == "quick"
    st = _wait(client, r.json()["job_id"])
    rep = client.get(f"/jobs/{st['job_id']}/result").json()
    assert rep["summary"]["mode"] == "quick" and st["mode"] == "quick"
    d = client.post(f"/jobs/{st['job_id']}/deep")
    assert d.status_code == 202 and d.json()["mode"] == "deep"
    st2 = _wait(client, d.json()["job_id"])
    rep2 = client.get(f"/jobs/{st2['job_id']}/result").json()
    assert rep2["summary"]["mode"] == "deep" and rep2["input"] == "long.docx"
    assert rep2["meta"]["deep_from_job"] == st["job_id"]
    assert rep2["summary"]["claims"] == rep["summary"]["claims"]
    assert client.post("/jobs/nope/deep").status_code == 404


def test_sync_check_default_stays_deep_and_mode_param(client):
    body = {"type": "text", "content": "CPI inflation was 4.6 percent in 2024-25."}
    assert client.post("/check", json=body).json()["summary"]["mode"] == "deep"
    assert client.post("/check?mode=quick", json=body).json()["summary"]["mode"] == "quick"
    assert client.post("/check", json={**body, "mode": "quick"}).json()["summary"]["mode"] == "quick"
    assert client.post("/check?mode=fast", json=body).status_code == 422


def test_uploads_are_never_written_to_disk(client, monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile, "TemporaryDirectory", lambda *a, **k: (_ for _ in ()).throw(AssertionError("disk")))
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", lambda *a, **k: (_ for _ in ()).throw(AssertionError("disk")))
    data = (ROOT / "samples" / "sample_policy_note.docx").read_bytes()
    assert client.post("/check/file?format=json&mode=quick", files={"file": ("s.docx", data)}).status_code == 200
    assert client.post("/check/file?format=json&numbers_only=true", files={"file": ("s.docx", data)}).status_code == 200
    st = _wait(client, client.post("/jobs/file", files={"file": ("s.docx", data)}).json()["job_id"])
    assert st["status"] == "done"


def test_public_rate_limits_and_job_cap(client, monkeypatch):
    monkeypatch.setattr(api, "PUBLIC", True)
    monkeypatch.setenv("TRUTHLENS_RATE_CHECKS", "3")
    monkeypatch.setenv("TRUTHLENS_RATE_DEEP", "1")
    body = {"type": "text", "content": "CPI inflation was 4.6 percent in 2024-25."}
    assert client.post("/check", json=body).status_code == 200            # deep: uses the one Deep allowance
    r = client.post("/check", json=body)
    assert r.status_code == 429 and "Deep checks per hour" in r.json()["detail"] and r.headers.get("retry-after")
    assert client.post("/check?mode=quick", json=body).status_code == 200
    assert client.post("/check?mode=quick", json=body).status_code == 429   # 3 checks used (one deep refused late)
    api.LIMITER.hits.clear()
    monkeypatch.setenv("TRUTHLENS_MAX_JOBS", "1")
    running = api.Job("x")
    api.JOBS[running.id] = running
    assert client.post("/jobs", json=body).status_code == 429
    api.JOBS.clear()
    assert client.post("/corrections", json={"claim_text": "x", "correct_verdict": "SUPPORTED"}).status_code == 403


def test_health_reports_data_freshness(client):
    h = client.get("/health").json()
    assert h["status"] == "healthy" and h["version"] == __import__("truthlens").__version__
    assert "synced" in h["data"] and h["data"]["bundled"]["state_data_accessed"] == "2026-11-03"
    assert "live_cache" in h["data"] and h["limits"]["upload_mb"] == 15
    assert h["default_mode"] == {"web_app_and_jobs": "quick", "check_endpoints": "deep"}


def test_user_keys_never_in_job_state_or_report(client):
    r = client.post("/jobs", json={"type": "text", "content": "CPI inflation was 4.6 percent in 2024-25.",
                                   "llm_provider": "openai", "llm_key": "sk-secret-user-key-123"})
    st = _wait(client, r.json()["job_id"])
    job = api.JOBS[st["job_id"]]
    import pickle
    assert b"sk-secret-user-key-123" not in pickle.dumps((job.state, job.result, job.blocks, job.label))
    assert "sk-secret-user-key-123" not in client.get(f"/jobs/{st['job_id']}/result").text


def test_page_has_mode_line_and_deep_button():
    from truthlens.webui import PAGE
    for s in ('id="deepbtn"', "Deep check (about 1 min)", "not checked in Quick mode", '"/deep"', "Update official data",
              "Using the official data bundled with TruthLens", 'id="bdetails"'):
        assert s in PAGE, s


def test_cli_deep_flag(monkeypatch, tmp_path, capsys):
    from truthlens import cli
    out = tmp_path / "r.json"
    rc = cli.main(["check", "--text", "CPI inflation was 4.6 percent in 2024-25.", "-f", "json", "-o", str(out), "--offline"])
    import json
    assert rc == 0 and json.loads(out.read_text())["summary"]["mode"] == "quick"
    rc = cli.main(["check", "--text", "CPI inflation was 4.6 percent in 2024-25.", "-f", "json", "-o", str(out),
                   "--offline", "--deep"])
    assert rc == 0 and json.loads(out.read_text())["summary"]["mode"] == "deep"


def test_framing_sentences_are_not_checkable_facts():
    from truthlens.claims import is_descriptive
    for t in ("This draft sets out the policy of the Government of Karnataka for rural drinking water supply.",
              "The State is home to a large rural population that depends on groundwater for drinking water.",
              "Jal Jeevan Mission is implemented in partnership with the States."):
        assert is_descriptive(t), t
    # a figure, a year or a fact verb keeps a sentence checkable
    for t in ("Karnataka is home to 6.1 crore people.",
              "The State depends on groundwater for 85 per cent of rural drinking water.",
              "The scheme was launched in partnership with the States in 2019.",
              "The stage of ground water extraction in Karnataka is around 70 per cent."):
        assert not is_descriptive(t), t
