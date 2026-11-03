"""v0.2 tests: claim extraction, every retriever (recorded or documented-format fixtures), verdicts, fixes,
reports, docx export, CLI, API, MCP, configuration and key hygiene. Fully offline."""
import json
from pathlib import Path

import pytest

from fixture_http import FIX, FixtureHTTP, Resp, fixture_pipeline
from truthlens.claims import RuleExtractor, checkable_numbers, classify, find_citations, segment
from truthlens.config import Config, redact
from truthlens.model import Claim, Evidence
from truthlens.readers import read_text

ROOT = Path(__file__).resolve().parent.parent
PIB_MCP = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2243781"


def _claim(text, ctype="entity", nums=None, cites=None):
    return Claim(id="c1", sentence_id="s1", sentence=text, text=text, type=ctype, location="para 1",
                 numbers=nums if nums is not None else [n.raw for n in checkable_numbers(text)],
                 citations=cites if cites is not None else find_citations(text))


# ---------------------------------------------------------------- claim extraction
@pytest.mark.parametrize("text,ctype", [
    ("India's real GDP grew by 7.8% in FY 2025-26.", "numeric"),
    ("Jal Jeevan Mission was launched on 15 August 2019 by the Prime Minister.", "entity"),
    ("Policymakers should invest more in source sustainability.", "opinion"),
    ("See the release (https://www.pib.gov.in/PressReleasePage.aspx?PRID=2243781) for details on MCP.", "citation"),
    ("Coverage rose sharply, as Harris et al. (2020) show for array libraries.", "citation"),
    ("Tap water reached 82.24% of rural households [3].", "citation"),
    ("Is this true?", None),
    ("Water matters a great deal to everyone here.", None),
])
def test_classify(text, ctype):
    assert classify(text) == ctype


def test_years_dates_and_reference_numbers_are_not_statistics():
    assert checkable_numbers("The Code on Social Security, 2020 was passed on 29 September 2020 (Table 3).") == []
    assert [n.raw for n in checkable_numbers("It provides 26 weeks of paid leave.")] == ["26"]
    assert [n.raw for n in checkable_numbers("234 of the 463 item groups")] == ["234", "463"]


def test_citation_finder():
    c = find_citations("Source text (doi:10.1038/s41586-020-2649-2) and https://pib.gov.in/x.aspx?PRID=1. Also [2, 4].")
    assert "doi:10.1038/s41586-020-2649-2" in c and "https://pib.gov.in/x.aspx?PRID=1" in c and "[2, 4]" in c


def test_rule_extractor_skips_headings_and_et_al_does_not_split():
    blocks = read_text("Policy note on water\n\nNumPy is described in Harris et al. (2020), doi:10.1038/s41586-020-2649-2.")
    sents = segment(blocks)
    claims = RuleExtractor().extract(sents, blocks)
    assert len(claims) == 1 and claims[0].type == "citation"


def test_llm_extractor_validates_and_falls_back():
    from truthlens.claims import LLMExtractor

    class Fake:
        provider = "fake"

        def __init__(self, payload):
            self.payload = payload

        def complete_json(self, system, user, max_tokens=2000):
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload

    blocks = read_text("GDP grew 7.8% in 2025-26 and the PLFS was revamped in January 2025. We should celebrate.")
    sents = segment(blocks)
    good = {"claims": [{"sentence": 0, "text": "GDP grew 7.8% in 2025-26", "type": "numeric"},
                       {"sentence": 0, "text": "The PLFS was revamped in January 2025", "type": "entity"},
                       {"sentence": 1, "text": "We should celebrate", "type": "opinion"},
                       {"sentence": 9, "text": "out of range", "type": "entity"},
                       {"sentence": 0, "text": "bad type", "type": "fact"}]}
    claims = LLMExtractor(Fake(good)).extract(sents, blocks)
    assert [c.type for c in claims] == ["numeric", "entity", "opinion"]
    assert claims[0].extractor == "llm:fake"
    fb = LLMExtractor(Fake(RuntimeError("down")))
    claims = fb.extract(sents, blocks)
    assert fb.fallbacks == 1 and claims and all(c.extractor == "rules(fallback)" for c in claims)


# ---------------------------------------------------------------- MoSPI live (recorded)
def test_mospi_state_level_plfs_and_nas_growth(tmp_path, http):
    from truthlens.checker import Checker
    from truthlens.retrievers.mospi import MospiClient, MospiStore
    from truthlens.sources.curated import CuratedStore
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    store = MospiStore(CuratedStore(), MospiClient(cfg, session=http))
    ck = Checker(store=store, online=False)
    f = ck.check_text("Telangana's unemployment rate was 4.1% in 2023-24.")[0]
    assert f.verdict == "MISMATCH" and f.official["value"] == 4.8 and f.official["live_source"]
    assert "api.mospi.gov.in/api/plfs/getData" in f.official["source"]["url"] and "state_code=26" in f.official["source"]["url"]
    f = ck.check_text("The unemployment rate in rural India was 2.5% in 2023-24.")[0]
    assert f.verdict == "MATCH" and "sector_code=1" in f.official["source"]["url"]
    f = ck.check_text("Real GDP grew 7.2% in 2024-25.")[0]
    assert f.verdict == "MATCH" and f.official["live"]["agrees"] is True     # curated value, live cross-check
    rec = store.live("gdp_growth_real", "2024-25", "default")
    assert abs(rec["value"] - 7.19) < 0.01 and "computed from constant price" in rec["source"]["title"]


def test_mospi_offline_uses_cache_only(tmp_path, http):
    from truthlens.retrievers.mospi import MospiClient
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path, offline=True)
    c = MospiClient(cfg, session=http)
    assert c.plfs(3, "2023-24", state_code=26) is None and http.calls == []


def test_mospi_esankhyiki_backend_patches_the_package(tmp_path, monkeypatch):
    import sys
    import types
    from truthlens.retrievers.mospi import MospiClient
    calls = {}

    class FakeSession:
        verify = False

        def mount(self, prefix, adapter):
            calls["mount"] = prefix

    fake = types.SimpleNamespace(_client=types.SimpleNamespace(base_url="http://10.24.89.9:5000", session=FakeSession()))

    def get_data(ds, filters):
        print("noisy debug output")
        calls["ds"] = ds
        return {"data": [{"value": "3.2", "year": "2023-24"}]}
    fake.get_data = get_data
    monkeypatch.setitem(sys.modules, "esankhyiki", fake)
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    cfg.mospi_backend = "esankhyiki"
    got = MospiClient(cfg).plfs(3, "2023-24")
    assert got["value"] == 3.2 and calls["ds"] == "PLFS"
    assert fake._client.base_url == "https://api.mospi.gov.in" and fake._client.session.verify is True


# ---------------------------------------------------------------- data.gov.in
def test_datagovin_resource_map_and_key_never_in_url(tmp_path, monkeypatch):
    from truthlens.retrievers.datagovin import DataGovInRetriever
    monkeypatch.setenv("DATAGOVIN_API_KEY", "dgikey-secret-123456")
    payload = json.loads((FIX / "datagovin_resource.json").read_text())
    seen = {}

    def serve(params, headers):
        seen.update(params)
        return Resp(payload)
    http = FixtureHTTP({"https://api.data.gov.in/resource/": serve})
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    cfg.datagovin_resources = {"tap": {"id": payload["index_name"], "keywords": ["tap water"], "title": "Tap water by state"}}
    r = DataGovInRetriever(cfg, session=http)
    ev = r.retrieve(_claim("Goa has tap water in 100 per cent of rural households."))
    assert ev and "Goa" in ev[0].snippet and ev[0].official
    assert seen["api-key"] == "dgikey-secret-123456"
    assert all("dgikey" not in e.source_url and "dgikey" not in json.dumps(e.to_dict()) for e in ev)
    assert "dgikey" not in json.dumps(list((tmp_path / "datagovin").glob("*.json")) and
                                      [p.read_text() for p in (tmp_path / "datagovin").glob("*.json")])
    assert r.retrieve(_claim("Unrelated claim about steel output.")) == []


def test_datagovin_without_key_is_inert(tmp_path):
    from truthlens.retrievers.datagovin import DataGovInRetriever
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    r = DataGovInRetriever(cfg, session=FixtureHTTP())
    assert r.status()["configured"] is False


# ---------------------------------------------------------------- official documents
def test_docs_index_pdf_pages_tables_and_search(tmp_path):
    from truthlens.retrievers.docs import DocIndex, extract_pdf, index_bytes
    data = (FIX / "docs" / "nas2026.pdf").read_bytes()
    title, passages = extract_pdf(data)
    assert "NATIONAL ACCOUNTS STATISTICS" in title.upper()
    assert {p["page"] for p in passages} >= {1, 2}
    idx = DocIndex(tmp_path / "i.sqlite")
    index_bytes(idx, "https://static.pib.gov.in/x.pdf", data, "pdf", True)
    hits = idx.search("First Revised Estimates for 2024-25 sixty statements", [], k=3)
    assert hits and hits[0]["page"] == 1 and "sixty statements" in hits[0]["text"]


def test_docs_fetcher_allow_list(tmp_path):
    from truthlens.net import FetchError
    from truthlens.retrievers.docs import DocFetcher
    http = FixtureHTTP()
    f = DocFetcher(Config.load(path="/nonexistent", cache_dir=tmp_path), session=http)
    with pytest.raises(FetchError):
        f.fetch("https://example.com/report.pdf")
    data, kind = f.fetch(PIB_MCP)
    assert kind == "html" and b"Model Context Protocol" in data
    with pytest.raises(FetchError):
        f.fetch("http://127.0.0.1/admin", any_domain=True)   # private addresses are refused even for citations


def test_index_local_folder_and_cli(tmp_path, monkeypatch):
    from truthlens.cli import main
    monkeypatch.setenv("TRUTHLENS_CACHE", str(tmp_path / "c"))
    rep = tmp_path / "reports"
    rep.mkdir()
    (rep / "note.txt").write_text("State water report 2026\n\nThe state commissioned 41 new water testing laboratories in 2025-26.")
    (rep / "skip.bin").write_bytes(b"\x00")
    assert main(["index", str(rep)]) == 0
    assert main(["index", "--list"]) == 0
    from truthlens.pipeline import Pipeline
    pipe = Pipeline(Config.load(path="/nonexistent", offline=True), llm=None)
    out = pipe.run(read_text("The state commissioned 41 new water testing laboratories in 2025-26."), "t")
    c = out["claims"][0]
    assert c["verdict"] == "SUPPORTED" and c["confidence"] == "low"   # the user's own indexed reports count as evidence
    ev = next(e for e in c["evidence"] if e["retriever"] == "docs")
    assert ev["publisher"].startswith("local file") and ev["official"] is False


def test_pib_rss_parser_reports_language():
    from truthlens.retrievers.docs import PIB_RSS, pib_rss_items
    xml = ('<?xml version="1.0"?><rss><channel><item><title>Cabinet approves scheme</title>'
           '<link>https://pib.gov.in/PressReleaseIframePage.aspx?PRID=1</link></item></channel></rss>').encode()
    http = FixtureHTTP({PIB_RSS: Resp(None, 200, xml, "text/xml", PIB_RSS)})
    items, lang = pib_rss_items(http)
    assert lang == "en" and items[0]["link"].endswith("PressReleasePage.aspx?PRID=1")
    hindi = "<rss><item><title>मंत्रिमंडल ने योजना को मंजूरी दी</title><link>https://pib.gov.in/x?PRID=2</link></item></rss>".encode()
    http = FixtureHTTP({PIB_RSS: Resp(None, 200, hindi, "text/xml", PIB_RSS)})
    assert pib_rss_items(http)[1] == "hi"


# ---------------------------------------------------------------- web search
@pytest.mark.parametrize("provider,env,fixture,endpoint", [
    ("brave", "BRAVE_API_KEY", "web_brave.json", "https://api.search.brave.com/res/v1/web/search"),
    ("tavily", "TAVILY_API_KEY", "web_tavily.json", "https://api.tavily.com/search"),
    ("serper", "SERPER_API_KEY", "web_serper.json", "https://google.serper.dev/search"),
])
def test_web_search_providers_rank_official_first(tmp_path, monkeypatch, provider, env, fixture, endpoint):
    from truthlens.retrievers.web import WebSearchRetriever
    monkeypatch.setenv(env, "k-secret-abcdef")
    payload = json.loads((FIX / fixture).read_text())
    http = FixtureHTTP({endpoint: Resp(payload)})
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    w = WebSearchRetriever(cfg, session=http)
    assert w.provider == provider
    ev = w.retrieve(_claim("Tap water now reaches 82.24% of rural households under Jal Jeevan Mission."))
    assert ev and ev[0].official and "gov.in" in ev[0].source_url
    hdr = http.last_headers
    assert any("k-secret-abcdef" in str(v) for v in hdr.values())


def test_tavily_keyless_is_opt_in(tmp_path, monkeypatch):
    from truthlens.retrievers.web import WebSearchRetriever
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    assert WebSearchRetriever(cfg).provider is None
    monkeypatch.setenv("TRUTHLENS_TAVILY_KEYLESS", "1")
    payload = json.loads((FIX / "web_tavily.json").read_text())
    http = FixtureHTTP({"https://api.tavily.com/search": Resp(payload)})
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    w = WebSearchRetriever(cfg, session=http)
    assert w.provider == "tavily" and w.search("jal jeevan")
    assert http.last_headers.get("X-Tavily-Access-Mode") == "keyless"


def test_web_search_fetches_official_page_for_verbatim_passage(tmp_path, monkeypatch):
    from truthlens.retrievers.docs import DocFetcher, DocsRetriever, DocIndex
    from truthlens.retrievers.web import WebSearchRetriever
    monkeypatch.setenv("SERPER_API_KEY", "s")
    http = FixtureHTTP({"https://google.serper.dev/search": Resp(json.loads((FIX / "web_serper.json").read_text()))})
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    docs = DocsRetriever(cfg, DocIndex(tmp_path / "i.sqlite"))
    w = WebSearchRetriever(cfg, session=http, docs=docs, fetcher=DocFetcher(cfg, http))
    ev = w.retrieve(_claim("The MCP server beta included 7 key statistical products."))
    assert ev[0].kind == "passage" and "7 key statistical products" in ev[0].snippet


# ---------------------------------------------------------------- citations
def test_doi_found_not_found_and_url_support(tmp_path, http):
    pipe = fixture_pipeline(tmp_path, session=http)
    cc = pipe.citations
    assert cc.resolve_doi("10.1038/s41586-020-2649-2")["title"] == "Array programming with NumPy"
    nf = cc.resolve_doi("10.9999/fake.2026.001")
    assert nf["status"] == "not_found"
    checks, ev = cc.check(_claim(f"The MCP beta covered 12 statistical products ({PIB_MCP}).", "citation"))
    assert checks[0]["status"] == "found" and checks[0]["support"] == "number_missing" and checks[0]["numbers_missing"] == ["12"]
    checks, _ = cc.check(_claim(f"The MCP beta covered 7 statistical products ({PIB_MCP}).", "citation"))
    assert checks[0]["support"] == "supports"


def test_numbered_references_resolve_through_reference_list(tmp_path, http):
    pipe = fixture_pipeline(tmp_path, session=http)
    text = (f"The MCP server now covers 21 products on the eSankhyiki portal [1].\n\nReferences\n\n"
            f"[1] PIB, Model Context Protocol server, 23 March 2026. {PIB_MCP}")
    rep = pipe.run(read_text(text), "t")
    c = rep["claims"][0]
    assert c["citation_checks"][0]["target"] == PIB_MCP and c["verdict"] == "SUPPORTED"


def test_fake_doi_caps_at_partly(pipe):
    rep = pipe.run(read_text("Rural tap water coverage reached 82.24% by August 2026 (doi:10.9999/fake.2026.001)."), "t")
    c = rep["claims"][0]
    assert c["verdict"] == "PARTLY SUPPORTED"
    assert any(w["code"] == "citation_not_found" for w in c["warnings"])
    assert rep["summary"]["citations_not_found"] == 1


# ---------------------------------------------------------------- verdict engine
def test_numeric_claims_use_deterministic_checker_and_fix(pipe):
    rep = pipe.run(read_text("India's unemployment rate was 4.9% in 2023-24."), "t")
    c = rep["claims"][0]
    assert c["verdict"] == "CONTRADICTED" and c["confidence"] == "high" and c["method"] == "deterministic-numeric"
    assert any(w["code"] == "plfs_status" for w in c["warnings"])
    assert c["suggested_fix"] == "India's unemployment rate was 3.2% in 2023-24."
    assert "MoSPI" in c["fix_source"]


def test_pct_vs_pp_fix(pipe):
    rep = pipe.run(read_text("Female labour force participation rose from 37.0% in 2022-23 to 41.7% in 2023-24, an increase of 4.7%."), "t")
    c = rep["claims"][0]
    assert c["verdict"] == "CONTRADICTED" and "4.7 percentage points" in c["suggested_fix"]


def test_heuristic_contradiction_and_support_from_documents(pipe):
    rep = pipe.run(read_text("Jal Jeevan Mission was launched on 2 October 2014.\n\n"
                             "Jal Jeevan Mission was launched on 15 August 2019 by the Prime Minister.\n\n"
                             "We must do more for water."), "t")
    v = [c["verdict"] for c in rep["claims"]]
    assert v == ["CONTRADICTED", "SUPPORTED", "SKIPPED"]
    assert rep["claims"][0]["confidence"] == "low" and rep["claims"][0]["quotes"]
    assert rep["claims"][0]["suggested_fix"] == "Jal Jeevan Mission was launched on 15 August 2019."
    assert rep["summary"]["checkable_claims"] == 2 and rep["summary"]["verified_score"] == 15.0   # 1 low-confidence SUPPORTED (0.3) of 2


def test_no_evidence_is_unverified(pipe):
    rep = pipe.run(read_text("The Reserve Bank of India is headquartered in Mumbai."), "t")
    assert rep["claims"][0]["verdict"] == "UNVERIFIED" and rep["claims"][0]["suggested_fix"] is None


def test_combine():
    from truthlens.verdict import combine
    assert combine(["SUPPORTED", "UNVERIFIED"]) == "PARTLY SUPPORTED"
    assert combine(["SUPPORTED", "CONTRADICTED"]) == "CONTRADICTED"
    assert combine([]) == "UNVERIFIED" and combine(["SUPPORTED", "SUPPORTED"]) == "SUPPORTED"


class FakeLLM:
    provider = "fake"
    label = "fake:model"

    def __init__(self, reply):
        self.reply = reply
        self.errors = []
        self.calls = 0

    def complete_json(self, system, user, max_tokens=2000):
        self.calls += 1
        if "extract" in system.lower():
            raise RuntimeError("use rules")
        return self.reply(user) if callable(self.reply) else self.reply


def test_llm_judge_requires_verbatim_quotes(tmp_path, http):
    good = FakeLLM({"verdict": "CONTRADICTED", "quotes": [{"evidence": "E1", "quote": "Rajya Sabha"}],
                    "rationale": "The release says the information was given in the Rajya Sabha by the MoS.",
                    "corrected_sentence": "The MCP server was announced by the Minister of State in the Rajya Sabha."})
    pipe = fixture_pipeline(tmp_path / "a", llm=good, session=http)
    rep = pipe.run(read_text("The MCP server was announced by the Finance Minister in the Lok Sabha."), "t")
    c = rep["claims"][0]
    if c["evidence"] and "Rajya Sabha" in c["evidence"][0]["snippet"]:
        assert c["verdict"] == "CONTRADICTED" and c["method"] == "llm-judge:fake" and c["suggested_fix"]
    invented = FakeLLM({"verdict": "SUPPORTED", "quotes": [{"evidence": "E1", "quote": "the Finance Minister announced it"}],
                        "rationale": "made up"})
    pipe = fixture_pipeline(tmp_path / "b", llm=invented, session=http)
    c = pipe.run(read_text("The MCP server was announced by the Finance Minister in the Lok Sabha."), "t")["claims"][0]
    assert c["verdict"] == "UNVERIFIED" and "fail-closed" in c["rationale"]


def test_llm_judge_not_called_without_evidence(tmp_path, http):
    llm = FakeLLM({"verdict": "SUPPORTED", "quotes": []})
    pipe = fixture_pipeline(tmp_path, llm=llm, session=http)
    c = pipe.run(read_text("The Bank of Japan is located in Tokyo."), "t")["claims"][0]
    assert c["verdict"] == "UNVERIFIED"


def test_llm_cannot_override_resolved_numbers(tmp_path, http):
    llm = FakeLLM({"verdict": "SUPPORTED", "quotes": [{"evidence": "E2", "quote": "x"}]})
    pipe = fixture_pipeline(tmp_path, llm=llm, session=http)
    c = pipe.run(read_text("Real GDP grew 6.5% in 2024-25."), "t")["claims"][0]
    assert c["verdict"] == "CONTRADICTED" and llm.calls <= 1


@pytest.mark.parametrize("provider,url,reply", [
    ("anthropic", "https://api.anthropic.com/v1/messages", {"content": [{"type": "text", "text": '{"verdict": "UNVERIFIED", "quotes": []}'}]}),
    ("openai", "https://api.openai.com/v1/chat/completions", {"choices": [{"message": {"content": '{"verdict": "UNVERIFIED"}'}}]}),
    ("ollama", "http://localhost:11434/api/chat", {"message": {"content": '```json\n{"verdict": "UNVERIFIED"}\n```'}}),
])
def test_llm_client_wire_formats(monkeypatch, provider, url, reply):
    from truthlens.llm import LLMClient
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-0001")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-secret-0002")
    http = FixtureHTTP({url: Resp(reply)})
    c = LLMClient(provider, session=http)
    assert c.complete_json("sys", "user") == {"verdict": "UNVERIFIED", "quotes": []} or c.complete_json("s", "u")["verdict"] == "UNVERIFIED"
    if provider == "anthropic":
        assert http.last_headers["x-api-key"] == "sk-ant-secret-0001" and http.last_json["system"] == "sys"
    if provider == "openai":
        assert http.last_headers["Authorization"] == "Bearer sk-oai-secret-0002"


def test_llm_errors_are_redacted(monkeypatch):
    from truthlens.llm import LLMClient, LLMError
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-0001")
    http = FixtureHTTP({"https://api.anthropic.com/v1/messages": Resp({"error": "bad key sk-ant-secret-0001"}, 401)})
    c = LLMClient("anthropic", session=http)
    with pytest.raises(LLMError) as e:
        c.complete_json("s", "u")
    assert "sk-ant-secret-0001" not in str(e.value) and "sk-ant-secret-0001" not in " ".join(c.errors)


# ---------------------------------------------------------------- config and key hygiene
def test_config_refuses_keys_in_toml(tmp_path):
    p = tmp_path / "truthlens.toml"
    p.write_text('[llm]\nprovider = "anthropic"\napi_key = "nope"\n')
    with pytest.raises(ValueError):
        Config.load(str(p))


def test_config_toml_and_env(tmp_path, monkeypatch):
    p = tmp_path / "truthlens.toml"
    p.write_text('[truthlens]\nretrievers = ["curated", "docs"]\n[docs]\nallowed_domains = ["example.org"]\n'
                 '[datagovin.resources.x]\nid = "0b6a0c4e-0000-4000-8000-000000000001"\nkeywords = ["tap"]\n')
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-secret-0002")
    cfg = Config.load(str(p))
    assert cfg.retrievers == ["curated", "docs"] and "example.org" in cfg.allowed_domains
    assert cfg.resolved_llm() == "openai" and "x" in cfg.datagovin_resources
    pub = json.dumps(cfg.public())
    assert "sk-oai-secret-0002" not in pub and '"OPENAI_API_KEY": true' in pub
    assert redact("error with sk-oai-secret-0002 and api-key=abc123") == "error with [redacted] and api-key=[redacted]"


def test_reports_never_contain_keys(tmp_path, monkeypatch, http):
    monkeypatch.setenv("BRAVE_API_KEY", "brave-secret-999999")
    monkeypatch.setenv("DATAGOVIN_API_KEY", "dgi-secret-888888")
    from truthlens.report_v2 import to_html, to_json, to_markdown
    pipe = fixture_pipeline(tmp_path, session=http, search_provider="none")
    rep = pipe.run(read_text("Real GDP grew 7.8% in 2025-26."), "t")
    for body in (to_json(rep), to_html(rep), to_markdown(rep)):
        assert "brave-secret" not in body and "dgi-secret" not in body


# ---------------------------------------------------------------- reports, docx, CLI, API, MCP
def test_v2_reports_and_docx_export(tmp_path, http):
    import docx
    from truthlens.docx_export import export_docx
    from truthlens.readers import read_file
    from truthlens.report_v2 import to_html, to_markdown
    src = ROOT / "samples" / "sample_policy_note.docx"
    pipe = fixture_pipeline(tmp_path, session=http)
    rep = pipe.run(read_file(src), src.name)
    html = to_html(rep)
    assert html.startswith("<!doctype html>") and "<script" not in html and "@media print" in html
    assert 'class="con"' in html and "Verified score" in html and "Suggested:" in html
    md = to_markdown(rep)
    assert "Verified score" in md and "| # | Where | Type | Verdict |" in md
    out = tmp_path / "corrected.docx"
    res = export_docx(rep, str(out), str(src))
    assert res["annotated"] >= 3 and res["comments"]
    d = docx.Document(str(out))
    body = "\n".join(p.text for p in d.paragraphs)
    assert "[suggested:" in body
    assert len(list(d.comments)) >= 3


def test_docx_export_for_text_input(tmp_path, pipe):
    import docx
    from truthlens.docx_export import export_docx
    rep = pipe.run(read_text("Real GDP grew 6.5% in 2024-25. We should grow faster."), "t")
    out = tmp_path / "c.docx"
    export_docx(rep, str(out))
    assert "[suggested:" in "\n".join(p.text for p in docx.Document(str(out)).paragraphs)


def test_cli_v2_json_docx_and_strict(tmp_path):
    from truthlens.cli import main
    src = ROOT / "samples" / "sample_policy_note.docx"
    out = tmp_path / "r.json"
    assert main(["check", str(src), "-f", "json", "-o", str(out), "--offline", "--docx-out", str(tmp_path / "c.docx")]) == 0
    rep = json.loads(out.read_text())
    assert rep["version"] == __import__("truthlens").__version__ and rep["summary"]["checkable_claims"] > 5 and rep["findings"]
    assert (tmp_path / "c.docx").exists()
    assert main(["check", "--text", "Real GDP grew 6.5% in 2024-25.", "--offline", "--strict", "-o", str(tmp_path / "x.md")]) == 1


def test_cli_numbers_only_is_v01(capsys):
    from truthlens.cli import main
    assert main(["check", "--text", "WPI inflation was 2.3% in 2024-25.", "-f", "json", "--offline", "--numbers-only"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["tool"] == "TruthLens India" and rep["findings"][0]["verdict"] == "MATCH"


def test_cli_doctor_and_sources_never_print_keys(capsys, monkeypatch):
    from truthlens.cli import main
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-0001")
    assert main(["doctor", "--offline"]) == 0
    assert main(["sources", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "ANTHROPIC_API_KEY=yes" in out and "sk-ant-secret" not in out and "curated" in out


def test_api_upload_page_and_v2(monkeypatch):
    from fastapi.testclient import TestClient
    import truthlens.api as api
    monkeypatch.setattr(api, "ONLINE", False)
    monkeypatch.setattr(api, "_PIPE", None)
    c = TestClient(api.app)
    page = c.get("/")
    assert page.status_code == 200 and "Drop a .docx" in page.text and "Try the sample" in page.text
    r = c.post("/check", json={"type": "text", "content": "Real GDP grew 6.5% in 2024-25. We should act faster on this."})
    j = r.json()
    assert j["claims"][0]["verdict"] == "CONTRADICTED" and j["summary"]["skipped_opinions"] == 1
    assert c.get("/sources").json()["sources"]
    r = c.post("/check", json={"type": "text", "content": "Real GDP grew 6.5% in 2024-25.", "numbers_only": True})
    assert r.json()["tool"] == "TruthLens India"


def test_mcp_check_claims(monkeypatch, tmp_path, http):
    import truthlens.mcp_server as m
    monkeypatch.setattr(m, "_pipe", fixture_pipeline(tmp_path, session=http))
    out = m.check_claims("India's unemployment rate was 4.9% in 2023-24.")
    assert out["claims"][0]["verdict"] == "CONTRADICTED" and out["claims"][0]["suggested_fix"]


# ---------------------------------------------------------------- labelled sets
@pytest.mark.parametrize("name,min_acc", [("testset_v2.jsonl", 0.9), ("testset_v2_holdout.jsonl", 0.6)])
def test_v2_testsets(tmp_path, http, name, min_acc):
    from truthlens.evaluate import evaluate_v2, load_testset
    path = ROOT / "data" / name
    rows = load_testset(path)
    assert len(rows) >= (40 if name == "testset_v2.jsonl" else 25)
    assert sum(1 for r in rows if r["type"] != "numeric") >= (20 if name == "testset_v2.jsonl" else 12)
    res = evaluate_v2(path, fixture_pipeline(tmp_path, session=http))
    print(f"\n{name}: {res['correct']}/{res['n']} = {res['accuracy']:.1%}; unsafe SUPPORTED {res['unsafe_supported']}")
    assert res["accuracy"] >= min_acc
    assert res["unsafe_supported"] == 0          # fail-closed: never SUPPORTED on a false or unknowable claim
    assert res["type_accuracy"] >= 0.95


def test_v3_adversarial_set(tmp_path, http):
    """Negation, extra claims, direction words, prompt injection and SSRF-style citations (v0.3)."""
    from truthlens.evaluate import evaluate_v2, load_testset
    path = ROOT / "data" / "testset_v3_adversarial.jsonl"
    assert len(load_testset(path)) >= 30
    res = evaluate_v2(path, fixture_pipeline(tmp_path, session=http))
    assert res["accuracy"] >= 0.85 and res["unsafe_supported"] == 0
