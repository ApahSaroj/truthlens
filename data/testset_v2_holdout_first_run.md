# Hold-out first run (v0.2 engine before any tuning; no LLM key, offline fixture corpus, heuristic judge)

Run on 1 Nov 2026 at the commit that adds this file. Not tuned against afterwards.

## data/testset_v2_holdout.jsonl

- Sentences: 28
- Verdict accuracy: **18/28 = 64.3%**
- Claim-type accuracy: 100.0%
- Unsafe SUPPORTED (expected CONTRADICTED or UNVERIFIED, got SUPPORTED): **0**
- Contradictions caught: 2/7

| Claim type | Correct |
|---|---|
| citation | 2/4 |
| entity | 6/10 |
| numeric | 8/12 |
| opinion | 2/2 |

| Verdict | Precision | Recall | Support |
|---|---|---|---|
| SUPPORTED | 1.00 | 0.69 | 16 |
| PARTLY SUPPORTED | 0.50 | 1.00 | 1 |
| CONTRADICTED | 1.00 | 0.29 | 7 |
| UNVERIFIED | 0.18 | 1.00 | 2 |
| SKIPPED | 1.00 | 1.00 | 2 |

Misses:

- #305 (numeric) “The IIP's quick estimate for May 2026 stood at 122.7, against 116.7 a year earlier.” expected SUPPORTED, got PARTLY SUPPORTED [heuristic]
- #306 (numeric) “Mining and quarrying output contracted 1.6 percent in May 2026.” expected SUPPORTED, got UNVERIFIED [heuristic]
- #307 (numeric) “Electricity and gas supply grew 7.9% in May 2026.” expected CONTRADICTED, got UNVERIFIED [heuristic]
- #312 (numeric) “The mission's service-level norm is 55 litres per capita per day.” expected SUPPORTED, got UNVERIFIED [heuristic]
- #313 (entity) “Jal Jeevan Mission will end in March 2026.” expected CONTRADICTED, got UNVERIFIED [heuristic]
- #317 (entity) “The Output PPI series was released by the Reserve Bank of India.” expected CONTRADICTED, got UNVERIFIED [heuristic]
- #318 (entity) “The Supply and Use Tables for 2022-23 and 2023-24 were updated in the NAS 2026 release.” expected SUPPORTED, got UNVERIFIED [heuristic]
- #323 (citation) “The NAS 2026 press release lists sixty statements (https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/aug/doc_9748_20260831” expected SUPPORTED, got UNVERIFIED [heuristic]
- #325 (citation) “The National Career Service portal is run by the Ministry of Education [https://www.pib.gov.in/PressReleasePage.aspx?PRID=2196924].” expected CONTRADICTED, got UNVERIFIED [heuristic]
- #328 (entity) “The PM Viksit Bharat Rozgar Yojana focuses especially on the services sector.” expected CONTRADICTED, got UNVERIFIED [heuristic]

