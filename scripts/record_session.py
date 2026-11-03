"""A requests.Session wrapper that records every GET it makes, so a live run can be replayed offline in tests.

Recorded file: tests/fixtures/live/recorded.json  {full_url: {"status", "ctype", "b64" | "text", "url"}}.
Bodies larger than 3 MB are not kept. Keys are never recorded: parameters named api-key/api_key are dropped
from the recorded URL (and such responses are skipped).

v0.4: POST requests are recorded too, keyed "POST <url>\n<body>" (the form or JSON body, keys sorted). A request that
carries an Authorization / x-api-key header (an S2 key, for example) is never recorded."""
from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures" / "live" / "recorded.json"


def post_key(url, data=None, json_body=None) -> str:
    if json_body is not None:
        body = json.dumps(json_body, sort_keys=True)
    elif isinstance(data, dict):
        body = urlencode(sorted(data.items()))
    else:
        body = data.decode() if isinstance(data, bytes) else (data or "")
    return f"POST {url}\n{body}"


class RecordingSession:
    def __init__(self, inner, path: Path = OUT):
        self.inner = inner
        self.headers = inner.headers
        self.path = path
        self.lock = threading.Lock()
        self.data = json.loads(path.read_text()) if path.exists() else {}

    def mount(self, *a, **k):
        return self.inner.mount(*a, **k)

    def get(self, url, params=None, **kw):
        r = self.inner.get(url, params=params, **kw)
        if params and any(k.lower() in ("api-key", "api_key") for k in params):
            return r
        full = url + ("?" + urlencode(params) if params else "")
        try:
            body = r.content
        except Exception:
            return r
        if len(body) <= 3 * 2 ** 20:
            ctype = r.headers.get("content-type", "")
            rec = {"status": r.status_code, "ctype": ctype, "url": full}
            if r.status_code in (301, 302, 303, 307, 308):
                rec["location"] = r.headers.get("location")
            try:
                rec["text"] = body.decode("utf-8")
            except UnicodeDecodeError:
                rec["b64"] = base64.b64encode(body).decode()
            with self.lock:
                self.data[full] = rec
        return r

    def post(self, url, data=None, json=None, headers=None, **kw):
        r = self.inner.post(url, data=data, json=json, headers=headers, **kw)
        if any(h.lower() in ("authorization", "x-api-key") for h in (headers or {})):
            return r
        try:
            body = r.content
        except Exception:
            return r
        if len(body) <= 3 * 2 ** 20:
            rec = {"status": r.status_code, "ctype": r.headers.get("content-type", ""), "url": url}
            try:
                rec["text"] = body.decode("utf-8")
            except UnicodeDecodeError:
                rec["b64"] = base64.b64encode(body).decode()
            with self.lock:
                self.data[post_key(url, data, json)] = rec
        return r

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
