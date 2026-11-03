"""v0.4.1 correctness fixes from an independent adversarial review. Each test was written to fail on v0.4.0
(the v0.4.0 behaviour is noted) before the fix. Fully offline."""
from __future__ import annotations

import pytest

from fixture_http import fixture_pipeline
from truthlens.readers import read_text


def _run(pipe, text):
    return pipe.run(read_text(text), "t")


@pytest.fixture
def P(tmp_path):
    return fixture_pipeline(tmp_path)


def _claim(rep):
    cs = [c for c in rep["claims"]]
    assert cs, rep
    return cs[0]


# ---- 1. change calculator --------------------------------------------------------------------
@pytest.mark.parametrize("text,verdict,needle", [
    # v0.4.0: SUPPORTED high (both endpoints match, the direction word was ignored)
    ("CPI inflation rose from 5.4 percent in 2023-24 to 4.6 percent in 2024-25.", "CONTRADICTED", "rose"),
    ("CPI inflation fell from 5.4 percent in 2023-24 to 4.6 percent in 2024-25.", "SUPPORTED", "fell"),
    # v0.4.0: SUPPORTED (magnitude matched, direction ignored)
    ("CPI inflation increased by 0.8 percentage points from 2023-24 to 2024-25.", "CONTRADICTED", "fell"),
    ("CPI inflation decreased by 0.8 percentage points from 2023-24 to 2024-25.", "SUPPORTED", "0.8"),
    # v0.4.0: UNVERIFIED (no second period; 'last year' was not resolved)
    ("CPI inflation in 2024-25 was 0.8 percentage points lower than last year.", "SUPPORTED", "2023-24"),
    ("CPI inflation in 2024-25 was 0.8 percentage points higher than the previous year.", "CONTRADICTED", "2023-24"),
    # endpoint wrong although the direction is right
    ("CPI inflation fell from 5.9 percent in 2023-24 to 4.6 percent in 2024-25.", "CONTRADICTED", "5.9"),
    # percent vs percentage points confused
    ("CPI inflation fell by 0.8 per cent between 2023-24 and 2024-25.", "CONTRADICTED", "percentage points"),
    ("The fiscal deficit moderated from 5.6 per cent of GDP in 2023-24 to 4.8 per cent in 2024-25.", "SUPPORTED", "4.8"),
    ("Real GDP growth slowed from 7.3 per cent in 2023-24 to 7.8 per cent in 2025-26.", "CONTRADICTED", "slowed"),
])
def test_change_calculator(P, text, verdict, needle):
    c = _claim(_run(P, text))
    assert c["verdict"] == verdict, (c["verdict"], c["rationale"])
    assert needle in c["rationale"]


def test_change_internal_inconsistency_needs_no_data():
    from truthlens.change import parse_change
    ch = parse_change("Widget output rose from 12 per cent to 9 per cent.")
    assert ch is not None and ch.internal_conflict()
    assert "rose" in ch.internal_conflict()


def test_change_parse_doubled_and_bps():
    from truthlens.change import parse_change
    assert parse_change("Exports doubled between 2015-16 and 2023-24.").factor == 2.0
    ch = parse_change("The repo rate was cut by 25 bps in 2025-26.")
    assert ch.direction == -1 and ch.by is not None and ch.by.unit == "pp"


def test_change_unknown_period_is_unverified(P):
    c = _claim(_run(P, "CPI inflation fell from 6.7 percent in 2022-23 to 5.4 percent in 2023-24."))
    assert c["verdict"] == "UNVERIFIED" and "2022-23" in c["rationale"]


# ---- 2. show the failing part ------------------------------------------------------------------
def test_contradicted_reason_names_failing_figure_and_quote_is_short(P):
    c = _claim(_run(P, "Real GDP grew 7.7 per cent in 2025-26."))       # 7.7 is the superseded vintage
    assert c["verdict"] in ("CONTRADICTED", "PARTLY SUPPORTED")
    assert "2025-26" in c["rationale"] and "7.7" in c["rationale"] and "7.8" in c["rationale"]
    assert c.get("failed_part") and "2025-26" in c["failed_part"]
    for q in c.get("quotes") or []:
        assert len(q["quote"]) <= 220


def test_table_quote_is_header_and_cell():
    from truthlens.verdict import short_quote
    row = "Year: 2025-26 | Indicator: Real GDP growth | Value: 7.8% | " + "Notes: " + "x" * 600
    q = short_quote(row, ["7.8"], ["2025-26"])
    assert len(q) <= 220 and "7.8" in q and "2025-26" in q


# ---- 3. opinion phrasing -------------------------------------------------------------------------
def test_hedged_fact_is_checked_not_skipped(P):
    rep = _run(P, "In my view, India's fiscal deficit has been rising every year.")   # v0.4.0: SKIPPED
    c = _claim(rep)
    assert c["verdict"] == "CONTRADICTED", c["rationale"]
    assert c["claim"].get("hedged") and "contains a factual claim" in c["claim"].get("note", "")
    assert rep["summary"]["skipped_opinions"] == 0


def test_pure_opinion_still_skipped(P):
    rep = _run(P, "In my view, the government should invest more in water conservation.")
    assert _claim(rep)["verdict"] == "SKIPPED"
    assert rep["summary"]["skipped_opinions"] == 1


def test_trend_without_series_is_unverified_not_skipped(P):
    c = _claim(_run(P, "Arguably, groundwater levels in Punjab have been falling every year."))
    assert c["verdict"] == "UNVERIFIED"


def test_trend_with_series_checked(P):
    c = _claim(_run(P, "The fiscal deficit has fallen every year since 2022-23."))
    assert c["verdict"] == "SUPPORTED", c["rationale"]


# ---- 4. tokenising --------------------------------------------------------------------------------
@pytest.mark.parametrize("sentence,token", [
    ("The model was built with NumPy and PyTorch.", "NumPy"),
    ("The model was built with NumPy and PyTorch.", "PyTorch"),
    ("Data come from MoSPI and the PLFS.", "MoSPI"),
    ("Stunting is reported in NFHS-5 for 2019-21.", "NFHS-5"),
    ("The Jal Jeevan Mission covers rural homes.", "Jal Jeevan Mission"),
    ("Payments run on U.P.I. rails.", "U.P.I."),
])
def test_proper_noun_tokens_kept_whole(sentence, token):
    from truthlens.claims import proper_nouns
    assert token in proper_nouns(sentence)


def test_missing_names_whole_token_case_insensitive():
    from truthlens.verdict import _missing_names
    assert _missing_names("The tool uses NumPy.", "numpy is used throughout") == []
    assert _missing_names("The tool uses NumPy.", "the number of users") == ["NumPy"]
    assert _missing_names("Data from MoSPI.", "Source: mospi release") == []
    assert _missing_names("NFHS-5 data.", "NFHS-4 data") == ["NFHS-5"]


# ---- 5. offline citations ---------------------------------------------------------------------------
def test_offline_cache_real_doi_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("TRUTHLENS_OFFLINE", "1")
    from truthlens.retrievers.citations import offline_doi_lookup
    from truthlens.retrievers import citations as C
    doi = C.offline_cache_dois()[0]
    got = offline_doi_lookup(doi)
    assert got and got["title"]


def test_offline_real_vs_fake_doi(tmp_path, monkeypatch):
    from truthlens.retrievers import citations as C
    from truthlens.config import Config
    from truthlens.pipeline import Pipeline
    monkeypatch.setenv("TRUTHLENS_OFFLINE", "1")
    pipe = Pipeline(cfg=Config.load(), llm=None)
    real = C.offline_cache_dois()[0]
    rep = pipe.run(read_text(f"A study found groundwater depletion in north India (doi:{real})."), "t")
    chk = rep["claims"][0]["citation_checks"][0]
    assert chk["status"] == "found" and "offline cache" in chk["detail"]
    rep = pipe.run(read_text("A study found groundwater depletion in north India (doi:10.9999/fake.2024.001)."), "t")
    chk = rep["claims"][0]["citation_checks"][0]
    assert chk["status"] == "unreachable" and "can't check offline" in chk["detail"]
    assert rep["claims"][0]["verdict"] == "UNVERIFIED"
    assert not any(w["code"] == "citation_not_found" for w in rep["claims"][0]["warnings"])


# ---- 6. rounding tolerance ------------------------------------------------------------------------------
def test_same_precision_difference_is_mismatch(P):
    c = _claim(_run(P, "CPI inflation was 4.5 percent in 2024-25."))      # v0.4.0: PARTLY, "likely rounding"
    assert c["verdict"] == "CONTRADICTED" and "4.6" in c["rationale"]
    assert "rounding" not in c["rationale"]


@pytest.mark.parametrize("text", ["CPI inflation was 5 percent in 2024-25.", "CPI inflation was 4.6 percent in 2024-25."])
def test_coarser_precision_is_rounding_match(P, text):
    c = _claim(_run(P, text))
    assert c["verdict"] == "SUPPORTED"


def test_rounding_rule_function():
    from truthlens.checker import is_rounding
    assert is_rounding("5", 4.6) and is_rounding("4.6", 4.56)
    assert not is_rounding("4.5", 4.6) and not is_rounding("4.6", 4.6) and not is_rounding("4", 4.6)


# ---- 7. split score ---------------------------------------------------------------------------------------
def test_summary_has_split_counts_and_headline(P):
    rep = _run(P, "CPI inflation was 4.6 percent in 2024-25. Real GDP grew 6.5 per cent in 2024-25. "
                  "The scheme improved lives across Bihar in 2019. We should invest more.")
    s = rep["summary"]
    for k in ("supported", "contradicted", "partly", "couldnt_check", "skipped", "headline", "checked_claims"):
        assert k in s, k
    assert s["contradicted"] == 1 and s["supported"] == 1 and s["skipped"] == 1
    # v0.5.3: the old split moved to split_line; the headline leads with what was checked against data
    assert "1 wrong" in s["split_line"] and "1 supported" in s["split_line"] and "couldn't check" in s["split_line"]
    assert s["headline"].startswith("2 claims checked against official data · 1 wrong")
    assert s["verified_score"] == 50.0      # over checked claims only (couldn't-check excluded)


def test_split_score_in_md_and_html(P):
    from truthlens.report_v2 import to_html as render_html, to_markdown as render_md
    rep = _run(P, "CPI inflation was 4.6 percent in 2024-25. Real GDP grew 6.5 per cent in 2024-25.")
    for out in (render_md(rep), render_html(rep)):
        assert "wrong" in out and "couldn" in out and "supported" in out.lower()


# ---- 8. source banner -------------------------------------------------------------------------------------
def test_unreachable_banner_in_report(P):
    rep = _run(P, "CPI inflation was 4.6 percent in 2024-25.")
    assert "unreachable_sources" in rep["summary"]


def test_not_live_verified_sources_marked():
    from truthlens.model import NOT_LIVE_VERIFIED, Evidence
    assert {"datagovin", "semanticscholar", "shodhganga"} <= set(NOT_LIVE_VERIFIED)
    e = Evidence(retriever="shodhganga", source_url="https://shodhganga.inflibnet.ac.in/x", title="t", snippet="s")
    assert e.to_dict()["not_live_verified"] is True


def test_cli_summary_is_split(P):
    from truthlens.cli import _v2_summary
    rep = _run(P, "CPI inflation was 4.6 percent in 2024-25. Real GDP grew 6.5 per cent in 2024-25.")
    line = _v2_summary(rep)
    assert "1 wrong" in line and "1 supported" in line and "couldn't check" in line and "skipped" in line


def test_doctor_marks_not_live_verified(capsys):
    from truthlens import cli
    assert cli.main(["doctor", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "untested live" in out
    for name in ("data.gov.in", "Semantic Scholar", "Shodhganga"):
        assert name in out


def test_html_evidence_tag_for_not_live_verified_source():
    from truthlens.report_v2 import _card
    c = {"claim": {"id": "c1", "text": "x", "sentence": "x", "type": "entity", "location": "p1"}, "verdict": "UNVERIFIED",
         "confidence": "n/a", "method": "heuristic", "rationale": "", "quotes": [], "numbers": [], "warnings": [],
         "citation_checks": [], "evidence": [{"id": "E1", "kind": "metadata", "retriever": "shodhganga", "snippet": "s",
                                              "source_url": "https://shodhganga.inflibnet.ac.in/x", "not_live_verified": True}]}
    assert "unverified source" in _card(1, c)


# ---- 7/8/10. web app ----------------------------------------------------------------------------------------
def test_webui_shows_split_score_banner_and_tags():
    from truthlens.webui import PAGE
    assert "S.headline" in PAGE and "couldn't check" in PAGE.lower()
    assert "unreachable_sources" in PAGE and "not live-verified" in PAGE.lower()
    assert "contains a factual claim" in PAGE and "failed_part" in PAGE and "unverified source" in PAGE


def test_webui_offers_offline_sample_report(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import truthlens.api as api
    monkeypatch.setattr(api, "ONLINE", False)
    client = TestClient(api.app)
    assert "Open sample report" in client.get("/").text
    r = client.get("/sample-report")
    assert r.status_code == 200 and "TruthLens" in r.text and "<script src" not in r.text


def test_more_than_halved(P):
    c = _claim(_run(P, "CPI inflation more than halved between 2024-25 and 2025-26."))   # v0.4.1 first run: CONTRADICTED
    assert c["verdict"] == "SUPPORTED", c["rationale"]
    c = _claim(_run(P, "CPI inflation more than halved between 2023-24 and 2024-25."))
    assert c["verdict"] == "CONTRADICTED"


def test_hedged_judgement_stays_opinion(P):
    rep = _run(P, "We believe the rebasing makes Indian statistics far more credible.")
    assert _claim(rep)["verdict"] == "SKIPPED"


# ---- 10. easy install -------------------------------------------------------------------------------------------
def test_one_command_launchers_and_setup():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    bat = (root / "start_truthlens.bat").read_text()
    sh = (root / "start_truthlens.sh").read_text()
    for t in (bat, sh):
        assert "-m venv" in t and "-m pip install" in t and "127.0.0.1:8765" in t and "sample_report_v041.html" in t
    assert "\r\n" in (root / "start_truthlens.bat").read_bytes().decode()
    assert (root / "Start TruthLens (Windows).bat").exists() and (root / "start-truthlens.sh").exists()
    setup = (root / "SETUP.md").read_text()
    assert setup.index("## Windows") < setup.index("## Mac and Linux")
    assert "python -m pip" in setup and "AI coding assistant" not in setup
    assert (root / "samples" / "sample_report_v041.html").exists()


def test_unreachable_sources_counts_claims():
    from types import SimpleNamespace
    from truthlens.pipeline import unreachable_sources
    from truthlens.report_v2 import banner_lines
    rs = [SimpleNamespace(consulted=[{"source": "rbi", "status": "timeout"}, {"source": "pib", "status": "2 passage(s)"}],
                          citation_checks=[]),
          SimpleNamespace(consulted=[{"source": "rbi", "status": "timeout"}], citation_checks=[])]
    un = unreachable_sources(rs, None)
    assert un == [{"source": "rbi", "status": "timeout", "claims_affected": 2}]
    lines = banner_lines({"summary": {"unreachable_sources": un, "offline": True}})
    assert any("Offline run" in x for x in lines) and any("rbi (timeout, 2 claims affected)" in x for x in lines)
