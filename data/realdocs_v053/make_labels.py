"""Hand labels (3 Nov 2026) for 200 claims v0.5.2 Deep counted as checkable (40 per doc, random.Random(20261103)).
A = checkable against an official national/state statistical dataset (Census, CGWB, NFHS, JJM dashboard, IMD, land-use stats)
B = state-specific programme/administrative figure (only the state's own documents hold it)
D = other factual statement with no statistical dataset (law, history, international facts, qualitative programme facts): needs a citation
C = not a factual claim (heading, TOC, page header/footer, table fragment, merged two-column text, target/plan/shall/objective/procedure/definition/assessment)
garbled = the extracted sentence mixes text from two PDF columns or table cells."""
import json
L = {
"ka_swp2022": {"c12":"C","c19":"C","c21":"C","c141":"C","c25":"C","c109":"C","c104":"C","c18":"C","c7":"C","c80":"C",
  "c34":"B*","c130":"C","c78":"C","c15":"C","c23":"C","c66":"C","c138":"C","c43":"A*","c77":"C","c119":"C","c42":"C","c103":"C",
  "c68":"C","c45":"C","c93":"C","c27":"C","c33":"D*","c128":"C","c16":"C","c4":"C","c10":"C","c41":"B*","c14":"C","c35":"C",
  "c32":"C","c124":"C","c8":"C","c26":"C","c24":"C","c3":"C"},
"mh_swp2019": {"c26":"A","c40":"D","c45":"B","c263":"C","c53":"B","c38":"B","c16":"C","c195":"C","c69":"C","c244":"C","c185":"C",
  "c33":"B","c49":"C","c158":"C","c52":"B","c93":"D","c181":"D","c231":"C","c88":"C","c90":"C","c159":"C","c99":"C","c191":"D",
  "c56":"B","c66":"C","c34":"A","c8":"C","c21":"D","c43":"D","c31":"A","c70":"C","c65":"C","c235":"C","c17":"C","c54":"C",
  "c50":"C","c6":"C","c11":"C","c236":"C","c19":"D"},
"od_swp2007": {"c13":"B","c20":"C","c23":"B","c130":"C","c31":"C","c19":"B","c8":"C","c62":"C","c70":"C","c109":"C","c90":"D",
  "c97":"C","c125":"C","c9":"C","c132":"C","c46":"C","c110":"C","c14":"C","c129":"C","c88":"C","c120":"C","c118":"C","c114":"C",
  "c116":"C","c56":"B","c24":"C","c108":"C","c15":"C","c17":"C","c124":"C","c119":"C","c3":"D","c21":"C","c122":"C","c113":"C",
  "c59":"C","c16":"C","c86":"C","c35":"C","c6":"C"},
"kl_spb_dw": {"c132":"C","c205":"C","c226":"D","c262":"A","c884":"C","c880":"C","c193":"D","c90":"C","c758":"C","c348":"B",
  "c759":"C","c713":"C","c164":"D","c245":"C","c633":"C","c257":"D","c467":"C","c923":"C","c703":"B","c246":"C","c454":"A",
  "c463":"C","c635":"D","c482":"C","c634":"D","c273":"B","c332":"D","c169":"D","c50":"C","c113":"C","c451":"D","c288":"C",
  "c743":"C","c674":"C","c309":"A","c158":"D","c562":"C","c512":"C","c71":"D","c128":"C"},
"ap_rws_om2025": {"c84":"A","c144":"C","c170":"C","c193":"C","c607":"C","c605":"C","c137":"D","c40":"C","c535":"C","c239":"C",
  "c536":"C","c749":"C","c684":"C","c708":"C","c524":"C","c120":"C","c183":"C","c485":"C","c784":"C","c189":"C","c303":"C",
  "c630":"C","c510":"C","c294":"B","c301":"C","c486":"C","c200":"C","c233":"B","c123":"C","c24":"C","c60":"B","c293":"D",
  "c214":"C","c532":"C","c501":"C","c222":"D","c411":"C","c336":"C","c313":"C","c751":"C"},
}
out, tot = [], {}
for doc, labs in L.items():
    sample = json.load(open(f"labels/{doc}_sample.json"))
    ids = [s["claim_id"] for s in sample]
    assert set(ids) == set(labs), (doc, set(ids) ^ set(labs))
    for s in sample:
        lab = labs[s["claim_id"]]
        s["label"], s["garbled_extraction"] = lab[0], lab.endswith("*")
        out.append(s)
        tot.setdefault(doc, {}).setdefault(lab[0], 0); tot[doc][lab[0]] += 1
json.dump(out, open("labels/labels_v052_sample.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(tot)); from collections import Counter; c = Counter(x["label"] for x in out); print(len(out), dict(c))
