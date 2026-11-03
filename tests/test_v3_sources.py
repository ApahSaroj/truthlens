"""v0.3 live sources, tested offline.

Recorded responses (tests/fixtures/live/recorded.json, captured 1 Nov 2026) serve MoSPI eSankhyiki, sansad.in
(Lok Sabha), the Rajya Sabha API and answer PDFs, the PIB English feed and the Economic Survey listing.
data.gov.in was unreachable from our network, so its responses are SYNTHETIC fixtures
(tests/fixtures/datagovin/*.json, every title ends in "(synthetic test fixture)"). See SYNTHETIC_FIXTURES.md.
"""
import json
from pathlib import Path

import pytest

from fixture_http import FixtureHTTP, Resp
from truthlens.claims import checkable_numbers
from truthlens.config import Config
from truthlens.model import Claim, Evidence

FIX = Path(__file__).parent / "fixtures"
DG = FIX / "datagovin"
A1 = "0b6a0c4e-0000-4000-8000-0000000000a1"   # synthetic: 31-03-2025 snapshot, Bihar 95.6
A2 = "0b6a0c4e-0000-4000-8000-0000000000a2"   # synthetic: 31-03-2026 snapshot, Bihar 97.1


def _cfg(tmp_path, **over):
    return Config.load(path="/nonexistent", cache_dir=Path(tmp_path), **over)


def _claim(text, type_="entity", numbers=None):
    return Claim(id="c1", sentence_id="s1", sentence=text, text=text, type=type_, location="p1",
                 numbers=numbers if numbers is not None else [n.raw for n in checkable_numbers(text)])


def _dg_http():
    """SYNTHETIC data.gov.in responses (documented /lists and /resource format)."""
    lists = json.loads((DG / "lists_page1.json").read_text())
    extra = {"https://api.data.gov.in/lists": Resp(lists),
             f"https://api.data.gov.in/resource/{A1}": Resp(json.loads((DG / "resource_a1_2025.json").read_text())),
             f"https://api.data.gov.in/resource/{A2}": Resp(json.loads((DG / "resource_a2_2026.json").read_text()))}
    return FixtureHTTP(extra)


def test_synthetic_datagovin_fixtures_are_marked():
    for f in DG.glob("*.json"):
        d = json.loads(f.read_text())
        titles = [d.get("title")] if "title" in d else [r["title"] for r in d["records"]]
        assert all("(synthetic test fixture)" in t for t in titles), f.name
    assert "synthetic" in (FIX / "SYNTHETIC_FIXTURES.md").read_text().lower()


# ----------------------------------------------------------------------------------------------- planner
ALL = {"docs", "pib", "parliament", "reports", "openalex", "web", "datagovin", "mospi-catalog", "datagovin-catalog"}


def test_planner_routes_numbers_to_official_data_first():
    from truthlens.planner import plan_claim
    p = plan_claim(_claim("Average monthly per capita consumption expenditure in rural Bihar was ₹3,670 in 2023-24.",
                          "numeric"), ALL)
    assert p.data_matchers == ["mospi-catalog", "datagovin-catalog"]
    assert p.geography == "Bihar" and p.period == ["2023-24"] and p.unit == "₹"
    assert p.routes[0] == "docs" and "parliament" in p.routes and "pib" not in p.routes and "openalex" not in p.routes


def test_planner_routes_scheme_study_and_report_claims():
    from truthlens.planner import plan_claim
    scheme = plan_claim(_claim("The Jal Jeevan Mission was launched in August 2019."), ALL)
    assert {"pib", "parliament"} <= set(scheme.routes) and not scheme.data_matchers
    study = plan_claim(_claim("A 2026 study of 926 households in Samastipur, Bihar found that 84.9 per cent had a "
                              "functional tap connection.", "numeric"), ALL)
    assert "openalex" in study.routes and study.geography == "Bihar"
    report = plan_claim(_claim("The Economic Survey says growth will stay strong."), ALL)
    assert "reports" in report.routes


def test_planner_only_routes_to_available_sources():
    from truthlens.planner import plan_claim
    p = plan_claim(_claim("India had 1,168 universities in 2021-22.", "numeric"), {"docs"})
    assert p.routes == ["docs"] and p.data_matchers == []
    assert plan_claim(_claim("Opinion sentence about the mission.", "opinion", numbers=["5"]), ALL).data_matchers == []


# ------------------------------------------------------------------------------------- freshness (tables)
ROWS = [{"state": "All India", "year": "2022-23", "sector": "Total", "value": "41.3"},
        {"state": "All India", "year": "2023-24", "sector": "Total", "value": "45.2"}]
SRC = {"url": "https://example.gov.in/t", "title": "T", "publisher": "P", "published": "2026-01-01", "as_of": "x"}


def _rows_match(text):
    from truthlens.retrievers.tables import match_rows
    return match_rows(text, checkable_numbers(text), ROWS, label="Labour force participation rate", source=SRC,
                      indicator_id="t", min_relevance=0.3)


def test_freshness_older_figure_without_period_is_superseded():
    [f] = _rows_match("The labour force participation rate was 41.3%.")
    assert f["verdict"] == "CLOSE" and f["reason"].startswith("Superseded")
    assert f["official"]["value"] == 45.2 and f["official"]["period"] == "2023-24"
    assert any(w["code"] == "superseded" for w in f["warnings"])


def test_freshness_explicit_period_and_latest_figure_match():
    [f] = _rows_match("The labour force participation rate was 41.3% in 2022-23.")
    assert f["verdict"] == "MATCH" and not f["warnings"]
    [g] = _rows_match("The labour force participation rate was 45.2%.")
    assert g["verdict"] == "MATCH"


def test_named_value_column_is_used_only_when_unambiguous():
    from truthlens.retrievers.tables import row_value
    assert row_value({"state_name": "Bihar", "households_with_tap_water____": "97.1"}) == ("households_with_tap_water____", 97.1)
    assert row_value({"state_name": "Bihar", "a": "1", "b": "2"}) is None      # two numeric columns: fail closed


def test_dedupe_findings_keeps_decided_figure():
    from truthlens.retrievers.tables import dedupe_findings
    fs = [{"claimed": "5", "verdict": "UNVERIFIED"}, {"claimed": "5", "verdict": "CLOSE"}, {"claimed": "7", "verdict": "UNVERIFIED"},
          {"claimed": "7", "verdict": "UNVERIFIED"}]
    assert [f["verdict"] for f in dedupe_findings(fs)] == ["CLOSE", "UNVERIFIED"]


# ------------------------------------------------------------------------------------------ MoSPI catalogue
@pytest.fixture
def mospi(tmp_path):
    from truthlens.retrievers.mospi_catalog import MospiCatalog
    return MospiCatalog(_cfg(tmp_path), FixtureHTTP())


@pytest.mark.parametrize("text,verdict,official", [
    ("Average monthly per capita consumption expenditure in rural India was ₹4,122 in 2023-24.", "MATCH", 4122),
    ("Kerala's sex ratio was 1,084 in 2011.", "MATCH", 1084),
    ("Bihar's sex ratio was 950 in 2011.", "MISMATCH", 918),
    ("India had 1,168 universities in 2021-22.", "MATCH", 1168),
])
def test_mospi_generic_matcher_on_recorded_api(mospi, text, verdict, official):
    fs = mospi.match(text, checkable_numbers(text))
    assert len(fs) == 1 and fs[0]["verdict"] == verdict and fs[0]["official"]["value"] == official
    assert fs[0]["official"]["source"]["url"].startswith("https://api.mospi.gov.in/")
    assert "retrieved" in fs[0]["official"]["as_of"] and "latest period in API" in fs[0]["official"]["as_of"]


@pytest.mark.parametrize("text", [
    "Average monthly per capita consumption expenditure was ₹5,000 in 2023-24.",   # rural/urban/imputed variants
    "Sex ratio was 950.",                                                         # no geography, no year
])
def test_mospi_generic_matcher_fails_closed_on_ambiguity(mospi, text):
    fs = mospi.match(text, checkable_numbers(text))
    assert fs and all(f["verdict"] == "UNVERIFIED" for f in fs) and len(fs) == 1


def test_mospi_catalog_no_candidate_and_offline(tmp_path, mospi):
    from truthlens.retrievers.mospi_catalog import MospiCatalog
    assert mospi.match("The figure was 42 in 2023-24.", checkable_numbers("The figure was 42 in 2023-24.")) == []
    off = MospiCatalog(_cfg(tmp_path / "off", offline=True), FixtureHTTP())
    assert off.unavailable() and off.indicators()[-1]["dataset"] == "IIP_ANNUAL"   # static only, no request
    assert not off.session.calls


# ------------------------------------------------------------------------------------------------ Parliament
def test_lok_sabha_recent_from_sansad_in(tmp_path):
    from truthlens.retrievers.parliament import ParliamentRetriever
    p = ParliamentRetriever(_cfg(tmp_path), FixtureHTTP())
    ev = p.retrieve(_claim("In a Lok Sabha answer on 6 August 2026, the Ministry of Jal Shakti addressed the extension "
                           "of the Jal Jeevan Mission."))
    assert ev and ev[0].source_type == "Lok Sabha" and ev[0].as_of == "2026-08-06"
    assert ev[0].snippet.startswith("Lok Sabha Unstarred Question No. 3018 (Extension of Jal Jeevan Mission), answered on "
                                    "6 August 2026 by the Ministry of Jal Shakti.")
    assert ev[0].source_url.startswith("https://sansad.in/getFile/") and ev[0].to_dict()["source_type"] == "Lok Sabha"
    assert not any("rajyasabha" in c for c in p.session.calls)       # 'Lok Sabha' in the claim: RS not queried
    # the OpenSansad (Hugging Face) query for this claim was not recorded: it fails closed and is logged
    assert any("huggingface" in e for e in p.errors)


def test_rajya_sabha_from_api_and_pdf(tmp_path):
    from truthlens.retrievers.parliament import ParliamentRetriever
    p = ParliamentRetriever(_cfg(tmp_path), FixtureHTTP())
    ev = p.retrieve(_claim("The Rajya Sabha took up a question on the Jal Jeevan Mission in Tamil Nadu in March 2025."))
    assert ev[0].source_type == "Rajya Sabha" and ev[0].meta["question_no"] == 1840 and ev[0].as_of == "2025-03-17"
    assert "JAL JEEVAN MISSION IN TAMIL NADU" in ev[0].snippet and "bucketapi.rajyasabha.digital" in ev[0].source_url
    assert not any("sansad.in/api_ls" in c for c in p.session.calls)


def test_parliament_query_terms_and_house_badge_fallback():
    from truthlens.retrievers.parliament import query_terms
    q = query_terms("The Jal Jeevan Mission is implemented by the Ministry of Education.")
    assert q[:3] == ["jal", "jeevan", "mission"] and "ministry" not in q
    e = Evidence(retriever="parliament", source_url="https://bucketapi.rajyasabha.digital/x.pdf", title="", snippet="")
    assert e.to_dict()["source_type"] == "Rajya Sabha"


def test_parliament_offline_returns_nothing(tmp_path):
    from truthlens.retrievers.parliament import ParliamentRetriever
    p = ParliamentRetriever(_cfg(tmp_path, offline=True), FixtureHTTP())
    assert p.retrieve(_claim("The Jal Jeevan Mission was launched in August 2019.")) == [] and not p.session.calls


# ------------------------------------------------------------------------------------- PIB, reports, OpenAlex
class _FakeFetcher:
    """Serves one PIB release page. SYNTHETIC HTML written for this test (the feed itself is recorded)."""
    HTML = (b"<html><head><title>Union Minister for Railways Flags Off Bengaluru-Mumbai Vande Bharat Sleeper Express Train"
            b"</title></head><body><p>Posted On: 31 OCT 2026 by PIB Delhi</p><p>The Union Minister for Railways flagged off "
            b"the Bengaluru-Mumbai Vande Bharat Sleeper Express train on 31 October 2026. (synthetic test fixture)</p>"
            b"</body></html>")

    def __init__(self):
        self.urls = []

    def fetch(self, url, any_domain=False):
        self.urls.append(url)
        return self.HTML, "html"


def test_pib_english_feed_and_release(tmp_path):
    from truthlens.retrievers.docs import DocIndex, DocsRetriever
    from truthlens.retrievers.live_docs import PIBRetriever
    cfg = _cfg(tmp_path)
    fetcher = _FakeFetcher()
    pib = PIBRetriever(cfg, FixtureHTTP(), docs=DocsRetriever(cfg, DocIndex(tmp_path / "i.sqlite")), fetcher=fetcher)
    items = pib.feed()                         # recorded: 301 pib.gov.in -> www.pib.gov.in, English
    assert len(items) == 20 and all(it["lang"] == "en" for it in items)
    assert all("PressReleasePage.aspx?PRID=" in it["link"] for it in items)
    ev = pib.retrieve(_claim("The Railways Minister flagged off the Bengaluru-Mumbai Vande Bharat Sleeper Express train."))
    assert fetcher.urls[0] == "https://pib.gov.in/PressReleasePage.aspx?PRID=2331297" and len(fetcher.urls) <= pib.max_fetch
    assert ev and ev[0].source_type == "PIB" and ev[0].retriever == "pib"


def test_pib_unrelated_claim_fetches_nothing(tmp_path):
    from truthlens.retrievers.docs import DocIndex, DocsRetriever
    from truthlens.retrievers.live_docs import PIBRetriever
    cfg = _cfg(tmp_path)
    fetcher = _FakeFetcher()
    pib = PIBRetriever(cfg, FixtureHTTP(), docs=DocsRetriever(cfg, DocIndex(tmp_path / "i.sqlite")), fetcher=fetcher)
    assert pib.retrieve(_claim("Groundwater levels in Punjab fell sharply last decade.")) == [] and fetcher.urls == []


def test_reports_listing_and_pdf_from_economic_survey(tmp_path):
    from truthlens.retrievers.docs import DocFetcher, DocIndex, DocsRetriever
    from truthlens.retrievers.live_docs import ReportsRetriever
    cfg = _cfg(tmp_path)
    http = FixtureHTTP()
    docs = DocsRetriever(cfg, DocIndex(tmp_path / "i.sqlite"))
    rep = ReportsRetriever(cfg, http, docs=docs, fetcher=DocFetcher(cfg, http), max_fetch=1)
    rep.pages = ["https://www.indiabudget.gov.in/economicsurvey/"]
    links = rep.links(rep.pages[0])
    assert any(ln["url"].endswith("/doc/stat/tab8.8.pdf") and "Child Sex Ratio" in ln["text"] for ln in links)
    rep.retrieve(_claim("Economic Survey table: population under different age groups and child sex ratio in 2001 and 2011."))
    assert docs.index.has("https://www.indiabudget.gov.in/economicsurvey/doc/stat/tab8.8.pdf")


def test_openalex_recorded_search_and_rate_limit(tmp_path):
    from truthlens.retrievers.live_docs import OpenAlexRetriever
    payload = json.loads((FIX / "live" / "openalex_search_jjm.json").read_text())
    oa = OpenAlexRetriever(_cfg(tmp_path), FixtureHTTP({"https://api.openalex.org/works": Resp(payload)}))
    ev = oa.retrieve(_claim("A 2026 study of households in Bihar found functional tap water access under Jal Jeevan Mission."))
    assert ev and ev[0].source_type == "Paper" and ev[0].source_url.startswith("https://doi.org/")
    limited = OpenAlexRetriever(_cfg(tmp_path / "b"), FixtureHTTP())     # recorded HTTP 429 for this query
    assert limited.retrieve(_claim("A 2026 study of 926 households in Samastipur, Bihar found that 84.9 per cent had a "
                                   "functional tap connection.", "numeric")) == []


# ---------------------------------------------------------------------------- data.gov.in (SYNTHETIC fixtures)
@pytest.fixture
def dg(tmp_path, monkeypatch):
    from truthlens.retrievers.datagovin import CatalogIndex, DataGovInClient, DataGovInMatcher, sync_catalog
    monkeypatch.setenv("DATAGOVIN_API_KEY", "dgtestkey0001")
    cfg = _cfg(tmp_path)
    http = _dg_http()
    client = DataGovInClient(cfg, http)
    index = CatalogIndex(tmp_path / "datagovin_catalog.sqlite")
    res = sync_catalog(client, index)
    return DataGovInMatcher(cfg, client, index), http, res


def test_datagovin_catalogue_sync_and_search(dg):
    m, http, res = dg
    assert res["indexed"] == 3 and res["total_reported"] == 3 and m.index.count() == 3
    hits = m.candidates("households with tap water connections in Bihar")
    assert {h["id"] for h in hits} == {A1, A2} and all(h["cover"] >= 0.3 for h in hits)
    assert m.candidates("rainfall in sub-divisions")[0]["id"].endswith("b1")
    assert m.candidates("steel production tonnes") == []
    assert m.index.meta("synced_at")
    # the key is sent to data.gov.in only, and never cached
    assert any("api-key=dgtestkey0001" in c for c in http.calls)
    cached = " ".join(p.read_text() for p in (m.cfg.cache_dir / "datagovin").glob("*.json"))
    assert "dgtestkey0001" not in cached


@pytest.mark.parametrize("text,verdict,value", [
    ("In Bihar, 97.1% of households had tap water connections.", "MATCH", 97.1),
    ("In Bihar, 95.6% of households had tap water connections.", "CLOSE", 97.1),             # superseded
    ("In Bihar, 95.6% of households had tap water connections as on 31-03-2025.", "MATCH", 95.6),
    ("In Bihar, 90% of households had tap water connections.", "UNVERIFIED", None),
])
def test_datagovin_row_matching_and_freshness(dg, text, verdict, value):
    m, _, _ = dg
    fs = m.match(text, checkable_numbers(text))
    assert len(fs) == 1 and fs[0]["verdict"] == verdict
    if value is not None:
        assert fs[0]["official"]["value"] == value
    if verdict == "CLOSE":
        assert fs[0]["reason"].startswith("Matches an older release") and fs[0]["warnings"][0]["code"] == "superseded"
        assert fs[0]["official"]["as_of"] == "updated on 2026-04-10"


def test_datagovin_matcher_without_key_or_index(tmp_path):
    from truthlens.retrievers.datagovin import CatalogIndex, DataGovInClient, DataGovInMatcher
    cfg = _cfg(tmp_path)
    m = DataGovInMatcher(cfg, DataGovInClient(cfg, FixtureHTTP()), CatalogIndex(tmp_path / "c.sqlite"))
    assert m.unavailable() == "skipped: needs a free data.gov.in key"
    t = "In Bihar, 97.1% of households had tap water connections."
    assert m.match(t, checkable_numbers(t)) == []


def test_datagovin_sample_key_is_opt_in(tmp_path, monkeypatch):
    from truthlens.retrievers.datagovin import SAMPLE_KEY, DataGovInClient
    c = DataGovInClient(_cfg(tmp_path), FixtureHTTP())
    assert c.key is None
    monkeypatch.setenv("TRUTHLENS_DATAGOVIN_SAMPLE_KEY", "1")
    assert c.key == SAMPLE_KEY and c.using_sample_key


def test_datagovin_superseded_through_pipeline(tmp_path, monkeypatch):
    from fixture_http import fixture_pipeline
    from truthlens.readers import read_text
    from truthlens.retrievers.datagovin import CatalogIndex, DataGovInClient, sync_catalog
    monkeypatch.setenv("DATAGOVIN_API_KEY", "dgtestkey0001")
    http = _dg_http()
    pipe = fixture_pipeline(tmp_path / "p", session=http)
    sync_catalog(DataGovInClient(pipe.cfg, http), CatalogIndex(pipe.cfg.cache_dir / "datagovin_catalog.sqlite"))
    rep = pipe.run(read_text("In Bihar, 95.6% of households had tap water connections."), "t")
    c = rep["claims"][0]
    assert c["verdict"] == "PARTLY SUPPORTED"
    assert any(w["code"] == "superseded" for w in c["warnings"])
    ev = [e for e in c["evidence"] if e["source_type"] == "data.gov.in"]
    assert ev and ev[0]["as_of"] == "updated on 2026-04-10"
    assert "dgtestkey0001" not in json.dumps(rep)


# ----------------------------------------------------------------------------------------------------- CLI
def test_cli_datagov_sync_search_status(tmp_path, monkeypatch, capsys):
    import truthlens.retrievers.datagovin as dgmod
    from truthlens import cli
    monkeypatch.setenv("TRUTHLENS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("DATAGOVIN_API_KEY", "dgtestkey0001")
    http = _dg_http()
    monkeypatch.setattr(dgmod, "make_session", lambda *a, **k: http)
    assert cli.main(["datagov", "sync"]) == 0
    out = capsys.readouterr()
    assert "3 resources indexed" in out.out
    assert cli.main(["datagov", "search", "tap", "water", "Bihar"]) == 0
    out = capsys.readouterr().out
    assert A1 in out and A2 in out and "2026-04-10" in out
    assert cli.main(["datagov", "status"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("3 resources") and "key: yes" in out and "dgtestkey0001" not in out


def test_cli_datagov_sync_offline_refuses(tmp_path, monkeypatch, capsys):
    from truthlens import cli
    monkeypatch.setenv("TRUTHLENS_CACHE", str(tmp_path / "cache"))
    assert cli.main(["datagov", "sync", "--offline"]) == 2
    assert "offline" in capsys.readouterr().err


def test_cli_doctor_ping_mocked(tmp_path, monkeypatch, capsys):
    import truthlens.net as net
    from truthlens import cli

    class Sess:
        def get(self, url, timeout=None, **k):
            if "data.gov.in" in url:
                raise ConnectionError("Tunnel connection failed: 502 Bad Gateway")
            if "openalex" in url:
                return Resp({"error": "rate"}, 429)
            body = {"indicator_code": 1, "records": [], "listOfQuestions": [], "rows": [], "message": {}}
            if "RssMain" in url:
                return Resp(None, 200, b"<rss><item><title>x</title></item></rss>", "text/xml")
            return Resp(body)
    monkeypatch.setenv("TRUTHLENS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(net, "make_session", lambda *a, **k: Sess())
    assert cli.main(["doctor", "--ping"]) == 0
    out = capsys.readouterr().out
    lines = {ln.strip()[2:].split("  ")[0].strip(): ln.strip() for ln in out.splitlines() if ln.strip()[:1] in "✔✘"}
    assert lines["MoSPI API"].startswith("✔") and lines["Lok Sabha"].startswith("✔") and lines["PIB feed"].startswith("✔")
    assert lines["data.gov.in"].startswith("✘") and "ConnectionError" in lines["data.gov.in"]
    assert lines["OpenAlex"].startswith("✘") and "rate-limited" in lines["OpenAlex"]
    assert len(lines) == len(cli.PING_CHECKS)


def test_cli_doctor_offline_does_not_ping(tmp_path, monkeypatch, capsys):
    import truthlens.net as net
    from truthlens import cli
    monkeypatch.setattr(net, "make_session", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
    assert cli.main(["doctor", "--ping", "--offline"]) == 0
    assert "connectivity" not in capsys.readouterr().out


def test_per_check_datagovin_key_reaches_worker_threads(tmp_path):
    """use_keys (the web app's per-check key) must reach retrievers running in the pipeline's thread pools."""
    from fixture_http import fixture_pipeline
    from truthlens.config import use_keys
    from truthlens.readers import read_text
    from truthlens.retrievers.datagovin import CatalogIndex, DataGovInClient, sync_catalog
    http = _dg_http()
    with use_keys({"DATAGOVIN_API_KEY": "perCheckKey77"}):
        pipe = fixture_pipeline(tmp_path / "p", session=http)
        sync_catalog(DataGovInClient(pipe.cfg, http), CatalogIndex(pipe.cfg.cache_dir / "datagovin_catalog.sqlite"))
        rep = pipe.run(read_text("In Bihar, 97.1% of households had tap water connections. "
                                 "In Bihar, 95.6% of households had tap water connections."), "t")
    assert [c["verdict"] for c in rep["claims"]] == ["SUPPORTED", "PARTLY SUPPORTED"]
    assert any("resource/" in c and "api-key=perCheckKey77" in c for c in http.calls)
    assert "perCheckKey77" not in json.dumps(rep)
