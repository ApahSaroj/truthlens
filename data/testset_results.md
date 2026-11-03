# TruthLens India v0.1: test-set results

`testset.jsonl` (65 sentences) was written together with the rules. `testset_holdout.jsonl` (25 sentences, messier phrasing) was written before it was first run: **20/25 (80%) on that first run**; the five misses were then fixed, so it is now a regression set too.

## testset.jsonl

- Sentences: 65
- Verdict accuracy: **64/65 = 98.5%**
- Trap recall (expected trap warnings raised): 25/25 = 100.0%

| Verdict | Precision | Recall | Support |
|---|---|---|---|
| MATCH | 1.00 | 1.00 | 38 |
| CLOSE | 1.00 | 0.75 | 4 |
| MISMATCH | 0.93 | 1.00 | 14 |
| UNVERIFIED | 1.00 | 1.00 | 9 |

## Misses

- #24 “The unemployment rate was 6.1% in 2017-18.” expected CLOSE, got MISMATCH

_The test set is small and was written by the developers alongside the rules, so it measures regressions, not real-world accuracy. A larger set of sentences taken from published Indian reports is on the roadmap._

## testset_holdout.jsonl

- Sentences: 25
- Verdict accuracy: **25/25 = 100.0%**
- Trap recall (expected trap warnings raised): 5/5 = 100.0%

| Verdict | Precision | Recall | Support |
|---|---|---|---|
| MATCH | 1.00 | 1.00 | 19 |
| CLOSE | — | — | 0 |
| MISMATCH | 1.00 | 1.00 | 3 |
| UNVERIFIED | 1.00 | 1.00 | 3 |

## Misses

None.

_The test set is small and was written by the developers alongside the rules, so it measures regressions, not real-world accuracy. A larger set of sentences taken from published Indian reports is on the roadmap._
