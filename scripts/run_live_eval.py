"""Score the India live set (data/testset_v3_india_live.jsonl) with and without live sources, no keys.

  python scripts/run_live_eval.py            # live run (records responses to tests/fixtures/live/recorded.json)
  python scripts/run_live_eval.py --offline  # curated snapshot + fixtures only
Writes data/testset_v3_india_live_<mode>.md. Labels were written before the first run."""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--set", default="testset_v3_india_live.jsonl")
    ap.add_argument("--tag", default="")
    ap.add_argument("--record", default="recorded.json", help="file under tests/fixtures/live/ for the recorded responses")
    a = ap.parse_args()
    from truthlens.config import Config
    from truthlens.evaluate import evaluate_v2
    from truthlens.net import make_session
    from truthlens.pipeline import Pipeline
    tmp = Path(tempfile.mkdtemp())
    if a.offline:
        from fixture_http import fixture_pipeline
        pipe = fixture_pipeline(tmp, offline=True)
        mode = "offline"
    else:
        from record_session import RecordingSession
        sess = RecordingSession(make_session(legacy_tls=True), ROOT / "tests" / "fixtures" / "live" / a.record)
        cfg = Config.load(path="/nonexistent", cache_dir=tmp)
        cfg.llm_provider = cfg.search_provider = "none"
        pipe = Pipeline(cfg, llm=None, session=sess)
        mode = "live"
    t0 = time.time()
    res = evaluate_v2(ROOT / "data" / a.set, pipe, workers=1 if a.offline else 6)
    dt = time.time() - t0
    if not a.offline:
        sess.save()
    lines = [f"# {a.set}: {mode} run{(' ' + a.tag) if a.tag else ''}", "",
             f"- Correct: **{res['correct']}/{res['n']} = {res['accuracy']:.1%}**",
             f"- Unsafe SUPPORTED: {res['unsafe_supported']}",
             f"- Contradictions caught: {res['contradictions_total'] - res['contradictions_missed']}/{res['contradictions_total']}",
             f"- Wall time: {dt:.0f} s", "", "| id | expected | got | method | sentence |", "|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(f"| {r['id']} | {r['expected']} | {r['got']}{'' if r['ok'] else ' ✗'} | {r['method']} | {r['text']} |")
    out = ROOT / "data" / f"{Path(a.set).stem}_{mode}{('_' + a.tag) if a.tag else ''}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6]))
    print("errors:", json.dumps(pipe.errors()[:12], indent=0))


if __name__ == "__main__":
    main()
