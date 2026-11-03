"""How the v0.5.3 non-claim filter treats the 200 hand-labelled claims (labels made before the filter was written)."""
import json
from collections import Counter
from truthlens.claims import non_claim_reason, is_descriptive

lab = json.load(open("/workspace/projects/0a5caa18-d686-4eed-be77-4ff38dfcaf75/work/truthlens-realdocs/labels/labels_v052_sample.json"))
cm = Counter()
for x in lab:
    r = non_claim_reason(x["text"]) or ("description" if is_descriptive(x["text"]) else None)
    cm[(x["label"], "set aside" if r else "kept")] += 1
    if x["label"] != "C" and r:
        print("LOST", x["label"], r, "|", x["text"][:150])
for x in lab:
    if x["label"] == "C" and not (non_claim_reason(x["text"]) or is_descriptive(x["text"])):
        print("KEPT-C |", x["text"][:150])
print(sorted(cm.items()))
