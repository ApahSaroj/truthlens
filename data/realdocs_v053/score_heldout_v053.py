"""Score the v0.5.3 not-a-claim filter on the held-out labels (labels/heldout_v053_labels.json, labelled first).
Run with PYTHONPATH=<truthlens tree>. Writes results/heldout_filter_v053.json."""
import json, sys
from collections import Counter
from pathlib import Path
from truthlens.claims import non_claim_reason, is_descriptive
H = Path(__file__).resolve().parent
lab = json.load(open(H / "labels" / "heldout_v053_labels.json"))
cm, lost, kept_c, rows = Counter(), [], [], []
for x in lab:
    r = non_claim_reason(x["text"]) or ("description" if is_descriptive(x["text"]) else None)
    cm[(x["label"], "set aside" if r else "kept")] += 1
    rows.append({**x, "filter": r})
    if x["label"] != "C" and r: lost.append((x["doc"], x["claim_id"], x["label"], r, x["text"][:160]))
    if x["label"] == "C" and not r: kept_c.append((x["doc"], x["claim_id"], x["text"][:120]))
nc = sum(v for (l, _), v in cm.items() if l == "C"); c_aside = cm[("C", "set aside")]
real = sum(v for (l, _), v in cm.items() if l != "C"); real_lost = real - sum(v for (l, k), v in cm.items() if l != "C" and k == "kept")
res = {"n": len(lab), "not_a_claim": nc, "not_a_claim_set_aside": c_aside, "real_claims": real,
       "real_claims_wrongly_dropped": real_lost, "by_label": {f"{l}/{k}": v for (l, k), v in sorted(cm.items())},
       "lost": lost, "kept_non_claims": kept_c, "rows": rows}
(H / "results" / "heldout_filter_v053.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
print(f"non-claims set aside {c_aside}/{nc}; real claims wrongly dropped {real_lost}/{real}"); print(res["by_label"])
for l in lost: print("LOST", l)
for k in kept_c: print("KEPT-C", k)
