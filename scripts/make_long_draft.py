"""Builds tests/fixtures/long_policy_draft.docx: a long (~50 sentence) India rural water / rural economy policy draft
used to time a full live check (v0.5.1 speed work). Sentences are reused from the labelled sets in data/ (v2, v3 India,
v4 India sources, v0.4.1 held-out) plus a few opinions and a reference list, so the mix of checkable figures, opinions
and citations is realistic.

  python scripts/make_long_draft.py
"""
from pathlib import Path

import docx

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "long_policy_draft.docx"

PARAS = [
    ("h", "Policy note (draft): rural water security and the rural economy"),
    ("h2", "1. Macroeconomic context"),
    ("p", "Real GDP grew 7.8% in 2025-26, up from 7.2% in 2024-25. Nominal GDP reached ₹345 lakh crore in 2025-26. "
          "Nominal GDP growth in 2024-25 was 9.4 per cent. Industrial production (IIP) grew 4.3% in 2025-26."),
    ("p", "CPI inflation was 2.1% in 2025-26. Wholesale price inflation was 2.3% in 2024-25. "
          "The fiscal deficit fell from 6.4 per cent of GDP in 2022-23 to 5.6 per cent in 2023-24. "
          "The revised estimate of the fiscal deficit for 2025-26 is 4.4% of GDP. "
          "The fiscal deficit is budgeted at 4.3% of GDP for 2026-27."),
    ("p", "The RBI's policy repo rate is 5.50%. The cash reserve ratio currently stands at 4%. "
          "The statutory liquidity ratio is 18%. "
          "India's foreign exchange reserves stood at US$719.7 billion in the week ended October 23, 2026."),
    ("p", "We believe macroeconomic stability gives the Centre room to raise spending on rural water supply."),
    ("h2", "2. Jobs and households"),
    ("p", "The PLFS unemployment rate on usual status was 3.2% in 2023-24. "
          "Female LFPR on usual status rose from 37.0% in 2022-23 to 41.7% in 2023-24, a rise of 4.7 percentage points. "
          "PLFS has been conducted by MoSPI since 2017-18. "
          "In Maharashtra, the usual-status unemployment rate fell from 4.8% in 2017-18 to 3.3% in 2023-24."),
    ("p", "Average monthly per capita consumption expenditure in rural India was ₹4,122 in 2023-24. "
          "Urban MPCE was ₹6,996 in 2023-24, nearly 70% higher than in rural India. "
          "India's population in the 2011 Census was 121.09 crore. "
          "India's sex ratio was 943 females per 1,000 males in the 2011 Census. Bihar's sex ratio was 950 in 2011."),
    ("p", "In NFHS-5, 35.5% of children under five were stunted. Under NFHS-5, child wasting was 21.0%."),
    ("h2", "3. Jal Jeevan Mission"),
    ("p", "Jal Jeevan Mission was launched by Prime Minister Narendra Modi on 15 August 2019 [1]. "
          "At the launch of Jal Jeevan Mission, only 3.23 crore rural households had tap water connections [1]. "
          "Today more than 15.91 crore rural households have tap water supply, about 82.24% of all rural households [1]. "
          "Jal Jeevan Mission now covers 92% of rural households with tap water."),
    ("p", "The Jal Jeevan Mission is implemented by the Ministry of Education. "
          "The Union Government has extended Jal Jeevan Mission till December 2028. "
          "Goa has provided tap water connections to 100% of its rural households. "
          "Ladakh has tap water connections in 98.53% of rural households."),
    ("p", "In a Lok Sabha answer on 6 August 2026, the Ministry of Jal Shakti addressed the extension of the Jal Jeevan "
          "Mission. A 2026 study of 926 households in Samastipur, Bihar found that 84.9 per cent had a functional tap "
          "connection."),
    ("p", "This is arguably the most ambitious drinking water programme in the world. "
          "It is essential that States invest in water quality testing."),
    ("h2", "4. Groundwater and energy"),
    ("p", "Groundwater pumping to increase food production causes persistent groundwater drought in India "
          "(arXiv:1908.00255). The stage of groundwater extraction in Punjab was 156.36% in 2024. "
          "A PhD thesis on Shodhganga found that 62% of wells in Telangana were over-exploited."),
    ("p", "All-India peak demand met was 258.27 GW in August 2026. "
          "Gujarat had an installed power generation capacity of 79,508.78 MW in September 2026. "
          "CEA data show that the all-India plant load factor was 66.85% in August 2026. "
          "Consumption of diesel (HSD) was 94.7 million tonnes in 2025-26. "
          "India imported 246.6 million tonnes of crude oil in 2025-26."),
    ("h2", "5. Evidence base"),
    ("p", "A recent meta-analysis found that piped water cut child diarrhoea by 30% (Sharma et al., 2024, "
          "doi:10.5555/jjm.fake.42). Statistical computing in Python builds on array programming with NumPy "
          "(Harris et al., 2020, doi:10.1038/s41586-020-2649-2). The Reserve Bank of India is headquartered in Mumbai."),
    ("p", "In March 2026 the Government introduced a Model Context Protocol server that links AI tools with official "
          "statistics; its beta version covered 12 statistical products [2]."),
    ("h2", "6. Recommendations"),
    ("p", "Policymakers should prioritise service delivery and source sustainability over new pipelines. "
          "States should publish village-level functionality data every quarter."),
]
REFS = [
    "[1] Press Information Bureau, “Jal Jeevan Mission Clocks Seven Years of Rural Transformation”, 14 August 2026. "
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2299487",
    "[2] Press Information Bureau, “Government has introduced a Model Context Protocol server…”, 23 March 2026. "
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2243781",
]


def main() -> Path:
    d = docx.Document()
    for kind, text in PARAS:
        if kind == "h":
            d.add_heading(text, level=1)
        elif kind == "h2":
            d.add_heading(text, level=2)
        else:
            d.add_paragraph(text)
    d.add_heading("References", level=2)
    for r in REFS:
        d.add_paragraph(r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.save(OUT)
    return OUT


if __name__ == "__main__":
    print(main())
