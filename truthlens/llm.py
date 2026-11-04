"""Bring-your-own-key LLM client: Anthropic, OpenAI (or any OpenAI-compatible server), local Ollama, and (v0.6) the
OpenAI-compatible endpoints of DeepSeek, Mistral, xAI (Grok), Google Gemini, Moonshot (Kimi), Alibaba Qwen (DashScope
international), Z.ai (GLM), OpenRouter, or a custom base URL.

Only used for (1) claim extraction and (2) judging non-numeric claims against retrieved evidence.
Keys come from the environment (or the per-request keys of the web app) at call time and are never logged, cached or
returned. Every call asks for JSON and the caller validates it; anything malformed is treated as "no answer" (fail
closed). Providers that reject `response_format: json_object` (HTTP 400) are asked once more with a plain prompt and
the JSON is parsed from the text.

v0.6 providers are untested live: their requests were only exercised against mocked HTTP in the test suite.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

import requests

from .config import LLM_ALIASES, LLM_KEY_ENV, Config, _env, redact

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# v0.6: OpenAI-compatible providers. Base URL and default model as given in each provider's own documentation
# (read 4 Nov 2026; the docs page is in "docs"). Override with TRUTHLENS_<NAME>_BASE_URL / TRUTHLENS_<NAME>_MODEL.
PROVIDERS = {
    "openai": {"label": "OpenAI", "base": "https://api.openai.com/v1", "model": "gpt-4o-mini",
               "docs": "https://platform.openai.com/docs/api-reference/chat"},
    "deepseek": {"label": "DeepSeek", "base": "https://api.deepseek.com", "model": "deepseek-flash",
                 "docs": "https://api-docs.deepseek.com/"},
    "mistral": {"label": "Mistral", "base": "https://api.mistral.ai/v1", "model": "mistral-small-latest",
                "docs": "https://docs.mistral.ai/api/"},
    "xai": {"label": "xAI Grok", "base": "https://api.x.ai/v1", "model": "grok-4.7",
            "docs": "https://docs.x.ai/docs/overview"},
    "gemini": {"label": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai",
               "model": "gemini-3.8-flash", "docs": "https://ai.google.dev/gemini-api/docs/openai"},
    "moonshot": {"label": "Moonshot Kimi", "base": "https://api.moonshot.ai/v1", "model": "kimi-k3.1-pro",
                 "docs": "https://platform.moonshot.ai/docs/guide/start-using-kimi-api"},
    "qwen": {"label": "Alibaba Qwen (DashScope international)",
             "base": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus",
             "docs": "https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope"},
    "zhipu": {"label": "Z.ai GLM", "base": "https://api.z.ai/api/paas/v4", "model": "glm-5.3", "temperature": 0.1,
              "docs": "https://docs.z.ai/guides/develop/openai/python"},
    "openrouter": {"label": "OpenRouter", "base": "https://openrouter.ai/api/v1", "model": "~openai/gpt-sol-latest",
                   "docs": "https://openrouter.ai/docs/quickstart"},
    "custom": {"label": "Custom OpenAI-compatible endpoint", "base": "", "model": "",
               "docs": "your provider's documentation"},
}
OPENAI_COMPATIBLE = tuple(PROVIDERS)
NATIVE = ("anthropic", "ollama")
DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-5", "ollama": "llama3.1",
                  **{k: v["model"] for k, v in PROVIDERS.items()}}
UNTESTED_LIVE = ("deepseek", "mistral", "xai", "gemini", "moonshot", "qwen", "zhipu", "openrouter", "custom")
# hosts that receive a user's key: never written to the shared live-answer cache (see livecache.NEVER_HOSTS)
PROVIDER_HOSTS = tuple(sorted({re.sub(r"^https?://([^/]+).*$", r"\1", v["base"]) for v in PROVIDERS.values() if v["base"]}))


class LLMError(Exception):
    pass


def norm_provider(name: Optional[str]) -> str:
    n = (name or "").strip().lower()
    return LLM_ALIASES.get(n, n)


def provider_choices() -> list:
    """[(id, label)] for the web app's provider picker and the CLI help."""
    out = [("anthropic", "Anthropic Claude")]
    out += [(k, v["label"]) for k, v in PROVIDERS.items()]
    return out


def is_public_mode() -> bool:
    return os.environ.get("TRUTHLENS_PUBLIC", "").strip().lower() in ("1", "true", "yes", "on")


def check_base_url(url: str, public: Optional[bool] = None) -> str:
    """A custom base URL is accepted only when it is https to a public host in public/hosted mode (the SSRF guard of
    truthlens.net: every resolved address must be public). Locally, http and local addresses are allowed (a model
    server on this machine). Returns the URL without a trailing slash; raises LLMError otherwise."""
    from urllib.parse import urlparse
    from .net import FetchError, check_public_url
    public = is_public_mode() if public is None else public
    u = (url or "").strip().rstrip("/")
    p = urlparse(u)
    if not u or p.scheme not in ("http", "https") or not p.hostname:
        raise LLMError("custom AI provider: give a base URL such as https://example.com/v1")
    if public and p.scheme != "https":
        raise LLMError("custom AI provider: only https base URLs are allowed on a hosted TruthLens")
    if p.query or p.fragment:
        raise LLMError("custom AI provider: the base URL must not carry a query string")
    try:
        check_public_url(u, allow_local=not public)
    except FetchError as e:
        raise LLMError(f"custom AI provider: {e}") from None
    return u


def _extract_json(text: str):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        pass
    for open_, close in (("{", "}"), ("[", "]")):
        a, b = text.find(open_), text.rfind(close)
        if a != -1 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except ValueError:
                continue
    raise LLMError("model did not return valid JSON")


class LLMClient:
    def __init__(self, provider: str, model: Optional[str] = None, timeout: float = 60.0,
                 session: Optional[requests.Session] = None):
        provider = norm_provider(provider)
        if provider not in DEFAULT_MODELS:
            raise LLMError(f"unknown LLM provider: {provider}")
        self.provider = provider
        env_model = _env(f"TRUTHLENS_{provider.upper()}_MODEL") or _env("TRUTHLENS_LLM_MODEL")
        self.model = model or env_model or DEFAULT_MODELS[provider]
        if provider == "custom" and not self.model:
            raise LLMError("custom AI provider: set a model name (TRUTHLENS_CUSTOM_MODEL)")
        self.timeout = timeout
        self._session = session
        self.calls = 0
        self.errors: list[str] = []

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            if self.provider == "custom":
                # the custom endpoint is reached through the SSRF-guarded session (private peers refused at connect
                # time) unless this is a local, non-hosted run
                from .net import make_session
                self._session = make_session(allow_local=not is_public_mode())
            else:
                self._session = requests.Session()
        return self._session

    @classmethod
    def from_config(cls, cfg: Config, session: Optional[requests.Session] = None) -> Optional["LLMClient"]:
        p = norm_provider(cfg.resolved_llm())
        if not p or cfg.offline:
            return None
        if p in LLM_KEY_ENV and not cfg.secret(LLM_KEY_ENV[p]):
            return None
        if p == "custom":
            try:
                check_base_url(_env("TRUTHLENS_CUSTOM_BASE_URL") or "")
            except LLMError:
                return None
        if p == "ollama" and not os.environ.get("OLLAMA_HOST"):
            os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
        if p not in DEFAULT_MODELS:
            return None
        try:
            return cls(p, cfg.llm_model, session=session)
        except LLMError:
            return None

    @property
    def label(self) -> str:
        tag = " (untested live)" if self.provider in UNTESTED_LIVE else ""
        return f"{self.provider}:{self.model}{tag}"

    def base_url(self) -> str:
        if self.provider == "custom":
            return check_base_url(_env("TRUTHLENS_CUSTOM_BASE_URL") or "")
        if self.provider == "openai":
            return (_env("TRUTHLENS_OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or PROVIDERS["openai"]["base"]).rstrip("/")
        return (_env(f"TRUTHLENS_{self.provider.upper()}_BASE_URL") or PROVIDERS[self.provider]["base"]).rstrip("/")

    def complete_json(self, system: str, user: str, max_tokens: int = 2000):
        self.calls += 1
        try:
            if self.provider == "anthropic":
                text = self._anthropic(system, user, max_tokens)
            elif self.provider == "ollama":
                text = self._ollama(system, user)
            else:
                text = self._openai(system, user, max_tokens)
            return _extract_json(text)
        except LLMError as e:
            self.errors.append(redact(str(e)))
            raise
        except Exception as e:
            msg = redact(f"{self.provider} call failed: {type(e).__name__}: {e}")
            self.errors.append(msg)
            raise LLMError(msg) from None

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        r = self.session.post(url, headers=headers, json=body, timeout=self.timeout, allow_redirects=False)
        if 300 <= r.status_code < 400:
            raise LLMError(f"{self.provider} answered with a redirect (HTTP {r.status_code}); redirects are not followed")
        if r.status_code >= 400:
            err = LLMError(f"{self.provider} HTTP {r.status_code}: {redact(r.text[:200])}")
            err.status = r.status_code
            raise err
        return r.json()

    def _anthropic(self, system: str, user: str, max_tokens: int) -> str:
        key = Config.secret("ANTHROPIC_API_KEY") or ""
        data = self._post(ANTHROPIC_URL, {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION,
                                          "content-type": "application/json"},
                          {"model": self.model, "max_tokens": max_tokens, "temperature": 0, "system": system,
                           "messages": [{"role": "user", "content": user}]})
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    def _openai(self, system: str, user: str, max_tokens: int) -> str:
        key = Config.secret(LLM_KEY_ENV.get(self.provider, "OPENAI_API_KEY")) or ""
        url = f"{self.base_url()}/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        temp = PROVIDERS.get(self.provider, {}).get("temperature", 0)
        body = {"model": self.model, "temperature": temp, "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        try:
            data = self._post(url, headers, body)
        except LLMError as e:
            if getattr(e, "status", None) != 400:
                raise
            # some OpenAI-compatible servers reject response_format (or a temperature of 0): ask once more with a
            # plain prompt that asks for JSON, and parse the JSON out of the text
            body = {"model": self.model, "max_tokens": max_tokens,
                    "messages": [{"role": "system", "content": system + "\n\nAnswer with one JSON object only, no other text."},
                                 {"role": "user", "content": user}]}
            data = self._post(url, headers, body)
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):      # some servers return content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        return content or ""

    def _ollama(self, system: str, user: str) -> str:
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        if not host.startswith("http"):
            host = "http://" + host
        data = self._post(f"{host}/api/chat", {"Content-Type": "application/json"},
                          {"model": self.model, "stream": False, "format": "json", "options": {"temperature": 0},
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        return data.get("message", {}).get("content", "")
