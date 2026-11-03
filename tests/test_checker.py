import pytest


def one(checker, text, claim=None):
    fs = checker.check_text(text)
    if claim:
        fs = [f for f in fs if f.claimed == claim]
    assert fs, f"no finding for {text!r}"
    return fs[0]


def codes(f):
    return {w["code"] for w in f.warnings}


def test_match_has_source_and_citation(checker):
    f = one(checker, "India's real GDP grew by 7.8% in FY 2025-26.")
    assert f.verdict == "MATCH"
    src = f.official["source"]
    assert src["url"].startswith("https://") and src["accessed"] == "2026-11-01"
    assert "7.8%" in f.citation and src["url"] in f.citation
    assert f.official["series_id"] == "IN.MOSPI.NAS.GDP.CONSTANT.GROWTH"


def test_rounding_is_match_not_close(checker):
    assert one(checker, "Real GDP grew 8% in 2025-26.").verdict == "MATCH"   # 7.8 rounds to 8


def test_close_within_tolerance(checker):
    f = one(checker, "Real GDP grew 7.7% in 2025-26.")
    assert f.verdict == "CLOSE" and "vintage" in codes(f)


def test_mismatch(checker):
    assert one(checker, "Headline CPI inflation was 3.5% in 2025-26.").verdict == "MISMATCH"


def test_unverified_never_guesses(checker):
    assert one(checker, "The unemployment rate was 3.2% in 2024-25.").verdict == "UNVERIFIED"
    assert one(checker, "GDP growth in Q1 FY27 was 8.1%.").verdict == "UNVERIFIED"
    assert one(checker, "India's population is 140 crore.").verdict == "UNVERIFIED"
    assert one(checker, "The debt-to-GDP ratio is 56.1 per cent in RE 2025-26.").verdict == "UNVERIFIED"


def test_level_in_crore_and_lakh_crore(checker):
    assert one(checker, "The fiscal deficit stood at ₹15,74,431 crore in 2024-25.").verdict == "MATCH"
    assert one(checker, "The fiscal deficit stood at ₹15.74 lakh crore in 2024-25.").verdict == "MATCH"


def test_comparator_bound(checker):
    assert one(checker, "India's nominal GDP crossed ₹300 lakh crore in 2024-25.").verdict == "MATCH"
    assert one(checker, "Real GDP grew more than 9% in 2025-26.").verdict == "MISMATCH"


def test_explicit_old_base_compared_with_old_series(checker):
    f = one(checker, "GDP at 2011-12 prices grew 6.5% in 2024-25.")
    assert f.verdict == "MATCH" and f.official["base"] == "2011-12" and "old_base" in codes(f)


def test_worldbank_fallback_for_calendar_year_cpi(checker):
    f = one(checker, "CPI inflation in 2024 was 4.95%.")
    assert f.verdict == "MATCH"
    assert f.official["source"]["publisher"].startswith("World Bank")
    assert {"fy_vs_cy", "secondary_source"} <= codes(f)


def test_worldbank_fallback_for_older_fy_gdp(checker):
    # not in the curated set; WDI year 2019 = FY 2019-20 (3.87%)
    f = one(checker, "Real GDP grew 3.9% in 2019-20.")
    assert f.verdict == "MATCH" and f.official["period"] == "2019-20"


def test_offline_without_cache_is_unverified(tmp_path):
    from truthlens.checker import Checker
    from truthlens.sources.worldbank import WorldBankClient
    ck = Checker(worldbank=WorldBankClient(cache_dir=tmp_path / "empty", offline=True))
    f = ck.check_text("Real GDP grew 3.9% in 2019-20.")[0]
    assert f.verdict == "UNVERIFIED" and "offline" in f.reason


@pytest.mark.parametrize("text,verdict", [
    ("The fiscal deficit is budgeted at 4.3% of GDP for 2026-27.", "MATCH"),
    ("The revised estimate of the fiscal deficit for 2025-26 is 4.4% of GDP.", "MATCH"),
    ("The fiscal deficit for 2022-23 was 6.4% of GDP.", "MATCH"),
    ("WPI inflation was 1.7% in FY20.", "MATCH"),
    ("35.5% of children under five are stunted (NFHS-5).", "MATCH"),
    ("IIP grew 4.3% in 2025-26.", "MATCH"),
])
def test_assorted(checker, text, verdict):
    assert one(checker, text).verdict == verdict


def test_finding_serialises(checker):
    import json
    f = one(checker, "India's real GDP grew by 7.8% in FY 2025-26.")
    json.dumps(f.to_dict(), default=str)
