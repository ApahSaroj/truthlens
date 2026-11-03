"""v0.5: fixes for held-out cases 716 and 717 (v0.4.1 held-out set). Written before the fixes; fully offline.
The clean held-out set is not relabelled; these tests pin the behaviour."""
import pytest

from fixture_http import fixture_pipeline
from truthlens import net
from truthlens.readers import read_text


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    monkeypatch.setattr(net, "resolve_host", lambda h: ["93.184.216.34"])


@pytest.fixture
def P(tmp_path):
    return fixture_pipeline(tmp_path)


def _c(P, t):
    return P.run(read_text(t), "t")["claims"][0]


def test_717_female_lfpr_change_uses_female_series(P):
    c = _c(P, "Female LFPR on usual status rose from 37.0% in 2022-23 to 41.7% in 2023-24, a rise of 4.7 percentage points.")
    assert c["verdict"] == "SUPPORTED", (c["verdict"], c["rationale"])


def test_sub_group_without_a_series_fails_closed(P):
    # no female unemployment series in the curated data: never compared with the all-persons figure
    c = _c(P, "Female unemployment rate on usual status was 3.2% in 2023-24.")
    assert c["verdict"] != "CONTRADICTED", c["rationale"]
    from truthlens.registry import load_registry
    ind = load_registry()["unemployment_rate"]
    assert ind.detect_variant("female unemployment rate on usual status").startswith("unmatched")
    assert load_registry()["lfpr"].detect_variant("female lfpr on usual status") == "female_usual_status"


def test_all_persons_lfpr_unchanged(P):
    c = _c(P, "LFPR on usual status rose from 57.9% in 2022-23 to 60.1% in 2023-24.")
    assert c["verdict"] == "SUPPORTED", c["rationale"]


def test_716_crr_acronym_routes_to_rbi(P):
    c = _c(P, "The CRR currently stands at 3 per cent.")
    assert "rbi" in c["plan"]["data_matchers"]
    assert c["verdict"] == "SUPPORTED", (c["verdict"], c["rationale"], c["consulted"])


def _judge(claim_text, passage, url="https://sansad.in/getFile/x.pdf"):
    from truthlens.claims import checkable_numbers
    from truthlens.model import Claim, Evidence
    from truthlens.verdict import HeuristicJudge
    c = Claim(id="c1", sentence_id="s1", sentence=claim_text, text=claim_text, type="numeric", location="p1",
              numbers=[n.raw for n in checkable_numbers(claim_text)])
    e = Evidence(retriever="parliament", source_url=url, title="Lok Sabha answer", snippet=passage, official=True, id="E1",
                 publisher="Lok Sabha")
    return HeuristicJudge().judge(c, [e], [])


def test_live_604_passage_for_another_date_never_contradicts():
    # v0.4.1 and v0.5 live run, 2 Nov 2026: CONTRADICTED from a Lok Sabha answer about reserves on another date
    j = _judge("India's foreign exchange reserves stood at US$719.7 billion in the week ended October 23, 2026.",
               "As of July 10, 2026, India's foreign exchange reserves stood at USD 675.2 billion, adequate in terms of "
               "the standard metrics of reserve adequacy.")
    assert j["verdict"] != "CONTRADICTED", j


def test_same_date_different_figure_still_contradicts():
    j = _judge("India's foreign exchange reserves stood at US$719.7 billion as of July 10, 2026.",
               "As of July 10, 2026, India's foreign exchange reserves stood at USD 675.2 billion, adequate in terms of "
               "the standard metrics of reserve adequacy.")
    assert j["verdict"] == "CONTRADICTED", j


def test_619_old_dated_passage_does_not_support_an_undated_snapshot_figure(tmp_path):
    """Live 2 Nov 2026 (v0.4.1 and v0.5): 'The repo rate was 6.5%.' was SUPPORTED by a December 2024 Rajya Sabha
    answer although RBI's current rate is 5.5%. An undated figure that differs from the current official snapshot
    is at most PARTLY SUPPORTED, with both values named."""
    from fixture_http import FixtureHTTP
    from truthlens.claims import checkable_numbers
    from truthlens.config import Config
    from truthlens.model import Claim, Evidence
    from truthlens.retrievers.ministry import RBISource
    from truthlens.verdict import HeuristicJudge, VerdictEngine

    class Docs:
        name, errors = "docs", []

        def retrieve(self, claim, k=4):
            return [Evidence(retriever="parliament", source_url="https://sansad.in/rs/x.pdf", title="Rajya Sabha answer",
                             snippet="REPO RATE. The policy repo rate was 6.5 per cent as on 17 December 2024, the "
                                     "Reserve Bank of India said.", official=True, publisher="Rajya Sabha",
                             date="2024-12-17")]
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    eng = VerdictEngine([Docs()], HeuristicJudge(), matchers={"rbi": RBISource(cfg, FixtureHTTP())})
    t = "The repo rate was 6.5%."
    r = eng.evaluate(Claim(id="c1", sentence_id="s1", sentence=t, text=t, type="numeric", location="p1",
                           numbers=[n.raw for n in checkable_numbers(t)]), [])
    assert r.verdict != "SUPPORTED", (r.verdict, r.rationale)
    assert "5.5" in r.rationale


def test_619_snapshot_finding_survives_the_curated_checkers_open_finding(tmp_path):
    """v0.5 India v4 live run, 2 Nov 2026: 'The repo rate was 6.5%.' was SUPPORTED again, run alone. The pipeline hands
    the engine the curated checker's finding for 6.5% ('No supported indicator recognised', UNVERIFIED), and the
    engine dropped RBI's UNVERIFIED snapshot finding ('The latest official value is 5.5...') because the figure already
    had an UNVERIFIED finding, so the undated-snapshot rule above never fired. The test above passed no findings."""
    from fixture_http import FixtureHTTP
    from truthlens.claims import checkable_numbers
    from truthlens.config import Config
    from truthlens.model import Claim, Evidence
    from truthlens.retrievers.ministry import RBISource
    from truthlens.verdict import HeuristicJudge, VerdictEngine

    class Docs:
        name, errors = "docs", []

        def retrieve(self, claim, k=4):
            return [Evidence(retriever="parliament", source_url="https://sansad.in/rs/x.pdf", title="Rajya Sabha answer",
                             snippet="REPO RATE. The policy repo rate was 6.5 per cent as on 17 December 2024, the "
                                     "Reserve Bank of India said.", official=True, publisher="Rajya Sabha",
                             date="2024-12-17")]
    t = "The repo rate was 6.5%."
    curated = [f.to_dict() for f in fixture_pipeline(tmp_path / "p").checker.check_blocks(read_text(t))]
    assert curated and all(f["verdict"] == "UNVERIFIED" and not f.get("official") for f in curated)
    cfg = Config.load(path="/nonexistent", cache_dir=tmp_path)
    eng = VerdictEngine([Docs()], HeuristicJudge(), matchers={"rbi": RBISource(cfg, FixtureHTTP())})
    r = eng.evaluate(Claim(id="c1", sentence_id="s1", sentence=t, text=t, type="numeric", location="p1",
                           numbers=[n.raw for n in checkable_numbers(t)]), curated)
    assert r.verdict != "SUPPORTED", (r.verdict, r.rationale)
    assert "5.5" in r.rationale


def test_curated_open_finding_kept_when_matcher_has_no_official_value(tmp_path):
    """Guard for the fix above: a matcher's UNVERIFIED finding without an official value does not replace the
    curated one, and a curated finding that has an official value is never replaced by a matcher's UNVERIFIED one."""
    from truthlens.verdict import _keep_matcher_unverified
    open_curated = {"claimed": "6.5%", "verdict": "UNVERIFIED", "official": None, "reason": "No supported indicator"}
    with_official = {"claimed": "6.5%", "verdict": "UNVERIFIED", "official": {"display": "5.5"},
                     "reason": "The latest official value is 5.5; the draft gives no date"}
    bare = {"claimed": "6.5%", "verdict": "UNVERIFIED", "official": None, "reason": "no matching row"}
    assert _keep_matcher_unverified(with_official, [open_curated])
    assert not _keep_matcher_unverified(bare, [open_curated])
    assert not _keep_matcher_unverified(with_official, [dict(with_official, reason="The latest official value is 5.4")])
    assert not _keep_matcher_unverified(with_official, [dict(open_curated, verdict="MATCH")])
    assert _keep_matcher_unverified(with_official, [])
