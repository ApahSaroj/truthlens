from truthlens.extractor import extract_claims, split_sentences
from truthlens.readers import Block


def claims(text):
    return extract_claims([Block(text, "para 1")])


def test_sentence_split_keeps_rs_abbreviation():
    sents = [s for _, s in split_sentences("The deficit was Rs. 15 lakh crore. 35.5% of children are stunted. Next.")]
    assert len(sents) == 3
    assert sents[0].startswith("The deficit was Rs. 15")


def test_indicator_and_period():
    c = claims("India's real GDP grew by 7.8% in FY 2025-26.")[0]
    assert c.indicator == "gdp_growth_real" and c.period.label == "2025-26"


def test_two_indicators_in_one_sentence():
    cs = claims("In 2025-26, real GDP expanded by 7.8 per cent, while nominal growth was 8.6 per cent.")
    assert [c.indicator for c in cs] == ["gdp_growth_real", "gdp_growth_nominal"]
    assert all(c.period.label == "2025-26" for c in cs)


def test_fiscal_deficit_percent_not_gdp_growth():
    c = claims("The fiscal deficit was 4.8% of GDP in 2024-25.")[0]
    assert c.indicator == "fiscal_deficit_pct_gdp"


def test_amount_vs_percent_resolution():
    cs = claims("The fiscal deficit was ₹15,74,431 crore (4.8% of GDP) in 2024-25.")
    assert [c.indicator for c in cs] == ["fiscal_deficit_amount", "fiscal_deficit_pct_gdp"]


def test_stage_is_local_to_the_number():
    cs = claims("The fiscal deficit was 4.8% of GDP in 2024-25 and is budgeted at 4.3% in 2026-27.")
    assert cs[0].stage is None and cs[1].stage == "BE"


def test_plfs_variants():
    assert claims("Unemployment (CWS) was 4.9% in 2023-24.")[0].variant == "cws"
    assert claims("Female LFPR was 41.7% in 2023-24.")[0].variant == "female_usual_status"
    c = claims("The unemployment rate was 3.2% in 2023-24.")[0]
    assert c.variant == "usual_status" and not c.variant_explicit


def test_state_geography():
    assert claims("Kerala's unemployment rate was 7% in 2023-24.")[0].geography == "Kerala"


def test_change_claims():
    c = claims("Female LFPR rose by 4.7 percentage points between 2022-23 and 2023-24.")[0]
    assert c.claim_type == "change"
    c = claims("GDP grew by 7.8% in 2025-26.")[0]
    assert c.claim_type == "level"  # 'grew by' a growth rate is a level of the growth series


def test_comparators():
    assert claims("Nominal GDP crossed ₹300 lakh crore in 2024-25.")[0].comparator == "ge"
    assert claims("Nearly 36% of children are stunted (NFHS-5).")[0].comparator == "approx"


def test_small_bare_numbers_and_ages_ignored():
    cs = claims("Among 12 states, persons aged 15 years and above had LFPR of 60.1% in 2023-24.")
    assert [c.number.raw for c in cs] == ["60.1%"]


def test_unrecognised_numbers_are_kept():
    cs = claims("Over 30 crore workers registered on the portal.")
    assert cs and cs[0].indicator is None


def test_works_without_spacy(monkeypatch):
    import truthlens.extractor as ex
    ex._spacy.cache_clear()
    monkeypatch.setattr(ex, "_spacy", lambda: None)
    assert len(ex.split_sentences("One is 7.8%. Two is 4.4%.")) == 2
