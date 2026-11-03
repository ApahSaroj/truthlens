"""Draw the v0.5.3 held-out sample (3 Nov 2026): 20 claims per real doc from the same population as
labels_v052_sample.json (v0.5.2 Deep claims with checkable=True and verdict != SKIPPED), excluding every claim
already in labels_v052_sample.json. random.Random(53053). Writes text only - no filter output is read."""
import json, random
from pathlib import Path
H = Path(__file__).resolve().parent
old = {(x["doc"], x["claim_id"]) for x in json.load(open(H / "labels_v052_sample.json"))}
rng = random.Random(53053)
out = []
for doc in ["ka_swp2022", "mh_swp2019", "od_swp2007", "kl_spb_dw", "ap_rws_om2025"]:
    r = json.load(open(H.parent / "results" / "v052" / f"{doc}_deep.json"))
    pool = [c for c in r["claims"] if c["claim"].get("checkable") and c["verdict"] != "SKIPPED"
            and (doc, c["claim"]["id"]) not in old]
    for c in rng.sample(pool, 20):
        out.append({"doc": doc, "claim_id": c["claim"]["id"], "text": c["claim"]["text"]})
json.dump(out, open(H / "heldout_v053_sample.json", "w"), indent=1, ensure_ascii=False)
print(len(out))
