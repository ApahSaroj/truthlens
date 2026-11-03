"""Build truthlens/data/state_data.json (v0.5.2) from official files downloaded on 3 Nov 2026.

  python scripts/build_state_data.py A-1.xlsx cgwb2025.txt

Inputs (not bundled; re-download to rebuild):
  A-1.xlsx      Census of India 2011, Table A-1 "Number of villages, towns, households, population and area (India,
                States/UTs, districts and sub-districts)", Office of the Registrar General & Census Commissioner, India:
                https://censusindia.gov.in/nada/index.php/catalog/42526/download/46152/A-1_NO_OF_VILLAGES_TOWNS_HOUSEHOLDS_POPULATION_AND_AREA.xlsx
  cgwb2025.txt  (kept in scripts/state_data_inputs/cgwb2025_state_table.txt) Annexure-I "State-wise ground water resources of India, 2025" of the PIB release of 18 Dec 2025
                (Ministry of Jal Shakti, Lok Sabha reply; CGWB Dynamic Ground Water Resources assessment 2025), copied
                row by row as "State|recharge|extractable|extraction|stage": https://www.pib.gov.in/PressReleasePage.aspx?PRID=2206073
NFHS-5 Karnataka values are typed in below from the NFHS-5 Karnataka state report (IIPS and MoHFW, 2021), page 4,
"Housing characteristics" and "Access to toilet facility": https://preview.dhsprogram.com/pubs/pdf/fr374/fr374_karnataka.pdf
(rchiips.org, the IIPS site, answered 404 from the build machine on 3 Nov 2026).
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

ACCESSED = "2026-11-03"
CENSUS_SRC = {"publisher": "Office of the Registrar General & Census Commissioner, India",
              "title": "Census of India 2011, Table A-1: Number of villages, towns, households, population and area",
              "url": "https://censusindia.gov.in/nada/index.php/catalog/42526", "published": "2011 Census", "accessed": ACCESSED}
CGWB_SRC = {"publisher": "Central Ground Water Board, Ministry of Jal Shakti",
            "title": "Dynamic Ground Water Resources assessment 2025, state-wise table (Annexure-I, PIB release of 18 Dec 2025)",
            "url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2206073", "published": "2025-12-18", "accessed": ACCESSED}
NFHS_SRC = {"publisher": "International Institute for Population Sciences and Ministry of Health and Family Welfare",
            "title": "National Family Health Survey (NFHS-5), 2019-21: Karnataka state report, p. 4 (household figures)",
            "url": "https://preview.dhsprogram.com/pubs/pdf/fr374/fr374_karnataka.pdf", "published": "2021", "accessed": ACCESSED}


def title_state(name: str) -> str:
    n = re.sub(r"[@&$#*]+$", "", name.strip()).strip()
    n = re.sub(r"\s*[@$#*&]+\s*$", "", n)
    n = n.replace(" & ", " and ").title().replace(" And ", " and ")
    return {"Nct Of Delhi": "Delhi", "Andaman and Nicobar Islands": "Andaman and Nicobar Islands"}.get(n, n)


def census(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[wb.sheetnames[0]]
    states, districts = [], []
    cur_state = None
    for r in ws.iter_rows(values_only=True):
        if not r or r[3] not in ("INDIA", "STATE", "DISTRICT"):
            continue
        level, name, tru = r[3], str(r[4]), str(r[5]).strip().lower()
        if level == "INDIA":
            geo = "All India"
        elif level == "STATE":
            geo = cur_state = title_state(name)
        else:
            geo = re.sub(r"\s*[@$#*&]+\s*$", "", name).strip()
        rec = {"tru": tru, "villages_inhabited": r[6], "villages_uninhabited": r[7], "towns": r[8], "households": r[9],
               "population": r[10], "males": r[11], "females": r[12], "area_sq_km": r[13], "density": r[14]}
        if level == "DISTRICT":
            districts.append({"state": cur_state, "district": geo, **rec})
        else:
            states.append({"state": geo, **rec})
    return states, districts


def cgwb(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        st, rech, extr, use, stage = line.split("|")
        out.append({"state": st, "recharge_bcm": float(rech), "extractable_bcm": float(extr), "extraction_bcm": float(use),
                    "stage_pct": float(stage)})
    return out


NFHS_KA = [
    ("households using an improved source of drinking water", "total", 96),
    ("households with basic drinking water service", "total", 93),
    ("households with water piped into their dwelling, yard or plot", "total", 47),
    ("households with water piped into their dwelling, yard or plot", "urban", 59),
    ("households with water piped into their dwelling, yard or plot", "rural", 38),
    ("households using an appropriate drinking water treatment method", "total", 39),
    ("households with access to a toilet facility", "total", 83),
    ("households with access to a toilet facility", "urban", 93),
    ("households with access to a toilet facility", "rural", 76),
    ("households that do not use a sanitation facility (open defecation)", "total", 18),
    ("households living in a pucca house", "total", 64),
    ("households with electricity", "total", 99),
    ("households using a clean fuel for cooking", "total", 80),
]


def main(a1, cg):
    states, districts = census(a1)
    data = {"meta": {"name": "TruthLens bundled state and district data", "version": "0.5.2", "accessed": ACCESSED,
                     "policy": "Every value was read from the official file at source.url on the access date. Nothing is "
                               "estimated or projected. NFHS-5 values are household percentages rounded to whole numbers "
                               "in the report text; they can support a matching figure but never contradict one.",
                     "sources": {"census2011": CENSUS_SRC, "cgwb2025": CGWB_SRC, "nfhs5_ka": NFHS_SRC}},
            "census2011_states": states, "census2011_districts": districts, "cgwb2025_states": cgwb(cg),
            "nfhs5_states": [{"state": "Karnataka", "indicator": i, "area": a, "value": v} for i, a, v in NFHS_KA]}
    out = Path(__file__).resolve().parents[1] / "truthlens" / "data" / "state_data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(out, len(states), "state rows,", len(districts), "district rows,", len(data["cgwb2025_states"]), "CGWB rows")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
