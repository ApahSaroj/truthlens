"""Live smoke test (no keys needed). Records what worked in docs/SMOKE_TEST.md.

  1. MoSPI: the official `mospi-esankhyiki` package (if installed) and TruthLens' REST client, PLFS
     unemployment rate 2023-24, all-India, persons 15+, usual status
  2. World Bank WDI: India population (SP.POP.TOTL)
  3. PIB: fetch one press release, index it, search it; read the PIB RSS feed
  4. Crossref: resolve one DOI (and confirm a fake DOI is reported as not found)
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "SMOKE_TEST.md"


def run(name, fn, results):
    t = time.time()
    try:
        detail = fn()
        results.append((name, True, detail, time.time() - t))
    except Exception as e:  # record, never crash
        results.append((name, False, f"{type(e).__name__}: {str(e)[:300]}", time.time() - t))
        traceback.print_exc()


def main():
    from truthlens.config import Config
    from truthlens.net import make_session
    from truthlens.retrievers.citations import CitationChecker
    from truthlens.retrievers.docs import DocFetcher, DocIndex, DocsRetriever, index_url, pib_rss_items
    from truthlens.retrievers.mospi import MospiClient
    from truthlens.sources.worldbank import WorldBankClient

    tmp = Path(tempfile.mkdtemp(prefix="truthlens-smoke-"))
    cfg = Config.load(path="/nonexistent", cache_dir=tmp)
    results = []

    def mospi_pkg():
        import esankhyiki
        from truthlens.net import LegacyTLSAdapter
        c = esankhyiki._client
        before = c.base_url
        c.base_url = "https://api.mospi.gov.in"
        c.session.verify = True
        c.session.mount("https://", LegacyTLSAdapter())
        with contextlib.redirect_stdout(io.StringIO()):
            d = esankhyiki.get_data("PLFS", {"indicator_code": 3, "frequency_code": 1, "year_type_code": 1, "year": "2023-24",
                                            "state_code": 99, "gender_code": 3, "age_code": 1, "sector_code": 3,
                                            "weekly_status_code": 1, "religion_code": 1, "social_category_code": 1,
                                            "education_code": 0})
        rows = d if isinstance(d, list) else d.get("data", [])
        row = rows[0]
        from importlib.metadata import version
        return (f"mospi-esankhyiki {version('mospi-esankhyiki')}: PLFS UR 2023-24 all-India PS+SS = {row['value']}{row['unit']} "
                f"(package default base_url was {before!r}; pointed at https://api.mospi.gov.in with TLS verification on)")

    def mospi_rest():
        c = MospiClient(cfg)
        got = c.plfs(3, "2023-24")
        nas = c.nas_gdp("2025-26")
        return (f"REST: PLFS UR 2023-24 = {got['value']}%; NAS GDP 2025-26 constant prices = ₹{nas['constant_price']:,.0f} crore "
                f"({nas['revision']}); {got['url']}")

    def worldbank():
        wb = WorldBankClient(cache_dir=tmp / "wb")
        s = wb.series("SP.POP.TOTL")
        y = max(s["values"])
        return f"SP.POP.TOTL India {y} = {s['values'][y]:,} (WDI last updated {s['lastupdated']})"

    pib_url = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2243781"

    def pib_fetch_index():
        idx = DocIndex(tmp / "index.sqlite")
        r = index_url(idx, DocFetcher(cfg), pib_url)
        hits = idx.search("beta version MCP server statistical products", [], k=1)
        return (f"indexed {r['passages']} passages, release date {r['date']}, title “{r['title'][:80]}”; "
                f"top hit: “{hits[0]['text'][:120]}…”")

    def pib_rss():
        items, lang = pib_rss_items(make_session(), cfg.timeout)
        return f"{len(items)} items, language served: {lang}; first: {items[0]['title'][:80] if items else '-'}"

    def crossref():
        cc = CitationChecker(cfg)
        a = cc.resolve_doi("10.1038/s41586-020-2649-2")
        b = cc.resolve_doi("10.5555/jjm.fake.42")
        return f"10.1038/s41586-020-2649-2 -> {a['status']} via {a.get('resolver')}: “{a.get('title')}” ({a.get('year')}); fake DOI -> {b['status']}"

    def datagovin():
        r = make_session().get("https://api.data.gov.in/lists?format=json&limit=1", timeout=cfg.timeout)
        return f"HTTP {r.status_code} (reachability only; data calls need DATAGOVIN_API_KEY)"

    for name, fn in [("MoSPI via official mospi-esankhyiki package", mospi_pkg), ("MoSPI via TruthLens REST client", mospi_rest),
                     ("World Bank WDI API", worldbank), ("PIB press release fetch + index", pib_fetch_index),
                     ("PIB RSS feed", pib_rss), ("Crossref / OpenAlex DOI lookup", crossref),
                     ("data.gov.in API reachability (no key)", datagovin)]:
        run(name, fn, results)
    lines = [f"# Live smoke test, {dt.datetime.now().astimezone().isoformat(timespec='minutes')}", "",
             "No API keys were used. Run with `python scripts/smoke_live.py`.", "",
             "| Check | Result | Detail | Seconds |", "|---|---|---|---|"]
    for name, ok, detail, sec in results:
        lines.append(f"| {name} | {'✅ worked' if ok else '❌ failed'} | {str(detail).replace('|', '/')} | {sec:.1f} |")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
