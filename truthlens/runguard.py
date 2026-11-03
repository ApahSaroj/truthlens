"""v0.5.1: per-request limits for live sources, so a long draft cannot spend minutes on dead or slow servers.

One RunGuard lives for one check (one Pipeline.run). Every outbound request goes through net.safe_get / net.safe_post,
which consult the guard of the current request (a context variable, so it reaches the worker threads):

* circuit breaker: once a host times out, fails to connect, or answers 5xx / 429, it is skipped for the rest of the
  request; the claims that would have asked it are marked "couldn't check: source X unavailable this run".
* memo cache: the same request (method, URL, headers, body) is fetched once per check; concurrent callers wait for the
  first one instead of sending their own.
* whole-document deadline: a total budget (default 60 s) for live sources. After it, no new request is sent; claims
  whose live checks did not finish keep their offline / deterministic result or stay UNVERIFIED ("ran out of time").
  A timeout never produces evidence, so it can never make a claim SUPPORTED or CONTRADICTED.
* shorter per-source timeouts (connect 5 s, read 10 s) and at most 3 requests at a time per host (rate limits).
* cancel: a cancelled check stops sending requests at once.

Without a guard (library use outside Pipeline.run) nothing changes.
"""
from __future__ import annotations

import contextvars
import threading
import time
from typing import Any, Optional

CURRENT: contextvars.ContextVar = contextvars.ContextVar("truthlens_run_guard", default=None)
# per-claim list of (kind, source) events: kind is "unavailable" or "deadline"; set by VerdictEngine.evaluate
CLAIM_EVENTS: contextvars.ContextVar = contextvars.ContextVar("truthlens_claim_events", default=None)

# host suffix -> the source name the report uses
HOST_SOURCES = [
    ("api.openalex.org", "openalex"), ("openalex.org", "openalex"), ("semanticscholar.org", "semanticscholar"),
    ("export.arxiv.org", "arxiv"), ("arxiv.org", "arxiv"), ("crossref.org", "citations (Crossref)"),
    ("doi.org", "citations (doi.org)"), ("shodhganga.inflibnet.ac.in", "shodhganga"), ("rbi.org.in", "rbi"),
    ("cea.nic.in", "cea"), ("ppac.gov.in", "ppac"), ("jaljeevanmission.gov.in", "jjm"), ("ejalshakti.gov.in", "jjm"),
    ("ndap.niti.gov.in", "ndap"), ("mospi.gov.in", "mospi"), ("worldbank.org", "worldbank"),
    ("data.gov.in", "datagovin"), ("pib.gov.in", "pib"), ("sansad.in", "parliament"), ("loksabha.nic.in", "parliament"),
    ("rajyasabha.nic.in", "parliament"), ("rajyasabha.digital", "parliament (Rajya Sabha)"),
    ("ndapapi.com", "ndap"), ("huggingface.co", "parliament (Lok Sabha archive on Hugging Face)"),
    ("indiabudget.gov.in", "reports"), ("search.brave.com", "web"), ("api.tavily.com", "web"), ("serper.dev", "web"),
]


# hosts whose published rate limit is stricter than the default cap: arXiv asks for one request at a time
HOST_LIMITS = {"export.arxiv.org": 1}


def source_of(host: str) -> str:
    h = (host or "").lower()
    for suffix, name in HOST_SOURCES:
        if h == suffix or h.endswith("." + suffix):
            return name
    return h or "unknown host"


class GuardStop(Exception):
    """Base for the guard's refusals (subclassed with net.FetchError in net.py so retrievers treat them as failures)."""


class _Entry:
    __slots__ = ("event", "value", "error")

    def __init__(self):
        self.event = threading.Event()
        self.value: Any = None
        self.error: Optional[BaseException] = None


class RunGuard:
    def __init__(self, budget: float = 60.0, connect_timeout: float = 5.0, read_timeout: float = 10.0,
                 per_host: int = 3, cancel: Optional[threading.Event] = None, mode: str = "deep"):
        self.mode = mode if mode in ("quick", "deep") else "deep"     # v0.5.2
        self.quick_skips = 0
        self.cache_hits = 0
        self.budget = float(budget)
        self.connect_timeout = float(connect_timeout)
        self.read_timeout = float(read_timeout)
        self.per_host = max(1, int(per_host))
        self.cancel = cancel or threading.Event()
        self.started = time.monotonic()
        self.deadline = self.started + self.budget
        self._lock = threading.Lock()
        self.broken: dict = {}          # host -> reason it was cut off
        self.skipped: dict = {}         # host -> number of requests not sent because the host was cut off
        self.memo: dict = {}            # request key -> _Entry
        self.memo_hits = 0
        self.deadline_refusals = 0
        self.hosts: dict = {}           # host -> {"calls", "seconds", "failures"}
        self._sems: dict = {}

    # ------------------------------------------------------------------ time
    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def expired(self) -> bool:
        return self.remaining() <= 0

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def timeout(self, requested) -> tuple:
        """(connect, read) for one request: the shorter of the per-source timeouts, the caller's and the time left."""
        left = max(0.5, self.remaining())
        req = requested[1] if isinstance(requested, tuple) else requested
        read = min(self.read_timeout, float(req) if req else self.read_timeout, left)
        return (min(self.connect_timeout, left), read)

    # ------------------------------------------------------------------ breaker
    def refusal(self, host: str) -> Optional[tuple]:
        """None when a request to host may be sent; else (kind, message) with kind cancelled|unavailable|deadline."""
        if self.cancel.is_set():
            return ("cancelled", "check cancelled")
        with self._lock:
            reason = self.broken.get(host)
            if reason is not None:
                self.skipped[host] = self.skipped.get(host, 0) + 1
                return ("unavailable", f"{source_of(host)} unavailable this run (skipped after it failed: {reason})")
        if self.expired():
            with self._lock:
                self.deadline_refusals += 1
            return ("deadline", f"ran out of time ({self.budget:g} s live-source limit for the whole document)")
        return None

    def trip(self, host: str, reason: str) -> None:
        with self._lock:
            self.broken.setdefault(host, reason[:120])

    def record(self, host: str, seconds: float, failed: bool) -> None:
        with self._lock:
            h = self.hosts.setdefault(host, {"calls": 0, "seconds": 0.0, "failures": 0})
            h["calls"] += 1
            h["seconds"] += seconds
            h["failures"] += int(failed)

    def slot(self, host: str) -> threading.BoundedSemaphore:
        with self._lock:
            s = self._sems.get(host)
            if s is None:
                n = min(self.per_host, next((v for k, v in HOST_LIMITS.items() if host == k or host.endswith("." + k)),
                                            self.per_host))
                s = self._sems[host] = threading.BoundedSemaphore(n)
            return s

    def note_quick_skip(self, host: str) -> None:
        with self._lock:
            self.quick_skips += 1

    def note_cache_hit(self, host: str) -> None:
        with self._lock:
            self.cache_hits += 1

    # ------------------------------------------------------------------ memo
    def memo_claim(self, key) -> tuple:
        """(entry, owner): owner=True means the caller must fetch and then call memo_done."""
        with self._lock:
            e = self.memo.get(key)
            if e is not None:
                self.memo_hits += 1
                return e, False
            e = self.memo[key] = _Entry()
            return e, True

    @staticmethod
    def memo_done(entry: _Entry, value=None, error: Optional[BaseException] = None) -> None:
        entry.value, entry.error = value, error
        entry.event.set()

    # ------------------------------------------------------------------ report
    def summary(self, claims_hit: int = 0) -> dict:
        with self._lock:
            skipped = [{"source": source_of(h), "host": h, "reason": r, "requests_skipped": self.skipped.get(h, 0)}
                       for h, r in sorted(self.broken.items())]
            per_host = {h: {"calls": v["calls"], "seconds": round(v["seconds"], 1), "failures": v["failures"]}
                        for h, v in sorted(self.hosts.items(), key=lambda kv: -kv[1]["seconds"])}
            hit = self.deadline_refusals > 0 or claims_hit > 0
            return {"mode": self.mode, "quick_skips": self.quick_skips, "live_cache_hits": self.cache_hits,
                    "budget_s": self.budget, "elapsed_s": round(self.elapsed(), 1), "deadline_hit": hit,
                    "claims_hit_deadline": claims_hit, "sources_cut_off": skipped, "memo_hits": self.memo_hits,
                    "per_host": per_host, "timeouts": {"connect_s": self.connect_timeout, "read_s": self.read_timeout},
                    "per_host_limit": self.per_host}


def note_claim_event(kind: str, source: str) -> None:
    ev = CLAIM_EVENTS.get()
    if ev is not None:
        ev.append((kind, source))


def from_config(cfg, cancel: Optional[threading.Event] = None, mode: str = "deep") -> RunGuard:
    return RunGuard(mode=mode, budget=float(getattr(cfg, "live_budget", 60.0)),
                    connect_timeout=float(getattr(cfg, "connect_timeout", 5.0)),
                    read_timeout=float(getattr(cfg, "read_timeout", 10.0)),
                    per_host=int(getattr(cfg, "per_host_limit", 3)), cancel=cancel)
