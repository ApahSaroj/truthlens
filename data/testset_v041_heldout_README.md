# v0.4.1 held-out set (25 sentences)

Written and labelled **before** TruthLens was run on any of these sentences (this file and the `.jsonl` were committed
before the first run). It covers the v0.4.1 review areas: period-change claims (8), opinion-hedged facts and trends (6,
incl. one pure opinion), rounding (4) and acronyms / name tokens (7). Labels are the true verdict against the official
source named in each line (live sources where the line says "live"). The same labels are used for the live and the
offline run, so offline runs are expected to score lower on the live-only items.

Rules: run once live and once offline; report those first-run numbers; do **not** tune on this set.
