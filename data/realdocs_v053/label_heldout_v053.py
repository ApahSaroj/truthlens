"""Hand labels for the v0.5.3 held-out sample (heldout_v053_sample.json), written 3 Nov 2026 (IST) from the claim text
alone, before any v0.5.3 filter output was produced for these claims.
Correction after the first scoring run: mh positions 34-38 had been typed one slot out of line with the
labels decided before scoring (c145 C, c114 D, c147 C, c57 D). The first-transcribed result is kept in
results/heldout_filter_v053_as_first_transcribed.json. Same scheme as make_labels.py:
A dataset-checkable, B state programme/administrative figure, D other fact needing a citation, C not a claim; * = garbled."""
import json
from collections import Counter
LAB = ("C C* D* C* C C C C* C* C C* C C* C C* C* A* C* A* C "      # ka 0-19
       "D B C C C D C C C C C B D C C D C C D C "                  # mh 20-39
       "C C C C D C C C D C* C C C B C C B B A C "                 # od 40-59
       "C D D C D C D C C D C D D B C D C C A C "                  # kl 60-79
       "C C C C C C C C C C D C C C C D D C C C").split()          # ap 80-99
s = json.load(open("heldout_v053_sample.json"))
assert len(LAB) == len(s) == 100
for x, l in zip(s, LAB):
    x["label"], x["garbled_extraction"] = l[0], l.endswith("*")
json.dump(s, open("heldout_v053_labels.json", "w"), indent=1, ensure_ascii=False)
print(Counter(x["label"] for x in s))
