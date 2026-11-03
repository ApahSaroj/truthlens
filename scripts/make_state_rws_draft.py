"""Builds tests/fixtures/state_rws_policy_draft.docx (v0.5.2): a long draft that resembles a State rural water supply
policy (Karnataka-like). It is written for testing, not taken from any real policy file.

CIRCULAR (v0.5.3): the draft's figures come from the same bundled data TruthLens checks them against, so results on it
are a regression test only, never evidence of accuracy on real documents (see data/realdocs_v053.md).

* figures are public facts that TruthLens can check against bundled official data (Census 2011 Table A-1, CGWB
  ground water assessment 2025, NFHS-5 Karnataka report) or well-known national facts, some deliberately changed
  (labelled CONTRADICTED) and some given without a year (labelled "not contradicted");
* programme description, objectives, procedures, roles and definitions (no figure to check);
* scheme-detail figures that no public dataset covers (placeholders, labelled "no dataset"); these numbers are
  invented for the test and are NOT facts about Karnataka;
* repeated figures (the same sentence again later in the draft).

Also writes tests/fixtures/state_rws_policy_draft_labels.json: the expected outcome for each labelled sentence.

  python scripts/make_state_rws_draft.py
"""
import json
from pathlib import Path

import docx

HERE = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT = HERE / "state_rws_policy_draft.docx"
LABELS = HERE / "state_rws_policy_draft_labels.json"

# (text, label) label: S supported, C contradicted, Cd changed district figure (district figures are never called wrong,
# so the honest outcome is "not contradicted"), N not contradicted (may be newer / rounded / assumed), D descriptive,
# X no dataset (placeholder), O opinion, None: unlabelled (live-only or national facts whose live answer we do not fix)
SECTIONS = [
    ("Karnataka Rural Drinking Water Supply Policy (draft for consultation)", [
        ("This draft sets out the policy of the Government of Karnataka for rural drinking water supply.", "D"),
        ("The policy shall apply to all rural habitations of the State.", "D"),
        ("The Rural Drinking Water and Sanitation Department shall be the nodal department for this policy.", "D"),
    ]),
    ("1. Background: the State and its people", [
        ("Karnataka had a population of 6.11 crore as per Census 2011.", "S"),
        ("As per Census 2011, Karnataka had a population of 61,095,297.", "S"),
        ("As per Census 2011, the rural population of Karnataka was 3.75 crore.", "S"),
        ("As per Census 2011, the urban population of Karnataka was 2.36 crore.", "S"),
        ("As per Census 2011, Karnataka had 1.34 crore households.", "S"),
        ("As per Census 2011, Karnataka had 79.47 lakh rural households.", "S"),
        ("As per Census 2011, Karnataka had 54.10 lakh urban households.", "S"),
        ("Karnataka has 27,397 inhabited villages according to the 2011 Census.", "S"),
        ("As per Census 2011, Karnataka had 347 towns.", "S"),
        ("The geographical area of Karnataka is 191,791 sq km as per Census 2011.", "S"),
        ("The population density of Karnataka was 319 persons per sq km in 2011.", "S"),
        ("As per Census 2011, Karnataka had a population of 6.5 crore.", "C"),
        ("As per Census 2011, Karnataka had 85 lakh rural households.", "C"),
        ("Karnataka had 29,500 inhabited villages according to the 2011 Census.", "C"),
        ("Karnataka has about 92 lakh rural households today.", "N"),
        ("The State is home to a large rural population that depends on groundwater for drinking water.", "D"),
        ("Rural Karnataka is diverse, from the coastal belt to the dry northern plains.", None),
    ]),
    ("2. Districts", [
        ("As per Census 2011, Tumakuru district had a population of 26.79 lakh.", "S"),
        ("As per Census 2011, Belagavi district had a population of 47.80 lakh.", "S"),
        ("As per Census 2011, Kolar district had 1,608 inhabited villages.", "S"),
        ("As per Census 2011, Raichur district had 2.68 lakh rural households.", "S"),
        ("As per Census 2011, Yadgir district had a population of 11.74 lakh.", "S"),
        ("As per Census 2011, Chitradurga district had 948 inhabited villages.", "S"),
        ("As per Census 2011, Mysuru district had a population of 35 lakh.", "N"),
        ("As per Census 2011, Dakshina Kannada district had 400 inhabited villages.", "N"),
        ("Each district shall constitute a District Water and Sanitation Mission chaired by the Deputy Commissioner.", "D"),
        ("The District Water and Sanitation Mission is responsible for approving village action plans.", "D"),
    ]),
    ("3. Groundwater", [
        ("The stage of ground water extraction in Karnataka was 66.49 per cent in the 2025 assessment.", "S"),
        ("As per the 2025 assessment, the total annual ground water recharge of Karnataka was 19.27 bcm.", "S"),
        ("As per the 2025 assessment, the annual extractable ground water resource of Karnataka was 17.41 bcm.", "S"),
        ("As per the 2025 assessment, annual ground water extraction for all uses in Karnataka was 11.58 bcm.", "S"),
        ("The stage of groundwater extraction in Karnataka was 72 per cent in the 2025 assessment.", "C"),
        ("For India as a whole, the stage of ground water extraction was 60.63 per cent in the 2025 assessment.", "S"),
        ("The stage of ground water extraction in Karnataka is around 70 per cent.", "N"),
        ("Over-dependence on groundwater makes many rural schemes vulnerable in summer.", None),
        ("The Department shall promote recharge structures near drinking water sources.", "D"),
        ("Source sustainability measures include check dams, recharge pits and rejuvenation of tanks.", "D"),
    ]),
    ("4. Household water and sanitation (NFHS-5)", [
        ("In Karnataka, 96 per cent of households use an improved source of drinking water (NFHS-5).", "S"),
        ("In Karnataka, 93 per cent of households have basic drinking water service as per NFHS-5.", "S"),
        ("In Karnataka, 47 per cent of households have water piped into their dwelling, yard or plot (NFHS-5).", "S"),
        ("In rural Karnataka, 38 per cent of households have water piped into their dwelling, yard or plot (NFHS-5).", "S"),
        ("In Karnataka, 83 per cent of households have access to a toilet facility (NFHS-5).", "S"),
        ("In Karnataka, 90 per cent of households use an improved source of drinking water (NFHS-5).", "N"),
        ("Safe sanitation and safe drinking water together reduce the burden of water-borne disease.", None),
    ]),
    ("5. National context", [
        ("Jal Jeevan Mission was launched on 15 August 2019.", None),
        ("India had a population of 121.09 crore in the 2011 Census.", "S"),
        ("As per Census 2011, India had 16.86 crore rural households.", "S"),
        ("As per Census 2011, India had 24.95 crore households.", "S"),
        ("The Jal Jeevan Mission aims to provide a functional household tap connection to every rural household.", "D"),
        ("The service level under the mission is 55 litres per capita per day.", None),
        ("Jal Jeevan Mission is implemented in partnership with the States.", "D"),
    ]),
    ("6. Objectives", [
        ("The objective of this policy is to provide safe and adequate drinking water to every rural household.", "D"),
        ("The policy aims to ensure that every household receives water of prescribed quality on a regular basis.", "D"),
        ("The policy seeks to promote community ownership of village water supply schemes.", "D"),
        ("The policy envisages a shift from source-based to service-based delivery.", "D"),
        ("The State will encourage the use of treated wastewater for non-potable purposes.", "D"),
        ("The Department will strengthen water quality monitoring at all levels.", "D"),
        ("The policy shall promote the conjunctive use of surface water and groundwater.", "D"),
        ("The State will support capacity building of Gram Panchayat members and pump operators.", "D"),
    ]),
    ("7. Institutional arrangements", [
        ("The Gram Panchayat is responsible for operation and maintenance of in-village infrastructure.", "D"),
        ("The Village Water and Sanitation Committee shall be a standing committee of the Gram Panchayat.", "D"),
        ("At least half of the members of the Village Water and Sanitation Committee shall be women.", "D"),
        ("The Taluk Panchayat shall review the progress of schemes every quarter.", "D"),
        ("The State Water and Sanitation Mission shall approve schemes above the delegated limit.", "D"),
        ("The roles of each institution are listed in Annexure II.", "D"),
        ("Rural Drinking Water and Sanitation Department engineers will provide technical support to Gram Panchayats.", "D"),
        ("The Zilla Panchayat Chief Executive Officer shall be the member secretary of the District Mission.", "D"),
    ]),
    ("8. Scheme details (placeholders for testing)", [
        ("The State operates 4,850 multi-village schemes serving 21,300 habitations.", "X"),
        ("A total of 12,640 water quality tests were conducted by district laboratories in the last quarter.", "X"),
        ("The State has trained 18,200 pump operators under the skilling programme.", "X"),
        ("Around 3,400 single-village schemes are being retrofitted with household tap connections.", "X"),
        ("The State has set up 76 water testing laboratories at taluk level.", "X"),
        ("The average per capita supply in surveyed villages was 48 litres per day.", "X"),
        ("About 2,150 villages received water by tanker during the last summer.", "X"),
        ("The State allotted Rs 2,400 crore to rural water supply operation and maintenance in the current year.", "X"),
    ]),
    ("9. Definitions", [
        ("Functional household tap connection means a tap connection that provides water of prescribed quality regularly.", "D"),
        ("Habitation refers to a cluster of households within a village.", "D"),
        ("Service level is defined as the quantity of water supplied per person per day.", "D"),
        ("Grey water means wastewater from kitchens and bathrooms, excluding toilet waste.", "D"),
        ("A multi-village scheme is a scheme that supplies water to more than one village from a common source.", "D"),
    ]),
    ("10. Procedures", [
        ("Every Gram Panchayat shall prepare a Village Action Plan before taking up new works.", "D"),
        ("Water samples shall be tested at least twice a year for chemical contamination.", "D"),
        ("Complaints shall be registered through the toll-free helpline and resolved within seven days.", "D"),
        ("Water tariffs shall be fixed by the Gram Panchayat in consultation with the Village Water and Sanitation Committee.", "D"),
        ("Operators shall maintain daily records of pumping hours and chlorination.", "D"),
        ("Schemes will be handed over to the Gram Panchayat after a trial run of three months.", "D"),
        ("Third-party inspection shall be carried out for all works.", "D"),
    ]),
    ("11. Repeated figures", [
        ("Karnataka had a population of 6.11 crore as per Census 2011.", "S"),
        ("As per Census 2011, Karnataka had 79.47 lakh rural households.", "S"),
        ("The stage of ground water extraction in Karnataka was 66.49 per cent in the 2025 assessment.", "S"),
        ("Karnataka has 27,397 inhabited villages according to the 2011 Census.", "S"),
    ]),
    ("12. Way forward", [
        ("The State should give priority to water-scarce taluks in the coming years.", "O"),
        ("We recommend that every Gram Panchayat publish its water accounts.", "O"),
        ("It is essential to move from asset creation to reliable service.", "O"),
        ("The Department should review this policy every five years.", "O"),
    ]),
]


MODERN = {"belgaum": "Belagavi", "bijapur": "Vijayapura", "bellary": "Ballari", "shimoga": "Shivamogga",
          "chikmagalur": "Chikkamagaluru", "tumkur": "Tumakuru", "mysore": "Mysuru", "gulbarga": "Kalaburagi"}


def district_profiles():
    """Section 13: two true Census 2011 figures per Karnataka district (from the bundled Table A-1 values) and
    a few changed ones; plus one descriptive sentence per district."""
    data = json.loads((Path(__file__).resolve().parent.parent / "truthlens" / "data" / "state_data.json").read_text())
    rows = [r for r in data["census2011_districts"] if r["state"] == "Karnataka" and r["tru"] == "total"
            and r["district"] not in ("Bangalore", "Bangalore Rural")]
    out = []
    for i, r in enumerate(rows):
        name = MODERN.get(r["district"].lower(), r["district"])
        lakh = r["population"] / 1e5
        hh = r["households"] / 1e5
        if i % 7 == 3:      # deliberately wrong, with the year: should be contradicted
            out.append((f"As per Census 2011, {name} district had a population of {lakh * 1.2:.2f} lakh.", "Cd"))
        else:
            out.append((f"As per Census 2011, {name} district had a population of {lakh:.2f} lakh.", "S"))
        out.append((f"As per Census 2011, {name} district had {hh:.2f} lakh households.", "S"))
        out.append((f"The {name} District Water and Sanitation Mission shall review water quality results every month.", "D"))
    return out


def main():
    SECTIONS.append(("13. District profiles", district_profiles()))
    d = docx.Document()
    labels = []
    sid = 0
    for head, sents in SECTIONS:
        d.add_heading(head, level=1)
        for i in range(0, len(sents), 3):
            chunk = sents[i:i + 3]
            d.add_paragraph(" ".join(t for t, _ in chunk))
            for t, lab in chunk:
                sid += 1
                labels.append({"n": sid, "text": t, "label": lab})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.save(OUT)
    LABELS.write_text(json.dumps(labels, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(OUT, sid, "sentences", dict(Counter(x["label"] for x in labels)))


if __name__ == "__main__":
    main()
