"""v0.5.1 speed work: per-request circuit breaker, memo cache, whole-document deadline (never SUPPORTED on a timeout),
per-source timeouts and per-host cap, background jobs with real progress, cancel, and GET /sw.js."""
import threading
import time
from pathlib import Path

import pytest
import requests

from truthlens import net, runguard
from truthlens.model import Claim, Evidence

ROOT = Path(__file__).resolve().parents[1]


class Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = {}

    def json(self):
        return self._payload


class Sess:
    """Fake session: per-host behaviour, counts calls, records the timeout it was given."""

    def __init__(self, behaviour=None, delay=0.0):
        self.behaviour = behaviour or {}
        self.calls = []
        self.timeouts = []
        self.delay = delay
        self.lock = threading.Lock()

    def _do(self, url, timeout):
        from urllib.parse import urlparse
        with self.lock:
            self.calls.append(url)
            self.timeouts.append(timeout)
        if self.delay:
            time.sleep(self.delay)
        b = self.behaviour.get(urlparse(url).hostname, 200)
        if isinstance(b, Exception):
            raise b
        return Resp(b, {"url": url})

    def get(self, url, timeout=None, headers=None, stream=True, allow_redirects=False):
        return self._do(url, timeout)

    def post(self, url, timeout=None, headers=None, json=None, data=None, allow_redirects=False):
        return self._do(url, timeout)


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    # every test host resolves to a public address (no real DNS in tests)
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"])


@pytest.fixture
def guard():
    g = runguard.RunGuard(budget=30)
    tok = runguard.CURRENT.set(g)
    yield g
    runguard.CURRENT.reset(tok)


# ------------------------------------------------------------------------------------------------ circuit breaker
def test_breaker_skips_a_host_after_a_timeout(guard):
    s = Sess({"api.openalex.org": requests.exceptions.ReadTimeout("slow"), "api.crossref.org": 200})
    with pytest.raises(net.NetworkError):
        net.safe_get(s, "https://api.openalex.org/works?search=a")
    with pytest.raises(net.SourceSkipped) as e:
        net.safe_get(s, "https://api.openalex.org/works?search=b")       # a different query, same host: not sent
    assert "openalex unavailable this run" in str(e.value)
    assert len(s.calls) == 1
    assert net.safe_get(s, "https://api.crossref.org/works/x").status_code == 200   # other hosts unaffected
    assert guard.broken.get("api.openalex.org") and guard.skipped["api.openalex.org"] == 1
    assert isinstance(e.value, net.FetchError)        # retrievers treat it like any failed fetch


@pytest.mark.parametrize("status,trips", [(500, True), (503, True), (429, True), (404, False), (200, False)])
def test_breaker_trips_on_5xx_and_429_only(guard, status, trips):
    s = Sess({"export.arxiv.org": status})
    assert net.safe_get(s, "https://export.arxiv.org/api/query?q=1").status_code == status
    if trips:
        with pytest.raises(net.SourceSkipped):
            net.safe_get(s, "https://export.arxiv.org/api/query?q=2")
        assert len(s.calls) == 1
    else:
        net.safe_get(s, "https://export.arxiv.org/api/query?q=2")
        assert len(s.calls) == 2


def test_breaker_trips_on_connection_error_for_post(guard):
    s = Sess({"ppac.gov.in": requests.exceptions.ConnectionError("refused")})
    with pytest.raises(net.NetworkError):
        net.safe_post(s, "https://ppac.gov.in/a", json_body={"x": 1})
    with pytest.raises(net.SourceSkipped):
        net.safe_post(s, "https://ppac.gov.in/b", json_body={"x": 2})
    assert len(s.calls) == 1


def test_ssrf_refusal_does_not_trip_the_breaker(guard, monkeypatch):
    monkeypatch.setattr(net, "resolve_host", lambda h: ["10.0.0.5"] if h == "intranet.example.com" else ["93.184.216.34"])
    s = Sess()
    with pytest.raises(net.FetchError):
        net.safe_get(s, "https://intranet.example.com/")
    assert not guard.broken and not s.calls


def test_no_guard_means_old_behaviour():
    assert runguard.CURRENT.get() is None
    s = Sess({"api.openalex.org": 503})
    for _ in range(3):
        assert net.safe_get(s, "https://api.openalex.org/works?q=1", timeout=20.0).status_code == 503
    assert len(s.calls) == 3 and s.timeouts == [20.0, 20.0, 20.0]


# ------------------------------------------------------------------------------------------------ memo cache
def test_memo_fetches_an_identical_query_once(guard):
    s = Sess()
    a = net.safe_get(s, "https://api.mospi.gov.in/api/plfs?year=2023-24")
    b = net.safe_get(s, "https://api.mospi.gov.in/api/plfs?year=2023-24")
    assert a is b and len(s.calls) == 1 and guard.memo_hits == 1
    net.safe_get(s, "https://api.mospi.gov.in/api/plfs?year=2022-23")       # a different query is fetched
    assert len(s.calls) == 2


def test_memo_keys_on_headers_and_post_body(guard):
    s = Sess()
    net.safe_get(s, "https://loadqa.ndapapi.com/v1/search", headers={"Authorization": "a"})
    net.safe_get(s, "https://loadqa.ndapapi.com/v1/search", headers={"Authorization": "b"})
    net.safe_post(s, "https://ppac.gov.in/q", json_body={"year": "2025-26"})
    net.safe_post(s, "https://ppac.gov.in/q", json_body={"year": "2025-26"})
    net.safe_post(s, "https://ppac.gov.in/q", json_body={"year": "2024-25"})
    assert len(s.calls) == 4


def test_memo_concurrent_callers_share_one_request(guard):
    s = Sess(delay=0.3)
    out = []

    def call():
        out.append(net.safe_get(s, "https://api.openalex.org/works?search=jjm"))
    ts = [threading.Thread(target=runguard_ctx(call)) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(s.calls) == 1 and len(out) == 8 and all(o is out[0] for o in out)


def test_memo_remembers_a_failure(guard):
    s = Sess({"api.crossref.org": 404})
    assert net.safe_get(s, "https://api.crossref.org/works/10.1/x").status_code == 404
    assert net.safe_get(s, "https://api.crossref.org/works/10.1/x").status_code == 404
    assert len(s.calls) == 1


def runguard_ctx(fn):
    import contextvars
    ctx = contextvars.copy_context()
    return lambda: ctx.copy().run(fn)


# ------------------------------------------------------------------------------------------------ timeouts and cap
def test_per_source_timeouts_are_short(guard):
    s = Sess()
    net.safe_get(s, "https://cea.nic.in/api/x", timeout=20.0)
    assert s.timeouts[0] == (5.0, 10.0)


def test_per_host_cap_limits_requests_in_flight():
    g = runguard.RunGuard(budget=30, per_host=3)
    tok = runguard.CURRENT.set(g)
    live, peak, lock = [0], [0], threading.Lock()

    class Slow(Sess):
        def _do(self, url, timeout):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.15)
            with lock:
                live[0] -= 1
            return Resp(200)
    s = Slow()
    try:
        ts = [threading.Thread(target=runguard_ctx(lambda i=i: net.safe_get(s, f"https://api.semanticscholar.org/q?{i}")))
              for i in range(10)]
        [t.start() for t in ts]
        [t.join() for t in ts]
    finally:
        runguard.CURRENT.reset(tok)
    assert peak[0] == 3


# ------------------------------------------------------------------------------------------------ deadline
def test_deadline_stops_new_requests():
    g = runguard.RunGuard(budget=0.05)
    tok = runguard.CURRENT.set(g)
    try:
        time.sleep(0.1)
        s = Sess()
        with pytest.raises(net.DeadlineExceeded) as e:
            net.safe_get(s, "https://www.rbi.org.in/")
        assert "ran out of time" in str(e.value) and not s.calls
        assert g.summary()["deadline_hit"] is True
    finally:
        runguard.CURRENT.reset(tok)


def _claim(text, ctype="entity"):
    return Claim(id="c1", sentence_id="s1", sentence=text, text=text, type=ctype, location="p1", numbers=[], citations=[],
                 entities=[], extractor="test")


JJM = "The Jal Jeevan Mission was launched in August 2019."
JJM_EV = Evidence(retriever="pib", source_url="https://pib.gov.in/x", title="JJM", publisher="PIB", official=True,
                  snippet="The Jal Jeevan Mission was launched in August 2019 to provide tap water to every rural household.")


class SlowPIB:
    """Would SUPPORT the claim, but only answers after `delay` seconds."""
    name = "pib"

    def __init__(self, delay):
        self.delay = delay
        self.errors = []

    def retrieve(self, claim, k):
        time.sleep(self.delay)
        return [Evidence(**JJM_EV.__dict__)]


def test_control_the_slow_source_supports_when_it_answers():
    from truthlens.verdict import HeuristicJudge, VerdictEngine
    res = VerdictEngine([SlowPIB(0.0)], HeuristicJudge(), plan=False).evaluate(_claim(JJM), [])
    assert res.verdict == "SUPPORTED"


def test_timeout_never_supported_deadline_marks_ran_out_of_time():
    from truthlens.verdict import HeuristicJudge, VerdictEngine
    g = runguard.RunGuard(budget=0.2)
    tok = runguard.CURRENT.set(g)
    try:
        t0 = time.monotonic()
        res = VerdictEngine([SlowPIB(3.0)], HeuristicJudge(), plan=False).evaluate(_claim(JJM), [])
        took = time.monotonic() - t0
    finally:
        runguard.CURRENT.reset(tok)
    assert res.verdict == "UNVERIFIED"
    assert res.live_limits["ran_out_of_time"] and "pib" in res.live_limits["deadline_sources"]
    assert res.rationale.startswith("Ran out of time")
    assert any(w["code"] == "ran_out_of_time" for w in res.warnings)
    assert {"source": "pib", "status": "deadline"} in res.consulted
    assert took < 2.5          # waited for the document deadline (+ grace), not the 25 s claim budget


def test_breaker_marks_later_claims_couldnt_check():
    from truthlens.verdict import HeuristicJudge, VerdictEngine
    s = Sess({"api.openalex.org": requests.exceptions.ConnectTimeout("dead")})

    class OpenAlexLike:
        name = "openalex"
        errors = []

        def retrieve(self, claim, k):
            try:
                net.safe_get(s, "https://api.openalex.org/works?search=" + claim.text[:20])
            except net.FetchError:
                return []
            return [Evidence(**JJM_EV.__dict__)]
    g = runguard.RunGuard(budget=30)
    tok = runguard.CURRENT.set(g)
    try:
        eng = VerdictEngine([OpenAlexLike()], HeuristicJudge(), plan=False)
        first = eng.evaluate(_claim(JJM), [])
        second = eng.evaluate(_claim("NITI Aayog replaced the Planning Commission in January 2015."), [])
    finally:
        runguard.CURRENT.reset(tok)
    assert len(s.calls) == 1
    assert first.verdict == second.verdict == "UNVERIFIED"
    assert second.live_limits["unavailable_sources"] == ["openalex"]
    assert second.rationale.startswith("Couldn't check — source openalex unavailable this run")
    assert any(w["code"] == "source_unavailable" for w in second.warnings)


def test_pipeline_deadline_never_adds_supported_or_contradicted(tmp_path, http):
    """Same sentences with the normal budget and with an expired budget: the expired run may lose verdicts (to
    couldn't check), never gain a SUPPORTED or CONTRADICTED the normal run did not give; and it reports the count."""
    from fixture_http import fixture_pipeline
    text = ("Real GDP grew 7.8% in 2025-26. The Jal Jeevan Mission was launched in August 2019. "
            "The Jal Jeevan Mission is implemented by the Ministry of Education. "
            "NITI Aayog replaced the Planning Commission in January 2015. India's sex ratio was 940 in 2011. "
            "Array programming with NumPy is described in a Nature paper (doi:10.1038/s41586-020-2649-2).")
    from truthlens.readers import read_text
    normal = fixture_pipeline(tmp_path / "a", session=http).run(read_text(text), "t")
    expired = fixture_pipeline(tmp_path / "b", session=http, live_budget=0.001).run(read_text(text), "t")
    nv = {c["claim"]["text"]: c["verdict"] for c in normal["claims"]}
    for c in expired["claims"]:
        if c["verdict"] in ("SUPPORTED", "CONTRADICTED"):
            assert nv[c["claim"]["text"]] == c["verdict"], c["claim"]["text"]
        if c.get("live_limits", {}).get("ran_out_of_time") and c["verdict"] == "UNVERIFIED":
            assert "Ran out of time" in c["rationale"]
    dl = expired["summary"]["live_deadline"]
    assert dl["budget_s"] == 0.001
    assert dl["claims_hit_deadline"] == sum(1 for c in expired["claims"] if c.get("live_limits", {}).get("ran_out_of_time"))
    assert normal["summary"]["live_deadline"]["claims_hit_deadline"] == 0
    assert expired["meta"]["live_checks"]["deadline_hit"] is True
    if dl["claims_hit_deadline"]:
        from truthlens.report_v2 import banner_lines, to_html
        assert any("ran out of time" in b for b in banner_lines(expired))
        assert "ran out of time" in to_html(expired)


def test_live_budget_and_limits_from_env(monkeypatch):
    from truthlens.config import Config
    c = Config.load(path="/nonexistent")
    assert (c.live_budget, c.connect_timeout, c.read_timeout, c.per_host_limit, c.claim_workers) == (60.0, 5.0, 10.0, 3, 12)
    monkeypatch.setenv("TRUTHLENS_LIVE_BUDGET", "90")
    monkeypatch.setenv("TRUTHLENS_WORKERS", "4")
    c = Config.load(path="/nonexistent")
    assert c.live_budget == 90.0 and c.claim_workers == 4
    g = runguard.from_config(c)
    assert g.budget == 90.0
    monkeypatch.setenv("TRUTHLENS_LIVE_BUDGET", "soon")
    with pytest.raises(ValueError):
        Config.load(path="/nonexistent")
    monkeypatch.setenv("TRUTHLENS_LIVE_BUDGET", "0")
    with pytest.raises(ValueError):
        Config.load(path="/nonexistent")


def test_pipeline_uses_more_workers(tmp_path, http):
    from fixture_http import fixture_pipeline
    assert fixture_pipeline(tmp_path, session=http).workers == 12


# ------------------------------------------------------------------------------------------------ jobs, progress, sw.js
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import truthlens.api as api  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "ONLINE", False)
    monkeypatch.setattr(api, "_PIPE", None)
    api.JOBS.clear()
    return TestClient(api.app)


def _wait(c, jid, timeout=60):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        st = c.get(f"/jobs/{jid}").json()
        if st["status"] != "running":
            return st
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_sw_js_is_204(client):
    r = client.get("/sw.js")
    assert r.status_code == 204 and r.content == b""


def test_job_text_progress_and_result(client):
    r = client.post("/jobs", json={"type": "text", "content": "Real GDP grew 7.8% in 2025-26. India's sex ratio was 940 in 2011."})
    assert r.status_code == 202
    jid = r.json()["job_id"]
    st = _wait(client, jid)
    assert st["status"] == "done" and st["claims_total"] >= 2 and st["claims_done"] == st["claims_total"]
    assert st["stage"] == "done" and st["elapsed_s"] >= 0
    rep = client.get(f"/jobs/{jid}/result").json()
    assert rep["tool"] == "TruthLens" and rep["summary"]["claims"] == st["claims_total"]
    assert "live_deadline" in rep["summary"]
    html = client.get(f"/jobs/{jid}/result?format=html")
    assert html.status_code == 200 and "<html" in html.text.lower()


def test_job_file_matches_sync_endpoint(client):
    data = (ROOT / "samples" / "sample_policy_note.docx").read_bytes()
    r = client.post("/jobs/file", files={"file": ("sample_policy_note.docx", data)})
    assert r.status_code == 202
    st = _wait(client, r.json()["job_id"])
    assert st["status"] == "done"
    rep = client.get(f"/jobs/{st['job_id']}/result").json()
    sync = client.post("/check/file?format=json", files={"file": ("sample_policy_note.docx", data)}).json()
    assert rep["input"] == sync["input"] == "sample_policy_note.docx"
    assert [c["verdict"] for c in rep["claims"]] == [c["verdict"] for c in sync["claims"]]


def test_job_errors_and_unknown_ids(client):
    assert client.post("/jobs/file", files={"file": ("a.exe", b"x")}).status_code == 415
    assert client.post("/jobs", json={"type": "text", "content": "  "}).status_code == 422
    assert client.get("/jobs/nope").status_code == 404
    assert client.get("/jobs/nope/result").status_code == 404
    assert client.post("/jobs/nope/cancel").status_code == 404


def test_job_cancel_stops_the_check(client, monkeypatch):
    import truthlens.pipeline as pl
    started = threading.Event()

    class SlowPipe:
        def __init__(self, cfg=None, **kw):       # v0.5.2: Pipeline(cfg, llm=None) for Quick mode
            self.cfg = cfg

        def run(self, blocks, name, meta=None, progress=None, cancel=None, **kw):   # v0.5.2: mode, prior, state_out
            for i in range(200):
                progress("checking claims", i, 200)
                started.set()
                if cancel.wait(0.05):
                    raise pl.CheckCancelled("check cancelled")
            return {"tool": "TruthLens", "summary": {}, "claims": []}
    monkeypatch.setattr(pl, "Pipeline", SlowPipe)
    jid = client.post("/jobs", json={"type": "text", "content": "GDP grew 7.2%."}).json()["job_id"]
    assert started.wait(10)
    st = client.get(f"/jobs/{jid}").json()
    assert st["status"] == "running" and st["claims_total"] == 200
    assert client.get(f"/jobs/{jid}/result").status_code == 409
    assert client.post(f"/jobs/{jid}/cancel").status_code == 200
    st = _wait(client, jid, 10)
    assert st["status"] == "cancelled"
    assert client.get(f"/jobs/{jid}/result").status_code == 410


def test_pipeline_cancel_raises(tmp_path, http):
    from fixture_http import fixture_pipeline
    from truthlens.pipeline import CheckCancelled
    from truthlens.readers import read_text
    ev = threading.Event()
    ev.set()
    with pytest.raises(CheckCancelled):
        fixture_pipeline(tmp_path, session=http).run(read_text("Real GDP grew 7.8% in 2025-26. CPI was 2.1% in 2025-26."),
                                                      "t", cancel=ev)


def test_pipeline_reports_progress(tmp_path, http):
    from fixture_http import fixture_pipeline
    from truthlens.readers import read_text
    seen = []
    rep = fixture_pipeline(tmp_path, session=http).run(
        read_text("Real GDP grew 7.8% in 2025-26. India's sex ratio was 940 in 2011."), "t",
        progress=lambda stage, d, t: seen.append((stage, d, t)))
    n = rep["summary"]["claims"]
    assert seen[0][0] == "finding claims"
    assert ("checking claims", 0, n) in seen and ("checking claims", n, n) in seen
    assert seen[-1] == ("writing report", n, n)


def test_page_shows_real_progress_not_under_a_minute():
    from truthlens.webui import PAGE
    assert "under a minute" not in PAGE.lower()
    # v0.5.2: the wait is stated per mode (Quick: seconds; Deep: about a minute), still with real progress
    assert "Quick check: a few seconds" in PAGE and "Deep check: about a minute" in PAGE
    assert "Checking claims: " in PAGE and '"jobs/file"' in PAGE and '"jobs"' in PAGE
    assert "/cancel" in PAGE
