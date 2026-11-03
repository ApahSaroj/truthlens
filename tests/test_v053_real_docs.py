"""v0.5.3: fixes found by running TruthLens on five real, public state water-policy documents (3 Nov 2026).

Every sentence below that is quoted from a real document says which one. No network: the deterministic checker, the
bundled state data and the report builders only."""
import json

import pytest

from truthlens.claims import non_claim_reason, strip_marks
from truthlens.config import Config
from truthlens.pipeline import Pipeline
from truthlens.readers import read_text


@pytest.fixture(scope="module")
def P():
    return Pipeline(Config.load(offline=True), llm=None)


def _claim(P, text):
    rep = P.run(read_text(text), "t", mode="quick")
    return rep, rep["claims"][0]


# ---- what is not a claim -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,why", [
    ("Modernising irrigation 9 3.5.", "heading"),                                  # contents entry (Karnataka 2022)
    ("Improving watersheds, rivers, and environment 14 3.12.", "heading"),
    ("Institutional Mechanism 2.1.", "heading"),
    ("WATER RESOURCES OF THE STATE", "heading"),
    ("Km.) 1118 890 0.57% Name of Districts: Ganjam, Gajapati Population ( Nos. ) 2001 2051 270937 310330 "
     "Arable Area ( Ha. ) : 44408", "table"),                                     # Odisha 2007 annexure row
    ("The first priority and charge on water shall be to meet the basic safe water needs.", "rule"),
    ("Guidelines will be developed for the reuse of treated waste water.", "plan"),
    ("Kerala also has set a target of 100% rural household coverage by 2024.", "plan"),
    ("With increasing population the demand for water is likely to increase to 55 billion cubic metres by 2051.", "plan"),
    ("Implement 24 x 7 water supply schemes in various urban local bodies.", "plan"),
    ("Director, Technical & Operations, Mob: 9447294911, Email id: someone@example.org", "contact"),
    ("G.O.Ms.No.25, PR&RD, Dt: 17.03.2025 (Amendment to 15th Finance Commission Guidelines)", "heading"),
    ("Quality conservation and improvement for groundwater is very important.", "rule"),
])
def test_not_a_claim(text, why):
    assert non_claim_reason(text) == why


@pytest.mark.parametrize("text", [
    # a past or present figure keeps the sentence, even next to a projection
    "Agriculture accounted for about 84% of water diversions and estimated water demands in the State may reach "
    "45,052 Million m3 (1591 TMC) by 2030 from 42,225 Million m3 (1,491 TMC) in 2020.",
    "Increasing hydropower capacity from 290 MW to 3684 MW up to March 2019.",
    "Gross cropped area in the State is 22.9 million ha (2015-16), net sown area is 17.19 million ha.",
    "WUAs formed till September 2017 are 5326.",
    "The State of Orissa has 11 river basins.",
    "Jal Jeevan Mission will end in March 2026.",                                   # labelled set v0.2 hold-out 309-ish
    "The ELI scheme aims to create more than 5 crore jobs over two years.",
    "The Bank of England sets India's policy repo rate.",
    "Female LFPR on usual status rose from 37.0% in 2022-23 to 41.7% in 2023-24, a rise of 4.7 percentage points.",
    "The Centre met its fiscal deficit target of 4.4 per cent of GDP in 2025-26.",
])
def test_claims_are_kept(text):
    assert non_claim_reason(text) is None, non_claim_reason(text)


def test_strip_marks():
    assert strip_marks("ii. Water resources assessment. 3.12.") == "Water resources assessment."
    assert strip_marks("(iv) Proper upkeep of water bodies") == "Proper upkeep of water bodies"


def test_not_checkable_reason_is_shown_and_counted(P):
    rep, c = _claim(P, "The first priority and charge on water shall be to meet the basic safe water needs of 55 lpcd.")
    assert c["verdict"] == "SKIPPED" and c["method"] == "not-checkable" and "shall" in c["rationale"]
    assert c["claim"]["not_claim"] == "rule"
    assert rep["summary"]["not_checkable_reasons"] == {"rule": 1}


# ---- a State figure is never compared with an all-India value -----------------------------------------------------
def test_state_population_not_contradicted_by_india(P):
    # Maharashtra State Water Policy 2019
    _rep, c = _claim(P, "With population of 112.4 million, as per population Census 2011 and geographical area of 0.308 "
                        "million sq. km, Maharashtra is ranked 2nd by population and 3rd in terms of area.")
    assert c["verdict"] != "CONTRADICTED"
    pop = next(n for n in c["numbers"] if n["claimed"] == "112.4 million")
    assert pop["verdict"] == "MATCH" and "112.37" in pop["official"]["display"]       # Census 2011 Table A-1


def test_city_population_not_compared_with_india(P):
    # Kerala State Planning Board, drinking water chapter
    _rep, c = _claim(P, "The Kochi Corporation is spread over 94.88 km2 and has been divided in to 74 wards with total "
                        "population of 6,02,046 as per 2011 census.")
    assert c["verdict"] != "CONTRADICTED"


def test_percentage_never_compared_with_an_area(P):
    from truthlens.claims import checkable_numbers
    from truthlens.retrievers.state_data import StateDataSource
    t = "The State of Karnataka covers an area of 1,91,791 Sq. Kms., i.e., 5.83% of the area of India (Census 2011)."
    fs = StateDataSource(Config.load(offline=True)).match(t, checkable_numbers(t))
    assert [(f["claimed"], f["verdict"]) for f in fs] == [("1,91,791", "MATCH")]


def test_abbreviations_do_not_end_a_sentence():
    from truthlens.extractor import split_sentences
    t = "The State of Karnataka covers an area of 1,91,791 Sq. Kms., i.e., 5.83% of the area of India. It is large."
    assert len(split_sentences(t)) == 2


# ---- no prose contradiction from a bare number, a vague passage or several figures --------------------------------
def test_bare_numbers_need_a_unit_for_a_heuristic_contradiction():
    from truthlens.verdict import _has_unit
    assert not _has_unit("193", "the United Nations 193 member states including India")
    assert not _has_unit("3.12", "Improving watersheds 14 3.12")
    assert _has_unit("288", "As many as 288 districts have been certified")
    assert _has_unit("538.43 lakhs", "Total Population : 538.43 lakhs")


def test_several_figures_against_one_official_value():
    from truthlens.verdict import one_value_many_figures
    off = {"display": "312,150"}
    fs = [{"claimed": "41700", "verdict": "MISMATCH", "official": off, "indicator_name": "Catchment area"},
          {"claimed": "7400", "verdict": "MISMATCH", "official": off, "indicator_name": "Catchment area"}]
    assert [f["verdict"] for f in one_value_many_figures(fs)] == ["UNVERIFIED", "UNVERIFIED"]
    fs.append({"claimed": "3,12,150", "verdict": "MATCH", "official": off, "indicator_name": "Catchment area"})
    out = one_value_many_figures(fs)
    assert [f["verdict"] for f in out] == ["UNVERIFIED", "UNVERIFIED", "MATCH"]
    assert "about something else" in out[0]["reason"]


def test_from_to_needs_the_same_scale():
    from truthlens.change import _scale_word
    assert _scale_word("42,225 Million") == "million" and _scale_word("20") == ""


# ---- PDF reading -------------------------------------------------------------------------------------------------
def _words(lines_left, lines_right, x_left=40, x_right=300, width=8):
    out = []
    for i, ln in enumerate(lines_left):
        x = x_left
        for w in ln.split():
            out.append({"x0": x, "x1": x + width * len(w), "top": 100 + 12 * i, "text": w})
            x += width * len(w) + 4
    for i, ln in enumerate(lines_right):
        x = x_right
        for w in ln.split():
            out.append({"x0": x, "x1": x + width * len(w), "top": 100 + 12 * i, "text": w})
            x += width * len(w) + 4
    return out


def test_two_column_gutter_found_and_single_column_left_alone():
    from truthlens.readers import _column_split
    left = ["aa bb cc dd ee ff gg"] * 30          # x 40..176
    right = ["hh ii jj kk ll mm nn"] * 30         # x 300..436
    x = _column_split(_words(left, right), 560)
    assert x is not None and 176 <= x <= 300
    one = _words(["aa bb cc dd ee ff gg hh ii jj kk ll mm nn oo pp qq rr ss tt uu vv ww xx"] * 30, [])
    assert _column_split(one, 560) is None


def test_running_headers_dropped_and_headings_kept_apart():
    from truthlens.readers import _paragraphs_from_lines, _running_lines
    pages = [["MAHARASHTRA STATE WATER POLICY (2019)", f"Body text of page {i} that runs the full width of the page.",
              f"{i}"] for i in range(1, 6)]
    rep = _running_lines(pages)
    assert "maharashtra state water policy (#)" in rep
    paras = _paragraphs_from_lines(["1.1. AREA AND DEMOGRAPHY",
                                    "The State covers an area of 1,91,791 sq km and it is the eighth largest State",
                                    "by population with over 61 million inhabitants in 2011 according to the Census."])
    assert paras[0] == "1.1. AREA AND DEMOGRAPHY" and paras[1].startswith("The State covers")


# ---- report: lead line, needs a source, claims to cite -------------------------------------------------------------
def test_lead_line_and_claims_to_cite(P):
    rep = P.run(read_text("CPI inflation was 4.6 percent in 2024-25. Real GDP grew 6.5 per cent in 2024-25. "
                          "The State has 1,234 multi-village schemes serving 5,678 habitations."), "t", mode="quick")
    s = rep["summary"]
    assert s["headline"].startswith("2 claims checked against official data · 1 wrong · 1 needs a source you should cite")
    assert s["needs_source"] == 1 and s["checked_against_data"] == 2 and "split_line" in s
    assert s["score_note"].startswith("Only 2 claims could be checked")
    cite = rep["claims_to_cite"]
    assert len(cite) == 1 and "multi-village" in cite[0]["text"]
    assert cite[0]["why"] == "Needs a source (no official dataset in TruthLens yet)"


def test_cite_csv_is_safe_for_spreadsheets():
    from truthlens.report_v2 import to_cite_csv
    rep = {"claims_to_cite": [{"location": "para 1", "text": "=HYPERLINK(\"http://x\")", "why": "Needs a source",
                               "numbers": ["5%"]}]}
    out = to_cite_csv(rep)
    assert out.startswith("\ufeff#,Where,Claim") and "'=HYPERLINK" in out


def test_render_and_cli_give_the_cite_list(tmp_path, P):
    from fastapi.testclient import TestClient
    from truthlens import api, cli
    rep = P.run(read_text("The State has 1,234 multi-village schemes serving 5,678 habitations."), "t", mode="quick")
    r = TestClient(api.app).post("/render?format=cite", json=json.loads(json.dumps(rep, default=str)))
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"] and "multi-village" in r.text
    f = tmp_path / "d.txt"
    f.write_text("The State has 1,234 multi-village schemes serving 5,678 habitations.", encoding="utf-8")
    out = tmp_path / "c.csv"
    assert cli.main(["check", str(f), "--offline", "-f", "cite", "-o", str(out)]) == 0
    assert "multi-village" in out.read_text(encoding="utf-8-sig")


def test_web_app_has_cite_button_and_plain_bucket_name():
    from truthlens.webui import PAGE
    assert 'id="citebtn"' in PAGE and "render?format=cite" in PAGE and 'l:"Needs a source"' in PAGE


# ---- v0.5.3 open bug: Karnataka area sentence matched directly but "no matching table" in the pipeline --------------
KA_AREA = "The State of Karnataka covers an area of 1,91,791 Sq. Kms."        # Karnataka State Water Policy 2022, p. 7


@pytest.mark.parametrize("text", [KA_AREA, "The State of Karnataka covers an area of 1,91,791 sq km.",
                                  "The State of Karnataka covers an area of 1,91,791 Sq. Kms. (Census 2011)"])
def test_karnataka_area_supported_in_pipeline(P, text):
    _rep, c = _claim(P, text)
    sd = [x for x in c["consulted"] if x["source"] == "state-data"]
    assert sd and sd[0]["status"] == "1 match(es)", c["consulted"]
    assert c["verdict"] in ("SUPPORTED", "PARTLY SUPPORTED")
    assert any(f["verdict"] == "MATCH" and f["claimed"] == "1,91,791" for f in c["numbers"])


def test_karnataka_area_direct_and_pipeline_agree(P):
    from truthlens.verdict import checkable_numbers
    direct = P.state_data.match(KA_AREA, checkable_numbers(KA_AREA))
    assert [f["verdict"] for f in direct] == ["MATCH"]


def test_relaxed_census_relevance_never_contradicts_alone(P):
    # the lower word-overlap cut-off for Census tables only lets an exact figure through; a different figure in the
    # same low-overlap wording is not called wrong, and another State's figure is not borrowed
    _rep, c = _claim(P, "The State of Karnataka covers an area of 2,50,000 Sq. Kms. as per Census 2011.")
    assert c["verdict"] != "CONTRADICTED"
    _rep, c = _claim(P, "The State of Kerala covers an area of 1,91,791 Sq. Kms.")
    assert c["verdict"] not in ("SUPPORTED", "PARTLY SUPPORTED")


def test_job_result_gives_the_cite_list(monkeypatch):
    import time
    from fastapi.testclient import TestClient
    from truthlens import api
    monkeypatch.setattr(api, "ONLINE", False)
    monkeypatch.setattr(api, "_PIPE", None)
    api.JOBS.clear()
    c = TestClient(api.app)
    r = c.post("/jobs", json={"type": "text", "content": "The State has 1,234 multi-village schemes serving 5,678 habitations."})
    jid = r.json()["job_id"]
    t0 = time.monotonic()
    while c.get(f"/jobs/{jid}").json()["status"] == "running" and time.monotonic() - t0 < 60:
        time.sleep(0.1)
    out = c.get(f"/jobs/{jid}/result?format=cite")
    assert out.status_code == 200 and "text/csv" in out.headers["content-type"] and "multi-village" in out.text
