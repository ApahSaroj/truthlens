"""Builds samples/sample_policy_note.docx: a short AI-style policy note with a mix of true and false
claims, numbers and citations (some fabricated on purpose) for the TruthLens demo report."""
from pathlib import Path

import docx
from docx.shared import Pt

OUT = Path(__file__).resolve().parent.parent / "samples" / "sample_policy_note.docx"
NAS = "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/aug/doc_9748_20260831_15530601.pdf"

PARAS = [
    ("h", "Policy note (AI-assisted draft): growth, jobs and rural water"),
    ("p", "India's real GDP grew by 7.8% in FY 2025-26, according to MoSPI's National Accounts Statistics 2026 "
          f"({NAS}). Nominal GDP reached ₹345.37 lakh crore in 2025-26."),
    ("p", "In 2024-25, real GDP growth moderated to 6.5%, weighed down by weak manufacturing."),
    ("p", "The unemployment rate fell to 4.9% in 2023-24, and Telangana's unemployment rate was 4.1% in the same year. "
          "Female labour force participation rose from 37.0% in 2022-23 to 41.7% in 2023-24, an increase of 4.7%."),
    ("p", "PLFS has been conducted by MoSPI since 2017-18. In absolute terms, the fiscal deficit for 2024-25 was ₹157.4 billion."),
    ("p", "Jal Jeevan Mission was launched by Prime Minister Narendra Modi on 15 August 2019 [1]. "
          "Today 92% of rural households have tap water connections, up from 3.23 crore households at launch [1]. "
          "The Union Government has extended Jal Jeevan Mission till December 2028."),
    ("p", "In March 2026 the Government introduced a Model Context Protocol server that links AI tools with official "
          "statistics; its beta version covered 12 statistical products [2]. "
          "The Output PPI series that now deflates the IIP was released by the Reserve Bank of India on 15 June 2026."),
    ("p", "A recent meta-analysis found that piped water cut child diarrhoea by 30% (Sharma et al., 2024, doi:10.5555/jjm.fake.42). "
          "Statistical computing in Python builds on array programming with NumPy (Harris et al., 2020, doi:10.1038/s41586-020-2649-2). "
          "The Reserve Bank of India is headquartered in Mumbai."),
    ("p", "Policymakers should prioritise service delivery and source sustainability over new pipelines."),
    ("h2", "Table 1: Key indicators"),
]
TABLE = [
    ["Indicator", "2024-25", "2025-26"],
    ["Real GDP growth (%)", "7.2%", "7.8%"],
    ["CPI inflation (%)", "4.6%", "2.6%"],
    ["Fiscal deficit (% of GDP)", "4.8%", "4.4%"],
]
REFS = [
    "[1] Press Information Bureau, “Jal Jeevan Mission Clocks Seven Years of Rural Transformation”, 14 August 2026. "
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2299487",
    "[2] Press Information Bureau, “Government has introduced a Model Context Protocol server…”, 23 March 2026. "
    "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2243781",
]


def main():
    d = docx.Document()
    d.styles["Normal"].font.size = Pt(11)
    for kind, text in PARAS:
        if kind == "h":
            d.add_heading(text, 1)
        elif kind == "h2":
            d.add_heading(text, 2)
        else:
            d.add_paragraph(text)
    t = d.add_table(rows=len(TABLE), cols=3)
    t.style = "Table Grid"
    for i, row in enumerate(TABLE):
        for j, v in enumerate(row):
            t.cell(i, j).text = v
    d.add_heading("References", 2)
    for r in REFS:
        d.add_paragraph(r)
    OUT.parent.mkdir(exist_ok=True)
    d.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
