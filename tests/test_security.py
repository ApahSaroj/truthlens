"""v0.3 security tests: SSRF protection for every user-supplied URL (reader, citation fetcher, doc fetcher)."""
from __future__ import annotations

import http.server
import threading

import pytest
import requests

from conftest import REAL_SESSION_GET
from fixture_http import Resp


class _Hits(http.server.BaseHTTPRequestHandler):
    hits: list = []

    def do_GET(self):  # noqa: N802
        _Hits.hits.append(self.path)
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><title>internal</title><p>SECRET internal admin page 42</p></html>")

    def log_message(self, *a):
        pass


@pytest.fixture
def local_server(monkeypatch):
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    _Hits.hits = []
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Hits)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    monkeypatch.setattr(requests.Session, "get", REAL_SESSION_GET)   # real HTTP, local only
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_local_server_is_reachable_without_the_guard(local_server):
    """Control: the server really answers, so the refusals below are the guard's doing."""
    r = requests.Session().get(local_server + "/control", timeout=5)
    assert r.status_code == 200 and _Hits.hits == ["/control"]


@pytest.mark.parametrize("variant", ["{u}/secret", "http://localhost:{p}/secret", "http://[::1]:{p}/secret",
                                     "http://2130706433:{p}/secret", "http://0.0.0.0:{p}/secret"])
def test_read_url_refuses_local_server(local_server, variant):
    from truthlens.readers import ReaderError, read_url
    port = local_server.rsplit(":", 1)[1]
    url = variant.format(u=local_server, p=port)
    with pytest.raises(ReaderError):
        read_url(url)
    assert _Hits.hits == []


def test_redirect_to_loopback_is_refused_before_the_internal_request(local_server, monkeypatch):
    """A public page that 302s to 127.0.0.1: the hop is validated before any request is made to it."""
    from truthlens import net
    from truthlens.readers import ReaderError, read_url
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"] if h == "public.example" else ["127.0.0.1"])
    calls = []

    class S:
        headers: dict = {}

        def get(self, url, timeout=None, headers=None, stream=False, allow_redirects=True):
            calls.append((url, allow_redirects))
            if url.startswith("http://public.example"):
                r = Resp(None, 302, b"", "text/html", url)
                r.headers["location"] = local_server + "/admin"
                return r
            return REAL_SESSION_GET(requests.Session(), url, timeout=timeout)

    with pytest.raises(ReaderError, match="private or local"):
        read_url("http://public.example/start", session=S())
    assert calls == [("http://public.example/start", False)]     # auto-redirects off, loopback never requested
    assert _Hits.hits == []


@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data/", "http://[fd00::1]/", "http://10.0.0.5/",
                                 "http://[::ffff:127.0.0.1]/", "http://100.64.0.1/", "file:///etc/passwd",
                                 "gopher://example.org/", "http://metadata.google.internal/", "http://user:pw@example.org/"])
def test_check_public_url_blocks(url):
    from truthlens.net import FetchError, check_public_url
    with pytest.raises(FetchError):
        check_public_url(url)


def test_dns_name_resolving_to_private_is_blocked(monkeypatch):
    from truthlens import net
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34", "10.1.2.3"])   # any private answer blocks
    with pytest.raises(net.FetchError):
        net.check_public_url("https://rebind.example/")


def test_redirect_cap(monkeypatch):
    from truthlens import net
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"])

    class Loop:
        def get(self, url, **k):
            r = Resp(None, 302, b"", "text/html", url)
            r.headers["location"] = url + "x"
            return r
    with pytest.raises(net.FetchError, match="too many redirects"):
        net.fetch_bytes(Loop(), "https://loop.example/a")


def test_guarded_session_refuses_private_peer_even_if_precheck_is_bypassed(local_server):
    """DNS-rebinding defence: the connection itself checks the peer address before sending the request."""
    from truthlens.net import FetchError, make_session
    s = make_session()
    with pytest.raises((FetchError, requests.exceptions.ConnectionError)):
        REAL_SESSION_GET(s, local_server + "/rebind", timeout=5)
    assert _Hits.hits == []


def test_citation_url_to_local_address_is_not_fetched(tmp_path, local_server):
    from fixture_http import fixture_pipeline
    pipe = fixture_pipeline(tmp_path)
    pipe.citations.fetcher.session = requests.Session()
    pipe.citations.fetcher.session.get = lambda *a, **k: REAL_SESSION_GET(requests.Session(), *a, **k)
    from truthlens.model import Claim
    c = Claim("c1", "s1", "x", f"See {local_server}/secret for the 42 figure.", "citation", "para 1",
              citations=[local_server + "/secret"])
    checks, ev = pipe.citations.check(c)
    assert checks[0]["status"] == "unreachable" and "private or local" in checks[0]["detail"]
    assert _Hits.hits == []
