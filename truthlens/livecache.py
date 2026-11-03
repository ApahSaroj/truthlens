"""v0.5.2: persistent cache of live-source answers (HTTP level), shared by every check on this machine or server.

What is stored: the public answer a source gave (HTTP 200 body, content type, final URL) for one request, keyed by
host + a SHA-256 of (method, URL, headers, body). The key is stored only as that hash, never as text, so no fragment of
a user's document (search queries are built from claim words) is written to disk in readable form. Requests that
carry credentials (an Authorization / API-key header, or a key/token query parameter), requests to AI providers and
keyed web-search APIs, and requests to local services are never cached.

What is never stored: failures. Timeouts, connection errors, HTTP 4xx/5xx/429 and redirects are not answers, so a
later check asks the source again. (A 404 "unknown DOI" is not cached either: it fails closed as "couldn't check".)

Where: <data dir>/live_cache (the same data dir `truthlens sync` uses: $TRUTHLENS_DATA_DIR, else ./data).
TTL: 7 days (TRUTHLENS_LIVE_CACHE_DAYS). Size cap: 200 MB (TRUTHLENS_LIVE_CACHE_MB), oldest files dropped first.
Off with TRUTHLENS_LIVE_CACHE=0.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, urlparse

SECRET_HEADERS = {"authorization", "x-api-key", "api-key", "apikey", "x-subscription-token", "x-goog-api-key",
                  "proxy-authorization", "cookie", "x-llm-key", "token", "x-auth-token"}
SECRET_PARAMS = {"key", "api_key", "apikey", "api-key", "token", "access_token", "auth", "subscription-key",
                 "client_secret", "password", "sig", "signature"}
NEVER_HOSTS = ("api.anthropic.com", "api.openai.com", "api.tavily.com", "api.search.brave.com", "search.brave.com",
               "google.serper.dev", "serper.dev")
MAX_ENTRY_BYTES = 8 * 2 ** 20


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def enabled() -> bool:
    return _env("TRUTHLENS_LIVE_CACHE", "1").lower() not in ("0", "false", "no", "off")


def cache_dir() -> Path:
    from .sync import data_dir
    return data_dir(None) / "live_cache"


def cacheable_request(method: str, url: str, headers: Optional[dict], allow_local: bool = False) -> bool:
    if allow_local or method not in ("GET", "POST"):
        return False
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if not host or any(host == h or host.endswith("." + h) for h in NEVER_HOSTS):
        return False
    if any(str(k).lower() in SECRET_HEADERS for k in (headers or {})):
        return False
    if any(k.lower() in SECRET_PARAMS for k, _v in parse_qsl(p.query, keep_blank_values=True)):
        return False
    return True


class LiveCache:
    def __init__(self, root: Optional[Path] = None, ttl_days: Optional[float] = None, max_mb: Optional[float] = None):
        self.root = Path(root) if root is not None else cache_dir()
        self.ttl = float(ttl_days if ttl_days is not None else (_env("TRUTHLENS_LIVE_CACHE_DAYS") or 7)) * 86400
        self.max_bytes = int(float(max_mb if max_mb is not None else (_env("TRUTHLENS_LIVE_CACHE_MB") or 200)) * 2 ** 20)
        self._lock = threading.Lock()
        self._writes = 0
        self.hits = 0
        self.stores = 0

    @staticmethod
    def digest(key) -> str:
        return hashlib.sha256(repr(key).encode("utf-8", "replace")).hexdigest()

    def _path(self, host: str, key) -> Path:
        safe_host = "".join(c if c.isalnum() or c in ".-" else "_" for c in (host or "unknown"))[:80]
        return self.root / safe_host / (self.digest(key)[:48] + ".json")

    def get(self, host: str, key, allow_stale: bool = False) -> Optional[dict]:
        p = self._path(host, key)
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not allow_stale and time.time() - float(rec.get("t", 0)) > self.ttl:
            return None
        if rec.get("status") != 200:
            return None
        with self._lock:
            self.hits += 1
        return rec

    def put(self, host: str, key, status: int, content: bytes, content_type: str, final_url: str,
            request_url: str = "") -> bool:
        if status != 200 or content is None or len(content) > MAX_ENTRY_BYTES:
            return False
        rec = {"t": time.time(), "status": 200, "ctype": (content_type or "")[:200],
               "body": base64.b64encode(content).decode("ascii")}
        # the final URL only when a redirect led to a different page and it carries no query string (a search query
        # is built from claim words, so it is never stored in readable form; the caller's own URL is used instead)
        if final_url and final_url != request_url and not urlparse(final_url).query:
            rec["url"] = final_url
        p = self._path(host, key)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(rec), encoding="utf-8")
            tmp.replace(p)
        except OSError:
            return False
        with self._lock:
            self.stores += 1
            self._writes += 1
            prune = self._writes % 50 == 1
        if prune:
            self.prune()
        return True

    def prune(self) -> dict:
        """Drop expired files, then the oldest ones until the cache is under the size cap."""
        files = []
        now = time.time()
        removed = 0
        for f in self.root.glob("*/*.json"):
            try:
                st = f.stat()
            except OSError:
                continue
            if now - st.st_mtime > self.ttl:
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
                continue
            files.append((st.st_mtime, st.st_size, f))
        total = sum(s for _m, s, _f in files)
        for _m, s, f in sorted(files):
            if total <= self.max_bytes:
                break
            try:
                f.unlink()
                total -= s
                removed += 1
            except OSError:
                pass
        return {"files": len(files), "bytes": total, "removed": removed}

    def stats(self) -> dict:
        n, size, newest = 0, 0, 0.0
        for f in self.root.glob("*/*.json"):
            try:
                st = f.stat()
            except OSError:
                continue
            n += 1
            size += st.st_size
            newest = max(newest, st.st_mtime)
        return {"entries": n, "mb": round(size / 2 ** 20, 1), "ttl_days": round(self.ttl / 86400, 1),
                "cap_mb": round(self.max_bytes / 2 ** 20), "newest": newest or None}


def response_from(rec: dict, url: str):
    """Rebuild a requests.Response from a cached record (already materialised: .content works, iter_content too)."""
    import requests
    r = requests.Response()
    r.status_code = 200
    r._content = base64.b64decode(rec.get("body") or "")
    r._content_consumed = True
    r.headers["content-type"] = rec.get("ctype") or ""
    r.headers["x-truthlens-cache"] = "hit"
    r.url = rec.get("url") or url
    r.encoding = None
    return r


_SHARED: Optional[LiveCache] = None
_SHARED_ROOT: Optional[Path] = None
_SHARED_LOCK = threading.Lock()


def shared() -> Optional[LiveCache]:
    """The process-wide cache for the current data dir (re-created when TRUTHLENS_DATA_DIR changes), or None if off."""
    global _SHARED, _SHARED_ROOT
    if not enabled():
        return None
    root = cache_dir()
    with _SHARED_LOCK:
        if _SHARED is None or _SHARED_ROOT != root:
            _SHARED, _SHARED_ROOT = LiveCache(root), root
        return _SHARED
