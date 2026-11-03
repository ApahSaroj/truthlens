# TruthLens v0.5.3 on five real public documents

Run on 3 Nov 2026 (IST) in the development sandbox. No keys, no AI provider. Each document was checked with
Quick, then with Deep of only what Quick left (the web app's path), one document after another (not in parallel).
Each run used a fresh live-answer cache and request cache. Everything here is in [`realdocs_v053/`](realdocs_v053/):
the per-document summaries (`*_summary_v052.json`, `*_summary_v053.json`), the analysis
(`analysis_v053.json`), the labels and the scripts as run (their paths are the build machine's).

The documents (public PDFs, not shipped with TruthLens):

| Key | Document |
|---|---|
| ka_swp2022 | Karnataka State Water Policy 2022 |
| mh_swp2019 | Maharashtra State Water Policy 2019 |
| od_swp2007 | Orissa State Water Policy 2007 (as printed in Orissa Review, Sept-Oct 2007) |
| kl_spb_dw | Kerala State Planning Board report on drinking water and sewerage |
| ap_rws_om2025 | Andhra Pradesh rural water supply O&M policy (2025 G.O. and SOP) |

## Before and after (Deep, v0.5.2 vs v0.5.3)

"Checkable" is the number of claims TruthLens tried to check. v0.5.3 reads PDFs line by line and one column at a
time, so the sentence and claim counts differ from v0.5.2 for the same file.

| Doc | Version | Claims | Checkable | Wrong | Partly | Supported | Couldn't check (of which: needs a source / source didn't respond / out of time) | Set aside | Quick s | Deep s |
|---|---|---|---|---|---|---|---|---|---|---|
| ka_swp2022 | v0.5.2 | 146 | 95 | 3 | 0 | 0 | 92 | 51 | 1.5 | 46.5 |
| | v0.5.3 | 98 | 22 | **0** | **1** | 0 | 21 (4 / 17 / 0) | 76 | 0.3 | 35.5 |
| mh_swp2019 | v0.5.2 | 271 | 155 | 2 | 0 | 0 | 153 | 116 | 1.6 | 38.1 |
| | v0.5.3 | 321 | 100 | **0** | **1** | 0 | 99 (81 / 18 / 0) | 221 | 1.5 | 45.7 |
| od_swp2007 | v0.5.2 | 132 | 71 | 1 | 0 | 0 | 70 | 61 | 2.2 | 35.7 |
| | v0.5.3 | 171 | 67 | **0** | 0 | 0 | 67 (49 / 18 / 0) | 104 | 1.0 | 36.0 |
| kl_spb_dw | v0.5.2 | 954 | 685 | 1 | 0 | 0 | 684 | 269 | 4.4 | 60.2 |
| | v0.5.3 | 970 | 526 | **0** | 0 | 0 | 526 (497 / 26 / 3) | 444 | 3.4 | 60.8 |
| ap_rws_om2025 | v0.5.2 | 805 | 411 | 0 | 0 | 0 | 411 | 394 | 3.2 | 47.2 |
| | v0.5.3 | 903 | 343 | 0 | 0 | 0 | 343 (325 / 18 / 0) | 560 | 2.7 | 49.7 |

Quick gave the same wrong and partly counts as Deep on all five documents in v0.5.3.

The two v0.5.3 "partly supported" results were checked by hand against the bundled Census 2011 Table A-1:

- Karnataka: "The State of Karnataka covers an area of 1,91,791 Sq. Kms., i.e., 5.83% of the area of India." The area
  matches Census 2011 (191,791 sq km); the 5.83% is not checked, so the claim is partly supported, not supported.
- Maharashtra: "With population of 112.4 million, as per population Census 2011 and geographical area of 0.308 million
  sq. km, Maharashtra is ranked 2nd ...". The population matches Census 2011 (112.37 million); the area is not checked.

Both are right, so there were **0 unsafe SUPPORTED** on these documents. Wall times are from one run each, in a shared
sandbox, and the live sources were slow or down for part of the run (17-26 claims per document "source didn't
respond"). Treat them as indicative only.

Honest reading: on real state water policy documents TruthLens v0.5.3 settles almost nothing against data (2 claims
in 1,058 checkable, both partly). What it now does is avoid false alarms, set aside text that is not a claim, and
list the claims a reader should see a source for (`-f cite`). That ceiling is explained below.

## The 7 false contradictions in v0.5.2 (Deep), and what v0.5.3 does with them

None of the 7 was a real error in the document.

| # | Doc | Sentence (shortened) | Why v0.5.2 called it wrong | v0.5.3 |
|---|---|---|---|---|
| 1 | ka | "Improving watersheds, rivers, and environment 14 3.12." (a contents entry) | The section number 3.12 was compared with a Lok Sabha answer that holds the figure 37. | Set aside as a heading. A bare number is no longer contradicted by a prose passage without an AI judge. |
| 2 | ka | "It is the eighth The allowable surface water largest state by population ... 61.13 million inhabitants (Census, ..." | Two PDF columns were merged into one sentence. Karnataka's 61.13 million, and a 35,916 million m³ water figure, were compared with the all-India Census population (121.09 crore). | The column is read on its own: "It is the eighth largest state by population with over 61.13 million inhabitants (Census, 2011) ...". A State figure is never compared with an all-India row. Result: couldn't check. Census 2011 gives 61.10 million; that is within 3% and the sentence says "over", so it is not called wrong. |
| 3 | ka | "Floods are becoming common ... Agriculture accounted for about 84% ... 45,052 Million m3 ... 10 to 20 times above the normal." | Merged columns. The change calculator read "42,225 Million → 20" (from "10 to 20 times") as a fall and called it inconsistent. | Columns are read separately. A from → to pair now needs matching scale words. Result: couldn't check. |
| 4 | mh | "In September 2015, the United Nations 193 member states ... 17 Sustainable Development Goals ... next 15 years." | The bare numbers 193 and 15 were "contradicted" by a Lok Sabha answer about SDG monitoring. | Bare numbers are not contradicted by prose. Result: couldn't check. |
| 5 | mh | "With population of 112.4 million, as per population Census 2011 ... Maharashtra ..." | The State's population was compared with all-India 121.09 crore. | Compared with Maharashtra's own Census row: matches 112.37 million. Result: partly supported. |
| 6 | od | "Km.) 41700 7400 4.75% Indravati River is a tributary of Godavari Basin of area3,12,812 Sq." (an annexure table row) | Every figure in the row was compared with the EnviStats Godavari catchment area (312,150 sq km). | When several figures in one sentence are compared with the same official value, they are not each called wrong. Result: couldn't check. |
| 7 | kl | "The Kochi Corporation is spread over 94.88 km2 ... total population of 6,02,046 as per 2011 census." | A city's population was compared with all-India 121.09 crore. | A city or district clause is not compared with a national row. City-level Census figures are not bundled, so the result is couldn't check. |

The fixes are tested in `tests/test_v053_real_docs.py`, using the quoted sentences.

## The ceiling: what kind of statement these documents are made of (200 hand labels)

On 3 Nov 2026, 200 claims were labelled by hand: 40 per document, drawn at random (`random.Random(20261103)`) from the
claims v0.5.2 Deep counted as checkable. The labels were made before the v0.5.3 not-a-claim filter was written.
See `make_labels.py` for the label key and `labels_v052_sample.json`.

| Label | Meaning | Count | Share |
|---|---|---|---|
| A | checkable against an official national or state statistical dataset (Census, CGWB, NFHS, JJM dashboard, IMD, land-use statistics) | 8 | **4%** |
| B | a state programme or administrative figure that only the State's own documents hold | 18 | **9%** |
| D | another factual statement with no statistical dataset behind it (law, history, qualitative programme facts): needs a citation | 24 | **12%** |
| C | not a factual claim (heading, contents entry, page header or footer, table fragment, merged columns, target, plan, "shall", definition, procedure) | 150 | **75%** |

So even a perfect dataset checker could settle only about 4% of what v0.5.2 called "checkable" on these documents.
That is why v0.5.3 leads with "checked against official data" and "need a source you should cite" rather than a score.

The filter on these 200 (the development set; the filter was written while looking at them, so this is **not** a clean
estimate): 90 of 150 non-claims set aside, and 3 of 50 real claims wrongly dropped.

## Held-out check of the not-a-claim filter (blind)

On 3 Nov 2026 (about 14:45-14:50 IST), a new sample was drawn:
20 claims per document, `random.Random(53053)`, from the same population (v0.5.2 Deep claims with checkable = true and
verdict not SKIPPED), with no overlap with the 200 above (`draw_heldout_v053.py`). The drawing script reads claim
text only. The 100 claims were labelled from the text alone, with the same key, before the filter was run on them
(`label_heldout_v053.py`, `heldout_v053_labels.json`). The filter was not changed after scoring.

Labels: A 4, B 6, D 19, C 71.

| Held-out result (n = 100) | As labelled (after the transcription fix) | As first transcribed |
|---|---|---|
| Non-claims set aside | **39 of 71 (55%)** | 37 of 71 |
| Real claims wrongly dropped | **1 of 29 (3%)** | 3 of 29 |

**The transcription fix, stated plainly.** After the first scoring run, I found that four Maharashtra labels
(positions 34-38) had been typed one slot out of line with the labels decided while reading the claims. The intended
labels were c145 C (a "shall" rule), c114 D, c147 C (a planning assumption) and c57 D. Correcting this helps the
filter's numbers, so both results are reported. The first-transcribed run is kept in
`heldout_filter_v053_as_first_transcribed.json`.

The one real claim dropped is Karnataka c38: a merged two-column sentence holding the Census 2011 population (label A,
garbled). The filter saw "projected to be ... in 2020" from the other column and set it aside as a plan. In v0.5.3's
own extraction, the column reader gives that sentence cleanly and it is kept (see contradiction #2 above).

The 32 non-claims the filter kept are mostly running headers ("Orissa Review * September-October - 2007 ..."),
signatures and designations ("The OSD to Chief Secretary to Government."), list items without a verb, table
captions, and section headings joined to their first sentence. They show up as "couldn't check" or "needs a source",
never as wrong. One sample size and one labeller (the developer): treat these as rough rates, not precise ones.

## Regression (recorded fixtures, no network), v0.5.3 work tree, 3 Nov 2026

| Set | v0.5.2 | v0.5.3 | Unsafe SUPPORTED |
|---|---|---|---|
| v0.1 numbers | 64/65 | 64/65 | — |
| v0.1 hold-out | 25/25 | 25/25 | — |
| Adversarial (50) | 48/50 | **50/50** | 0 |
| India v3 | 24/25 | 24/25 | 0 |
| v0.2 dev | 43/45 | 43/45 | 0 |
| v0.2 hold-out | 21/28 | 21/28 | 0 |
| India v4 | 25/25 | 25/25 | 0 |
| v0.4.1 held-out, offline | 20/25 | 20/25 | 0 |

Adversarial rows 422 and 426 (labelled UNVERIFIED; "The MCP server covers 500 statistical products", "... covers 99
products") were CONTRADICTED in v0.5.2 and are now UNVERIFIED. Both carry a bare number, so the likely cause is the
bare-number rule written for the real documents. I did not trace it row by row, and the rule was not tuned on these rows. Files: `evals_v052.json`,
`evals_v053.json`.
