"""Bring-your-own-key: per-request keys are used, scoped, and never leak."""
import os

from truthlens.config import Config, SECRET_ENV, redact, use_keys


def test_use_keys_scoped_and_redacted(monkeypatch):
    for k in SECRET_ENV:
        monkeypatch.delenv(k, raising=False)
    assert Config.secret("ANTHROPIC_API_KEY") is None
    with use_keys({"ANTHROPIC_API_KEY": "sk-ant-test-123456", "NOT_A_SECRET": "x"}):
        assert Config.secret("ANTHROPIC_API_KEY") == "sk-ant-test-123456"
        assert Config.load(offline=True).resolved_llm() == "anthropic"
        assert "sk-ant-test-123456" not in redact("boom sk-ant-test-123456 boom")
        assert "NOT_A_SECRET" not in os.environ
    assert Config.secret("ANTHROPIC_API_KEY") is None


def test_api_key_field_not_in_report(monkeypatch):
    from fastapi.testclient import TestClient
    import truthlens.api as api
    for k in SECRET_ENV:
        monkeypatch.delenv(k, raising=False)
    seen = {}

    class FakePipe:
        def __init__(self, cfg):
            seen["provider"] = cfg.resolved_llm()
            seen["key"] = Config.secret("OPENAI_API_KEY")

        def run(self, blocks, name, meta=None, **kw):     # v0.5.2: mode=
            return {"tool": "TruthLens", "input": name, "summary": {}}

    import truthlens.pipeline as pl
    monkeypatch.setattr(pl, "Pipeline", FakePipe)
    c = TestClient(api.app)
    r = c.post("/check", json={"type": "text", "content": "GDP grew 7.2% in 2024-25.",
                               "llm_provider": "openai", "llm_key": "sk-user-secret-999"})
    assert r.status_code == 200
    assert seen == {"provider": "openai", "key": "sk-user-secret-999"}
    assert "sk-user-secret-999" not in r.text
    assert Config.secret("OPENAI_API_KEY") is None
    page = c.get("/").text
    assert "Optional: your own AI key" in page   # v0.5.3 copy (the NDAP token box was removed) and 'type="password"' in page
