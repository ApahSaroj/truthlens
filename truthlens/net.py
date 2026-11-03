"""Shared HTTP helpers: a JSON disk cache, a safe fetcher (no private addresses), domain allow-lists
and a TLS adapter for government servers that still need legacy renegotiation (api.mospi.gov.in)."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import ssl
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

from . import __version__
from .config import redact

# Some government web firewalls (e.g. pib.gov.in) reject user agents that carry a URL; this one is accepted.
UA = f"Mozilla/5.0 (compatible) TruthLens/{__version__}"


class FetchError(Exception):
    pass


class NetworkError(FetchError):
    """v0.5.1: the request itself failed (timeout, connection refused/reset, TLS): trips the per-request breaker."""


from .runguard import CURRENT as _GUARD, GuardStop, note_claim_event, source_of  # noqa: E402


class SourceSkipped(FetchError, GuardStop):
    """v0.5.1: not sent: the host already failed in this check (circuit breaker) or the check was cancelled."""


class DeadlineExceeded(FetchError, GuardStop):
    """v0.5.1: not sent: the whole-document live-source budget is used up."""


class DiskCache:
    """Tiny JSON cache: one file per key under <cache_dir>/<namespace>/, with a TTL."""

    def __init__(self, root: Path, namespace: str, ttl: int = 7 * 24 * 3600):
        self.dir = Path(root) / namespace
        self.ttl = ttl

    def _path(self, key: str) -> Path:
        return self.dir / (hashlib.sha256(key.encode("utf-8")).hexdigest()[:40] + ".json")

    def get(self, key: str, allow_stale: bool = False) -> Optional[Any]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not allow_stale and time.time() - rec.get("t", 0) > self.ttl:
            return None
        return rec.get("v")

    def set(self, key: str, value: Any) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._path(key).write_text(json.dumps({"t": time.time(), "v": value}, ensure_ascii=False),
                                       encoding="utf-8")
        except OSError:
            pass


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def domain_allowed(url: str, allowed: list) -> bool:
    h = host_of(url)
    if not h:
        return False
    for d in allowed:
        d = d.lower().lstrip(".")
        if h == d or h.endswith("." + d):
            return True
    return False


BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
                     "metadata", "metadata.google.internal", "metadata.goog", "instance-data", "instance-data.ec2.internal"}
MAX_REDIRECTS = 5


def ip_is_public(addr: str) -> bool:
    """True only for globally routable unicast addresses (IPv4 and IPv6, IPv4-mapped/compat unwrapped).
    Blocks private, loopback, link-local (incl. 169.254.169.254 metadata), CGNAT, unspecified, multicast,
    reserved, documentation and unique-local ranges."""
    try:
        ip = ipaddress.ip_address(addr.split("%")[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip.sixtofour is not None:
            ip = ip.sixtofour
        elif ip.teredo is not None:
            return False
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    return bool(ip.is_global)


def resolve_host(host: str) -> list[str]:
    """All addresses a host name resolves to (overridable in tests)."""
    return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})


def _proxied(url: str) -> bool:
    try:
        return bool(requests.utils.get_environ_proxies(url))
    except Exception:
        return False


def _is_public_host(host: str, url: str = "") -> bool:
    h = (host or "").lower().rstrip(".").strip("[]")
    if not h or h in BLOCKED_HOSTNAMES or h.endswith((".localhost", ".local", ".internal", ".intranet", ".lan", ".home.arpa")):
        return False
    try:
        ipaddress.ip_address(h.split("%")[0])
        return ip_is_public(h)          # an IP literal: no DNS involved
    except ValueError:
        pass
    try:
        addrs = resolve_host(h)
    except (socket.gaierror, UnicodeError, OSError):
        # no local DNS: only acceptable when an egress proxy resolves names for us
        return _proxied(url or f"https://{h}/")
    return bool(addrs) and all(ip_is_public(a) for a in addrs)


def check_public_url(url: str, allow_local: bool = False) -> None:
    """Raise FetchError unless the URL is http(s) to a public host (every resolved address must be public).
    allow_local=True (v0.5) is only ever set from the user's own plug-in config (`allow_local: true`, default false):
    it lifts the private-address check for that source, never the scheme or embedded-credential checks."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise FetchError(f"only http(s) URLs can be fetched: {url[:80]}")
    if not p.hostname:
        raise FetchError("URL has no host")
    if p.username or p.password:
        raise FetchError("URLs with embedded credentials are refused")
    if not allow_local and not _is_public_host(p.hostname, url):
        raise FetchError(f"refusing to fetch a private or local address: {p.hostname}")


class LegacyTLSAdapter(HTTPAdapter):
    """Keeps certificate verification on but allows legacy TLS renegotiation, which some Indian
    government servers still require (OpenSSL 3 refuses it by default). Also applies when a proxy is used."""

    def _ctx(self):
        ctx = ssl.create_default_context()
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        return ctx

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ctx()
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **kwargs):
        kwargs["ssl_context"] = self._ctx()
        return super().proxy_manager_for(proxy, **kwargs)


def _guard_pools(poolmanager) -> None:
    """Make every direct connection check the address it actually connected to before any request byte
    is sent (defeats DNS rebinding between our pre-check and the connect). Proxied connections are not
    affected: there the peer is the configured egress proxy."""
    from urllib3.connection import HTTPConnection, HTTPSConnection
    from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

    def _check(sock):
        try:
            peer = sock.getpeername()[0]
        except OSError:
            return
        if not ip_is_public(peer):
            sock.close()
            raise FetchError(f"refusing connection to a private or local address: {peer}")

    class GHTTPConnection(HTTPConnection):
        def _new_conn(self):
            sock = super()._new_conn()
            _check(sock)
            return sock

    class GHTTPSConnection(HTTPSConnection):
        def _new_conn(self):
            sock = super()._new_conn()
            _check(sock)
            return sock

    class GHTTPPool(HTTPConnectionPool):
        ConnectionCls = GHTTPConnection

    class GHTTPSPool(HTTPSConnectionPool):
        ConnectionCls = GHTTPSConnection

    poolmanager.pool_classes_by_scheme = {"http": GHTTPPool, "https": GHTTPSPool}


class GuardedAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        _guard_pools(self.poolmanager)


class GuardedLegacyTLSAdapter(LegacyTLSAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        _guard_pools(self.poolmanager)


def make_session(legacy_tls: bool = False, allow_local: bool = False) -> requests.Session:
    """Session for all outbound HTTP. Direct connections refuse private/local peers (see _guard_pools).
    allow_local=True: only for a plug-in whose own config says `allow_local: true` (local services)."""
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    if allow_local:
        s.trust_env = False       # a local service is reached directly, never through an egress proxy
        return s
    s.mount("http://", GuardedAdapter())
    s.mount("https://", GuardedLegacyTLSAdapter() if legacy_tls else GuardedAdapter())
    return s


def safe_get(session, url: str, timeout: float = 20.0, headers: Optional[dict] = None, stream: bool = True,
             max_redirects: int = MAX_REDIRECTS, allow_local: bool = False):
    """GET with SSRF protection (see _safe_get_raw), run under the current request's guard when there is one
    (v0.5.1: circuit breaker, memo cache, deadline, per-source timeouts, per-host concurrency cap)."""
    key = ("GET", url, tuple(sorted((headers or {}).items())), bool(allow_local))
    return _guarded(url, key, timeout, lambda t: _safe_get_raw(session, url, t, headers, stream, max_redirects, allow_local),
                    _live_cache_for(session, "GET", url, headers, allow_local))


MEMO_MAX_BYTES = 48 * 2 ** 20


def _materialise(r):
    """Read a real requests.Response body once so the memo can hand the same response to every caller."""
    if isinstance(r, requests.Response) and not r._content_consumed:
        buf = bytearray()
        try:
            for chunk in r.raw.stream(65536, decode_content=True) if r.raw is not None else []:
                buf.extend(chunk)
                if len(buf) > MEMO_MAX_BYTES:
                    raise FetchError(f"response larger than {MEMO_MAX_BYTES // 2 ** 20} MB")
        except FetchError:
            raise
        except Exception as e:
            raise NetworkError(redact(f"{type(e).__name__}: {e}")) from None
        finally:
            try:
                r.close()
            except Exception:
                pass
        r._content = bytes(buf)
        r._content_consumed = True
    return r


QUICK_SKIP_MSG = "not checked in Quick mode (live sources are only asked in a Deep check)"


class QuickModeSkip(SourceSkipped):
    """v0.5.2: not sent: Quick mode answers from bundled data, the synced store and cached answers only."""


def _live_cache_for(session, method: str, url: str, headers, allow_local: bool):
    """The shared persistent answer cache, for real HTTP sessions only (test doubles never read or write it)."""
    if not isinstance(session, requests.Session):
        return None
    from . import livecache
    if not livecache.cacheable_request(method, url, headers, allow_local):
        return None
    return livecache.shared()


def _guarded(url: str, key, timeout, send, live_cache=None):
    g = _GUARD.get()
    if g is None:
        return send(timeout)
    host = (urlparse(url).hostname or "").lower()
    if live_cache is not None:
        rec = live_cache.get(host, key)
        if rec is not None:
            from .livecache import response_from
            g.note_cache_hit(host)
            return response_from(rec, url)
    if getattr(g, "mode", "deep") == "quick":
        g.note_quick_skip(host)
        note_claim_event("quick", source_of(host))
        raise QuickModeSkip(QUICK_SKIP_MSG)
    stop = g.refusal(host)
    if stop:
        kind, msg = stop
        note_claim_event(kind, source_of(host))
        raise (DeadlineExceeded if kind == "deadline" else SourceSkipped)(msg)
    entry, owner = g.memo_claim(key)
    if not owner:
        if not entry.event.wait(max(0.1, g.remaining() + g.read_timeout)):
            note_claim_event("deadline", source_of(host))
            raise DeadlineExceeded(f"ran out of time ({g.budget:g} s live-source limit for the whole document)")
        if entry.error is not None:
            if isinstance(entry.error, GuardStop):
                kind = "deadline" if isinstance(entry.error, DeadlineExceeded) else "unavailable"
                note_claim_event(kind, source_of(host))
            raise entry.error
        return entry.value
    t0 = time.monotonic()
    failed = False
    try:
        sem = g.slot(host)
        if not sem.acquire(timeout=max(0.0, g.remaining())):
            note_claim_event("deadline", source_of(host))
            raise DeadlineExceeded(f"ran out of time ({g.budget:g} s live-source limit for the whole document)")
        try:
            stop = g.refusal(host)      # the host may have failed while this request waited for a slot
            if stop:
                kind, msg = stop
                note_claim_event(kind, source_of(host))
                raise (DeadlineExceeded if kind == "deadline" else SourceSkipped)(msg)
            r = send(g.timeout(timeout))
            status = getattr(r, "status_code", 200)
            if isinstance(status, int) and (status >= 500 or status == 429):
                failed = True
                g.trip(host, f"HTTP {status}")
            r = _materialise(r)
        finally:
            sem.release()
    except NetworkError as e:
        failed = True
        g.trip(host, str(e))
        g.memo_done(entry, error=e)
        g.record(host, time.monotonic() - t0, True)
        raise
    except BaseException as e:
        g.memo_done(entry, error=e)
        if not isinstance(e, GuardStop):
            g.record(host, time.monotonic() - t0, True)
        raise
    g.memo_done(entry, value=r)
    g.record(host, time.monotonic() - t0, failed)
    if live_cache is not None and not failed and getattr(r, "status_code", 0) == 200:
        try:
            live_cache.put(host, key, 200, r.content, (getattr(r, "headers", {}) or {}).get("content-type", ""),
                           getattr(r, "url", url) or url, url)
        except Exception:
            pass                    # a cache write must never break a check
    return r


def _safe_get_raw(session, url: str, timeout: float = 20.0, headers: Optional[dict] = None, stream: bool = True,
                  max_redirects: int = MAX_REDIRECTS, allow_local: bool = False):
    """GET with SSRF protection: redirects are followed by hand, and every hop (scheme, host, every resolved
    address) is validated *before* a request is sent to it. Returns the final response."""
    from urllib.parse import urljoin
    seen = 0
    first_host = (urlparse(url).hostname or "").lower()
    while True:
        # allow_local covers only the configured host itself: a redirect to any other host gets the full check
        check_public_url(url, allow_local and (urlparse(url).hostname or "").lower() == first_host)
        try:
            try:
                r = session.get(url, timeout=timeout, headers=headers or {}, stream=stream, allow_redirects=False)
            except TypeError:  # simple test doubles
                r = session.get(url, timeout=timeout, headers=headers or {})
        except FetchError:
            raise
        except Exception as e:
            raise NetworkError(redact(f"{type(e).__name__}: {e}")) from None
        status = getattr(r, "status_code", 200)
        loc = (getattr(r, "headers", {}) or {}).get("location") or (getattr(r, "headers", {}) or {}).get("Location")
        if status in (301, 302, 303, 307, 308) and loc:
            seen += 1
            if seen > max_redirects:
                raise FetchError(f"too many redirects (>{max_redirects})")
            try:
                r.close()
            except Exception:
                pass
            url = urljoin(url, loc)
            continue
        try:
            r.url = url
        except Exception:
            pass
        return r


def with_params(url: str, params: Optional[dict]) -> str:
    """url + query string, the way requests builds it (None values dropped, lists repeated)."""
    from urllib.parse import urlencode
    q = {k: v for k, v in (params or {}).items() if v is not None}
    return url + (("&" if "?" in url else "?") + urlencode(q, doseq=True) if q else "")


def safe_post(session, url: str, timeout: float = 20.0, headers: Optional[dict] = None, data=None, json_body=None,
              allow_local: bool = False):
    """POST with SSRF protection (see _safe_post_raw), under the current request's guard when there is one."""
    try:
        body = json.dumps(json_body, sort_keys=True, default=str) if json_body is not None else repr(data)
    except (TypeError, ValueError):
        body = repr((json_body, data))
    key = ("POST", url, tuple(sorted((headers or {}).items())), body, bool(allow_local))
    return _guarded(url, key, timeout, lambda t: _safe_post_raw(session, url, t, headers, data, json_body, allow_local),
                    _live_cache_for(session, "POST", url, headers, allow_local))


def _safe_post_raw(session, url: str, timeout: float = 20.0, headers: Optional[dict] = None, data=None, json_body=None,
                   allow_local: bool = False):
    """POST with the same SSRF protection as safe_get (scheme, host and every resolved address checked before any
    byte is sent; the session's guarded adapters re-check the connected peer). Redirects are never followed for a
    POST: a 3xx answer is returned as is and callers treat it as a failure (fail closed)."""
    check_public_url(url, allow_local)
    try:
        kw = {"timeout": timeout, "headers": headers or {}}
        if json_body is not None:
            kw["json"] = json_body
        if data is not None:
            kw["data"] = data
        try:
            r = session.post(url, allow_redirects=False, **kw)
        except TypeError:  # simple test doubles
            r = session.post(url, **kw)
    except FetchError:
        raise
    except Exception as e:
        raise NetworkError(redact(f"{type(e).__name__}: {e}")) from None
    status = getattr(r, "status_code", 200)
    if status in (301, 302, 303, 307, 308):
        raise FetchError(f"unexpected redirect (HTTP {status}) on POST; not followed")
    return r


def get_json(session, url: str, timeout: float = 20.0, headers: Optional[dict] = None, max_bytes: int = 8 * 2 ** 20,
             allow_local: bool = False):
    """safe_get + size cap + JSON decode. Raises FetchError on HTTP >= 400 (the status is in the message)."""
    data, _ct, _final = fetch_bytes(session, url, timeout, max_bytes, headers, allow_local=allow_local)
    try:
        return json.loads(data.decode("utf-8", "replace"))
    except ValueError as e:
        raise FetchError(f"not JSON: {str(e)[:60]}") from None


def fetch_bytes(session: requests.Session, url: str, timeout: float = 20.0, max_bytes: int = 40 * 2 ** 20,
                headers: Optional[dict] = None, allow_local: bool = False) -> tuple[bytes, str, str]:
    """GET a public URL with a size cap and per-hop SSRF checks. Returns (content, content_type, final_url)."""
    r = safe_get(session, url, timeout, headers, allow_local=allow_local)
    status = getattr(r, "status_code", 200)
    if status >= 400:
        raise FetchError(f"HTTP {status}")
    final = getattr(r, "url", url) or url
    ctype = (getattr(r, "headers", {}) or {}).get("content-type", "")
    if hasattr(r, "iter_content"):
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf.extend(chunk)
            if len(buf) > max_bytes:
                raise FetchError(f"document larger than {max_bytes // 2 ** 20} MB")
        return bytes(buf), ctype, final
    content = getattr(r, "content", b"")
    return content, ctype, final
