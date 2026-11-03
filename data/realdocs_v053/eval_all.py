"""All labelled regression sets (recorded fixtures, no keys, no network) + v0.4.1 held-out offline.
Usage: python eval_all.py ROOT OUT.json   (ROOT = an extracted TruthLens tree; run with PYTHONPATH=ROOT)"""
import json, os, sys, tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests")); sys.path.insert(0, str(ROOT / "scripts"))
os.environ["TRUTHLENS_CACHE"] = tempfile.mkdtemp()
os.environ["TRUTHLENS_DATA_DIR"] = tempfile.mkdtemp()
from conftest import FixtureSession  # noqa
from fixture_http import fixture_pipeline  # noqa
from truthlens.checker import Checker  # noqa
from truthlens.evaluate import evaluate, evaluate_v2  # noqa
from truthlens.sources.worldbank import WorldBankClient  # noqa

res = {}
ck = Checker(worldbank=WorldBankClient(cache_dir=Path(tempfile.mkdtemp()), session=FixtureSession()))
for name in ("testset.jsonl", "testset_holdout.jsonl"):
    r = evaluate(ROOT / "data" / name, ck)
    res[name] = {"n": r["n"], "correct": r["correct"]}
    print(name, r["correct"], "/", r["n"], flush=True)
for name in ["testset_v3_adversarial.jsonl", "testset_v3_india_live.jsonl", "testset_v2.jsonl", "testset_v2_holdout.jsonl",
             "testset_v4_india_sources.jsonl"]:
    r = evaluate_v2(ROOT / "data" / name, fixture_pipeline(Path(tempfile.mkdtemp())))
    res[name] = {"n": r["n"], "correct": r["correct"], "unsafe_supported": r["unsafe_supported"],
                 "misses": [(x["id"], x["expected"], x["got"]) for x in r["rows"] if not x["ok"]]}
    print(name, r["correct"], "/", r["n"], "unsafe", r["unsafe_supported"], res[name]["misses"], flush=True)
# v0.4.1 held-out, offline (bundled data + offline citation cache), as data/testset_v041_heldout_offline_first.md
from truthlens.config import Config  # noqa
from truthlens.pipeline import Pipeline  # noqa
cfg = Config.load(offline=True)
r = evaluate_v2(ROOT / "data" / "testset_v041_heldout.jsonl", Pipeline(cfg, llm=None))
res["testset_v041_heldout.jsonl (offline)"] = {"n": r["n"], "correct": r["correct"], "unsafe_supported": r["unsafe_supported"],
                                               "misses": [(x["id"], x["expected"], x["got"]) for x in r["rows"] if not x["ok"]]}
print("v041 offline", r["correct"], "/", r["n"], "unsafe", r["unsafe_supported"], flush=True)
OUT.write_text(json.dumps(res, indent=1))
