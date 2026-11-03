"""Integrity of the curated dataset and accuracy on the labelled test sets."""
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from truthlens.registry import load_registry
from truthlens.sources.curated import load_curated

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_DOMAINS = ("mospi.gov.in", "pib.gov.in", "indiabudget.gov.in", "rbi.org.in", "censusindia.gov.in",
                    "dhsprogram.com")  # dhsprogram.com hosts the official IIPS/MoHFW NFHS-5 fact sheet


def test_every_record_is_sourced():
    data = load_curated()
    assert data["records"]
    for r in data["records"]:
        s = r["source"]
        host = urlparse(s["url"]).netloc
        assert host.endswith(OFFICIAL_DOMAINS), s["url"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["accessed"])
        assert s["publisher"] and s["title"] and s["published"]
        assert r["status"] in ("current", "superseded_vintage", "old_base")


def test_records_reference_registered_indicators():
    reg = load_registry()
    for r in load_curated()["records"]:
        assert r["indicator"] in reg


def test_one_current_value_per_series_period_stage():
    seen = {}
    for r in load_curated()["records"]:
        if r["status"] != "current":
            continue
        k = (r["indicator"], r["variant"], r["period"], r.get("stage"), r["source"]["key"])
        assert k not in seen, k
        seen[k] = r


def test_registry_has_at_least_ten_indicators():
    assert len(load_registry()) >= 10


@pytest.mark.parametrize("name,min_acc", [("testset.jsonl", 0.95), ("testset_holdout.jsonl", 0.9)])
def test_testset_accuracy(checker, name, min_acc):
    from truthlens.evaluate import evaluate, load_testset
    path = ROOT / "data" / name
    if name == "testset.jsonl":
        assert len(load_testset(path)) >= 40
    res = evaluate(path, checker)
    print(f"\n{name}: accuracy {res['correct']}/{res['n']} = {res['accuracy']:.1%}; "
          f"trap recall {res['trap_hit']}/{res['trap_expected']}")
    assert res["accuracy"] >= min_acc
    assert res["trap_recall"] >= 0.9
