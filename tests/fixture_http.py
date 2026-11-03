"""Offline HTTP double used by the tests, the evaluator and the sample builder.

Serves recorded responses: World Bank (tests/fixtures/wb_*.json), MoSPI eSankhyiki
(tests/fixtures/mospi_responses.json), Crossref (tests/fixtures/crossref/*.json; anything else is a 404,
as both Crossref and OpenAlex answered for the fake DOIs used in the test sets), official documents
(tests/fixtures/docs/manifest.json), data.gov.in, web search and LLM fixtures (tests/fixtures/*.json).
Any other URL raises, so a test can never reach the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode, urlparse, unquote

FIX = Path(__file__).parent / "fixtures"


class Resp:
    def __init__(self, payload=None, status=200, content=None, ctype="application/json", url=""):
        self._payload = payload
        self.status_code = status
        self.content = content if content is not None else (json.dumps(payload).encode() if payload is not None else b"")
        self.headers = {"content-type": ctype}
        self.url = url
        self.text = self.content.decode("utf-8", "replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            return json.loads(self.content.decode("utf-8"))
        return self._payload

    def iter_content(self, n):
        for i in range(0, len(self.content), n):
            yield self.content[i:i + n]


class FixtureHTTP:
    """Stands in for requests.Session (get/post/mount/headers)."""

    def __init__(self, extra: dict | None = None):
        self.calls: list[str] = []
        self.headers: dict = {}
        self.mospi = json.loads((FIX / "mospi_responses.json").read_text(encoding="utf-8"))
        self.docs = {m["url"]: FIX / "docs" / m["file"] for m in json.loads((FIX / "docs" / "manifest.json").read_text())}
        self.extra = extra or {}
        # v0.3: responses recorded from live sources on 1 Nov 2026 (scripts/record_session.py)
        live = FIX / "live" / "recorded.json"
        self.live = json.loads(live.read_text(encoding="utf-8")) if live.exists() else {}
        # v0.4: responses recorded live on 2 Nov 2026 from NDAP, RBI, CEA, PPAC, JJM, arXiv, Semantic Scholar (429s),
        # Shodhganga (bot-challenge page) and the v0.3 sources, during scripts/run_live_eval.py --record recorded_v04.json
        v04 = FIX / "live" / "recorded_v04.json"
        if v04.exists():
            for k, v in json.loads(v04.read_text(encoding="utf-8")).items():
                self.live.setdefault(k, v)

    def mount(self, *a, **k):
        pass

    def get(self, url, params=None, timeout=None, headers=None, stream=False, allow_redirects=True):
        full = url + ("?" + urlencode(params) if params else "")
        self.calls.append(full)
        self.last_headers = headers or {}
        if not params and "?" in url:      # v0.4: callers pass the query in the URL (net.with_params + safe_get)
            from urllib.parse import parse_qsl
            params_seen = dict(parse_qsl(url.split("?", 1)[1], keep_blank_values=True))
        else:
            params_seen = params or {}
        for key, r in self.extra.items():
            if full == key or full.startswith(key):
                return r(params_seen, headers or {}) if callable(r) else r
        host = urlparse(url).netloc
        rec = self.live.get(full)
        if rec is not None and full not in self.mospi:
            import base64
            body = base64.b64decode(rec["b64"]) if "b64" in rec else rec.get("text", "").encode("utf-8")
            r = Resp(None, rec["status"], body, rec.get("ctype", ""), full)
            if rec.get("location"):
                r.headers["location"] = rec["location"]
            return r
        if "api.worldbank.org" in host:
            code = url.split("/indicator/")[1].split("?")[0]
            f = FIX / f"wb_{code}.json"
            return Resp(json.loads(f.read_text())) if f.exists() else Resp({"message": "not found"}, 404)
        if "api.mospi.gov.in" in host:
            if full in self.mospi:
                return Resp(self.mospi[full], url=full)
            return Resp({"data": [], "msg": "No Data Found", "statusCode": True}, url=full)
        if host == "api.crossref.org":
            doi = unquote(url.split("/works/")[1])
            f = FIX / "crossref" / (doi.replace("/", "_") + ".json")
            return Resp(json.loads(f.read_text())) if f.exists() else Resp(None, 404, b"Resource not found.", "text/plain")
        if host == "api.openalex.org":
            return Resp(None, 404, b'{"error":"not found"}')
        if url in self.docs:
            p = self.docs[url]
            ctype = "application/pdf" if p.suffix == ".pdf" else "text/html; charset=utf-8"
            return Resp(None, 200, p.read_bytes(), ctype, url)
        raise RuntimeError(f"network disabled in tests: {url}")

    def post(self, url, json=None, headers=None, timeout=None, data=None, allow_redirects=False):
        self.calls.append(url)
        self.last_headers = headers or {}
        self.last_json = json
        self.last_data = data
        for key, r in self.extra.items():
            if url == key or url.startswith(key):
                return r(json if json is not None else data, headers or {}) if callable(r) else r
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from record_session import post_key
        rec = self.live.get(post_key(url, data, json))
        if rec is not None:
            import base64
            body = base64.b64decode(rec["b64"]) if "b64" in rec else rec.get("text", "").encode("utf-8")
            return Resp(None, rec["status"], body, rec.get("ctype", ""), url)
        raise RuntimeError(f"network disabled in tests: {url}")


def fixture_pipeline(tmp: Path, llm=None, preload_docs: bool = True, session: FixtureHTTP | None = None, **cfg_over):
    """A Pipeline that runs fully offline on recorded responses, with the official-document fixtures indexed."""
    from truthlens.config import Config
    from truthlens.pipeline import Pipeline
    from truthlens.retrievers.docs import DocIndex, index_bytes
    from truthlens.sources.worldbank import WorldBankClient
    sess = session or FixtureHTTP()
    cfg = Config.load(path="/nonexistent", cache_dir=Path(tmp), **cfg_over)
    cfg.llm_provider = cfg_over.get("llm_provider", "none")
    cfg.search_provider = cfg_over.get("search_provider", "none")
    idx = DocIndex(Path(tmp) / "index.sqlite")
    if preload_docs:
        for url, p in sess.docs.items():
            if not idx.has(url):
                index_bytes(idx, url, p.read_bytes(), "pdf" if p.suffix == ".pdf" else "html", official=True)
    wb = WorldBankClient(cache_dir=Path(tmp) / "wb", session=sess)
    return Pipeline(cfg, llm=llm, docs_index=idx, session=sess, worldbank=wb)
