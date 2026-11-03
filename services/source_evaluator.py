import json
from pathlib import Path

SOURCES_PATH = Path(__file__).resolve().parent.parent / "data" / "trusted_sources.json"


def load_sources():
    with open(SOURCES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_source(domain: str):
    sources = load_sources()
    for category, info in sources.items():
        if domain in info["domains"]:
            return {"domain": domain, "category": category, "weight": info["weight"]}
    return {"domain": domain, "category": "unknown", "weight": 10}
