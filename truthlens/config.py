"""Configuration: environment variables first, then truthlens.toml, then defaults.

Keys are read from the environment only (never from the TOML file) and are never written to
reports, caches or logs. `Config.public()` returns a redacted view that is safe to print.

Environment variables
  TRUTHLENS_LLM              anthropic | openai | ollama | none   (default: first one with a key)
  ANTHROPIC_API_KEY          Anthropic key           TRUTHLENS_ANTHROPIC_MODEL (default claude-sonnet-4-5)
  OPENAI_API_KEY             OpenAI key              TRUTHLENS_OPENAI_MODEL    (default gpt-4o-mini)
  OPENAI_BASE_URL            OpenAI-compatible base URL (optional)
  OLLAMA_HOST                e.g. http://localhost:11434 (enables Ollama)  TRUTHLENS_OLLAMA_MODEL (default llama3.1)
  BRAVE_API_KEY | TAVILY_API_KEY | SERPER_API_KEY   web search (first configured wins unless TRUTHLENS_SEARCH set)
  TRUTHLENS_SEARCH           brave | tavily | serper | none
  TRUTHLENS_TAVILY_KEYLESS   1 to use Tavily's keyless mode (sends claim text to Tavily; off by default)
  DATAGOVIN_API_KEY          data.gov.in OGD API key (optional; data.gov.in is not developed further)
  S2_API_KEY                 optional Semantic Scholar key (higher rate limit); key-free by default
  OPENALEX_API_KEY           optional OpenAlex key (larger daily budget)
  TRUTHLENS_MOSPI            1/0 (default 1): live MoSPI eSankhyiki API lookups
  TRUTHLENS_MOSPI_BASE_URL   default https://api.mospi.gov.in
  TRUTHLENS_MOSPI_BACKEND    rest (default) | esankhyiki (use the official Python package)
  TRUTHLENS_CACHE            cache directory (default ~/.cache/truthlens)
  TRUTHLENS_CONTACT_EMAIL    sent to Crossref/OpenAlex as `mailto` (polite pool), optional
  TRUTHLENS_OFFLINE          1 = no network at all (cache and bundled data only)
  TRUTHLENS_CONFIG           path to truthlens.toml (default ./truthlens.toml, then ~/.config/truthlens/truthlens.toml)
"""
from __future__ import annotations

import contextlib
import contextvars
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:  # Python 3.11+
    import tomllib as _toml  # type: ignore
except ImportError:  # pragma: no cover - Python 3.9/3.10
    try:
        import tomli as _toml  # type: ignore
    except ImportError:
        _toml = None

SECRET_ENV = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "BRAVE_API_KEY", "TAVILY_API_KEY", "SERPER_API_KEY",
              "DATAGOVIN_API_KEY", "S2_API_KEY", "OPENALEX_API_KEY")

DEFAULT_ALLOWED_DOMAINS = [
    # Government of India and official statistics
    "gov.in", "nic.in", "rbi.org.in", "indiabudget.gov.in", "mospi.gov.in", "pib.gov.in",
    "censusindia.gov.in", "niti.gov.in", "data.gov.in", "sebi.gov.in", "cag.gov.in",
    # international organisations
    "worldbank.org", "who.int", "un.org", "unicef.org", "undp.org", "imf.org", "oecd.org",
    "adb.org", "ilo.org", "fao.org", "unesco.org", "wto.org",
    # official NFHS fact-sheet host (IIPS/MoHFW publications)
    "dhsprogram.com",
    # Parliament of India (Digital Sansad, Rajya Sabha document stores) - v0.3
    "sansad.in", "rajyasabha.digital", "rajyasabha.nic.in",
]


# Per-request keys (e.g. a key a user pastes into the web page). They live only in this context
# for the duration of one check, are never written anywhere, and take priority over the environment.
_KEY_OVERRIDES: contextvars.ContextVar[dict] = contextvars.ContextVar("truthlens_key_overrides", default={})


@contextlib.contextmanager
def use_keys(keys: Optional[dict]):
    """Temporarily use the given secrets (names from SECRET_ENV) instead of the environment."""
    clean = {k: v.strip() for k, v in (keys or {}).items() if k in SECRET_ENV and v and v.strip()}
    token = _KEY_OVERRIDES.set(clean)
    try:
        yield
    finally:
        _KEY_OVERRIDES.reset(token)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    o = _KEY_OVERRIDES.get()
    if name in o:
        return o[name]
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _truthy(v: Optional[str], default: bool = False) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def default_cache_dir() -> Path:
    base = _env("TRUTHLENS_CACHE") or os.path.join(_env("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "truthlens")
    return Path(base)


def _load_toml(path: Optional[str]) -> tuple[dict, Optional[str]]:
    cands = [path] if path else [_env("TRUTHLENS_CONFIG"), "truthlens.toml",
                                 os.path.expanduser("~/.config/truthlens/truthlens.toml")]
    for c in cands:
        if c and Path(c).is_file():
            if _toml is None:
                return {}, f"{c} found but no TOML parser (pip install tomli on Python < 3.11)"
            with open(c, "rb") as fh:
                data = _toml.load(fh)
            for bad in ("api_key", "key", "token", "password"):
                if _contains_key(data, bad):
                    raise ValueError(f"{c}: put API keys in environment variables, not in truthlens.toml")
            return data, c
    return {}, None


def _contains_key(d: Any, name: str) -> bool:
    if isinstance(d, dict):
        return any(k.lower() == name or _contains_key(v, name) for k, v in d.items())
    return False


@dataclass
class Config:
    offline: bool = False
    cache_dir: Path = field(default_factory=default_cache_dir)
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    search_provider: Optional[str] = None
    tavily_keyless: bool = False
    mospi_enabled: bool = True
    mospi_base_url: str = "https://api.mospi.gov.in"
    mospi_backend: str = "rest"
    contact_email: Optional[str] = None
    allowed_domains: list = field(default_factory=lambda: list(DEFAULT_ALLOWED_DOMAINS))
    datagovin_resources: dict = field(default_factory=dict)
    retrievers: list = field(default_factory=lambda: ["curated", "worldbank", "mospi", "datagovin", "docs", "web", "citations",
                                                     "pib", "parliament", "openalex", "reports",
                                                     "ndap", "rbi", "cea", "ppac", "jjm", "semanticscholar", "arxiv",
                                                     "shodhganga", "plugins", "state-data"])
    timeout: float = 20.0
    claim_budget: float = 25.0         # seconds per claim for live sources (run in parallel)
    # v0.5.1 speed limits (env TRUTHLENS_LIVE_BUDGET / _CONNECT_TIMEOUT / _READ_TIMEOUT / _PER_HOST / _WORKERS,
    # or the same names in [truthlens] of truthlens.toml)
    live_budget: float = 60.0          # seconds of live-source time for the whole document
    connect_timeout: float = 5.0       # per request
    read_timeout: float = 10.0         # per request (seconds without data)
    per_host_limit: int = 3            # requests in flight per host (OpenAlex / Semantic Scholar rate limits)
    claim_workers: int = 12            # claims checked at the same time
    # v0.5.2: how many of a document's most important claims may use the slow live fallbacks (PIB, Parliament
    # answers, the NDAP catalogue, report listings); every other claim goes only to the sources that hold its data
    fallback_claims: int = 20
    max_doc_mb: float = 40.0
    web_fetch_top: int = 2
    config_file: Optional[str] = None
    toml: dict = field(default_factory=dict)

    # ---- secrets: read on demand from the environment, never stored on the object ----
    @staticmethod
    def secret(name: str) -> Optional[str]:
        return _env(name)

    @classmethod
    def load(cls, path: Optional[str] = None, **overrides) -> "Config":
        data, src = _load_toml(path)
        tl = data.get("truthlens", data)
        c = cls()
        c.config_file = src
        c.toml = data
        c.offline = _truthy(_env("TRUTHLENS_OFFLINE"), bool(tl.get("offline", False)))
        c.cache_dir = Path(_env("TRUTHLENS_CACHE") or tl.get("cache_dir") or default_cache_dir()).expanduser()
        llm = data.get("llm", {})
        c.llm_provider = (_env("TRUTHLENS_LLM") or llm.get("provider") or "").lower() or None
        c.llm_model = llm.get("model")
        search = data.get("search", {})
        c.search_provider = (_env("TRUTHLENS_SEARCH") or search.get("provider") or "").lower() or None
        c.tavily_keyless = _truthy(_env("TRUTHLENS_TAVILY_KEYLESS"), bool(search.get("tavily_keyless", False)))
        c.web_fetch_top = int(search.get("fetch_top_official", c.web_fetch_top))
        mospi = data.get("mospi", {})
        c.mospi_enabled = _truthy(_env("TRUTHLENS_MOSPI"), bool(mospi.get("enabled", True)))
        c.mospi_base_url = _env("TRUTHLENS_MOSPI_BASE_URL") or mospi.get("base_url") or c.mospi_base_url
        c.mospi_backend = (_env("TRUTHLENS_MOSPI_BACKEND") or mospi.get("backend") or "rest").lower()
        c.contact_email = _env("TRUTHLENS_CONTACT_EMAIL") or tl.get("contact_email")
        docs = data.get("docs", {})
        extra = docs.get("allowed_domains", [])
        c.allowed_domains = list(dict.fromkeys(c.allowed_domains + list(extra)))
        c.max_doc_mb = float(docs.get("max_mb", c.max_doc_mb))
        c.datagovin_resources = data.get("datagovin", {}).get("resources", {}) or {}
        if tl.get("retrievers"):
            c.retrievers = list(tl["retrievers"])
        c.timeout = float(tl.get("timeout", c.timeout))
        for attr, env, kind in (("live_budget", "TRUTHLENS_LIVE_BUDGET", float),
                                ("connect_timeout", "TRUTHLENS_CONNECT_TIMEOUT", float),
                                ("read_timeout", "TRUTHLENS_READ_TIMEOUT", float),
                                ("per_host_limit", "TRUTHLENS_PER_HOST", int),
                                ("claim_workers", "TRUTHLENS_WORKERS", int),
                                ("fallback_claims", "TRUTHLENS_FALLBACK_CLAIMS", int)):
            raw = _env(env) or tl.get(attr)
            if raw not in (None, ""):
                try:
                    val = kind(raw)
                except (TypeError, ValueError):
                    raise ValueError(f"{env} / {attr} must be a number, got {raw!r}") from None
                if val <= 0:
                    raise ValueError(f"{env} / {attr} must be greater than 0, got {raw!r}")
                setattr(c, attr, val)
        for k, v in overrides.items():
            if v is not None:
                setattr(c, k, v)
        return c

    # ---- what is configured ----
    def resolved_llm(self) -> Optional[str]:
        if self.llm_provider in ("none", "off", "0"):
            return None
        if self.llm_provider:
            return self.llm_provider
        if self.secret("ANTHROPIC_API_KEY"):
            return "anthropic"
        if self.secret("OPENAI_API_KEY"):
            return "openai"
        if _env("OLLAMA_HOST"):
            return "ollama"
        return None

    def resolved_search(self) -> Optional[str]:
        if self.search_provider in ("none", "off", "0"):
            return None
        if self.search_provider:
            return self.search_provider
        for name, env in (("brave", "BRAVE_API_KEY"), ("tavily", "TAVILY_API_KEY"), ("serper", "SERPER_API_KEY")):
            if self.secret(env):
                return name
        if self.tavily_keyless:
            return "tavily"
        return None

    def public(self) -> dict:
        """A redacted, printable view (no secrets)."""
        return {
            "config_file": self.config_file, "offline": self.offline, "cache_dir": str(self.cache_dir),
            "llm": self.resolved_llm(), "search": self.resolved_search(), "tavily_keyless": self.tavily_keyless,
            "mospi": self.mospi_enabled, "mospi_base_url": self.mospi_base_url, "mospi_backend": self.mospi_backend,
            "retrievers": self.retrievers, "allowed_domains": len(self.allowed_domains),
            "keys_present": {k: bool(self.secret(k)) for k in SECRET_ENV},
        }


def redact(text: str) -> str:
    """Remove any configured secret value from a string (used on every error message we keep)."""
    if not text:
        return text
    values = [os.environ.get(k) for k in SECRET_ENV] + list(_KEY_OVERRIDES.get().values())
    for v in values:
        if v and len(v) >= 6:
            text = text.replace(v, "[redacted]")
    import re
    text = re.sub(r"(api[-_]?key=)[^&\s]+", r"\1[redacted]", text, flags=re.I)
    return text
