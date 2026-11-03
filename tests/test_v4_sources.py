"""v0.4 sources, tested offline.

RECORDED (tests/fixtures/live/recorded_v04.json, captured live on 2 Nov 2026 by scripts/run_live_eval.py --record):
  RBI home page + press-release RSS + WSS extract, CEA dashboard JSON, PPAC import/export and consumption JSON + home
  page, the JJM dashboard table, NDAP catalogue searches, arXiv Atom answers, Semantic Scholar HTTP 429 answers and the
  Shodhganga bot-challenge page.
SYNTHETIC (tests/fixtures/v04/, every file says so): a Semantic Scholar search hit and DOI
  record (our network only ever got HTTP 429), and a Shodhganga OpenSearch answer (bot challenge on 2 Nov 2026).
"""
import json
from pathlib import Path

import pytest

from fixture_http import FixtureHTTP, Resp, fixture_pipeline
from truthlens import net
from truthlens.claims import checkable_numbers, find_citations
from truthlens.config import Config, use_keys
from truthlens.model import Claim, Evidence

FIX = Path(__file__).parent / "fixtures"
V4 = FIX / "v04"
LIVE = json.loads((FIX / "live" / "recorded_v04.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"])


def _cfg(tmp_path, **over):
    return Config.load(path="/nonexistent", cache_dir=Path(tmp_path), **over)


def _nums(t):
    return checkable_numbers(t)


def _claim(text, type_="numeric"):
    # built like claims._make_claim does: numbers *and* citations (an arXiv id is only checked when it is a citation)
    return Claim(id="c1", sentence_id="s1", sentence=text, text=text, type=type_, location="p1",
                 numbers=[n.raw for n in checkable_numbers(text)], citations=find_citations(text))


def _live_text(key):
    return LIVE[key]["text"]


# ------------------------------------------------------------------------------------------------ net
def test_safe_post_refuses_private_addresses_and_redirects(monkeypatch):
    monkeypatch.setattr(net, "resolve_host", lambda h: ["10.0.0.5"])
    with pytest.raises(net.FetchError):
        net.safe_post(FixtureHTTP(), "https://internal.example/x", data={"a": 1})
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"])
    r = Resp(None, 302, b"", "text/html")
    r.headers["location"] = "http://169.254.169.254/"
    with pytest.raises(net.FetchError, match="redirect"):
        net.safe_post(FixtureHTTP({"https://public.example/p": r}), "https://public.example/p", data={})
    with pytest.raises(net.FetchError):
        net.safe_post(FixtureHTTP(), "file:///etc/passwd")


# ------------------------------------------------------------------------------------------------ RBI
def test_rbi_parsers_on_recorded_pages():
    from truthlens.retrievers.ministry import _text_of_html, parse_rbi_rates, parse_rbi_wss
    home = parse_rbi_rates(_text_of_html(_live_text("https://www.rbi.org.in/").encode()))
    assert home["rates"]["Policy Repo Rate"] == 5.5 and home["rates"]["CRR"] == 3.0 and home["rates"]["SLR"] == 18.0
    assert home["fx"]["USD"] > 50
    wss = parse_rbi_wss(_text_of_html(_live_text("https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63890").encode()))
    assert wss["total"]["usd_mn"] == 719748 and wss["gold"]["usd_mn"] == 103150 and wss["fx_as_of"] == "2026-10-23"
    assert wss["credit_growth"]["yoy"] == 18.2


def test_rbi_matches_rates_and_reserves(tmp_path):
    from truthlens.retrievers.ministry import RBISource
    src = RBISource(_cfg(tmp_path), FixtureHTTP())
    v = lambda t: [(f["verdict"], f["official"]["display"]) for f in src.match(t, _nums(t))]
    assert v("The RBI's policy repo rate is 5.50%.") == [("MATCH", "5.5")]
    assert v("The cash reserve ratio currently stands at 4%.")[0][0] == "MISMATCH"
    assert v("India's foreign exchange reserves stood at US$719.7 billion in the week ended October 23, 2026.")[0][0] == "MATCH"
    # snapshot rule: an undated, past-tense figure may be historical -> never contradicted by today's rate
    f = src.match("The repo rate was 6.5%.", _nums("The repo rate was 6.5%."))
    assert f and f[0]["verdict"] == "UNVERIFIED" and "older" in f[0]["reason"]
    # the clause rule: CRR's figure is not compared with the repo rate
    both = src.match("The repo rate is 5.5% and the CRR is 3%.", _nums("The repo rate is 5.5% and the CRR is 3%."))
    assert sorted(f["verdict"] for f in both) == ["MATCH", "MATCH"]


# ------------------------------------------------------------------------------------------------ CEA
def test_cea_installed_capacity_and_performance(tmp_path):
    from truthlens.retrievers.ministry import CEASource
    src = CEASource(_cfg(tmp_path), FixtureHTTP())
    v = lambda t: [(f["verdict"], f["official"]["display"]) for f in src.match(t, _nums(t))]
    assert v("Gujarat had an installed power generation capacity of 79,508.78 MW in September 2026.") == [("MATCH", "79,508.78")]
    assert v("Rajasthan's installed generation capacity was 70,000 MW in September 2026.")[0][0] == "MISMATCH"
    assert v("All-India peak demand met was 258.27 GW in August 2026.") == [("MATCH", "258.27")]
    # a national total TruthLens derives by adding states never contradicts a figure
    f = src.match("India's installed power generation capacity is 512 GW.", _nums("India's installed power generation capacity is 512 GW."))
    assert f and f[0]["verdict"] == "UNVERIFIED"
    # a figure for a month the snapshot is not about is not matched at all
    assert v("Gujarat had an installed power generation capacity of 79,508.78 MW in March 2025.") == []


# ------------------------------------------------------------------------------------------------ PPAC
def test_ppac_imports_consumption_and_prices(tmp_path, monkeypatch):
    import datetime as dt
    from truthlens.retrievers import ministry
    from truthlens.retrievers.ministry import PPACSource

    class D(dt.date):
        @classmethod
        def today(cls):
            return dt.date(2026, 11, 2)
    monkeypatch.setattr(ministry.dt, "date", D)
    src = PPACSource(_cfg(tmp_path), FixtureHTTP())
    v = lambda t: [(f["verdict"], f["official"]["display"], f["indicator_name"]) for f in src.match(t, _nums(t))]
    got = v("India imported 246.6 million tonnes of crude oil in 2025-26.")
    assert got[0][:2] == ("MATCH", "246.6") and "million tonnes" in got[0][2]
    assert v("India's crude oil imports were 300 million tonnes in 2025-26.")[0][0] == "MISMATCH"
    assert v("Consumption of diesel (HSD) was 94.7 million tonnes in 2025-26.")[0][:2] == ("MATCH", "94.71")
    assert "petrol" not in v("Diesel consumption was 50 million tonnes in 2025-26.")[0][2]      # never the wrong product
    assert v("The retail selling price of petrol in Delhi is ₹102.12 per litre.")[0][:2] == ("MATCH", "102.12")


# ------------------------------------------------------------------------------------------------ JJM
def test_jjm_encoding_and_state_table(tmp_path):
    from truthlens.retrievers.ministry import JJMSource, _jjm_enc
    assert _jjm_enc("0") == "11"           # the dashboard's encodeTxt("0") with encN = 1
    src = JJMSource(_cfg(tmp_path), FixtureHTTP())
    v = lambda t: [(f["verdict"], f["official"]["display"]) for f in src.match(t, _nums(t))]
    assert v("Ladakh has tap water connections in 98.53% of rural households.") == [("MATCH", "98.53")]
    assert v("Ladakh has tap water connections in 90% of rural households.")[0][0] == "MISMATCH"
    assert v("Goa has provided tap water connections to 100% of its rural households.")[0][0] == "MATCH"
    assert v("Over 15.99 crore rural households have tap water connections.")[0][0] == "MATCH"
    # an all-India per cent TruthLens computes from the state rows never contradicts the draft
    f = src.match("Today 70% of rural households have tap water connections.", _nums("Today 70% of rural households have tap water connections."))
    assert all(x["verdict"] != "MISMATCH" for x in f)


def test_ministry_source_down_fails_closed(tmp_path):
    from truthlens.retrievers.ministry import CEASource
    src = CEASource(_cfg(tmp_path), FixtureHTTP({"https://cea.nic.in/": lambda *a: (_ for _ in ()).throw(RuntimeError("down"))}))
    assert src.match("Gujarat had 79,508.78 MW in September 2026 installed capacity.",
                     _nums("Gujarat had 79,508.78 MW in September 2026 installed capacity.")) == []
    assert src.errors and "down" in src.errors[0]


# ------------------------------------------------------------------------------------------------ NDAP
def test_ndap_catalogue_is_a_pointer_never_support(tmp_path):
    from truthlens.retrievers.ndap import NDAPCatalog
    cat = NDAPCatalog(_cfg(tmp_path), FixtureHTTP())
    hits = cat.search("punjab groundwater extraction stage")
    assert hits and hits[0]["id"] == 2227 and "Stage of Extraction" in hits[0]["name"]
    ev = cat.retrieve(_claim("The stage of groundwater extraction in Punjab was 156.36% in 2024."))
    assert ev and ev[0].kind == "catalogue" and ev[0].source_type == "NDAP" and not ev[0].official
    assert ev[0].source_url == "https://ndap.niti.gov.in/dataset/2227"
    # and the engine never hands a catalogue entry to the judge
    from truthlens.verdict import HeuristicJudge, VerdictEngine

    class Only:
        name = "ndap"
        errors = []

        def retrieve(self, claim, k):
            return [Evidence(**{**ev[0].__dict__})]
    res = VerdictEngine([Only()], HeuristicJudge(), plan=False).evaluate(
        _claim("Stage of groundwater extraction: Punjab dataset updated, NDAP dataset 2227.", "entity"), [])
    assert res.verdict == "UNVERIFIED"
    assert any(w["code"] == "dataset_pointer" for w in res.warnings)


def test_ndap_search_sends_site_headers_and_fails_closed(tmp_path):
    from truthlens.retrievers.ndap import NDAPCatalog
    http = FixtureHTTP({"https://loadqa.ndapapi.com/v1/search": Resp({"Message": "Invalid Request"})})
    cat = NDAPCatalog(_cfg(tmp_path), http)
    assert cat.search("anything here") == []
    assert http.last_headers.get("Origin") == "https://ndap.niti.gov.in"
    assert cat.errors and "Invalid Request" in cat.errors[0]


def test_ndap_token_path_removed():
    """v0.5.3: the NDAP data-rows path (an "NDAP profile" token) was never verified and was removed."""
    import truthlens.retrievers.ndap as nd
    from truthlens.config import SECRET_ENV
    from truthlens.webui import PAGE
    assert not hasattr(nd, "NDAPData") and "NDAP_API_TOKEN" not in SECRET_ENV
    assert "ndkey" not in PAGE and "ndap_token" not in PAGE and "NDAP token" not in PAGE



# ------------------------------------------------------------------------------------------------ planner, badges, UI, CLI
def test_planner_routes_each_subject_to_its_source():
    from truthlens.planner import plan_claim
    avail = {"docs", "pib", "parliament", "openalex", "semanticscholar", "arxiv", "shodhganga", "ndap", "web",
             "mospi-catalog", "rbi", "cea", "ppac", "jjm"}
    dm = lambda t, ty="numeric": plan_claim(_claim(t, ty), avail).data_matchers
    assert dm("The repo rate is 5.5%.")[0] == "rbi"
    assert dm("India's installed power capacity is 500 GW.")[0] == "cea"
    assert dm("India imported 246.6 million tonnes of crude oil in 2025-26.")[0] == "ppac"
    assert dm("15 crore rural households have tap water connections.")[0] == "jjm"
    assert dm("CPI inflation was 2.1% in 2025-26.")[0] == "mospi-catalog"
    p = plan_claim(_claim("A PhD thesis found that 62% of wells were over-exploited.", "entity"), avail)
    assert {"openalex", "semanticscholar", "arxiv", "shodhganga"} <= set(p.routes)
    assert "ndap" in plan_claim(_claim("CPI inflation was 2.1% in 2025-26."), avail).routes


def test_new_badges():
    from truthlens.model import source_type_for
    for r, badge in (("ndap", "NDAP"), ("rbi", "RBI"), ("cea", "CEA"), ("ppac", "PPAC"), ("jjm", "JJM"),
                     ("semanticscholar", "Paper"), ("arxiv", "Paper"), ("shodhganga", "Thesis"), ("indiawris", "India-WRIS"),
                     ("hmis", "HMIS")):
        assert source_type_for(Evidence(retriever=r, source_url="", title="", snippet="")) == badge
    assert source_type_for(Evidence(retriever="", source_url="https://cea.nic.in/x", title="", snippet="")) == "CEA"


def test_web_ui_live_line():
    from truthlens.webui import PAGE as UPLOAD_PAGE
    for s in ("RBI, CEA, PPAC, Jal Jeevan Mission, PIB", "NDAP catalogue only names a dataset to cite",
              "Untested (never answered our test network",
              '"Thesis"', '"NDAP"', '"India-WRIS"', '"HMIS"', "Dataset to cite"):
        assert s in UPLOAD_PAGE, s
    assert "data.gov.in (with a free key), PIB" not in UPLOAD_PAGE


def test_doctor_ping_covers_new_sources(monkeypatch, capsys):
    from truthlens import cli

    class R:
        status_code = 200
        text = ("Policy Repo Rate categories CRUDE OIL graph_table_data results data <entry> <item> Token Required "
                "indicator_code records listOfQuestions rows message")
    monkeypatch.setattr(net, "safe_get", lambda *a, **k: R())
    monkeypatch.setattr(net, "safe_post", lambda *a, **k: R())
    monkeypatch.setattr(net, "make_session", lambda *a, **k: object())
    assert cli.main(["doctor", "--ping"]) == 0
    out = capsys.readouterr().out
    for name in ("NDAP catalogue", "RBI rates", "CEA", "PPAC", "JJM dashboard", "India-WRIS", "HMIS",
                 "Semantic Scholar", "arXiv", "Shodhganga"):
        assert name in out, name
    # v0.5.3: the token-gated NDAP data probe was removed with the synthetic NDAP rows; no token line is printed
    assert "NDAP data" not in out and "token needed" not in out
