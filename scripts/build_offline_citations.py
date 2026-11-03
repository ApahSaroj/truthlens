"""Build truthlens/data/offline_citations.json: a small offline Crossref/OpenAlex/arXiv cache made only from responses
recorded from the live services (tests/fixtures). Synthetic fixtures are never used. Run from the repo root:

    python scripts/build_offline_citations.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
OUT = ROOT / "truthlens" / "data" / "offline_citations.json"


def _oa_abstract(inv):
    if not inv:
        return ""
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _, w in pos)


def main() -> None:
    dois: dict = {}
    for f in sorted((FIX / "crossref").glob("*.json")):
        m = json.loads(f.read_text())["message"]
        year = None
        for k in ("published-print", "published-online", "issued", "created"):
            parts = (m.get(k) or {}).get("date-parts") or [[None]]
            if parts and parts[0] and parts[0][0]:
                year = parts[0][0]
                break
        doi = m["DOI"].lower()
        dois[doi] = {"resolver": "crossref", "title": " ".join(m.get("title") or []),
                     "container": " ".join(m.get("container-title") or []), "year": year,
                     "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (m.get("author") or [])][:8],
                     "abstract": re.sub(r"<[^>]+>", " ", m.get("abstract", "")).strip(),
                     "url": m.get("URL") or f"https://doi.org/{doi}", "recorded": "2026-11-01", "source_file": f"crossref/{f.name}"}
    oa = json.loads((FIX / "live" / "openalex_search_jjm.json").read_text())
    for r in oa.get("results", []):
        if not r.get("doi"):
            continue
        doi = r["doi"].lower().replace("https://doi.org/", "")
        dois.setdefault(doi, {"resolver": "openalex", "title": r.get("title") or "",
                              "container": ((r.get("primary_location") or {}).get("source") or {}).get("display_name") or "",
                              "year": r.get("publication_year"),
                              "authors": [a.get("author", {}).get("display_name", "") for a in (r.get("authorships") or [])][:8],
                              "abstract": _oa_abstract(r.get("abstract_inverted_index")), "url": r["doi"],
                              "recorded": "2026-11-01", "source_file": "live/openalex_search_jjm.json"})
    arxiv: dict = {}
    for name in ("recorded.json", "recorded_v04.json"):
        rec = json.loads((FIX / "live" / name).read_text())
        for url, v in rec.items():
            m = re.search(r"export\.arxiv\.org/api/query\?id_list=([\d.]+)", url)
            if not m or v.get("status") != 200:
                continue
            text = v.get("text") or ""
            entry = re.search(r"<entry>(.*?)</entry>", text, re.S)
            if not entry or "<title>Error</title>" in entry.group(1):
                continue
            e = entry.group(1)
            title = re.sub(r"\s+", " ", (re.search(r"<title>(.*?)</title>", e, re.S) or [None, ""])[1]).strip()
            if not title:
                continue
            summary = re.sub(r"\s+", " ", (re.search(r"<summary>(.*?)</summary>", e, re.S) or [None, ""])[1]).strip()
            year = (re.search(r"<published>(\d{4})", e) or [None, None])[1]
            authors = re.findall(r"<name>(.*?)</name>", e)[:8]
            arxiv[m.group(1)] = {"resolver": "arxiv", "title": title, "year": int(year) if year else None, "authors": authors,
                                 "abstract": summary, "url": f"https://arxiv.org/abs/{m.group(1)}",
                                 "recorded": "2026-11-02", "source_file": f"live/{name}"}
    OUT.write_text(json.dumps({
        "_about": "Offline citation cache: DOI and arXiv records recorded from the live Crossref, OpenAlex and arXiv APIs "
                  "(tests/fixtures). Used only when TruthLens runs offline. A DOI found here is reported as 'citation exists "
                  "(offline cache)'; a DOI not here is 'can't check offline', never 'fake'.",
        "dois": dois, "arxiv": arxiv}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(dois)} DOI(s), {len(arxiv)} arXiv id(s) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
