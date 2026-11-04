"""v0.7: compare two versions by meaning. Unit tests use a tiny bag-of-words embedder (no model download, no network);
one optional test uses the real model and is skipped when it is not installed and downloaded."""
import json
import os

import pytest

from truthlens import compare as C
from truthlens import meaning as M
from truthlens.readers import Block

# a health policy (any sector works: nothing below is about water)
OLD = [
    Block("1. Introduction", "page 1"),
    Block("The previous policy guided the health sector for two decades and served the country well.", "page 1"),
    Block("2. Primary Care", "page 1"),
    Block("2.1 The Government should provide free primary care services in all districts of the country.", "page 2"),
    Block("Every district hospital shall maintain a register of essential medicines and publish it annually.", "page 2"),
    Block("3. Financing", "page 2"),
    Block("Public health spending shall be raised to 2 percent of GDP by 2010 through budget allocations.", "page 3"),
    Block("The Ministry may encourage states to set up insurance schemes for poor families in rural areas.", "page 3"),
    Block("4. Tobacco Control", "page 3"),
    Block("Advertising of tobacco products near schools shall be banned under the existing tobacco law.", "page 4"),
]
NEW = [
    Block("1. Introduction", "page 1"),
    Block("Therefore, a new health policy responsive to these changes in disease burden is required.", "page 1"),
    Block("2. Primary Care", "page 1"),
    Block("2.1 The Government shall provide free primary care services in all districts of the country by 2025.", "page 2"),
    Block("Every district hospital may keep a register of essential medicines and publish it when possible.", "page 2"),
    Block("3. Financing", "page 2"),
    Block("Public health spending shall be raised to 2.5 percent of GDP by 2025 through budget allocations.", "page 3"),
    Block("States will set up insurance schemes for poor families in rural areas through the National Health Agency.", "page 3"),
    Block("4. Digital Health", "page 3"),
    Block("A national digital health registry will link electronic records of patients across hospitals.", "page 4"),
]


@pytest.fixture()
def emb():
    return M.HashEmbedder()


def _items(rep):
    return {(it["old"] or {}).get("text", "") or it["new"][0]["text"]: (t["topic"], it) for t in rep["topics"]
            for it in t["items"]}


# ---- obligation rules: sector-neutral, no AI ------------------------------------------------------------------------
@pytest.mark.parametrize("text,level", [
    ("The Board shall publish the list.", 3), ("Schools must report every term.", 3),
    ("The agency will ensure compliance.", 3), ("Firms should file returns online.", 2),
    ("It is essential to train staff.", 2), ("States may adopt the scheme.", 1),
    ("Efforts will be made to cover all villages.", 1), ("Industry will be encouraged to recycle.", 1),
    ("As far as possible, power shall be supplied at night.", 1), ("The sector employs many people.", 0),
    ("Water is essential to sustain life.", 0),
])
def test_obligation_levels(text, level):
    assert M.obligation(text) == level


def test_change_labels_by_rule():
    assert M.change_label("Schools should report results.", "Schools shall report results.")[0] == "strengthened"
    lab, why = M.change_label("Hospitals shall publish data.", "Hospitals may publish data where possible.")
    assert lab == "weakened" and any("obligation" in w for w in why)
    lab, why = M.change_label("Ports shall be modernised.", "Ports shall be modernised by 2030.")
    assert lab == "strengthened" and any("deadline added" in w for w in why)
    lab, why = M.change_label("The tariff shall be revised by 2015.", "The tariff shall be revised.")
    assert lab == "weakened" and any("deadline removed" in w for w in why)
    lab, why = M.change_label("Coverage shall reach 40 % of firms.", "Coverage shall reach 60 % of firms.")
    assert lab == "changed figure" and "40 %" in why[0] and "60 %" in why[0]
    lab, why = M.change_label("Disputes should be settled quickly.",
                              "Disputes should be settled quickly by the State Dispute Resolution Authority.")
    assert lab == "strengthened" and any("named body added" in w for w in why)
    assert M.change_label("Roads shall be safe.", "Roads shall be made safe.")[0] == "kept"


# ---- matching, labels, topics -----------------------------------------------------------------------------------------
def test_meaning_compare_labels_and_quotes(emb):
    rep = M.compare_meaning(OLD, NEW, emb)
    items = _items(rep)
    t, it = items["2.1 The Government should provide free primary care services in all districts of the country."]
    assert it["label"] == "strengthened" and t == "Primary Care"
    assert it["new"][0]["text"].startswith("2.1 The Government shall provide")
    assert it["old"]["location"] == "page 2" and it["old"]["para"] == "2.1"
    _t, it = items["Every district hospital shall maintain a register of essential medicines and publish it annually."]
    assert it["label"] == "weakened"
    _t, it = items["Public health spending shall be raised to 2 percent of GDP by 2010 through budget allocations."]
    assert it["label"] == "changed figure" and "2 percent → 2.5 percent" in it["rule"][0]
    _t, it = items["The Ministry may encourage states to set up insurance schemes for poor families in rural areas."]
    assert it["label"] == "strengthened"           # may/encourage -> will, named body added
    _t, it = items["Advertising of tobacco products near schools shall be banned under the existing tobacco law."]
    assert it["label"] == "dropped" and it["new"] == []
    t, it = items["A national digital health registry will link electronic records of patients across hospitals."]
    assert it["label"] == "new" and t == "Digital Health"
    s = rep["summary"]
    assert s["dropped"] >= 1 and s["new"] >= 1 and sum(s.values()) >= 6
    assert rep["topic_source"] == "headings"
    names = [t["topic"] for t in rep["topics"]]
    assert "Financing" in names and "Primary Care" in names


def test_topics_from_headings_are_generic_and_water_preset_is_opt_in(emb):
    rep = M.compare_meaning(OLD, NEW, emb)
    assert not any(t["topic"] in dict(M.WATER_PRESET) for t in rep["topics"])
    water = M.compare_meaning(OLD, NEW, emb, topics="water")
    assert water["topic_source"] == "preset:water"


def test_cluster_topics_when_no_headings(emb):
    old = [Block(b.text, b.location) for b in OLD if len(b.text.split()) > 4]
    new = [Block(b.text, b.location) for b in NEW if len(b.text.split()) > 4]
    rep = M.compare_meaning(old, new, emb)
    assert rep["topic_source"] == "clusters"
    assert all(t["topic"] for t in rep["topics"])
    # labels are the groups' own words, not a fixed sector list
    assert any(w in " ".join(t["topic"] for t in rep["topics"]) for w in ("health", "insurance", "district", "spending",
                                                                          "register", "primary", "tobacco", "digital"))


def test_why_only_quotes_the_document(emb):
    rep = M.compare_meaning(OLD, NEW, emb)
    new_text = " ".join(b.text for b in NEW)
    for t in rep["topics"]:
        for w in t["why"]:
            assert w["text"] in new_text and w["cue"]
        if not t["why"]:
            assert t["why_note"] == "Reason not stated in the document"
    intro = next(t for t in rep["topics"] if t["topic"] == "Introduction")
    assert intro["why"] and intro["why"][0]["text"].startswith("Therefore, a new health policy")
    assert next(t for t in rep["topics"] if t["topic"] == "Financing")["why_note"] == "Reason not stated in the document"


def test_lead_ins_tables_and_captions_are_not_matched():
    assert not M._usable("The objectives of the policy are to:")
    assert not M._usable("Malaria (cases in million) 75 2.7 2.2 Leprosy 38.1 57.3 3.74")
    assert not M._usable("Table 2: Differentials in health status among states")
    assert M._usable("Spending shall rise to 2.5 % of GDP by 2025.")


def test_heading_detection_handles_joined_headings_and_contents_pages():
    blocks = [Block("2. Preamble ........................ 4", "page 1"),
              Block("14. Sustainable Groundwater Management In view of falling water tables, wells will be metered.", "page 5"),
              Block("Some text that is long enough to count as a sentence here.", "page 5"),
              Block("2.1 The state is endowed with bountiful resources which were considered abundant earlier.", "page 6")]
    heads = [h["heading"] for h in M.doc_headings(blocks)]
    assert heads == ["Sustainable Groundwater Management"]      # contents line and numbered paragraph are not headings


# ---- report surfaces -------------------------------------------------------------------------------------------------
def _fake(monkeypatch):
    monkeypatch.setattr(M, "FastEmbedder", lambda *a, **k: M.HashEmbedder())


def test_add_meaning_and_reports(monkeypatch):
    _fake(monkeypatch)
    rep = C.compare_blocks(OLD, NEW, "old.pdf", "new.pdf")
    C.add_meaning(rep, OLD, NEW)
    assert "near_copies" in rep and rep["meaning"]["topics"]
    md = C.render(rep, "md")
    assert "## Match by meaning" in md and "| Topic | kept | strengthened | weakened | changed figure | new | dropped |" in md
    assert "## Wording comparison" in md and "Reason not stated in the document" in md
    h = C.render(rep, "html")
    assert "<h2>Match by meaning</h2>" in h and "<details id='t0'>" in h and "Near-copied sentences" in h
    j = json.loads(C.render(rep, "json"))
    assert j["meaning"]["summary"]["changed figure"] >= 1


def test_meaning_unavailable_keeps_wording(monkeypatch):
    class Broken:
        name = "x"

        def embed(self, texts):
            raise M.MeaningUnavailable("Match by meaning needs the optional extra: pip install \"truthlens[meaning]\"")
    rep = C.compare_blocks(OLD, NEW)
    C.add_meaning(rep, OLD, NEW, embedder=Broken())
    assert "optional extra" in rep["meaning"]["unavailable"] and "near_copies" in rep
    assert "Not run" in C.render(rep, "md") and "Not run" in C.render(rep, "html")


def test_fastembedder_without_package_says_how_to_install(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "fastembed":
            raise ImportError("no fastembed")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(M.MeaningUnavailable) as e:
        M.FastEmbedder(cache_dir=os.devnull + "x").embed(["a"])
    assert 'pip install "truthlens[meaning]"' in str(e.value)


def test_model_choice_names():
    assert M.model_name("english") == M.DEFAULT_MODEL
    assert M.model_name("multilingual") == M.MULTILINGUAL_MODEL
    assert "Hindi" in M.MODEL_NOTES[M.MULTILINGUAL_MODEL]


def _write(tmp_path, name, blocks):
    p = tmp_path / name
    p.write_text("\n\n".join(b.text for b in blocks), encoding="utf-8")
    return str(p)


def test_cli_compare_meaning(tmp_path, monkeypatch, capsys):
    _fake(monkeypatch)
    from truthlens.cli import main
    o, n = _write(tmp_path, "old.txt", OLD), _write(tmp_path, "new.txt", NEW)
    out = tmp_path / "r.json"
    assert main(["compare", o, n, "--meaning", "-f", "json", "-o", str(out)]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["meaning"]["summary"]["dropped"] >= 1
    assert "compare by meaning" in capsys.readouterr().err
    assert main(["compare", o, n, "--meaning", "--topics", "clusters", "-f", "md", "-o", str(tmp_path / "r.md")]) == 0
    assert "Match by meaning" in (tmp_path / "r.md").read_text(encoding="utf-8")


def test_api_compare_meaning(tmp_path, monkeypatch):
    _fake(monkeypatch)
    from fastapi.testclient import TestClient
    from truthlens.api import app
    c = TestClient(app)
    files = {"old": ("old.txt", "\n\n".join(b.text for b in OLD).encode(), "text/plain"),
             "new": ("new.txt", "\n\n".join(b.text for b in NEW).encode(), "text/plain")}
    r = c.post("/compare/file?format=json&meaning=true", files=files)
    assert r.status_code == 200 and r.json()["meaning"]["topics"]
    r = c.post("/compare/file?format=json", files=files)
    assert r.status_code == 200 and "meaning" not in r.json()
    r = c.post("/compare/file?format=html&meaning=true&topics=clusters", files=files)
    assert r.status_code == 200 and "Match by meaning" in r.text
    st = c.get("/compare/meaning-status").json()
    assert "installed" in st and "cache_dir" not in st


def test_webui_has_meaning_toggle():
    from truthlens.webui import PAGE
    assert 'id="cmpmeaning"' in PAGE and "compare/meaning-status" in PAGE and "Match by meaning" in PAGE


# ---- optional AI summary (mocked) -------------------------------------------------------------------------------------
class FakeLLM:
    label = "fake:model"

    def __init__(self, answer=None, exc=None):
        self.answer, self.exc, self.calls = answer, exc, []

    def complete_json(self, system, user, max_tokens=400):
        self.calls.append(user)
        if self.exc:
            raise self.exc
        return self.answer(user) if callable(self.answer) else self.answer


def test_ai_summary_grounded_ok(emb):
    rep = M.compare_meaning(OLD, NEW, emb)
    llm = FakeLLM({"summary": "The new version makes free primary care a firm duty with a deadline.", "quote_ids": [1, 2]})
    M.ai_summaries(rep, llm)
    t = next(t for t in rep["topics"] if t["topic"] == "Primary Care")
    assert t["ai_summary"]["status"] == "ok" and t["ai_summary"]["label"] == "AI summary, check the quotes"
    assert "Use ONLY the numbered quotes" in M.AI_SYSTEM and "[1]" in llm.calls[0]
    assert rep["ai"]["summaries"] >= 1


def test_ai_summary_rejected_when_it_cites_text_or_figures_not_in_quotes(emb):
    rep = M.compare_meaning(OLD, NEW, emb)
    M.ai_summaries(rep, FakeLLM({"summary": 'The policy says "costs fell sharply after reforms" and cut spending to 9 percent.',
                                 "quote_ids": [1]}))
    t = next(t for t in rep["topics"] if t["topic"] == "Financing")
    a = t["ai_summary"]
    assert a["status"] == "rejected" and a["text"] == ""
    assert any("not in the document quotes" in p for p in a["problems"]) and any("figure 9" in p for p in a["problems"])
    rep2 = M.compare_meaning(OLD, NEW, emb)
    M.ai_summaries(rep2, FakeLLM({"summary": "Spending rises.", "quote_ids": [99]}))
    assert all(t["ai_summary"]["status"] == "rejected" for t in rep2["topics"] if "ai_summary" in t)


def test_ai_summary_failure_never_echoes_the_key(emb):
    rep = M.compare_meaning(OLD, NEW, emb)
    M.ai_summaries(rep, FakeLLM(exc=RuntimeError("HTTP 401 bad key sk-ant-SECRET123")))
    blob = json.dumps(rep)
    assert "SECRET123" not in blob and rep["ai"]["failed"] >= 1


# ---- optional: the real model --------------------------------------------------------------------------------------------
def _real_model_ready():
    st = M.status()
    return st["installed"] and st["model_downloaded"]


@pytest.mark.skipif(not _real_model_ready(), reason="optional meaning model not installed/downloaded "
                                                     "(pip install \"truthlens[meaning]\" and run once online)")
def test_real_model_pairs_a_paraphrase():
    rep = M.compare_meaning(OLD, NEW, M.FastEmbedder())
    items = _items(rep)
    _t, it = items["2.1 The Government should provide free primary care services in all districts of the country."]
    assert it["label"] == "strengthened"


def test_bare_subjunctive_and_negation_flag():
    assert M.obligation("Roof top harvesting be implemented on all buildings.") == 2
    assert M.obligation("Water is to be shared.") == 3
    lab, why = M.change_label("Recharge wells should not be encouraged.", "Recharge wells should be adopted with safeguards.")
    assert any("may reverse the meaning" in w for w in why)
