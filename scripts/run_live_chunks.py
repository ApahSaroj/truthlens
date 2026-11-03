"""Run a labelled set live in chunks (for environments that cap a command's run time), then write the same report as
scripts/run_live_eval.py. Each sentence is still run exactly once.

  python scripts/run_live_chunks.py --set testset_v041_heldout.jsonl --tag first --start 0 --end 8
  ... --start 8 --end 16, --start 16 --end 25, then:
  python scripts/run_live_chunks.py --set testset_v041_heldout.jsonl --tag first --finish
"""
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
    ap.add_argument("--set", required=True)
    ap.add_argument("--tag", default="first")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=0)
    ap.add_argument("--finish", action="store_true")
    ap.add_argument("--record", default="recorded_v041.json")
    a = ap.parse_args()
    from truthlens.evaluate import evaluate_v2, load_testset
    stem = Path(a.set).stem
    state = Path(tempfile.gettempdir()) / f"{stem}_live_{a.tag}_state.json"
    rows = json.loads(state.read_text()) if state.exists() else {"rows": [], "time": 0.0}
    if a.finish:
        rs = sorted(rows["rows"], key=lambda r: r["id"])
        n, correct = len(rs), sum(r["ok"] for r in rs)
        unsafe = sum(1 for r in rs if r["got"] == "SUPPORTED" and r["expected"] in ("CONTRADICTED", "UNVERIFIED"))
        con = [r for r in rs if r["expected"] == "CONTRADICTED"]
        lines = [f"# {a.set}: live run {a.tag}", "", f"- Correct: **{correct}/{n} = {correct / n:.1%}**",
                 f"- Unsafe SUPPORTED: {unsafe}",
                 f"- Contradictions caught: {sum(r['got'] == 'CONTRADICTED' for r in con)}/{len(con)}",
                 f"- Wall time: {rows['time']:.0f} s (run in chunks: scripts/run_live_chunks.py)", "",
                 "| id | expected | got | method | sentence |", "|---|---|---|---|---|"]
        for r in rs:
            lines.append(f"| {r['id']} | {r['expected']} | {r['got']}{'' if r['ok'] else ' ✗'} | {r['method']} | {r['text']} |")
        out = ROOT / "data" / f"{stem}_live_{a.tag}.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines[:6]))
        return
    from record_session import RecordingSession
    from truthlens.config import Config
    from truthlens.net import make_session
    from truthlens.pipeline import Pipeline
    items = load_testset(ROOT / "data" / a.set)[a.start:a.end]
    done = {r["id"] for r in rows["rows"]}
    items = [it for it in items if it["id"] not in done]
    if not items:
        print("nothing to run")
        return
    sub = Path(tempfile.mkdtemp()) / "subset.jsonl"
    sub.write_text("\n".join(json.dumps(it) for it in items) + "\n", encoding="utf-8")
    sess = RecordingSession(make_session(legacy_tls=True), ROOT / "tests" / "fixtures" / "live" / a.record)
    cache = Path(tempfile.gettempdir()) / f"{stem}_live_{a.tag}_cache"
    cfg = Config.load(path="/nonexistent", cache_dir=cache)
    cfg.llm_provider = cfg.search_provider = "none"
    pipe = Pipeline(cfg, llm=None, session=sess)
    t0 = time.time()
    res = evaluate_v2(sub, pipe, workers=6)
    rows["time"] += time.time() - t0
    sess.save()
    rows["rows"] += res["rows"]
    state.write_text(json.dumps(rows), encoding="utf-8")
    for r in res["rows"]:
        print(r["id"], r["expected"], r["got"], "" if r["ok"] else "MISS")
    print("errors:", json.dumps(pipe.errors()[:8]))


if __name__ == "__main__":
    main()
