# v0.5.1 speed: before / after timings (3 Nov 2026)

Draft: `tests/fixtures/long_policy_draft.docx` (built by `scripts/make_long_draft.py`): an India rural water / rural
economy policy note, 67 sentences, 51 claims (4 opinions), with references, DOIs and an arXiv id. 40 of its sentences are
copied unchanged from the labelled sets in `data/`.

Method: the web app's code path (`POST /check/file?format=json`, FastAPI test client), live sources, no keys, an empty
cache for every run (`TRUTHLENS_CACHE` pointed at a new directory), run from a Linux sandbox that reaches the internet
through a proxy in the US. "Before" is v0.5.0 (commit f470640), "after" is v0.5.1. Every request was timed by wrapping
`net.safe_get` / `net.safe_post`.

These timings are from this sandbox, not from the Windows PC where the 232 s check was seen; a network where more
servers hang (as there) is what the "dead servers" rows simulate.

"Work tree" rows ran on the uncommitted v0.5.1 code; normal run 1 and the 57.5 s dead-server run were before two small
follow-ups (arXiv capped at one request at a time; no duplicate entry in the unreachable-sources banner). The "final"
rows ran from a fresh `git archive` extract of the commit in a clean venv.

## Normal network

| Run | Wall time | Headline | Labelled sentences correct (of 40) | Unsafe SUPPORTED |
|---|---|---|---|---|
| v0.5.0 run 1 | 84.4 s | 7 wrong · 3 partly · 31 supported · 6 couldn't check · 4 skipped | 36 | 1 (235) |
| v0.5.0 run 2 | 59.5 s | 7 wrong · 2 partly · 32 supported · 6 couldn't check · 4 skipped | 36 | 1 (235) |
| v0.5.0 run 3 | 59.2 s | 7 wrong · 2 partly · 32 supported · 6 couldn't check · 4 skipped | 36 | 1 (235) |
| v0.5.1 run 1 (work tree) | 30.7 s | 7 wrong · 2 partly · 31 supported · 7 couldn't check · 4 skipped | 38 | 0 |
| v0.5.1 run 2 (work tree) | 32.4 s | 7 wrong · 2 partly · 31 supported · 7 couldn't check · 4 skipped | 38 | 0 |
| v0.5.1 final, fresh extract, run 1 | 35.7 s | 6 wrong · 1 partly · 31 supported · 9 couldn't check · 4 skipped | 37 | 0 |
| v0.5.1 final, fresh extract, run 2 | 38.4 s | 6 wrong · 1 partly · 31 supported · 9 couldn't check · 4 skipped | 37 | 0 |

235 is "The Reserve Bank of India is headquartered in Mumbai." (labelled UNVERIFIED in the v0.2 set). The v0.5.1 runs
did not call it SUPPORTED because PIB was cut off after one timeout; this is run-to-run variation on the fail-closed side,
not an accuracy fix. In v0.5.1 final run 2, 85 requests were answered from the per-request memo cache instead of being sent.

Failures seen (normal network):

- v0.5.0: Lok Sabha archive on Hugging Face (datasets-server.huggingface.co) read timeouts and HTTP 500/502, up to 105.6 s
  of request time per run; arXiv HTTP 429 and 20 s read timeouts; Semantic Scholar HTTP 429 on 13-15 calls per run (all its calls except one 404);
  pib.gov.in proxy errors; one 20 s MoSPI read timeout (run 1). Crossref/OpenAlex 404 for the made-up DOI (expected).
- v0.5.1: the same servers failed (Hugging Face read timeouts, arXiv 429 or read timeout, Semantic Scholar 429,
  OpenAlex 429 in two runs, one pib.gov.in read timeout); each was cut off after its first failure (up to 16 requests
  skipped per host instead of sent).

Verdict changes between v0.5.0 run 2 and v0.5.1 final run 1 on the same draft (4 of 51): 512 (Lok Sabha answer)
CONTRADICTED → SUPPORTED, its label; 525 (Samastipur study) PARTLY → UNVERIFIED and the arXiv groundwater sentence
SUPPORTED → UNVERIFIED (OpenAlex / arXiv cut off after a 429 or timeout); 235 SUPPORTED → UNVERIFIED. 228 (PLFS since
2017-18) was UNVERIFIED in both. The v0.5.0 runs also differed from each other (run 1 vs run 2: two verdicts).

## Dead servers (simulated)

`SIMULATE_DEAD` made six hosts hang until the client's read timeout and then fail, below both versions' code:
www.rbi.org.in, api.mospi.gov.in, api.crossref.org, api.openalex.org, datasets-server.huggingface.co, pib.gov.in.

| Run | Wall time | Headline | Labelled correct (of 40) | Unsafe SUPPORTED |
|---|---|---|---|---|
| v0.5.0 | 377.6 s (MoSPI alone: 141 requests × 20 s timeouts) | 5 wrong · 26 supported · 16 couldn't check · 4 skipped | 29 | 0 |
| v0.5.1 (work tree) | 57.5 s | 5 wrong · 25 supported · 17 couldn't check · 4 skipped | 29 | 0 |
| v0.5.1 final, fresh extract | 60.2 s (1 claim hit the 60 s deadline) | 5 wrong · 26 supported · 16 couldn't check · 4 skipped | 29 | 0 |
| v0.5.1, `TRUTHLENS_LIVE_BUDGET=20` | 20.6 s (33 claims hit the deadline, 27 of them couldn't check) | 3 wrong · 17 supported · 27 couldn't check · 4 skipped | 22 | 0 |

The v0.5.1 final dead-server run gave the same verdict for every claim as the v0.5.0 dead-server run. The 20 s run
gave no SUPPORTED, PARTLY SUPPORTED or CONTRADICTED verdict that the 60 s run did not give: every change moved a claim to
"couldn't check".
