"""v0.2 pipeline: read -> sentences -> claims -> numbers (deterministic) + evidence -> verdicts -> report."""
from __future__ import annotations

import datetime as dt
from collections import Counter
from pathlib import Path
from typing import Optional, Union

from . import __version__
from .checker import Checker
from .claims import (NON_CLAIM_LABELS, LLMExtractor, RuleExtractor, _make_claim, claim_priority, is_descriptive,
                     non_claim_reason, norm_claim_key, segment)
from .config import Config, redact
from .llm import LLMClient
from .model import CONTRADICTED, DATED, PARTLY, SEVERITY, SKIPPED, SUPPORTED, UNVERIFIED, VERDICTS, ClaimResult
from .readers import Block, read_file, read_text, read_url
from .retrievers.citations import CitationChecker, references_from_blocks
from .retrievers.datagovin import DataGovInRetriever
from .retrievers.docs import DocFetcher, DocIndex, DocsRetriever
from .retrievers.mospi import MospiClient, MospiStore
from .retrievers.web import WebSearchRetriever
from .retrievers.datagovin import DataGovInMatcher
from .retrievers.live_docs import OpenAlexRetriever, PIBRetriever, ReportsRetriever
from .retrievers.mospi_catalog import MospiCatalog
from .retrievers.parliament import ParliamentRetriever
from .retrievers.ministry import CEASource, JJMSource, PPACSource, RBISource
from .retrievers.ndap import NDAPCatalog
from .retrievers.papers import ArxivRetriever, SemanticScholarRetriever, ShodhgangaRetriever
from .sources.curated import CuratedStore
from .sources.worldbank import WorldBankClient
from .verdict import HeuristicJudge, LLMJudge, VerdictEngine


CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}


class Pipeline:
    def __init__(self, cfg: Optional[Config] = None, llm: Union[str, None, LLMClient] = "auto",
                 checker: Optional[Checker] = None, docs_index: Optional[DocIndex] = None,
                 session=None, worldbank: Optional[WorldBankClient] = None, llm_extract: bool = True,
                 plugin_session=None):
        self.cfg = cfg or Config.load()
        cfg = self.cfg
        self.llm = LLMClient.from_config(cfg) if llm == "auto" else llm
        on = set(cfg.retrievers)
        curated = CuratedStore()
        self.mospi = MospiClient(cfg, session) if "mospi" in on else None
        store = MospiStore(curated, self.mospi) if self.mospi and cfg.mospi_enabled else curated
        if checker is None:
            wb = worldbank or WorldBankClient(offline=cfg.offline or "worldbank" not in on, session=session)
            checker = Checker(store=store, worldbank=wb)
        self.checker = checker
        self.fetcher = DocFetcher(cfg, session)
        self.docs = DocsRetriever(cfg, docs_index)
        self.web = WebSearchRetriever(cfg, session=session, docs=self.docs, fetcher=self.fetcher)
        self.datagovin = DataGovInRetriever(cfg, session)
        self.citations = CitationChecker(cfg, session=session, docs=self.docs, fetcher=self.fetcher) if "citations" in on else None
        live_session = session
        self.pib = PIBRetriever(cfg, live_session, docs=self.docs, fetcher=self.fetcher)
        self.parliament = ParliamentRetriever(cfg, live_session, fetcher=self.fetcher)
        self.openalex = OpenAlexRetriever(cfg, live_session)
        self.reports = ReportsRetriever(cfg, live_session, docs=self.docs, fetcher=self.fetcher, web=self.web)
        # v0.4 sources
        self.ndap = NDAPCatalog(cfg, live_session)
        self.s2 = SemanticScholarRetriever(cfg, live_session)
        self.arxiv = ArxivRetriever(cfg, live_session)
        self.shodhganga = ShodhgangaRetriever(cfg, live_session)
        if self.citations is not None:
            self.citations.s2 = self.s2 if "semanticscholar" in on else None
            self.citations.arxiv = self.arxiv if "arxiv" in on else None
        self.ministry = {c.name: c(cfg, live_session) for c in (RBISource, CEASource, PPACSource, JJMSource) if c.name in on}
        # v0.5: the user's own REST / MCP sources (sources.d/*.yaml); off with retrievers lacking "plugins"
        from .plugins import build_sources
        self.plugins, self.plugin_problems = (build_sources(cfg, None if plugin_session is None else plugin_session)
                                              if "plugins" in on else ({}, []))
        retrievers = []
        if "docs" in on:
            retrievers.append(self.docs)
        if "datagovin" in on:
            retrievers.append(self.datagovin)
        if "web" in on:
            retrievers.append(self.web)
        for name, r in (("pib", self.pib), ("parliament", self.parliament), ("openalex", self.openalex), ("reports", self.reports),
                        ("ndap", self.ndap), ("semanticscholar", self.s2), ("arxiv", self.arxiv),
                        ("shodhganga", self.shodhganga)):
            if name in on and not cfg.offline:
                retrievers.append(r)
        self.retrievers = retrievers
        self.matchers = {}
        self.mospi_catalog = MospiCatalog(cfg, session if session is not None else None) if "mospi" in on else None
        if self.mospi_catalog is not None:
            self.matchers["mospi-catalog"] = self.mospi_catalog
        self.datagov_matcher = DataGovInMatcher(cfg, self.datagovin.client) if "datagovin" in on else None
        if self.datagov_matcher is not None:
            self.matchers["datagovin-catalog"] = self.datagov_matcher
        self.matchers.update(self.ministry)
        # v0.5.2: bundled Census 2011 / CGWB 2025 / NFHS-5 state and district data (offline, Quick mode)
        from .retrievers.state_data import StateDataSource
        self.state_data = StateDataSource(cfg, session) if "state-data" in on else None
        if self.state_data is not None:
            self.matchers["state-data"] = self.state_data
        self.matchers.update(self.plugins)
        self.judge = LLMJudge(self.llm) if self.llm else HeuristicJudge()
        self.extractor = LLMExtractor(self.llm) if (self.llm and llm_extract) else RuleExtractor()
        self.engine = VerdictEngine(retrievers, self.judge, self.citations, matchers=self.matchers,
                                    budget=float(getattr(cfg, "claim_budget", 25.0)))
        self.engine.checker = self.checker      # v0.4.1: the change calculator reads the official series
        self.workers = max(1, int(getattr(cfg, "claim_workers", 12)))     # v0.5.1: was 6
        self.mode = "deep"      # v0.5.2: default for library use; the web app and CLI pass mode="quick" by default

    # ------------------------------------------------------------------ status
    def sources_status(self) -> list[dict]:
        out = [{"name": "curated", "configured": True,
                "detail": f"bundled official snapshot, {len(self.checker.store.records)} values (offline fallback)"}]
        wb = self.checker.wb
        out.append({"name": "worldbank", "configured": not wb.offline, "detail": "World Bank WDI API, no key (secondary source)"})
        out.append({"name": "mospi", "configured": bool(self.mospi and not self.mospi.offline),
                    "detail": f"MoSPI eSankhyiki API ({self.cfg.mospi_base_url}, backend {self.cfg.mospi_backend}), no key"
                    if self.mospi and not self.mospi.offline else "disabled or offline (TRUTHLENS_MOSPI=0 / --offline)"})
        for r in (self.docs, self.datagovin, self.web, self.pib, self.parliament, self.openalex, self.reports,
                  self.mospi_catalog, self.datagov_matcher, self.ndap, *self.ministry.values(),
                  self.state_data, self.s2, self.arxiv, self.shodhganga, *self.plugins.values()):
            if r is not None:
                st = r.status()
                if r in (self.pib, self.parliament, self.openalex, self.reports, self.ndap, self.s2, self.arxiv,
                         self.shodhganga) and r not in self.retrievers:
                    st = dict(st, configured=False, detail=st["detail"] + " (off: offline or not in retrievers)")
                out.append(st)
        if self.citations:
            out.append(self.citations.status())
        out.append({"name": "llm", "configured": bool(self.llm),
                    "detail": self.llm.label if self.llm else "no key: rule-based extraction and heuristic judge (lower confidence)"})
        return out

    def errors(self) -> list[str]:
        errs = list(self.checker.wb.errors)
        if self.mospi:
            errs += self.mospi.errors
        for r in (self.docs, self.datagovin, self.web, self.citations, self.pib, self.parliament, self.openalex,
                  self.reports, self.mospi_catalog, self.datagov_matcher, self.ndap,
                  *self.ministry.values(), self.s2, self.arxiv, self.shodhganga, *self.plugins.values()):
            if r is not None:
                errs += r.errors
        errs += [f"plugin config: {p}" for p in self.plugin_problems]
        errs += self.datagovin.client.errors
        errs += self.fetcher.errors
        if self.llm:
            errs += self.llm.errors
        # v0.5.2: requests the run itself chose not to send (Quick mode, the time limit, a host already cut off) are
        # not failures of the source; they are reported per claim, in the "couldn't check" reasons
        errs = [e for e in errs if not any(m in str(e) for m in GUARD_MESSAGES)]
        return [redact(e) for e in dict.fromkeys(errs)]

    # ------------------------------------------------------------------ run
    def run(self, blocks: list[Block], name: str, meta: Optional[dict] = None, progress=None, cancel=None,
            mode: Optional[str] = None, prior: Optional[dict] = None, state_out: Optional[dict] = None) -> dict:
        """Check a document. v0.5.1: runs under a per-request RunGuard (circuit breaker, memo cache, whole-document
        live-source deadline, per-source timeouts, per-host cap) unless the caller already set one.
        progress(stage, done, total) is called as the check moves on; cancel is a threading.Event.

        v0.5.2: mode "quick" sends no request at all (bundled and synced official data, cached answers, deterministic
        checks); claims that need a live source come back UNVERIFIED "Not checked in Quick mode". mode "deep" is the
        v0.5.1 live behaviour. Default: the pipeline's own mode (Pipeline.mode, "deep" unless set).
        prior: the state_out of an earlier run of the same document; only the claims it left "not checked in Quick
        mode" are evaluated again, every other result is reused as it was."""
        from . import runguard
        mode = mode or self.mode
        guard = runguard.CURRENT.get()
        tok = None
        if guard is None:
            guard = runguard.from_config(self.cfg, cancel, mode=mode)
            tok = runguard.CURRENT.set(guard)
        elif cancel is not None:
            guard.cancel = cancel
        from .retrievers.state_data import DOC_STATE, DOC_YEAR, document_year, dominant_state
        doc_tok = DOC_STATE.set(dominant_state(b.text for b in blocks) if len(blocks) >= 5 else None)
        # v0.6: the document's own year (title lines), for the DATED rule
        year_tok = DOC_YEAR.set(document_year(b.text for b in blocks) if len(blocks) >= 5 else None)
        try:
            meta = dict(meta or {})
            if DOC_YEAR.get():
                meta["document_year"] = DOC_YEAR.get()
            return self._run(blocks, name, meta, progress or (lambda *a: None), guard, prior, state_out)
        finally:
            DOC_YEAR.reset(year_tok)
            DOC_STATE.reset(doc_tok)
            if tok is not None:
                runguard.CURRENT.reset(tok)

    def _prepare(self, blocks: list[Block]):
        """Sentences, claims, numeric findings and findings per claim (no network)."""
        sentences = segment(blocks)
        claims = self.extractor.extract(sentences, blocks)
        findings = [f.to_dict() for f in self.checker.check_blocks(blocks)]
        findings = [f for f in findings if not _inside_citation(f["sentence"], f["claimed"])]
        by_sentence: dict = {}
        for f in findings:
            by_sentence.setdefault((f["location"], f["sentence"]), []).append(f)
        sent_key = {s.id: (s.location, s.text) for s in sentences}
        claimed_sents = {c.sentence_id for c in claims}
        # any sentence with numbers the deterministic checker saw becomes a numeric claim
        for s in sentences:
            if s.id not in claimed_sents and by_sentence.get((s.location, s.text)):
                if any(f["verdict"] != "UNVERIFIED" or f.get("indicator") for f in by_sentence[(s.location, s.text)]):
                    claims.append(_make_claim(len(claims) + 1, s, s.text, "numeric", "rules(numbers)"))
        claims.sort(key=lambda c: int(c.sentence_id[1:]))
        for i, c in enumerate(claims, 1):
            c.id = f"c{i}"
            # v0.5.2: objectives, procedures and definitions with no figure, date or citation are not checkable facts
            # v0.5.3: nor are headings, contents entries, table fragments, rules (shall/should), plans, targets,
            # projections and contact details
            if c.type != "opinion":
                why = non_claim_reason(c.text) or ("description" if is_descriptive(c.text) else "")
                if why:
                    c.checkable, c.not_claim = False, why
        per_claim: dict = {c.id: [] for c in claims}
        by_sid: dict = {}
        for c in claims:
            by_sid.setdefault(c.sentence_id, []).append(c)
        for sid, cs in by_sid.items():
            for f in by_sentence.get(sent_key[sid], []):
                target = next((c for c in cs if f["claimed"] in c.text and c.type != "opinion"), None) or \
                    next((c for c in cs if c.type != "opinion"), None)
                if target:
                    per_claim[target.id].append(f)
        return sentences, claims, findings, per_claim

    def _run(self, blocks: list[Block], name: str, meta: Optional[dict], progress, guard, prior=None,
             state_out=None) -> dict:
        import copy
        progress("finding claims", 0, 0)
        if prior:
            sentences, claims, findings, per_claim = (prior["sentences"], prior["claims"], prior["findings"],
                                                      prior["per_claim"])
        else:
            sentences, claims, findings, per_claim = self._prepare(blocks)
        if self.citations is not None:
            self.citations.refs = references_from_blocks(blocks)
        # v0.5.2: importance order (figures with units, years and places first); live fallbacks (PIB, Parliament,
        # NDAP catalogue) only for the most important claims; repeated claims are checked once
        for c in claims:
            c_prio = claim_priority(c)
            setattr(c, "_priority", c_prio)
        ranked = sorted([c for c in claims if c.type != "opinion" and c.checkable], key=lambda c: -c._priority)
        cap = max(0, int(getattr(self.cfg, "fallback_claims", 20)))
        for i, c in enumerate(ranked):
            setattr(c, "_fallback", i < cap)
        prior_res = (prior or {}).get("results") or {}
        results_by_id: dict = {}
        todo: list = []
        first_of: dict = {}
        dupes: dict = {}
        for c in claims:
            if c.id in prior_res and prior_res[c.id].unchecked_reason != "quick":
                results_by_id[c.id] = prior_res[c.id]
                continue
            if c.type != "opinion" and not c.checkable:
                results_by_id[c.id] = not_checkable_result(c, per_claim.get(c.id) or [])
                continue
            k = (norm_claim_key(c.text), tuple(sorted(f["claimed"] for f in per_claim.get(c.id) or [])))
            if c.type != "opinion" and k in first_of:
                dupes[c.id] = first_of[k]
                continue
            first_of[k] = c.id
            todo.append(c)
        todo.sort(key=lambda c: -getattr(c, "_priority", 0))
        total = len(todo)
        progress("checking claims", 0, total)
        if guard.cancel.is_set():
            raise CheckCancelled("check cancelled")
        if self.workers > 1 and len(todo) > 1:
            import concurrent.futures as cf
            import threading
            done_n = [0]
            lock = threading.Lock()

            def one(c):
                if guard.cancel.is_set():
                    raise CheckCancelled("check cancelled")
                r = self.engine.evaluate(c, per_claim[c.id])
                with lock:
                    done_n[0] += 1
                    n = done_n[0]
                progress("checking claims", n, total)
                return r

            ex = cf.ThreadPoolExecutor(max_workers=self.workers)
            try:
                # each worker runs in a copy of this context, so per-request keys (use_keys) and the guard reach it
                import contextvars
                futs = [ex.submit(contextvars.copy_context().run, one, c) for c in todo]
                pending = set(futs)
                while pending:
                    _done, pending = cf.wait(pending, timeout=0.5)
                    if guard.cancel.is_set():
                        raise CheckCancelled("check cancelled")
                for c, f in zip(todo, futs):
                    results_by_id[c.id] = f.result()
            finally:
                ex.shutdown(wait=not guard.cancel.is_set(), cancel_futures=True)
        else:
            for i, c in enumerate(todo, 1):
                if guard.cancel.is_set():
                    raise CheckCancelled("check cancelled")
                results_by_id[c.id] = self.engine.evaluate(c, per_claim[c.id])
                progress("checking claims", i, total)
        for cid, src in dupes.items():
            r = copy.copy(results_by_id[src])
            r.claim = next(c for c in claims if c.id == cid)
            r.warnings = list(r.warnings) + [{"code": "repeated_claim", "severity": "info",
                                              "message": f"Same statement as claim {src}; checked once."}]
            results_by_id[cid] = r
        results = [results_by_id[c.id] for c in claims]
        for r in results:
            r.priority = getattr(r.claim, "_priority", 0)
            if r.verdict == UNVERIFIED and not r.unchecked_reason:
                r.unchecked_reason = "no_data"
        progress("writing report", total, total)
        res_by_sid: dict = {}
        for r in results:
            res_by_sid.setdefault(r.claim.sentence_id, []).append(r)
        for s in sentences:
            rs = res_by_sid.get(s.id, [])
            s.claims = [r.claim.id for r in rs]
            vs = [r.verdict for r in rs if r.verdict != SKIPPED]
            if vs:
                s.verdict = max(vs, key=lambda v: SEVERITY[v])
            elif rs:
                s.verdict = SKIPPED
            else:
                s.verdict = None
        hit = sum(1 for r in results if (r.live_limits or {}).get("ran_out_of_time"))
        meta = dict(meta or {})
        meta["live_checks"] = guard.summary(hit)
        meta["mode"] = guard.mode
        if prior:
            meta["deep_rerun_of_unchecked"] = total
        if state_out is not None:
            state_out.update({"sentences": sentences, "claims": claims, "findings": findings, "per_claim": per_claim,
                              "results": {r.claim.id: r for r in results}})
        return build_report_v2(name, blocks, sentences, results, findings, self, meta)


def not_checkable_result(claim, findings) -> ClaimResult:
    r = ClaimResult(claim=claim)
    r.verdict, r.method, r.confidence = SKIPPED, "not-checkable", "n/a"
    r.rationale = NON_CLAIM_LABELS.get(getattr(claim, "not_claim", "") or "description", NON_CLAIM_LABELS["description"])
    r.numbers = findings
    return r


GUARD_MESSAGES = ("not checked in Quick mode", "live-source limit for the whole document", "unavailable this run (skipped",
                  "check cancelled")


class CheckCancelled(Exception):
    """v0.5.1: the user cancelled the check (web app Cancel)."""


def _inside_citation(sentence: str, raw: str) -> bool:
    from .claims import DOI_RX, URL_RX
    for rx in (URL_RX, DOI_RX):
        for m in rx.finditer(sentence):
            if raw.strip() and raw.strip() in m.group(0):
                return True
    return False


def build_report_v2(name, blocks, sentences, results, findings, pipe: Optional[Pipeline], meta: dict) -> dict:
    counts = Counter(r.verdict for r in results)
    checkable = sum(counts.get(v, 0) for v in VERDICTS)
    # v0.4.1: the score is computed over CHECKED claims (supported, partly, contradicted); "couldn't check"
    # (UNVERIFIED) is reported separately so it is not read as "wrong"
    checked = counts.get(SUPPORTED, 0) + counts.get(PARTLY, 0) + counts.get(CONTRADICTED, 0)
    sup_conf = Counter(r.confidence for r in results if r.verdict == SUPPORTED)
    weighted = sum(CONFIDENCE_WEIGHT.get(c, 0.3) * n for c, n in sup_conf.items())
    score = round(100.0 * weighted / checked, 1) if checked else None
    split = {"contradicted": counts.get(CONTRADICTED, 0), "partly": counts.get(PARTLY, 0),
             "supported": counts.get(SUPPORTED, 0), "couldnt_check": counts.get(UNVERIFIED, 0),
             "skipped": counts.get(SKIPPED, 0), "dated": counts.get(DATED, 0)}
    unreachable = unreachable_sources(results, pipe)
    types = Counter(r.claim.type for r in results)
    cites = [c for r in results for c in r.citation_checks]
    num_counts = Counter(f["verdict"] for f in findings)
    sources: dict = {}
    for r in results:
        for e in r.evidence:
            if e.source_url and e.source_url not in sources:
                sources[e.source_url] = {"url": e.source_url, "title": e.title, "publisher": e.publisher, "date": e.date,
                                         "retriever": e.retriever, "official": e.official}
    meta = dict(meta)
    meta["blocks"] = len(blocks)
    if pipe is not None:
        meta["extractor"] = pipe.extractor.name
        meta["judge"] = pipe.judge.name
        meta["sources_status"] = pipe.sources_status()
        meta["errors"] = pipe.errors()
    return {
        "tool": "TruthLens",
        "version": __version__,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "input": name,
        "meta": meta,
        "summary": {
            "mode": meta.get("mode", "deep"),
            "statements": len(sentences),
            "checkable": sum(1 for r in results if r.verdict != SKIPPED),
            "not_checkable": sum(1 for r in results if r.method == "not-checkable"),
            "opinions": sum(1 for r in results if r.verdict == SKIPPED and r.method != "not-checkable"),
            "couldnt_check_reasons": unchecked_buckets(results),
            "banner": short_banner(results, unreachable, meta.get("mode", "deep")),
            "sentences": len(sentences),
            "claims": len(results),
            "checkable_claims": checkable,
            "verdicts": {v: counts.get(v, 0) for v in VERDICTS},
            "skipped_opinions": counts.get(SKIPPED, 0),
            **split,
            "checked_claims": checked,
            # v0.5.3: lead with what was checked against data, what is wrong and what needs a source; the old split
            # ('8 wrong · 7 supported · 3 couldn't check · 1 skipped') stays in split_line
            "headline": lead_line(split, results),
            "split_line": headline(split),
            # v0.6: DATED claims were compared with official data (for another year or boundary); they are counted
            # here but not in the verified score, which is over supported / partly / contradicted only
            "checked_against_data": checked + counts.get(DATED, 0),
            "dated_label": "Dated: figure is for an earlier year or boundary",
            "needs_source": sum(1 for r in results if r.verdict == UNVERIFIED and (r.unchecked_reason or "no_data") == "no_data"),
            "not_checked_this_run": sum(1 for r in results if r.verdict == UNVERIFIED
                                        and (r.unchecked_reason or "no_data") != "no_data"),
            "not_checkable_reasons": dict(Counter(getattr(r.claim, "not_claim", "") or "description"
                                                  for r in results if r.method == "not-checkable")),
            "score_note": ("" if checked >= MIN_SCORED else
                           f"Only {checked + counts.get(DATED, 0)} claim{'s' if checked + counts.get(DATED, 0) != 1 else ''} "
                           "could be checked against official data, too few for a meaningful score."
                           + (" Dated claims are not scored." if counts.get(DATED, 0) else "")),
            "hedged_factual": sum(1 for r in results if getattr(r.claim, "hedged", False)),
            "unreachable_sources": unreachable,
            "live_deadline": _deadline_summary(meta.get("live_checks"), results),
            "data_freshness": _freshness(pipe),
            "offline": bool(pipe is not None and pipe.cfg.offline),
            "verified_score": score,
            "score_method": ("confidence-weighted over checked claims (supported + partly + contradicted): SUPPORTED counts "
                             "1.0 (high), 0.6 (medium), 0.3 (low confidence). Couldn't-check claims are not in the score."),
            "couldnt_check_note": COULDNT_CHECK_NOTE,
            "supported_by_confidence": {k: sup_conf.get(k, 0) for k in ("high", "medium", "low")},
            "low_confidence_supported": sup_conf.get("low", 0),
            "claim_types": dict(types),
            "citations_checked": len(cites),
            "citations_not_found": sum(1 for c in cites if c.get("status") == "not_found"),
            "suggested_fixes": sum(1 for r in results if r.suggested_fix),
            "numbers_checked": len(findings),
            "numbers": {"MATCH": num_counts.get("MATCH", 0), "CLOSE": num_counts.get("CLOSE", 0),
                        "MISMATCH": num_counts.get("MISMATCH", 0), "UNVERIFIED": num_counts.get("UNVERIFIED", 0),
                        "DATED": num_counts.get("DATED", 0)},
            "warnings": sum(1 for r in results for w in r.warnings if w["severity"] in ("warn", "error")),
        },
        "blocks": [{"text": b.text, "location": b.location} for b in blocks],
        "sentences": [s.to_dict() for s in sentences],
        "claims": [r.to_dict() for r in results],
        "findings": findings,   # v0.1-compatible numeric findings
        "claims_to_cite": claims_to_cite(results),
        "sources": list(sources.values()),
    }


REASON_ORDER = ["no_data", "no_response", "quick", "deadline"]


def unchecked_buckets(results) -> dict:
    """v0.5.2: couldn't-check claims split by honest reason."""
    from .verdict import UNCHECKED_REASONS
    out = {k: {"label": UNCHECKED_REASONS[k], "claims": 0} for k in REASON_ORDER}
    for r in results:
        if r.verdict == UNVERIFIED:
            k = r.unchecked_reason or "no_data"
            out.setdefault(k, {"label": k, "claims": 0})["claims"] += 1
    return out


def short_banner(results, unreachable, mode: str) -> dict:
    """v0.5.2: one or two plain lines for the top of the report (top 3 reasons); the per-source list is the detail."""
    b = unchecked_buckets(results)
    total = sum(v["claims"] for v in b.values())
    if not total:
        return {}
    top = sorted(((v["claims"], k) for k, v in b.items() if v["claims"]), reverse=True)[:3]
    phrases = {"no_data": "{n} need a source you should cite (no official dataset in TruthLens covers them yet)",
               "no_response": "{n} waited on a source that didn't respond",
               "quick": "{n} need live sources (not checked in Quick mode)",
               "deadline": "{n} ran out of time"}
    parts = [phrases.get(k, k + ": {n}").format(n=n) for n, k in top]
    line = f"{total} claim{'s' if total != 1 else ''} not checked against data: " + "; ".join(parts) + "."
    out = {"text": line, "top": [k for _n, k in top]}
    if b["quick"]["claims"]:
        out["deep_hint"] = (f"{b['quick']['claims']} claim{'s' if b['quick']['claims'] != 1 else ''} not checked in Quick "
                            "mode — Deep check (about 1 min).")
    srcs = [u["source"] for u in unreachable if u.get("claims_affected")]
    if srcs:
        out["sources_down"] = srcs[:3]
    return out


def _deadline_summary(lc: Optional[dict], results) -> dict:
    """v0.5.1: the whole-document live-source limit and how many claims hit it (shown in the report)."""
    if not lc:
        return {}
    hit = sum(1 for r in results if (getattr(r, "live_limits", None) or {}).get("ran_out_of_time"))
    hit_unv = sum(1 for r in results if (getattr(r, "live_limits", None) or {}).get("ran_out_of_time")
                  and r.verdict == UNVERIFIED)
    cut = sum(1 for r in results if (getattr(r, "live_limits", None) or {}).get("unavailable_sources"))
    out = {"budget_s": lc.get("budget_s"), "elapsed_s": lc.get("elapsed_s"), "claims_hit_deadline": hit,
           "claims_hit_deadline_unverified": hit_unv, "claims_with_sources_cut_off": cut,
           "sources_cut_off": [d.get("source") for d in lc.get("sources_cut_off") or []]}
    if hit:
        out["note"] = (f"{hit} claim(s) ran out of time: their live checks did not finish within the "
                       f"{lc.get('budget_s'):g} s limit for the whole document. They keep their official-data result "
                       "or are marked couldn't check; a timeout never counts as supported or wrong.")
    return out


def _freshness(pipe) -> dict:
    """v0.5: when `truthlens sync` last refreshed the local data (stale after 7 days)."""
    try:
        from .sync import freshness
        return freshness(pipe.cfg if pipe is not None else None)
    except Exception:
        return {}


COULDNT_CHECK_NOTE = ("“Needs a source” means TruthLens has no official dataset for that claim yet; “couldn't check” means a "
                      "source did not answer in this run. Neither is a finding that the claim is wrong: cite a source for "
                      "those claims (download the list of claims to cite) or check them by hand.")
MIN_SCORED = 5      # v0.5.3: below this many checked claims the score is not shown as a headline number


def _n(k: int, one: str, many: str) -> str:
    return f"{k} {one if k == 1 else many}"


def lead_line(split: dict, results) -> str:
    """v0.5.3 headline: '12 claims checked against official data · 1 wrong · 40 need a source you should cite'."""
    checked = split["supported"] + split["partly"] + split["contradicted"] + split.get("dated", 0)
    needs = sum(1 for r in results if r.verdict == UNVERIFIED and (r.unchecked_reason or "no_data") == "no_data")
    other = split["couldnt_check"] - needs
    bits = [_n(checked, "claim checked against official data", "claims checked against official data"),
            f"{split['contradicted']} wrong"]
    if split.get("partly"):
        bits.append(f"{split['partly']} partly right")
    if split.get("dated"):
        bits.append(f"{split['dated']} dated (earlier year or boundary)")
    bits.append(_n(needs, "needs a source you should cite", "need a source you should cite"))
    if other > 0:
        bits.append(f"{other} not checked this run")
    return " · ".join(bits)


def claims_to_cite(results) -> list:
    """v0.5.3: the claims a reader should see a source for (no official dataset in TruthLens, or no answer this run),
    in document order; downloadable from the web app and with `truthlens check -f cite`."""
    from .verdict import UNCHECKED_REASONS
    out = []
    for r in results:
        if r.verdict == DATED:
            # v0.6: a dated figure needs the year it is for, or a current figure
            from .report_v2 import DATED_WHY
            out.append({"claim_id": r.claim.id, "location": r.claim.location, "text": r.claim.text,
                        "why": DATED_WHY, "reason": "dated", "numbers": list(r.claim.numbers or [])})
            continue
        if r.verdict != UNVERIFIED:
            continue
        k = r.unchecked_reason or "no_data"
        out.append({"claim_id": r.claim.id, "location": r.claim.location, "text": r.claim.text,
                    "why": UNCHECKED_REASONS.get(k, k), "reason": k, "numbers": list(r.claim.numbers or [])})
    return out


def headline(split: dict) -> str:
    """'8 wrong · 7 supported · 3 couldn't check · 1 skipped' (partly shown when there are any)."""
    bits = [f"{split['contradicted']} wrong"]
    if split.get("partly"):
        bits.append(f"{split['partly']} partly supported")
    if split.get("dated"):
        bits.append(f"{split['dated']} dated")
    bits += [f"{split['supported']} supported", f"{split['couldnt_check']} couldn't check", f"{split['skipped']} skipped"]
    return " · ".join(bits)


def unreachable_sources(results, pipe) -> list[dict]:
    """v0.4.1 banner data: sources that failed (error/timeout) this run and how many claims each affected."""
    hit: dict = {}
    for r in results:
        seen = set()
        for c in r.consulted:
            st = str(c.get("status") or "")
            if st in ("error", "timeout") or (st.startswith("error") and not any(m in st for m in GUARD_MESSAGES)):
                seen.add((c.get("source"), "error" if st.startswith("error") else st))
        for c in r.citation_checks:
            if c.get("status") == "unreachable" and "offline" not in str(c.get("detail", "")) \
                    and not any(m in str(c.get("detail", "")) for m in GUARD_MESSAGES):
                seen.add(("citations", "error"))
        for s in (getattr(r, "live_limits", None) or {}).get("unavailable_sources") or []:
            if not any(x[0] == s for x in seen):
                seen.add((s, "unavailable"))
        for src, st in seen:
            d = hit.setdefault(src, {"source": src, "status": st, "claims_affected": 0})
            d["claims_affected"] += 1
    if pipe is not None:
        # errors a retriever absorbed itself (it then returned nothing): every claim that asked it was affected
        for e in pipe.errors():
            low = e.lower()
            name = next((n for p, n in ERROR_PREFIXES if low.startswith(p)), None)
            if low.startswith("plugin:"):
                name = ":".join(low.split(":")[:2])
            label = "parliament (Lok Sabha archive on Hugging Face)" if "huggingface" in low else name
            if name and name not in hit and label not in hit:
                asked = sum(1 for r in results if any(c.get("source") == name for c in r.consulted))
                hit[name] = {"source": label, "status": "error", "claims_affected": 0, "claims_asked": asked,
                             "detail": "the source failed inside the run; claims that asked it may have been answered by its other routes"}
    return sorted(hit.values(), key=lambda d: (-d["claims_affected"], d["source"]))


ERROR_PREFIXES = [("pib", "pib"), ("parliament", "parliament"), ("lok sabha", "parliament"), ("rajya sabha", "parliament"),
                  ("openalex", "openalex"), ("semantic scholar", "semanticscholar"), ("arxiv", "arxiv"),
                  ("shodhganga", "shodhganga"), ("ndap", "ndap"), ("rbi", "rbi"), ("cea", "cea"), ("ppac", "ppac"),
                  ("jjm", "jjm"), ("mospi", "mospi"), ("world bank", "worldbank"), ("worldbank", "worldbank"),
                  ("data.gov.in", "datagovin"), ("datagovin", "datagovin"), ("reports", "reports"), ("crossref", "citations"),
                  ("doi ", "citations")]


# ---------------------------------------------------------------------- entry points
def check_path(path, pipe: Optional[Pipeline] = None, **kw) -> dict:
    pipe = pipe or Pipeline(**kw)
    blocks = read_file(path)
    return pipe.run(blocks, Path(path).name, {"source_path": Path(path).name})


def check_text(text: str, name: str = "text input", pipe: Optional[Pipeline] = None, **kw) -> dict:
    pipe = pipe or Pipeline(**kw)
    return pipe.run(read_text(text), name)


def check_url(url: str, pipe: Optional[Pipeline] = None, **kw) -> dict:
    pipe = pipe or Pipeline(**kw)
    blocks, meta = read_url(url)
    return pipe.run(blocks, url, meta)
