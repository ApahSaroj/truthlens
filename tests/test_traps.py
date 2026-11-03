def finding(checker, text, claim=None):
    fs = checker.check_text(text)
    return next(f for f in fs if claim is None or f.claimed == claim)


def warn(f, code):
    return [w for w in f.warnings if w["code"] == code]


def test_lakh_crore_vs_million(checker):
    f = finding(checker, "The fiscal deficit was ₹157.4 billion in 2024-25.")
    assert f.verdict == "MISMATCH"
    w = warn(f, "unit_scale")
    assert w and "100" in w[0]["message"]


def test_population_million_slip(checker):
    f = finding(checker, "According to Census 2011, India's population was 12.1 million.")
    assert warn(f, "unit_scale")


def test_fy_vs_calendar_year(checker):
    f = finding(checker, "India's GDP grew 7.1% in 2024.")
    assert f.verdict == "UNVERIFIED"
    msg = warn(f, "fy_vs_cy")[0]["message"]
    assert "FY 2023-24" in msg and "FY 2024-25" in msg


def test_budget_estimate_vs_actual(checker):
    f = finding(checker, "The fiscal deficit in 2023-24 was 5.8% of GDP.")
    assert f.verdict == "MISMATCH"
    assert any("RE" in w["message"] for w in warn(f, "budget_stage"))


def test_budget_stage_unstated(checker):
    f = finding(checker, "The fiscal deficit was 4.8% of GDP in 2024-25.")
    assert f.verdict == "MATCH" and warn(f, "budget_stage")


def test_plfs_usual_status_vs_cws(checker):
    f = finding(checker, "India's unemployment rate was 4.9% in 2023-24.")
    assert f.verdict == "MISMATCH"
    assert any(w["severity"] == "error" and "CWS" in w["message"] for w in warn(f, "plfs_status"))


def test_plfs_year_called_fy(checker):
    f = finding(checker, "Unemployment in usual status was 3.2% in FY 2023-24.")
    assert warn(f, "plfs_year")


def test_old_base_series(checker):
    f = finding(checker, "Real GDP grew 6.5% in 2024-25.")
    assert f.verdict == "MISMATCH" and warn(f, "old_base")
    f = finding(checker, "Industrial production grew 4.0% in 2024-25.")
    assert warn(f, "old_base")


def test_registrations_vs_beneficiaries(checker):
    f = finding(checker, "Over 30 crore unorganised workers registered on the e-Shram portal have benefited.")
    assert f.verdict == "UNVERIFIED" and warn(f, "registrations_vs_beneficiaries")


def test_percent_vs_percentage_points(checker):
    f = finding(checker, "The female LFPR rose from 37.0% in 2022-23 to 41.7% in 2023-24, an increase of 4.7%.", "4.7%")
    assert f.verdict == "MISMATCH"
    assert "percentage points" in warn(f, "pct_vs_pp")[0]["message"]
    f = finding(checker, "Female LFPR rose by 4.7 percentage points between 2022-23 and 2023-24.")
    assert f.verdict == "MATCH"


def test_relative_change_in_percent_is_fine(checker):
    f = finding(checker, "Female LFPR rose by 12.7% between 2022-23 and 2023-24.")
    assert f.verdict == "MATCH"


def test_wrong_year(checker):
    f = finding(checker, "Child wasting stood at 21% in NFHS-5.")
    assert f.verdict == "MISMATCH" and warn(f, "wrong_year")


def test_survey_vs_admin(checker):
    f = finding(checker, "Stunting has fallen to 33% as per Poshan Tracker.")
    assert f.verdict == "UNVERIFIED" and warn(f, "survey_vs_admin")


def test_cpi_splice_note(checker):
    f = finding(checker, "CPI inflation fell to 2.1% in 2025-26.")
    assert any("2024=100" in w["message"] for w in warn(f, "source_note"))
