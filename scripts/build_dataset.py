"""Builds truthlens/data/india_official.json from values read off official documents.

Every value below was read from a document fetched on 2026-11-01; the fetched copies
live in web/downloads/truthlens/ of the Hark workspace. Do not add values that were not
read from a fetched official document.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from truthlens.parsing import format_indian  # noqa: E402

ACCESSED = "2026-11-01"

S = {
    "NAS2026": dict(
        publisher="MoSPI (National Statistics Office)",
        title="Press Release: National Accounts Statistics - 2026 publication (base year 2022-23), table in para 10",
        url="https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/aug/doc_9748_20260831_15530601.pdf",
        published="2026-08-31",
    ),
    "PE2526": dict(
        publisher="MoSPI (National Statistics Office)",
        title="Press Note on Provisional Estimates of Annual GDP for 2025-26 (base 2022-23)",
        url="https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jun/doc202665884801.pdf",
        published="2026-06-05",
    ),
    "NEWSERIES": dict(
        publisher="MoSPI (National Statistics Office)",
        title="Press Note on New Series of GDP Estimates with Base Year 2022-23 (Second Advance Estimates 2025-26)",
        url="https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/feb/doc2026227806401.pdf",
        published="2026-02-27",
    ),
    "PE2425OLD": dict(
        publisher="MoSPI (National Statistics Office)",
        title="Press Note on Provisional Estimates of Annual GDP for 2024-25 (base 2011-12), Statements 1-2",
        url="https://mospi.gov.in/sites/default/files/press_release/NAD_PR_30may2025.pdf",
        published="2025-05-30",
    ),
    "RBIAR": dict(
        publisher="Reserve Bank of India",
        title="RBI Annual Report 2025-26, Appendix Table: Inflation, Money and Credit",
        url="https://www.rbi.org.in/scripts/AnnualReportPublications.aspx?Id=1477",
        published="2026-05-29",
    ),
    "PLFS2324": dict(
        publisher="MoSPI (National Sample Survey Office)",
        title="Press Note on PLFS Annual Report July 2023 - June 2024, Tables 1, 3, 4 and 6",
        url="https://www.mospi.gov.in/sites/default/files/press_release/Press_note_AR_PLFS_2023_24_22092024.pdf",
        published="2024-09-23",
    ),
    "PLFS2025": dict(
        publisher="MoSPI (National Statistics Office)",
        title="Press Note on PLFS Annual Report 2025 (January-December 2025), key findings",
        url="https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774607827733_3e8964a9-268b-4cc9-ad65-cfc8a9e32f08_Press_note_AR_PLFS_2025_23032025_V2.1_26032026_final.pdf",
        published="2026-03-27",
    ),
    "BAG2627": dict(
        publisher="Ministry of Finance, Union Budget",
        title="Budget at a Glance 2026-27, Deficit Statistics",
        url="https://www.indiabudget.gov.in/doc/Budget_at_Glance/budget_at_a_glance.pdf",
        published="2026-02-01",
    ),
    "BAG2526": dict(
        publisher="Ministry of Finance, Union Budget",
        title="Budget at a Glance 2025-26, Budget at a Glance table",
        url="https://www.indiabudget.gov.in/budget2025-26/doc/Budget_at_Glance/budget_at_a_glance.pdf",
        published="2025-02-01",
    ),
    "BAG2425": dict(
        publisher="Ministry of Finance, Union Budget",
        title="Budget at a Glance 2024-25, Budget at a Glance table",
        url="https://www.indiabudget.gov.in/budget2024-25/doc/Budget_at_Glance/budget_at_a_glance.pdf",
        published="2024-07-23",
    ),
    "CENSUSC16": dict(
        publisher="Office of the Registrar General & Census Commissioner, India",
        title="Census of India 2011, Table C-16 (Language), India total population 1,21,08,54,977",
        url="https://censusindia.gov.in/nada/index.php/catalog/42458/download/46089/C-16_25062018.pdf",
        published="2018-06-25",
    ),
    "NFHSFS": dict(
        publisher="IIPS / Ministry of Health and Family Welfare",
        title="NFHS-5 (2019-21) India Fact Sheet, indicators 81-84 (copy hosted by The DHS Program)",
        url="https://dhsprogram.com/pubs/pdf/OF43/India_National_Fact_Sheet.pdf",
        published="2021-11-24",
    ),
    "IIPPPI": dict(
        publisher="MoSPI (National Statistics Office)",
        title="IIP (base 2022-23, Output PPI deflator) - May 2026 release; Sectoral Annual Growth Rates table. Supersedes the 1 June 2026 WPI-deflated series.",
        url="https://www.pib.gov.in/PressReleasePage.aspx?PRID=2278961",
        published="2026-06-29",
    ),
    "IIPWPI": dict(
        publisher="MoSPI (National Statistics Office)",
        title="First press release of IIP new series (base 2022-23, WPI deflator), Statement IV",
        url="https://www.pib.gov.in/PressReleasePage.aspx?PRID=2267531",
        published="2026-06-01",
    ),
    "IIPOLD": dict(
        publisher="MoSPI (National Statistics Office)",
        title="IIP Quick Estimates for March 2026 (base 2011-12), Apr-Mar cumulative growth",
        url="https://www.mospi.gov.in/uploads/latestReleases/latest_release_1777370981972_ac151bbf-29ab-4f2c-a10e-bd727a4d3564_IIP_Press_release_March_2026.pdf",
        published="2026-04-28",
    ),
}

CRORE = 1e7
records = []


def add(indicator, period, value, src, *, variant="default", base=None, vintage=None, stage=None,
        status="current", unit="percent", note=None, display=None):
    src_obj = dict(S[src])
    src_obj["accessed"] = ACCESSED
    src_obj["key"] = src
    records.append(dict(
        indicator=indicator, variant=variant, period=period, value=value, unit=unit,
        base=base, vintage=vintage, stage=stage, status=status, note=note,
        display=display, source=src_obj,
    ))


# --- Real GDP growth (constant prices), % y-o-y, financial year ---
for p, v in [("2023-24", 7.3), ("2024-25", 7.2), ("2025-26", 7.8)]:
    add("gdp_growth_real", p, v, "NAS2026", base="2022-23",
        vintage={"2023-24": "Final Estimate (updated, NAS 2026)", "2024-25": "First Revised Estimate (updated, NAS 2026)",
                 "2025-26": "Provisional Estimate (updated, NAS 2026)"}[p])
add("gdp_growth_real", "2025-26", 7.7, "PE2526", base="2022-23", vintage="Provisional Estimate (5 Jun 2026)", status="superseded_vintage")
add("gdp_growth_real", "2025-26", 7.6, "NEWSERIES", base="2022-23", vintage="Second Advance Estimate (27 Feb 2026)", status="superseded_vintage")
add("gdp_growth_real", "2024-25", 7.1, "NEWSERIES", base="2022-23", vintage="new-series estimate (27 Feb 2026)", status="superseded_vintage")
add("gdp_growth_real", "2023-24", 7.2, "NEWSERIES", base="2022-23", vintage="new-series estimate (27 Feb 2026)", status="superseded_vintage")
add("gdp_growth_real", "2024-25", 6.5, "PE2425OLD", base="2011-12", vintage="Provisional Estimate, old series", status="old_base")
add("gdp_growth_real", "2023-24", 9.2, "PE2425OLD", base="2011-12", vintage="First Revised Estimate, old series", status="old_base")

# --- Nominal GDP growth, % ---
for p, v in [("2023-24", 11.1), ("2024-25", 9.4), ("2025-26", 8.6)]:
    add("gdp_growth_nominal", p, v, "NAS2026", base="2022-23", vintage="updated, NAS 2026")
add("gdp_growth_nominal", "2023-24", 11.0, "NEWSERIES", base="2022-23", vintage="27 Feb 2026", status="superseded_vintage")
add("gdp_growth_nominal", "2024-25", 9.7, "NEWSERIES", base="2022-23", vintage="27 Feb 2026", status="superseded_vintage")
add("gdp_growth_nominal", "2025-26", 8.9, "PE2526", base="2022-23", vintage="Provisional Estimate (5 Jun 2026)", status="superseded_vintage")
add("gdp_growth_nominal", "2023-24", 12.0, "PE2425OLD", base="2011-12", vintage="old series", status="old_base")
add("gdp_growth_nominal", "2024-25", 9.8, "PE2425OLD", base="2011-12", vintage="old series", status="old_base")

# --- Nominal GDP level (current prices), INR (stored absolute; source in Rs crore) ---
def gdp_level(p, crore, src, status, base, vintage):
    add("gdp_nominal", p, crore * CRORE, src, base=base, vintage=vintage, status=status, unit="inr",
        display=f"₹{crore/1e5:,.2f} lakh crore")

gdp_level("2022-23", 26177001, "NAS2026", "current", "2022-23", "Final Estimate (updated, NAS 2026)")
gdp_level("2023-24", 29073287, "NAS2026", "current", "2022-23", "Final Estimate (updated, NAS 2026)")
gdp_level("2024-25", 31798524, "NAS2026", "current", "2022-23", "First Revised Estimate (updated, NAS 2026)")
gdp_level("2025-26", 34536796, "NAS2026", "current", "2022-23", "Provisional Estimate (updated, NAS 2026)")
gdp_level("2022-23", 26117627, "NEWSERIES", "superseded_vintage", "2022-23", "27 Feb 2026")
gdp_level("2023-24", 28983909, "NAS2026", "superseded_vintage", "2022-23", "previously released (Feb/Jun 2026)")
gdp_level("2024-25", 31807309, "NAS2026", "superseded_vintage", "2022-23", "previously released (Feb/Jun 2026)")
gdp_level("2025-26", 34635638, "NAS2026", "superseded_vintage", "2022-23", "Provisional Estimate as released 5 Jun 2026")
gdp_level("2023-24", 30122956, "PE2425OLD", "old_base", "2011-12", "old series")
gdp_level("2024-25", 33068145, "PE2425OLD", "old_base", "2011-12", "Provisional Estimate, old series")

# --- Real GDP level (constant 2022-23 prices), INR ---
def gdp_real_level(p, crore, src, status, vintage):
    add("gdp_real", p, crore * CRORE, src, base="2022-23", vintage=vintage, status=status, unit="inr",
        display=f"₹{crore/1e5:,.2f} lakh crore")

gdp_real_level("2022-23", 26177001, "NAS2026", "current", "Final Estimate (updated, NAS 2026)")
gdp_real_level("2023-24", 28094358, "NAS2026", "current", "Final Estimate (updated, NAS 2026)")
gdp_real_level("2024-25", 30115428, "NAS2026", "current", "First Revised Estimate (updated, NAS 2026)")
gdp_real_level("2025-26", 32470100, "NAS2026", "current", "Provisional Estimate (updated, NAS 2026)")
gdp_real_level("2025-26", 32312034, "NAS2026", "superseded_vintage", "Provisional Estimate as released 5 Jun 2026")
gdp_real_level("2024-25", 29988619, "NAS2026", "superseded_vintage", "previously released (Feb/Jun 2026)")

# --- CPI inflation (All India, combined), annual average, % ---
add("cpi_inflation", "2023-24", 5.4, "RBIAR", base="2012=100")
add("cpi_inflation", "2024-25", 4.6, "RBIAR", base="2012=100")
add("cpi_inflation", "2025-26", 2.1, "RBIAR", base="spliced: 2012=100 (Apr-Dec 2025) + 2024=100 (Jan-Mar 2026)",
    note="RBI computed 2025-26 as the average of monthly inflation rates: April-December 2025 on the old base (2012=100), January 2026 onwards on the new base (2024=100).")

# --- WPI inflation (All commodities, 2011-12=100), % ---
for p, v in [("2017-18", 2.9), ("2018-19", 4.3), ("2019-20", 1.7), ("2020-21", 1.3), ("2021-22", 13.0),
             ("2022-23", 9.4), ("2023-24", -0.7), ("2024-25", 2.3), ("2025-26", 0.7)]:
    add("wpi_inflation", p, v, "RBIAR", base="2011-12=100")

# --- PLFS (persons 15+, rural+urban); PLFS years are July-June ---
years = ["2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24"]
plfs = {
    ("unemployment_rate", "usual_status"): [6.0, 5.8, 4.8, 4.2, 4.1, 3.2, 3.2],
    ("unemployment_rate", "cws"): [8.7, 8.7, 8.8, 7.5, 6.6, 5.1, 4.9],
    ("lfpr", "usual_status"): [49.8, 50.2, 53.5, 54.9, 55.2, 57.9, 60.1],
    ("lfpr", "cws"): [48.4, 48.5, 51.2, 51.8, 51.7, 54.6, 56.4],
    ("lfpr", "female_usual_status"): [23.3, 24.5, 30.0, 32.5, 32.8, 37.0, 41.7],
}
for (ind, var), vals in plfs.items():
    for p, v in zip(years, vals):
        add(ind, p, v, "PLFS2324", variant=var, note="PLFS survey year July-June (e.g. 2023-24 = July 2023 - June 2024).")
add("unemployment_rate", "2025", 3.1, "PLFS2025", variant="usual_status", note="Calendar year 2025 (revamped PLFS from January 2025).")
add("lfpr", "2025", 59.3, "PLFS2025", variant="usual_status", note="Calendar year 2025.")
add("lfpr", "2025", 40.0, "PLFS2025", variant="female_usual_status", note="Calendar year 2025.")
add("unemployment_rate", "2025", 9.9, "PLFS2025", variant="youth_usual_status", note="Age 15-29, calendar year 2025.")
add("unemployment_rate", "2024", 10.3, "PLFS2025", variant="youth_usual_status", note="Age 15-29, calendar year 2024 (as reported in the 2025 annual report press note).")

# --- Union fiscal deficit, % of GDP and Rs crore ---
fd = [
    ("2022-23", "Actual", 6.4, 1737755, "BAG2425"),
    ("2023-24", "BE", 5.9, 1786816, "BAG2425"),
    ("2023-24", "RE", 5.8, 1734773, "BAG2425"),
    ("2023-24", "Provisional Actual", 5.6, 1653670, "BAG2425"),
    ("2023-24", "Actual", 5.6, 1654643, "BAG2526"),
    ("2024-25", "BE", 4.9, 1613312, "BAG2425"),
    ("2024-25", "RE", 4.8, 1569527, "BAG2526"),
    ("2024-25", "Actual", 4.8, 1574431, "BAG2627"),
    ("2025-26", "BE", 4.4, 1568936, "BAG2526"),
    ("2025-26", "RE", 4.4, 1558492, "BAG2627"),
    ("2026-27", "BE", 4.3, 1695768, "BAG2627"),
]
for p, st, pct, crore, src in fd:
    add("fiscal_deficit_pct_gdp", p, pct, src, stage=st)
    add("fiscal_deficit_amount", p, crore * CRORE, src, stage=st, unit="inr",
        display=f"₹{format_indian(crore)} crore (₹{crore/1e5:.2f} lakh crore)")

for p, st, pct in [("2024-25", "Actual", 1.7), ("2025-26", "BE", 1.5), ("2025-26", "RE", 1.5), ("2026-27", "BE", 1.5)]:
    add("revenue_deficit_pct_gdp", p, pct, "BAG2627", stage=st)

# --- Population, Census 2011 ---
add("population", "2011", 1210854977, "CENSUSC16", unit="persons", display="1,21,08,54,977 (121.09 crore)",
    note="Census 2011 (reference date 1 March 2011), total as printed in Table C-16. The RGI Primary Census Abstract release (2013) gives a final total of 1,210,569,573; the two differ by about 2.85 lakh. Both round to 121.1 crore / 1.21 billion.")

# --- NFHS (children under 5), % ---
for ind, n5, n4 in [("child_stunting", 35.5, 38.4), ("child_wasting", 19.3, 21.0), ("child_underweight", 32.1, 35.8)]:
    add(ind, "2019-21", n5, "NFHSFS", vintage="NFHS-5 (2019-21)")
    add(ind, "2015-16", n4, "NFHSFS", vintage="NFHS-4 (2015-16)")

# --- IIP general index, annual growth % ---
for p, v in [("2023-24", 6.8), ("2024-25", 5.7), ("2025-26", 4.3)]:
    add("iip_growth", p, v, "IIPPPI", base="2022-23 (Output PPI deflator)")
for p, v in [("2023-24", 6.7), ("2024-25", 6.4), ("2025-26", 4.3)]:
    add("iip_growth", p, v, "IIPWPI", base="2022-23 (WPI deflator)", status="superseded_vintage",
        note="Superseded on 29 Jun 2026 by the Output-PPI-deflated series.")
add("iip_growth", "2023-24", 5.9, "IIPWPI", base="2011-12", status="old_base")
add("iip_growth", "2024-25", 4.0, "IIPOLD", base="2011-12", status="old_base")
add("iip_growth", "2025-26", 4.1, "IIPOLD", base="2011-12", status="old_base")

out = {
    "meta": {
        "name": "TruthLens India curated official statistics",
        "version": "0.1.0",
        "accessed": ACCESSED,
        "policy": "Every value was read from the official document at source.url on the access date. Values that could not be verified are left out.",
        "status_values": {
            "current": "latest official figure in the current series",
            "superseded_vintage": "an earlier official estimate of the same series (revised since)",
            "old_base": "official figure from the previous base-year series",
        },
    },
    "records": records,
}
p = Path(__file__).resolve().parent.parent / "truthlens" / "data" / "india_official.json"
p.write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(len(records), "records written")
