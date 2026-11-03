"""Run TruthLens Quick, then Deep-of-what-Quick-left (the web app path), on the real public documents.

Usage: python run_realdocs.py TAG [doc_key ...]
Writes results/<TAG>/<doc>_{quick,deep}.json and results/<TAG>/<doc>_summary.json.
Each run uses a fresh live-answer cache and request cache (TRUTHLENS_DATA_DIR / TRUTHLENS_CACHE under /tmp)."""
import copy, json, os, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = Path("/workspace/projects/0a5caa18-d686-4eed-be77-4ff38dfcaf75/web/downloads/realdocs")
DOC_FILES = {
    "ka_swp2022": "ka_state_water_policy_2022.pdf",
    "mh_swp2019": "mh_state_water_policy_2019.pdf",
    "od_swp2007": "od_state_water_policy_2007.pdf",
    "kl_spb_dw": "kl_spb_drinking_water.pdf",
    "ap_rws_om2025": "ap_rural_om_policy_2025.pdf",
}

tag = sys.argv[1]
keys = sys.argv[2:] or list(DOC_FILES)
out = HERE / "results" / tag
out.mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp(prefix=f"tl_{tag}_"))
os.environ["TRUTHLENS_DATA_DIR"] = str(tmp / "data")
os.environ["TRUTHLENS_CACHE"] = str(tmp / "cache")
os.environ.pop("NDAP_API_TOKEN", None)

from truthlens.config import Config
from truthlens.pipeline import Pipeline
from truthlens.readers import read_file


def summ(rep, secs):
    s = rep["summary"]
    keep = {k: s.get(k) for k in ("statements", "claims", "checkable", "not_checkable", "opinions", "contradicted",
                                   "partly", "supported", "couldnt_check", "skipped", "headline", "verified_score",
                                   "supported_by_confidence", "couldnt_check_reasons", "needs_source",
                                   "checked_against_data", "lead")}
    keep["wall_s"] = round(secs, 1)
    return keep


for k in keys:
    blocks = read_file(DOCS / DOC_FILES[k])
    cfg = Config.load()
    q = Pipeline(cfg, llm=None); q.mode = "quick"
    st = {}
    t = time.monotonic(); rq = q.run(blocks, DOC_FILES[k], {"source_path": DOC_FILES[k]}, mode="quick", state_out=st)
    tq = time.monotonic() - t
    d = Pipeline(Config.load(), llm=None); d.mode = "deep"
    t = time.monotonic(); rd = d.run(blocks, DOC_FILES[k], {"source_path": DOC_FILES[k]}, mode="deep",
                                     prior=copy.deepcopy(st))
    td = time.monotonic() - t
    (out / f"{k}_quick.json").write_text(json.dumps(rq, ensure_ascii=False, default=str))
    (out / f"{k}_deep.json").write_text(json.dumps(rd, ensure_ascii=False, default=str))
    s = {"doc": k, "file": DOC_FILES[k], "blocks": len(blocks), "quick": summ(rq, tq), "deep": summ(rd, td),
         "errors_deep": rd["meta"].get("errors", [])[:20]}
    (out / f"{k}_summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False, default=str))
    print(k, "quick", s["quick"]["headline"], s["quick"]["wall_s"], "| deep", s["deep"]["headline"], s["deep"]["wall_s"],
          flush=True)
