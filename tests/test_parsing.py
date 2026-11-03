import pytest

from truthlens.parsing import find_numbers, find_periods, format_indian, human_inr


def nums(text):
    ps = find_periods(text)
    return find_numbers(text, [(p.start, p.end) for p in ps])


@pytest.mark.parametrize("text,value,kind", [
    ("₹15,74,431 crore", 15744310000000, "inr"),
    ("Rs 345.37 lakh crore", 345.37e12, "inr"),
    ("Rs. 2.5 lakh", 250000, "inr"),
    ("INR 3 trillion", 3e12, "inr"),
    ("1,21,08,54,977 people", 1210854977, "bare"),
    ("1,210,854,977 people", 1210854977, "bare"),
    ("121.09 crore people", 1.2109e9, "count"),
    ("1.21 billion people", 1.21e9, "count"),
    ("7.8 per cent", 7.8, "percent"),
    ("7.8 percent", 7.8, "percent"),
    ("7.8%", 7.8, "percent"),
    ("(-)0.7%", -0.7, "percent"),
    ("-0.7%", -0.7, "percent"),
    ("4.7 percentage points", 4.7, "pp"),
    ("25 basis points", 0.25, "pp"),
    ("US$ 4 trillion", 4e12, "usd"),
])
def test_number_parsing(text, value, kind):
    n = nums(text)[0]
    assert n.value == pytest.approx(value)
    assert n.unit_kind == kind


def test_decimals_kept():
    assert nums("7.80%")[0].decimals == 2
    assert nums("8%")[0].decimals == 0


def test_range_flagged():
    n = nums("growth of 6.3-6.8% in 2026-27")[0]
    assert n.is_range


def test_period_numbers_not_values():
    vals = [n.raw for n in nums("rose from 37.0% in 2022-23 to 41.7% in 2023-24")]
    assert vals == ["37.0%", "41.7%"]


@pytest.mark.parametrize("text,label,kind", [
    ("in FY 2023-24", "2023-24", "fy"),
    ("in 2023-24", "2023-24", "fy"),
    ("in FY24", "2023-24", "fy"),
    ("in FY2025", "2024-25", "fy"),
    ("in fiscal 2025-26", "2025-26", "fy"),
    ("July 2023 - June 2024", "2023-24", "fy"),
    ("in Q1 FY27", "Q1 2026-27", "quarter"),
    ("in June 2026", "Jun 2026", "month"),
    ("as per NFHS-5", "2019-21", "survey"),
    ("NFHS-4 round", "2015-16", "survey"),
    ("in 2019-21", "2019-21", "span"),
    ("Census 2011", "2011", "cy"),
    ("in 2024", "2024", "cy"),
])
def test_periods(text, label, kind):
    p = find_periods(text)[0]
    assert (p.label, p.kind) == (label, kind)


def test_base_year_not_claim_period():
    ps = find_periods("GDP at 2011-12 prices grew 6.5% in 2024-25; CPI (2012=100)")
    base = {p.label: p.is_base for p in ps}
    assert base["2011-12"] is True and base["2024-25"] is False and base["2012"] is True


def test_indian_formatting():
    assert format_indian(1210854977) == "1,21,08,54,977"
    assert format_indian(1574431) == "15,74,431"
    assert human_inr(15.74431e12) == "₹15.74 lakh crore"
