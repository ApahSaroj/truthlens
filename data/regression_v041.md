# v0.4.1 results on every labelled set (no keys: rule-based extraction + heuristic judge)

## Clean estimate: v0.4.1 held-out set, first run (labelled and committed before running; not tuned on)

| run | correct | unsafe SUPPORTED | contradictions caught | file |
|---|---|---|---|---|
| live, 2 Nov 2026 | **22/25 (88%)** | **0** | 5/6 | `testset_v041_heldout_live_first.md` |
| offline (bundled snapshot + offline citation cache) | **20/25 (80%)** | **0** | 5/6 | `testset_v041_heldout_offline_first.md` |

Live misses: 716 (CRR "3 per cent": the RBI source was not routed from the acronym "CRR" alone, so UNVERIFIED),
717 (Female LFPR "on usual status": the variant was read as all-persons usual status, so correct figures were called
CONTRADICTED, a false contradiction), 723 (peak demand August vs July: no month-on-month series for the change
calculator, so UNVERIFIED). Offline also misses 715 and 724 (RBI and JJM values that only the live sources hold).
These were **not** fixed, so the numbers above stay a clean estimate.

## Other sets

| set | how run | v0.4.0 | v0.4.1 | unsafe SUPPORTED (v0.4.1) |
|---|---|---|---|---|
| adversarial v3 + 16 period-change cases (`testset_v3_adversarial.jsonl`, 50) | recorded fixtures | 32/34 (old cases) | first run **47/50** (new cases 15/16); after the "more than halved" fix 48/50 | 0 |
| India v3 (`testset_v3_india_live.jsonl`, 25) | live, 2 Nov 2026 | 23/25 | **23/25** | 0 |
| India v3 | recorded fixtures | 24/25 | 24/25 | 0 |
| India v4 sources (`testset_v4_india_sources.jsonl`, 25) | live, 2 Nov 2026 | 25/25 (after tuning) | **22/25** | 0 |
| India v4 sources | recorded fixtures | 24/25 | 24/25 | 1 (id 619, same as v0.4.0 on fixtures) |
| v0.2 dev (`testset_v2.jsonl`, 45) | recorded fixtures | 43/45 | 43/45 | 0 |
| v0.2 hold-out (`testset_v2_holdout.jsonl`, 28) | recorded fixtures | 21/28 | 21/28 | 0 |
| v0.1 numbers (`testset.jsonl`, 65) | recorded fixtures | 65/65 | 64/65 | n/a |
| v0.1 hold-out (`testset_holdout.jsonl`, 25) | recorded fixtures | 25/25 | 25/25 | n/a |

Notes
- India v4 live 22/25: ids 604-606 (forex reserves, gold, bank credit for the week ended 23 Oct 2026) are now
  UNVERIFIED because RBI's latest Weekly Statistical Supplement is a newer week and the dated figures are no longer in
  the live table. The v0.4.0 code run the same day calls 604 CONTRADICTED (a wrong contradiction); v0.4.1 says UNVERIFIED.
- India v3 live misses: 514 (PIB feed unreachable through our proxy that hour), 525 (OpenAlex HTTP 429).
- v0.1 #24 "The unemployment rate was 6.1% in 2017-18" (labelled CLOSE) is now MISMATCH: under the v0.4.1 rounding
  rule a same-precision difference (6.1 vs the official 6.0) is a mismatch unless the draft's figure is a recorded
  earlier estimate. The label was not changed.
- India v4 fixtures, id 619 "The repo rate was 6.5%." is SUPPORTED (unsafe) when run after the other v4 items on the
  recorded fixtures (in isolation it is UNVERIFIED); v0.4.0 behaves the same. Not fixed in v0.4.1.
