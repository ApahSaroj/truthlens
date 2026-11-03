"""Bring-your-own-key LLM client: Anthropic, OpenAI (or any OpenAI-compatible server) and local Ollama.

Only used for (1) claim extraction and (2) judging non-numeric claims against retrieved evidence.
Keys come from the environment at call time and are never logged or returned. Every call asks for
JSON and the caller validates it; anything malformed is treated as "no answer" (fail closed).
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

import requests

from .config import Config, redact

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-4o-mini", "ollama": "llama3.1"}


class LLMError(Exception):
    pass


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
        if provider not in DEFAULT_MODELS:
            raise LLMError(f"unknown LLM provider: {provider}")
        self.provider = provider
        env_model = os.environ.get(f"TRUTHLENS_{provider.upper()}_MODEL")
        self.model = model or env_model or DEFAULT_MODELS[provider]
        self.timeout = timeout
        self.session = session or requests.Session()
        self.calls = 0
        self.errors: list[str] = []

    @classmethod
    def from_config(cls, cfg: Config, session: Optional[requests.Session] = None) -> Optional["LLMClient"]:
        p = cfg.resolved_llm()
        if not p or cfg.offline:
            return None
        if p == "anthropic" and not cfg.secret("ANTHROPIC_API_KEY"):
            return None
        if p == "openai" and not cfg.secret("OPENAI_API_KEY"):
            return None
        if p == "ollama" and not os.environ.get("OLLAMA_HOST"):
            os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
        return cls(p, cfg.llm_model, session=session)

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    def complete_json(self, system: str, user: str, max_tokens: int = 2000):
        self.calls += 1
        try:
            if self.provider == "anthropic":
                text = self._anthropic(system, user, max_tokens)
            elif self.provider == "openai":
                text = self._openai(system, user, max_tokens)
            else:
                text = self._ollama(system, user)
            return _extract_json(text)
        except LLMError as e:
            self.errors.append(str(e))
            raise
        except Exception as e:
            msg = redact(f"{self.provider} call failed: {type(e).__name__}: {e}")
            self.errors.append(msg)
            raise LLMError(msg) from None

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        r = self.session.post(url, headers=headers, json=body, timeout=self.timeout)
        if r.status_code >= 400:
            raise LLMError(f"{self.provider} HTTP {r.status_code}: {redact(r.text[:200])}")
        return r.json()

    def _anthropic(self, system: str, user: str, max_tokens: int) -> str:
        key = Config.secret("ANTHROPIC_API_KEY") or ""
        data = self._post(ANTHROPIC_URL, {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION,
                                          "content-type": "application/json"},
                          {"model": self.model, "max_tokens": max_tokens, "temperature": 0, "system": system,
                           "messages": [{"role": "user", "content": user}]})
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    def _openai(self, system: str, user: str, max_tokens: int) -> str:
        key = Config.secret("OPENAI_API_KEY") or ""
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        data = self._post(f"{base}/chat/completions",
                          {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          {"model": self.model, "temperature": 0, "max_tokens": max_tokens,
                           "response_format": {"type": "json_object"},
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        return data["choices"][0]["message"]["content"]

    def _ollama(self, system: str, user: str) -> str:
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        if not host.startswith("http"):
            host = "http://" + host
        data = self._post(f"{host}/api/chat", {"Content-Type": "application/json"},
                          {"model": self.model, "stream": False, "format": "json", "options": {"temperature": 0},
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        return data.get("message", {}).get("content", "")
