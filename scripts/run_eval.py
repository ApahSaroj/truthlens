"""Evaluate both labelled-set generations and write the results files.

v0.1 numbers-only sets -> data/testset_results.md
v0.2 all-claim sets    -> data/testset_results_v2.md

Everything is offline: World Bank, MoSPI and Crossref answers are recorded fixtures, and the evidence
index holds the six official documents in tests/fixtures/docs. No LLM or search key is used, so the
v0.2 numbers measure the rule-based extractor and the heuristic judge (the no-key configuration).
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from conftest import FixtureSession  # noqa: E402
from fixture_http import fixture_pipeline  # noqa: E402
from truthlens.checker import Checker  # noqa: E402
from truthlens.evaluate import evaluate, evaluate_v2, to_markdown, to_markdown_v2  # noqa: E402
from truthlens.sources.worldbank import WorldBankClient  # noqa: E402


def v1():
    ck = Checker(worldbank=WorldBankClient(cache_dir=Path(tempfile.mkdtemp()), session=FixtureSession()))
    parts = []
    for name in ("testset.jsonl", "testset_holdout.jsonl"):
        res = evaluate(ROOT / "data" / name, ck)
        parts.append(to_markdown(res).replace("# TruthLens India v0.1 test-set results", f"## {name}"))
        print(f"{name}: {res['correct']}/{res['n']} = {res['accuracy']:.1%} · trap recall {res['trap_hit']}/{res['trap_expected']}")
    header = ("# TruthLens India v0.1: test-set results\n\n"
              "`testset.jsonl` (65 sentences) was written together with the rules. `testset_holdout.jsonl` (25 sentences, "
              "messier phrasing) was written before it was first run: **20/25 (80%) on that first run**; the five misses "
              "were then fixed, so it is now a regression set too.\n\n")
    (ROOT / "data" / "testset_results.md").write_text(header + "\n".join(parts), encoding="utf-8")


def v2():
    parts = []
    for name in ("testset_v2.jsonl", "testset_v2_holdout.jsonl"):
        res = evaluate_v2(ROOT / "data" / name, fixture_pipeline(Path(tempfile.mkdtemp())))
        parts.append(to_markdown_v2(res, name))
        print(f"{name}: {res['correct']}/{res['n']} = {res['accuracy']:.1%} · unsafe SUPPORTED {res['unsafe_supported']} · "
              f"contradictions caught {res['contradictions_total'] - res['contradictions_missed']}/{res['contradictions_total']}")
    header = ("# TruthLens v0.2: all-claim test-set results (no keys: rule-based extraction + heuristic judge)\n\n"
              "Both sets were written before the v0.2 engine existed. Labels are the correct verdict **given the offline evidence "
              "that ships with the tests** (see `data/testset_v2_README.md`).\n\n"
              "**Hold-out, first run (honest number): 18/28 = 64.3%, 0 unsafe SUPPORTED, 2/7 contradictions caught** "
              "(`data/testset_v2_holdout_first_run.md`). The dev set was then used for tuning. The hold-out was looked at once more "
              "after tuning, which exposed two unsafe SUPPORTED verdicts from lexical matching; the general fix (a claim's names must "
              "appear in the evidence before a no-key SUPPORTED) was kept, so the hold-out figures below are no longer a clean "
              "hold-out. Treat the first-run number as the estimate.\n\n")
    (ROOT / "data" / "testset_results_v2.md").write_text(header + "\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    v1()
    v2()
