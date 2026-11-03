# Contributing to TruthLens India

Thanks for helping. The rules that matter most:

1. **Official sources only.** Every value in `truthlens/data/india_official.json` must be read from an official
   document (MoSPI, RBI, Union Budget / CGA, RGI Census, IIPS NFHS, ministries via PIB) that you opened yourself.
   Record the exact URL, the table/paragraph, the publication date and the date you accessed it in
   `scripts/build_dataset.py`. If you cannot verify a value, leave it out. Never add values from memory,
   news reports or AI answers.
2. **Keep it fail-closed.** A rule that might mis-assign a number should make it UNVERIFIED, not MISMATCH.
3. **Label tests.** Add sentences to `data/testset.jsonl` for each new indicator or trap (at least three),
   with the expected verdict and trap codes.
4. Run `pytest` and `python scripts/run_eval.py` before opening a pull request.

Good first contributions: new aliases for existing indicators, state-level values for one indicator,
more NFHS indicators, sentences from real published reports for the test set.

## Design

The web app and HTML report follow `DESIGN.md` (tokens, type, motion, do's and don'ts). Read it before changing the UI and update it when you change a token.
