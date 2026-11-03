"""Re-run every labelled all-claim set on recorded fixtures (no keys, no network) and write data/regression_v04.md.

  python scripts/run_regression.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

from fixture_http import fixture_pipeline  # noqa: E402
from truthlens.evaluate import evaluate_v2  # noqa: E402

SETS = ["testset_v3_adversarial.jsonl", "testset_v3_india_live.jsonl", "testset_v2.jsonl", "testset_v2_holdout.jsonl",
        "testset_v4_india_sources.jsonl"]


def main():
    only = sys.argv[1:] or SETS
    lines = ["# Regression run (recorded fixtures, no keys, no network)", "",
             "| set | n | correct | unsafe SUPPORTED | contradictions caught |", "|---|---|---|---|---|"]
    for name in only:
        res = evaluate_v2(ROOT / "data" / name, fixture_pipeline(Path(tempfile.mkdtemp())))
        row = (f"| {name} | {res['n']} | {res['correct']}/{res['n']} ({res['accuracy']:.0%}) | {res['unsafe_supported']} | "
               f"{res['contradictions_total'] - res['contradictions_missed']}/{res['contradictions_total']} |")
        print(row, flush=True)
        lines.append(row)
        for r in res["rows"]:
            if not r["ok"]:
                lines.append(f"|  miss {r['id']} | expected {r['expected']} | got {r['got']} | {r['method']} | {r['text'][:90]} |")
    if not sys.argv[1:]:
        (ROOT / "data" / "regression_v04.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        print("\n".join(lines[4:]))


if __name__ == "__main__":
    main()
