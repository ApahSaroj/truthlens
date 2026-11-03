# v0.2 labelled sets (all claim types)

`testset_v2.jsonl` (45 sentences, ids 201-245) and `testset_v2_holdout.jsonl` (28 sentences, ids 301-328).

Each line: `{"id", "text", "type", "expected"}`.

- `type` is the expected primary claim type: `numeric`, `citation`, `entity` (factual, non-numeric) or `opinion`.
- `expected` is the **correct verdict given the offline evidence that ships with the tests**: the curated
  India dataset, the recorded World Bank responses, and six official documents in `tests/fixtures/docs/`
  (five PIB press releases and the MoSPI NAS 2026 press-release PDF, fetched on 1 Nov 2026). A true
  statement with no evidence in that corpus is labelled `UNVERIFIED`, because TruthLens fails closed.
  A sentence whose content is supported but whose cited DOI does not exist is labelled `PARTLY SUPPORTED`.
- Opinions are labelled `SKIPPED`.

Both files were written on 1 Nov 2026 **before** the v0.2 claim extractor, retrievers and verdict
engine were written. The hold-out set was committed before any code was run against it; its first-run
score is recorded in `data/testset_results_v2.md` and was not tuned against.
