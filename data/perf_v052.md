# v0.5.2 Quick and Deep: measured timings, memory and accuracy (3 Nov 2026)

All numbers on this page were measured on 3 Nov 2026 in a **Linux sandbox via a US proxy** (Python 3.12), not on a
Windows PC and not on a hosting service. Live runs used real government and research servers with no keys. Treat the
times as one network on one day: a slower or more restricted network (an office PC in India, a free hosting tier) can
be faster or slower, and servers that hang are bounded by the 60 s live budget described in `perf_v051.md`.

"Fresh extract" means a `git archive` of the commit unpacked into an empty folder, installed into a new virtual
environment, with no live-answer cache (`data/live_cache` absent) and an empty request cache.

## 51-claim draft (`tests/fixtures/long_policy_draft.docx`)

The same draft as `perf_v051.md`: 67 sentences, 51 claims (4 opinions), 40 sentences copied from the labelled sets.
Web app code path (`POST /check/file?format=json&mode=...`, FastAPI test client), fresh extract.

| Run | Wall time | Headline | Labelled sentences correct (of 40) | Unsafe SUPPORTED |
|---|---|---|---|---|
| Quick | 0.4 s | 1 wrong · 13 supported · 33 couldn't check · 4 skipped | 19 | 0 |
| Deep, empty live cache, run 1 | 32.9 s | 5 wrong · 1 partly · 29 supported · 12 couldn't check · 4 skipped | 34 | 0 |
| Deep, live cache warm from run 1 (64 answers reused) | 13.4 s | 6 wrong · 1 partly · 29 supported · 11 couldn't check · 4 skipped | 35 | 0 |
| Deep, live cache emptied again | 33.1 s | 6 wrong · 1 partly · 29 supported · 11 couldn't check · 4 skipped | 35 | 0 |

Quick sends no request to any server: it answers from the bundled and synced official data, the deterministic checks
and saved answers, and marks the rest "not checked in Quick mode" (most of the 33 here). That is why it is right on
fewer labelled sentences; its "couldn't check" never means wrong.

Failures seen in every Deep run (each server was cut off after its first failure): the Lok Sabha archive on Hugging
Face (read timeouts, 6 claims affected), Semantic Scholar HTTP 429 (4 claims), OpenAlex HTTP 429 (2-3 claims),
Crossref 404 for the made-up DOI (expected). No claim hit the 60 s deadline.

Compared with v0.5.1 (37/40 on its final runs), two CEA sentences ("peak demand met was 258.27 GW in August 2026",
"plant load factor was 66.85% in August 2026") moved from SUPPORTED to couldn't check. Cause: CEA published September
2026 figures between the v0.5.1 runs and these, and TruthLens reads only CEA's latest month, so August claims no longer
match (checked against `https://cea.nic.in/api/power-sector-performance` on 3 Nov 2026: August 258.27 GW / 66.85%,
September 269.06 GW / 68.34%). This is the fail-closed side, not a code regression; reading earlier months is future work.

## Karnataka rural water policy draft (`tests/fixtures/state_rws_policy_draft.docx`)

> **Circular; withdrawn as evidence (v0.5.3).** This draft was generated from the same bundled data it is checked
> against, so the accuracy figures in this section (86 of 86 and the rest) only show that TruthLens reads back its own
> data. They must not be cited as accuracy on real documents. The wall times were measured and stand. Real-document
> results: `data/realdocs_v053.md`.

209 statements, 169 claims, 113 of them checkable facts (the rest are descriptive text or opinions). Labels in
`tests/fixtures/state_rws_policy_draft_labels.json`. Work tree at the final code, web app code path, live sources for
Deep, empty live cache.

| Mode | Wall time | Headline | Couldn't check: why | Known-true supported | Seeded errors caught | Unsafe SUPPORTED |
|---|---|---|---|---|---|---|
| Quick | 1.0 s | 4 wrong · 86 supported · 23 couldn't check · 56 skipped | 17 not checked in Quick mode, 6 no official dataset | 86 of 86 | 4 of 4 | 0 |
| Deep | 10.6 s | 4 wrong · 86 supported · 23 couldn't check · 56 skipped | 23 no official dataset | 86 of 86 | 4 of 4 | 0 |

By label (both modes): 86/86 known-true SUPPORTED; 4/4 seeded wrong figures CONTRADICTED; 4/4 seeded claims with no
data source not called SUPPORTED; 5/5 near-miss figures not called SUPPORTED or wrong; 66/66 descriptive sentences
skipped as "Not a checkable fact"; 8/8 claims that should stay unverified stayed unverified; 4/4 opinions skipped.

Before the v0.5.2 descriptive-text fix, a Deep run on the same draft gave 5 wrong · 86 supported · 25 couldn't check ·
53 skipped (12.0 s), with three framing sentences ("This draft sets out the policy...", "The State is home to a large
rural population that depends on groundwater...", "Jal Jeevan Mission is implemented in partnership with the States.")
shown as couldn't check. They are now "Not a checkable fact". That earlier run also called "The stage of ground water
extraction in Karnataka is around 70 per cent." wrong (labelled a near miss); the final runs did not. That change is
run-to-run variation in live answers, not a fix.

## Launcher and web server (fresh extract, `./start_truthlens.sh`)

The Mac/Linux launcher was run in a second fresh extract: it created `.venv`, installed TruthLens, and started uvicorn
on 127.0.0.1:8765 (ready within about 65 s, install included). Then, over real HTTP:

| Step | Result |
|---|---|
| `GET /` | 200, the web app page |
| `POST /check/file?mode=quick` (51-claim draft) | 200 in 0.2 s, 1 wrong · 13 supported · 33 couldn't check · 4 skipped |
| `POST /jobs/file` (Quick job, what the page does) → poll `GET /jobs/{id}` → `GET /jobs/{id}/result` | 202, done in 0.23 s, result 200, same headline |
| `POST /jobs/{id}/deep` (the Deep check button) → poll → result | 202, done in 29.3 s, result 200, 5 wrong · 1 partly · 27 supported · 14 couldn't check · 4 skipped |

Server memory (resident set size of the uvicorn Python process, from `/proc/<pid>/status`, one worker):

| Moment | RSS |
|---|---|
| Just started, before any request | 36.8 MB |
| After a first Quick check (checking code loaded) | 66-68 MB |
| Peak during the Deep check (sampled every 0.2 s) | 149.7 MB |
| Idle again after the Deep check | 148.8 MB (Python keeps the memory it grew to) |

Disk: the unpacked folder without its virtual environment 24.1 MB (including 4.8 MB of live-answer cache, 66 files
from one Deep check); the virtual environment 110 MB.

## Not measured

- The Windows `.bat` launchers were not run.
- The page was not used in a real browser; the job flow was driven over HTTP as the page does.
- The Dockerfile was not built (no Docker in the sandbox), so image size and memory inside a container are unknown.
- Memory with several checks at once (up to 4 are allowed) was not measured.
