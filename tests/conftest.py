import json
import sys
from pathlib import Path

import pytest

from truthlens.checker import Checker
from truthlens.sources.worldbank import WorldBankClient

FIX = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parent.parent

import requests as _requests  # noqa: E402
REAL_SESSION_GET = _requests.Session.get   # saved before the autouse fixture blocks the network


class FixtureResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FixtureSession:
    """Stands in for requests.Session: serves recorded World Bank responses, never touches the network."""

    def __init__(self):
        self.calls = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append(url)
        code = url.split("/indicator/")[1].split("?")[0]
        f = FIX / f"wb_{code}.json"
        if not f.exists():
            return FixtureResponse({"message": "not found"}, status=404)
        return FixtureResponse(json.loads(f.read_text()))


@pytest.fixture
def wb(tmp_path):
    return WorldBankClient(cache_dir=tmp_path / "wbcache", session=FixtureSession())


@pytest.fixture
def checker(wb):
    return Checker(worldbank=wb)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch, tmp_path):
    """Block real HTTP in every test; also point the default cache at a temp dir."""
    monkeypatch.setenv("TRUTHLENS_CACHE", str(tmp_path / "cache"))
    # v0.5: no plug-in sources and a private data dir (sync state, corrections) unless a test sets them
    monkeypatch.setenv("TRUTHLENS_SOURCES_DIR", str(tmp_path / "sources.d"))
    monkeypatch.setenv("TRUTHLENS_DATA_DIR", str(tmp_path / "data"))
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_HOST", "BRAVE_API_KEY", "TAVILY_API_KEY", "SERPER_API_KEY",
              "DATAGOVIN_API_KEY", "S2_API_KEY", "OPENALEX_API_KEY", "TRUTHLENS_LLM", "TRUTHLENS_SEARCH", "TRUTHLENS_TAVILY_KEYLESS", "TRUTHLENS_CONFIG",
              "TRUTHLENS_OFFLINE"):
        monkeypatch.delenv(k, raising=False)
    import requests

    def _blocked(*a, **k):
        raise RuntimeError("network disabled in tests")
    monkeypatch.setattr(requests.Session, "get", _blocked)
    monkeypatch.setattr(requests.Session, "post", _blocked)
    monkeypatch.setattr(requests, "get", _blocked)
    monkeypatch.setattr(requests, "post", _blocked)


@pytest.fixture
def http():
    from fixture_http import FixtureHTTP
    return FixtureHTTP()


@pytest.fixture
def pipe(tmp_path, http):
    from fixture_http import fixture_pipeline
    return fixture_pipeline(tmp_path / "pipe", session=http)
