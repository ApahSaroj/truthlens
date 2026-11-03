"""Citation checker: does the source a sentence cites exist, and does it contain/support the claim?

* URLs cited in the draft are fetched (any public domain; private and local addresses are refused),
  text is extracted (HTML or PDF with page numbers) and indexed, then searched for the claim's numbers
  and key terms.
* DOIs are resolved with Crossref (https://api.crossref.org/works/{doi}); when Crossref has no record,
  OpenAlex (https://api.openalex.org/works/doi:{doi}) is tried. A DOI unknown to both is reported as
  "not found", which is a strong sign of a fabricated reference. The title and abstract (when the
  publisher deposited one) are what can be checked without the full text.
* Numbered references [n] and author-year references are resolved through the draft's own
  reference list ("References" / "Sources" section) when it contains a URL or DOI.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote

from ..config import Config, redact
from ..model import Claim, Evidence
from ..net import DiskCache, domain_allowed, FetchError, make_session, safe_get, with_params
from .base import Retriever, best_window, contains_number, norm_ws, terms

CROSSREF = "https://api.crossref.org/works/"
OPENALEX = "https://api.openalex.org/works/doi:"
REF_HEAD_RX = re.compile(r"^\s*(references|sources|bibliography|works cited|notes)\s*:?\s*$", re.I)
REF_ENTRY_RX = re.compile(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[.)])\s+(.*)$")


def references_from_blocks(blocks) -> dict:
    """Map reference numbers to the citations (URL/DOI) in the draft's reference list."""
    from ..claims import find_citations
    refs: dict = {}
    in_refs = False
    for b in blocks:
        t = b.text.strip()
        if REF_HEAD_RX.match(t):
            in_refs = True
            continue
        m = REF_ENTRY_RX.match(t)
        if m and (in_refs or "http" in t or "doi" in t.lower()):
            num = m.group(1) or m.group(2)
            cites = [c for c in find_citations(m.group(3)) if c.startswith(("http", "doi:", "arxiv:"))]
            refs[num] = {"text": m.group(3)[:300], "citations": cites}
    return refs


def _jats_to_text(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "")


def _openalex_abstract(inv: Optional[dict]) -> str:
    if not inv:
        return ""
    pos = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    return " ".join(w for _, w in sorted(pos))


OFFLINE_FOUND = "citation exists (offline cache: recorded from {resolver} on {recorded})"
OFFLINE_UNKNOWN = "can't check offline: not in the offline citation cache (this does not mean the reference is fake)"


def _offline_cache() -> dict:
    import json
    from importlib import resources
    try:
        return json.loads(resources.files("truthlens.data").joinpath("offline_citations.json").read_text(encoding="utf-8"))
    except Exception:
        return {"dois": {}, "arxiv": {}}


def offline_cache_dois() -> list[str]:
    """DOIs in the shipped offline cache (recorded from Crossref/OpenAlex; see scripts/build_offline_citations.py)."""
    return sorted(_offline_cache().get("dois", {}))


def offline_doi_lookup(doi: str) -> Optional[dict]:
    rec = _offline_cache().get("dois", {}).get((doi or "").lower().strip().rstrip("."))
    if not rec:
        return None
    return dict(rec, status="found", doi=doi, detail=OFFLINE_FOUND.format(**rec),
                resolver=f"offline cache ({rec.get('resolver')})")


def offline_arxiv_lookup(aid: str) -> Optional[dict]:
    rec = _offline_cache().get("arxiv", {}).get(aid)
    return dict(rec, detail=OFFLINE_FOUND.format(**rec)) if rec else None


class CitationChecker(Retriever):
    name = "citations"

    def __init__(self, cfg: Config, session=None, docs=None, fetcher=None):
        super().__init__(cfg)
        self.session = session or make_session()
        self.cache = DiskCache(cfg.cache_dir, "citations", ttl=30 * 24 * 3600)
        self.docs = docs
        self.fetcher = fetcher
        self.refs: dict = {}
        self.s2 = None        # SemanticScholarRetriever (v0.4): third DOI registry
        self.arxiv = None     # ArxivRetriever (v0.4): arXiv ids

    def status(self) -> dict:
        return self._status(True, "Crossref + OpenAlex for DOIs; cited URLs fetched and searched (no key needed)")

    # ------------------------------------------------------------------ DOI
    def resolve_doi(self, doi: str) -> dict:
        doi = doi.lower().strip().rstrip(".")
        cached = self.cache.get("doi:" + doi)
        if cached is not None:
            return cached
        if self.cfg.offline:
            # v0.4.1: a shipped cache of recorded Crossref/OpenAlex records answers offline; an unknown DOI offline is
            # "can't check offline", never "fake"
            return self.cache.get("doi:" + doi, allow_stale=True) or offline_doi_lookup(doi) or \
                {"status": "unreachable", "doi": doi, "detail": OFFLINE_UNKNOWN}
        params = {"mailto": self.cfg.contact_email} if self.cfg.contact_email else {}
        out: dict = {"doi": doi}
        try:
            r = safe_get(self.session, with_params(CROSSREF + quote(doi, safe="/:;()"), params), self.cfg.timeout, stream=False)
            if r.status_code == 200:
                m = r.json().get("message", {})
                year = None
                for k in ("published-print", "published-online", "issued", "created"):
                    parts = (m.get(k) or {}).get("date-parts") or [[None]]
                    if parts and parts[0] and parts[0][0]:
                        year = parts[0][0]
                        break
                out.update({"status": "found", "resolver": "crossref", "title": " ".join(m.get("title") or []),
                            "container": " ".join(m.get("container-title") or []), "year": year,
                            "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (m.get("author") or [])][:8],
                            "abstract": _jats_to_text(m.get("abstract", "")), "url": m.get("URL") or f"https://doi.org/{doi}"})
            elif r.status_code == 404:
                r2 = safe_get(self.session, with_params(OPENALEX + quote(doi, safe="/:;()"), params), self.cfg.timeout, stream=False)
                if r2.status_code == 200:
                    m = r2.json()
                    out.update({"status": "found", "resolver": "openalex", "title": m.get("title") or "",
                                "container": ((m.get("primary_location") or {}).get("source") or {}).get("display_name") or "",
                                "year": m.get("publication_year"),
                                "authors": [a.get("author", {}).get("display_name", "") for a in (m.get("authorships") or [])][:8],
                                "abstract": _openalex_abstract(m.get("abstract_inverted_index")),
                                "url": m.get("doi") or f"https://doi.org/{doi}"})
                elif r2.status_code == 404:
                    p = self.s2.by_doi(doi) if self.s2 is not None else None
                    if isinstance(p, dict) and p.get("title"):
                        out.update({"status": "found", "resolver": "semanticscholar", "title": p.get("title") or "",
                                    "container": p.get("venue") or "", "year": p.get("year"),
                                    "authors": [a.get("name", "") for a in (p.get("authors") or [])][:8],
                                    "abstract": p.get("abstract") or "", "url": f"https://doi.org/{doi}"})
                    else:
                        out.update({"status": "not_found", "detail": "unknown to Crossref and OpenAlex" +
                                    (" and Semantic Scholar" if isinstance(p, dict) and p.get("_status") == 404 else "")})
                else:
                    raise RuntimeError(f"OpenAlex HTTP {r2.status_code}")
            else:
                raise RuntimeError(f"Crossref HTTP {r.status_code}")
        except Exception as e:
            self.errors.append(redact(f"DOI {doi}: {type(e).__name__}: {e}"))
            return {"status": "unreachable", "doi": doi, "detail": redact(str(e))[:200]}
        self.cache.set("doi:" + doi, out)
        return out

    # ------------------------------------------------------------------ URL
    def url_passages(self, url: str) -> tuple[Optional[dict], list[dict], Optional[str]]:
        """Return (doc meta, passages, error)."""
        if self.docs is None:
            return None, [], "no document index"
        idx = self.docs.index
        if not idx.has(url):
            if self.fetcher is None:
                return None, [], "no fetcher"
            try:
                from .docs import index_bytes
                data, kind = self.fetcher.fetch(url, any_domain=True)
                index_bytes(idx, url, data, kind, official=domain_allowed(url, self.cfg.allowed_domains))
            except FetchError as e:
                return None, [], str(e)
            except Exception as e:
                return None, [], redact(f"{type(e).__name__}: {e}")
        return idx.doc(url), idx.passages_for(url), None

    # ------------------------------------------------------------------ check
    def check(self, claim: Claim) -> tuple[list[dict], list[Evidence]]:
        from ..claims import _strip_citations, checkable_numbers, NUMREF_RX
        body = NUMREF_RX.sub(" ", _strip_citations(claim.text))
        nums = [n.raw for n in checkable_numbers(body)]
        num_tokens = [re.sub(r"[^\d.,]", "", n).strip(".,") for n in nums]
        num_tokens = [n for n in num_tokens if n]
        want = terms(body)
        results, evidence = [], []
        targets: list[tuple[str, str]] = []
        for c in claim.citations:
            if c.startswith(("http://", "https://", "doi:", "arxiv:")):
                targets.append((c, c))
            else:
                key = c.strip("[]").split(",")[0].split("-")[0].split("–")[0].strip()
                ref = self.refs.get(key)
                if ref and ref["citations"]:
                    for rc in ref["citations"]:
                        targets.append((c, rc))
                else:
                    results.append({"citation": c, "status": "unresolved",
                                    "detail": "reference not found in the draft's reference list, or it has no URL/DOI"})
        for shown, target in targets:
            if target.startswith("arxiv:"):
                rec, ev = self._check_arxiv(shown, target[6:], want, num_tokens)
                results.append(rec)
                evidence += ev
                continue
            if target.startswith("doi:"):
                meta = self.resolve_doi(target[4:])
                rec = {"citation": shown, "target": target, **{k: meta.get(k) for k in ("status", "resolver", "title", "year",
                                                                                         "container", "url", "detail")}}
                if meta.get("status") == "found":
                    text = (f"{meta.get('title', '')}. {', '.join(meta.get('authors') or [])} ({meta.get('year') or ''}). "
                            f"{meta.get('container') or ''}. {meta.get('abstract', '')}")
                    rec.update(self._support(text, want, num_tokens))
                    window, _ = best_window(meta.get("abstract") or "", want, num_tokens)
                    head = (f"{meta.get('title', '')}. {', '.join(meta.get('authors') or [])} ({meta.get('year') or 'n.d.'}). "
                            f"{meta.get('container') or ''}.")
                    snippet = norm_ws(head + (" Abstract: " + window if window else ""))
                    evidence.append(Evidence(retriever="citation", source_url=meta.get("url") or f"https://doi.org/{target[4:]}",
                                             title=meta.get("title") or target, snippet=snippet,
                                             date=str(meta.get("year") or "") or None,
                                             publisher=f"{meta.get('container') or ''} (via {meta.get('resolver')})".strip(),
                                             official=False, score=rec.get("cover", 0), kind="metadata",
                                             meta={"cited": True, "support": rec.get("support")}))
                results.append(rec)
                continue
            doc, passages, err = self.url_passages(target)
            if err or not passages:
                results.append({"citation": shown, "target": target, "status": "unreachable" if err else "empty",
                                "detail": err or "no text could be extracted"})
                continue
            full = " ".join(p["text"] for p in passages)
            rec = {"citation": shown, "target": target, "status": "found", "title": (doc or {}).get("title"),
                   "url": target, "date": (doc or {}).get("date")}
            rec.update(self._support(full, want, num_tokens))
            hits = self.docs.index.search(body, num_tokens, k=4, url=target) if self.docs else []
            for h in hits or []:
                snippet, _ = best_window(h["text"], want, num_tokens)
                evidence.append(Evidence(retriever="citation", source_url=target, title=(doc or {}).get("title") or target,
                                         snippet=snippet or h["text"], date=(doc or {}).get("date"),
                                         publisher=(doc or {}).get("publisher") or "", page=h["page"],
                                         official=bool((doc or {}).get("official")), score=round(h["score"], 3),
                                         kind="passage", meta={"cited": True, "support": rec.get("support")}))
            results.append(rec)
        return results, evidence

    def _check_arxiv(self, shown: str, aid: str, want: set, nums: list) -> tuple[dict, list]:
        """Does arXiv know this id? Found -> its title/abstract can be checked like a DOI's (citation evidence)."""
        if self.arxiv is None:
            return {"citation": shown, "target": f"arxiv:{aid}", "status": "unreachable", "detail": "arXiv source off"}, []
        if self.cfg.offline and self.arxiv.cache.get(f"https://export.arxiv.org/api/query?id_list={aid}", allow_stale=True) is None:
            off = offline_arxiv_lookup(aid)
            if off is None:
                return {"citation": shown, "target": f"arxiv:{aid}", "status": "unreachable", "detail": OFFLINE_UNKNOWN}, []
            text = f"{off['title']}. {', '.join(off['authors'])}. {off['abstract']}"
            out = {"citation": shown, "target": f"arxiv:{aid}", "status": "found", "resolver": "offline cache (arxiv)",
                   "title": off["title"], "year": off.get("year"), "url": off["url"], "detail": off["detail"]}
            out.update(self._support(text, want, nums))
            window, _ = best_window(off["abstract"], want, nums)
            snippet = norm_ws(f"{off['title']}. {', '.join(off['authors'][:4])} ({off.get('year')}). arXiv preprint."
                              + (" Abstract: " + window if window else ""))
            return out, [Evidence(retriever="citation", source_url=off["url"], title=off["title"], snippet=snippet,
                                  date=str(off.get("year") or ""), publisher="arXiv (offline cache)", official=False,
                                  score=out.get("cover", 0), kind="metadata", source_type="Paper",
                                  meta={"cited": True, "support": out.get("support"), "preprint": True, "offline_cache": True})]
        recs = self.arxiv.by_id(aid)
        if recs is None:
            return {"citation": shown, "target": f"arxiv:{aid}", "status": "unreachable",
                    "detail": (self.arxiv.errors[-1] if self.arxiv.errors else "arXiv not reachable")[:200]}, []
        rec = next((r for r in recs if aid in r["id"]), None)
        if rec is None or not rec.get("title") or rec["title"].lower() == "error":
            return {"citation": shown, "target": f"arxiv:{aid}", "status": "not_found", "detail": "unknown to arXiv"}, []
        text = f"{rec['title']}. {', '.join(rec['authors'])}. {rec['summary']}"
        out = {"citation": shown, "target": f"arxiv:{aid}", "status": "found", "resolver": "arxiv", "title": rec["title"],
               "year": rec["published"][:4], "url": rec["id"]}
        out.update(self._support(text, want, nums))
        window, _ = best_window(rec["summary"], want, nums)
        snippet = norm_ws(f"{rec['title']}. {', '.join(rec['authors'][:4])} ({rec['published'][:4]}). arXiv preprint."
                          + (" Abstract: " + window if window else ""))
        ev = Evidence(retriever="citation", source_url=rec["id"], title=rec["title"], snippet=snippet, date=rec["published"],
                      publisher="arXiv (via arXiv API)", official=False, score=out.get("cover", 0), kind="metadata",
                      source_type="Paper", meta={"cited": True, "support": out.get("support"), "preprint": True})
        return out, [ev]

    @staticmethod
    def _support(text: str, want: set, nums: list[str]) -> dict:
        present = [n for n in nums if contains_number(text, n)]
        missing = [n for n in nums if n not in present]
        snippet, _ = best_window(text, want, nums)
        cover = len(want & terms(snippet)) / (len(want) or 1)
        if nums and missing:
            support = "number_missing" if not present else "partial"
        elif cover >= 0.5:
            support = "supports"
        elif cover >= 0.3:
            support = "partial"
        else:
            support = "not_in_source"
        return {"numbers_found": present, "numbers_missing": missing, "cover": round(cover, 2), "support": support}

    def retrieve(self, claim: Claim, k: int = 4) -> list[Evidence]:
        return self.check(claim)[1][:k]
