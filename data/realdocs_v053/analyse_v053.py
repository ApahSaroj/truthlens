"""Before/after (v052 vs v053 results), the v0.5.2 Deep contradictions and their v0.5.3 verdicts, every v0.5.3 SUPPORTED."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent / "results"
DOCS = ["ka_swp2022", "mh_swp2019", "od_swp2007", "kl_spb_dw", "ap_rws_om2025"]
out = {"table": [], "v052_contradicted": [], "v053_supported": []}
for d in DOCS:
    row = {"doc": d}
    for tag in ("v052", "v053"):
        s = json.load(open(R / tag / f"{d}_summary.json"))
        for m in ("quick", "deep"):
            q = s[m]
            row[f"{tag}_{m}"] = {k: q.get(k) for k in ("claims", "checkable", "contradicted", "partly", "supported", "couldnt_check",
                                                      "skipped", "needs_source", "checked_against_data", "wall_s", "headline")}
    out["table"].append(row)
    old = json.load(open(R / "v052" / f"{d}_deep.json"))
    new = json.load(open(R / "v053" / f"{d}_deep.json"))
    newby = {c["claim"]["text"]: c for c in new["claims"]}
    for c in old["claims"]:
        if c["verdict"] == "CONTRADICTED":
            n = newby.get(c["claim"]["text"])
            out["v052_contradicted"].append({"doc": d, "text": c["claim"]["text"], "v052_rationale": c["rationale"][:400],
                                             "v052_numbers": [(f["claimed"], f["verdict"], (f.get("official") or {}).get("display"), f.get("indicator_name")) for f in c.get("numbers", []) if f["verdict"] != "UNVERIFIED"],
                                             "v053_verdict": n["verdict"] if n else "(sentence not extracted the same way)",
                                             "v053_reason": (n["claim"].get("not_claim") or n["rationale"][:300]) if n else None})
    for c in new["claims"]:
        if c["verdict"] in ("SUPPORTED", "PARTLY SUPPORTED", "CONTRADICTED"):
            out["v053_supported"].append({"doc": d, "verdict": c["verdict"], "text": c["claim"]["text"],
                                          "numbers": [(f["claimed"], f["verdict"], f.get("reason", "")[:200]) for f in c.get("numbers", [])],
                                          "rationale": c["rationale"][:300]})
(R / "analysis_v053.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
for r in out["table"]:
    print(r["doc"], {k: (v["claims"], v["checkable"], v["contradicted"], v["partly"], v["supported"], v["couldnt_check"], v["skipped"], v["needs_source"], v["checked_against_data"], v["wall_s"]) for k, v in r.items() if k != "doc"})
for x in out["v052_contradicted"]: print("\nC052", x["doc"], x["text"][:300], "\n   ", x["v052_numbers"], "\n   ->", x["v053_verdict"], x["v053_reason"])
for x in out["v053_supported"]: print("\nS053", x)
