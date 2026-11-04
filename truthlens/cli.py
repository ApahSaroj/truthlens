"""Command line interface.

  truthlens check draft.docx -f html -o report.html [--docx-out corrected.docx]
  truthlens index ./reports            add your own folder of reports to the local evidence index
  truthlens index --url URL            add an allow-listed official page or PDF
  truthlens index --pib-rss            add the current PIB press releases
  truthlens sources                    which evidence sources are active, and what is indexed
  truthlens doctor [--ping]            configuration, keys present (never printed), connectivity
  truthlens indicators                 India statistics covered by the deterministic number checker
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .readers import ReaderError


def _v1_summary(report: dict) -> str:
    s = report["summary"]
    v = s["verdicts"]
    return (f"TruthLens: {s['numbers_checked']} numbers · {v['MISMATCH']} mismatch · {v['CLOSE']} close · "
            f"{v['MATCH']} match · {v['UNVERIFIED']} unverified · {s['warnings']} data-trap warnings")


def _v2_summary(report: dict) -> str:
    s = report["summary"]
    v = s["verdicts"]
    from .report_v2 import banner_lines, headline_text, split_counts
    score = "n/a" if s["verified_score"] is None else f"{s['verified_score']:.0f}%"
    sp = split_counts(s)
    checked = s.get("checked_claims", sp["supported"] + sp["partly"] + sp["contradicted"])
    line = (f"TruthLens: {headline_text(s)}\n"
            + (f"  {s['split_line']}\n" if s.get("split_line") else "")
            + f"  verified score {score} of {checked} checked claims (couldn't-check not counted"
            f"{'; ' + str(s.get('low_confidence_supported')) + ' supported are low-confidence' if s.get('low_confidence_supported') else ''})"
            f" · {s['citations_not_found']} citation(s) not found · {s['suggested_fixes']} suggested fixes"
            f"{' · ' + str(s.get('hedged_factual')) + ' opinion-worded sentence(s) checked for their factual claim' if s.get('hedged_factual') else ''}")
    for b in banner_lines(report):
        line += "\n  ! " + b
    return line


def _config(args):
    from .config import Config
    over = {}
    if getattr(args, "offline", False):
        over["offline"] = True
    cfg = Config.load(getattr(args, "config", None), **over)
    if getattr(args, "no_llm", False):
        cfg.llm_provider = "none"
    elif getattr(args, "llm", None):
        cfg.llm_provider = args.llm
    if getattr(args, "search", None):
        cfg.search_provider = args.search
    if getattr(args, "retrievers", None):
        cfg.retrievers = [r.strip() for r in args.retrievers.split(",") if r.strip()]
    return cfg


def cmd_check(args) -> int:
    if args.numbers_only:
        from .core import check_path, check_text, check_url
        from .report import to_html, to_json, to_markdown
        online = not args.offline
        try:
            if args.text:
                report = check_text(args.input, online=online)
            elif args.input == "-":
                report = check_text(sys.stdin.read(), name="stdin", online=online)
            elif args.input.startswith(("http://", "https://")):
                report = check_url(args.input, online=online)
            else:
                report = check_path(args.input, online=online)
        except ReaderError as e:
            print(f"truthlens: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"truthlens: could not read input: {e}", file=sys.stderr)
            return 2
        if args.format == "cite":
            print("truthlens: -f cite needs the full check (drop --numbers-only)", file=sys.stderr)
            return 2
        body = {"html": to_html, "md": to_markdown, "markdown": to_markdown, "json": to_json}[args.format](report)
        _emit(body, args.output)
        print(_v1_summary(report), file=sys.stderr)
        return 1 if args.strict and report["summary"]["verdicts"]["MISMATCH"] else 0

    from .pipeline import Pipeline
    from .readers import read_file, read_text, read_url
    from .report_v2 import to_html, to_json, to_markdown
    cfg = _config(args)
    mode = "deep" if getattr(args, "deep", False) else "quick"
    try:
        # v0.5.2: Quick (default) asks no live source and no AI provider; --deep is the full live check
        pipe = Pipeline(cfg, llm=None) if mode == "quick" else Pipeline(cfg)
        if args.text:
            blocks, name, src = read_text(args.input), "text input", None
        elif args.input == "-":
            blocks, name, src = read_text(sys.stdin.read()), "stdin", None
        elif args.input.startswith(("http://", "https://")):
            blocks, meta = read_url(args.input)
            name, src = args.input, None
        else:
            blocks, name, src = read_file(args.input), Path(args.input).name, args.input
    except ReaderError as e:
        print(f"truthlens: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"truthlens: could not read input: {e}", file=sys.stderr)
        return 2
    report = pipe.run(blocks, name, {"source_path": Path(src).name} if src else {}, mode=mode)
    from .report_v2 import to_cite_csv, to_claims_csv
    body = {"html": to_html, "md": to_markdown, "markdown": to_markdown, "json": to_json,
            "cite": to_cite_csv, "csv": to_claims_csv}[args.format](report)
    _emit(body, args.output)
    if args.docx_out:
        from .docx_export import export_docx
        res = export_docx(report, args.docx_out, src)
        print(f"truthlens: corrected draft with {res['annotated']} annotation(s) written to {args.docx_out}"
              f"{'' if res['comments'] else ' (inline suggestions only: this python-docx has no comment support)'}", file=sys.stderr)
    print(_v2_summary(report), file=sys.stderr)
    _attention(report)
    return 1 if args.strict and report["summary"]["verdicts"]["CONTRADICTED"] else 0


def _attention(report: dict, limit: int = 5) -> None:
    """Quiet by default: only list what a person must act on (contradicted first, then partly supported)."""
    act = [c for c in report["claims"] if c["verdict"] in ("CONTRADICTED", "PARTLY SUPPORTED", "DATED")]
    act.sort(key=lambda c: {"CONTRADICTED": 0, "PARTLY SUPPORTED": 1}.get(c["verdict"], 2))
    if not act:
        print("truthlens: nothing needs fixing. Unverified claims are listed in the report.", file=sys.stderr)
        return
    print(f"truthlens: {len(act)} claim(s) need your attention:", file=sys.stderr)
    for c in act[:limit]:
        line = f"  - {c['verdict']}: {c['claim']['text'][:110]}"
        if c.get("suggested_fix"):
            line += f"\n      fix: {c['suggested_fix'][:140]}"
        print(line, file=sys.stderr)
    if len(act) > limit:
        print(f"  … and {len(act) - limit} more in the report.", file=sys.stderr)


def _emit(body: str, out):
    if out:
        Path(out).write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body + ("\n" if not body.endswith("\n") else ""))


def cmd_compare(args) -> int:
    """v0.6: compare two versions of a document (near-copied sentences, changed figures, dropped commitments,
    new sections). Local text comparison: no network, no AI."""
    from .compare import compare_paths, meaning_line, render, summary_line
    from .readers import ReaderError
    mopts = {}
    if getattr(args, "meaning", False):
        mopts = {"meaning": True, "topics": args.topics, "threshold": args.meaning_threshold, "model": args.model}
        if getattr(args, "ai_summary", False):
            from .config import Config
            from .llm import LLMClient
            cfg = Config.load(getattr(args, "config", None))
            if args.llm:
                cfg.llm_provider = args.llm
            llm = LLMClient.from_config(cfg)
            if llm is None:
                print("truthlens: --ai-summary needs an AI provider: pass --llm and --ask-key (or set its key), or run "
                      "Ollama with --llm ollama; continuing without AI summaries", file=sys.stderr)
            else:
                mopts["llm"] = llm
    try:
        rep = compare_paths(args.old, args.new, near_copy=args.threshold, **mopts)
    except ReaderError as e:
        print(f"truthlens: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"truthlens: {e}", file=sys.stderr)
        return 2
    _emit(render(rep, args.format), args.output)
    print(f"TruthLens compare: {summary_line(rep)}", file=sys.stderr)
    m = rep.get("meaning")
    if m and m.get("unavailable"):
        print(f"truthlens: match by meaning not run: {m['unavailable']}", file=sys.stderr)
    elif m:
        print(f"TruthLens compare by meaning ({m['seconds']['total']} s): {meaning_line(m)}", file=sys.stderr)
    return 0


def cmd_index(args) -> int:
    from .net import make_session
    from .retrievers.docs import DocFetcher, DocIndex, index_path, index_url, pib_rss_items
    cfg = _config(args)
    idx = DocIndex(cfg.cache_dir / "index.sqlite")
    if args.list:
        for d in idx.docs():
            print(f"{d['passages']:5d}  {d['date'] or '----------'}  {'official' if d['official'] else 'local   '}  {d['title'][:70]}  {d['url']}")
        return 0
    done = 0
    for p in args.paths:
        if not Path(p).exists():
            print(f"truthlens: not found: {p}", file=sys.stderr)
            continue
        for r in index_path(idx, Path(p), official=args.official):
            print(("ERROR " + r["error"] if "error" in r else f"indexed {r['passages']:4d} passages  {r['url']}"))
            done += "error" not in r
    fetcher = DocFetcher(cfg)
    for u in args.url or []:
        try:
            r = index_url(idx, fetcher, u)
            print(f"indexed {r['passages']:4d} passages  {u}")
            done += 1
        except Exception as e:
            print(f"truthlens: {u}: {e}", file=sys.stderr)
    if args.pib_rss:
        try:
            items, lang = pib_rss_items(make_session(), cfg.timeout)
        except Exception as e:
            print(f"truthlens: PIB RSS: {e}", file=sys.stderr)
            items, lang = [], "?"
        if lang != "en":
            print(f"truthlens: note: PIB served the feed in '{lang}' (it can redirect Lang=1 to Hindi); indexing anyway.",
                  file=sys.stderr)
        for it in items[: args.max]:
            try:
                r = index_url(idx, fetcher, it["link"])
                print(f"indexed {r['passages']:4d} passages  {it['link']}  {it['title'][:60]}")
                done += 1
            except Exception as e:
                print(f"truthlens: {it['link']}: {e}", file=sys.stderr)
    print(f"truthlens: {done} document(s) added; index at {idx.path} now holds {len(idx.docs())}.", file=sys.stderr)
    return 0 if done or not (args.paths or args.url or args.pib_rss) else 1


def cmd_sources(args) -> int:
    action = getattr(args, "action", None) or "status"
    if action == "add":
        return _sources_add(args)
    if action == "test":
        return _sources_test(args)
    if action == "examples":
        from .plugins import examples
        for name, text in examples().items():
            desc = next((ln.split(":", 1)[1].strip() for ln in text.splitlines() if ln.startswith("description:")), "")
            print(f"{name:20s} {desc}")
        return 0
    from .pipeline import Pipeline
    pipe = Pipeline(_config(args), llm=None)
    rows = pipe.sources_status()
    if action == "list":
        from .plugins import source_dirs
        rows = [r for r in rows if str(r["name"]).startswith("plugin:")]
        print(f"plug-in sources (from {', '.join(str(d) for d in source_dirs(pipe.cfg))}):")
        if not rows:
            print("  none yet. Add one: truthlens sources add worldbank-wdi   (see: truthlens sources examples)")
    for s in rows:
        print(f"{'✔' if s['configured'] else '·'} {s['name']:10s} {s['detail']}")
    for p in pipe.plugin_problems:
        print(f"✘ {p}")
    return 0


def _sources_add(args) -> int:
    from .plugins import add, examples
    import yaml
    target = args.target
    if not target:
        print("truthlens: give a YAML file or a bundled example name: " + ", ".join(examples()), file=sys.stderr)
        return 2
    try:
        text = Path(target).read_text(encoding="utf-8") if Path(target).is_file() else examples().get(target, "")
        spec = yaml.safe_load(text) if text else None
        cmd = ((spec or {}).get("server") or {}).get("command") if isinstance(spec, dict) else None
        if cmd and not args.yes:
            # an MCP stdio source runs a program on this computer: show it and ask
            print(f"This source starts a program on your computer: {' '.join(map(str, cmd if isinstance(cmd, list) else [cmd]))}")
            if not sys.stdin.isatty() or input("Add it? [y/N] ").strip().lower() not in ("y", "yes"):
                print("truthlens: not added (use --yes to confirm non-interactively)", file=sys.stderr)
                return 1
        out = add(target, _config(args))
    except ValueError as e:
        print(f"truthlens: not added: {e}", file=sys.stderr)
        return 2
    print(f"added {out}. Test it with: truthlens sources test {out.stem}")
    return 0


def _sources_test(args) -> int:
    from .plugins import load_all, test_source
    cfg = _config(args)
    specs, problems = load_all(cfg)
    spec = next((s for s in specs if s["name"] == (args.target or "").replace("plugin:", "")), None)
    if spec is None:
        print(f"truthlens: no enabled plug-in named {args.target!r}" + (f" ({'; '.join(problems)})" if problems else ""),
              file=sys.stderr)
        return 2
    res = test_source(spec, cfg, args.claim)
    print(f"{res['name']}: test claim: {res['claim']}")
    if res["unavailable"]:
        print(f"  {res['unavailable']}")
        return 1
    for label, g in res["groups"].items():
        print(f"  {label}: {g['rows_total']} row(s) from {g['source'].get('url')}")
        for r in g["rows"]:
            print(f"    {r}")
    for f in res["findings"]:
        print(f"  {f['claimed']}: {f['verdict']} - {f['reason']}")
    for e in res["errors"]:
        print(f"  error: {e}")
    return 0 if res["groups"] and not res["errors"] else 1


def cmd_sync(args) -> int:
    from .sync import format_result, freshness, run_sync, schedule_command
    if args.schedule:
        cmd = schedule_command(args.schedule, args.os)
        print("# Add this to your scheduler to run `truthlens sync` " + args.schedule + " (TruthLens does not install it):")
        if (args.os or ("windows" if os.name == "nt" else "unix")) == "windows":
            print("# Windows: paste into a Command Prompt")
        else:
            print("# Linux/macOS: run `crontab -e` and add this line")
        print(cmd)
        return 0
    if args.status:
        print(freshness(_config(args))["message"])
        return 0
    cfg = _config(args)
    srcs = [x.strip() for x in args.sources.split(",")] if args.sources else None
    res = run_sync(cfg, sources=srcs, index_new=not args.no_index, max_docs=args.max_docs,
                   progress=lambda n: print(f"syncing {n} …", file=sys.stderr))
    print(format_result(res))
    return 0 if res.get("offline") or any(r["status"] == "ok" for r in res["sources"].values()) else 1


def _pipe_for(args):
    from .pipeline import Pipeline
    cfg = _config(args)
    return Pipeline(cfg, llm=None if getattr(args, "no_llm", False) else "auto")


def cmd_corrections(args) -> int:
    from . import corrections as C
    cfg = _config(args)
    pend = C.load_pending(cfg)
    if args.action == "list":
        for r in pend:
            print(f"[{r['id']}] {r.get('reported_verdict') or '?'} -> {r['correct_verdict']}: {r['claim_text'][:120]}")
        print(f"{len(pend)} pending correction(s) in {C.pending_path(cfg)}")
        return 0
    if not pend:
        print("No pending corrections.")
        return 0
    if not sys.stdin.isatty():
        print("truthlens: `corrections review` asks you about each item; run it in a terminal. Nothing was changed.",
              file=sys.stderr)
        return 1

    def decide(rec, now):
        return {"a": "accept", "r": "reject"}.get(input("  [a]ccept / [r]eject / [s]kip? ").strip().lower()[:1], "skip")

    def approve(rec):
        return input(f"  {rec['source_url']} is not on the official allow-list. Add it to your local index anyway? [y/N] "
                     ).strip().lower() in ("y", "yes")
    done = C.review(cfg, _pipe_for(args), decide, approve)
    print(f"\n{done['accepted']} accepted, {done['rejected']} rejected, {done['skipped']} skipped, "
          f"{done['sources_added']} source(s) added. Labelled cases: {C.testset_path(cfg)}")
    return 0


def cmd_eval(args) -> int:
    from .evaluate import evaluate_v2
    from . import corrections as C
    path = Path(args.path) if args.path else (C.testset_path(_config(args)) if args.user_corrections else None)
    if path is None:
        print("truthlens: give --user-corrections or --path FILE.jsonl", file=sys.stderr)
        return 2
    if not path.exists():
        print(f"truthlens: no labelled cases yet at {path} (accept corrections with `truthlens corrections review`)",
              file=sys.stderr)
        return 1
    res = evaluate_v2(path, _pipe_for(args))
    for r in res["rows"]:
        print(f"{'✔' if r['ok'] else '✘'} {r['id']}: expected {r['expected']}, got {r['got']}  {r['text'][:90]}")
    print(f"{res['correct']}/{res['n']} correct; unsafe SUPPORTED: {res['unsafe_supported']}")
    return 0


def cmd_doctor(args) -> int:
    from .config import Config
    from .llm import LLMClient
    cfg = _config(args)
    pub = cfg.public()
    print(f"TruthLens {__version__}")
    print(f"config file   : {pub['config_file'] or '(none; using environment and defaults)'}")
    print(f"cache dir     : {pub['cache_dir']}")
    print(f"offline       : {pub['offline']}")
    print("keys present  : " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in pub["keys_present"].items()))
    llm = LLMClient.from_config(cfg)
    print(f"LLM           : {llm.label if llm else 'none -> rule-based claim extraction + heuristic judge (lower confidence)'}")
    print(f"web search    : {pub['search'] or 'none'}{' (Tavily keyless mode)' if cfg.tavily_keyless and not Config.secret('TAVILY_API_KEY') else ''}")
    print(f"MoSPI live    : {'on' if pub['mospi'] and not cfg.offline else 'off'} ({pub['mospi_base_url']}, backend {pub['mospi_backend']})")
    print(f"retrievers    : {', '.join(pub['retrievers'])}")
    print(f"allow-list    : {pub['allowed_domains']} official domains for document fetching")
    from .model import NOT_LIVE_VERIFIED
    print("untested live (tested only on synthetic or rate-limited fixtures; evidence is tagged “unverified source”):")
    for name in ("data.gov.in", "Semantic Scholar", "Shodhganga"):
        detail = next(v for v in NOT_LIVE_VERIFIED.values() if v.startswith(name))
        print(f"  - {detail}")
    if args.ping and not cfg.offline:
        print("connectivity  :")
        for name, ok, detail in _ping(cfg):
            print(f"  {'✔' if ok else '✘'} {name:17s} {detail}")
    return 0


NDAP_HDR = {"Origin": "https://ndap.niti.gov.in", "Referer": "https://ndap.niti.gov.in/"}
JJM_BODY = None   # filled lazily (needs the dashboard's parameter encoding)

PING_CHECKS = [
    # (source, URL, legacy TLS, what a healthy answer looks like[, method, headers, body])
    ("World Bank", "https://api.worldbank.org/v2/country/IND/indicator/SP.POP.TOTL?format=json&per_page=1", False, None),
    ("MoSPI API", "{mospi}/api/plfs/getIndicatorListByFrequency?frequency_code=1", True, "indicator_code"),
    ("MoSPI catalog", "{mospi}/api/hces/getHcesIndicatorList", True, "indicator_code"),
    ("data.gov.in", "https://api.data.gov.in/lists?format=json&notfilters[source]=visualize.data.gov.in&filters[active]=1&offset=0&limit=1", False, "records"),
    ("PIB feed", "https://pib.gov.in/RssMain.aspx?ModId=6&reg=3&lang=1", False, "<item>"),
    ("Lok Sabha", "https://sansad.in/api_ls/question/qetFilteredQuestionsAns?loksabhaNo=18&pageNo=1&pageSize=1&locale=en", False, "listOfQuestions"),
    ("Rajya Sabha", "https://integration.rajyasabha.digital/rsdebate/api/question/search-questions?searchParam=water&searchOn=title&matchesOn=allWords&page=1&size=1", False, "records"),
    ("LS archive (HF)", "https://datasets-server.huggingface.co/search?dataset=opensansad/lok-sabha-qa&config=default&split=train&query=water&offset=0&length=1", False, "rows"),
    ("OpenAlex", "https://api.openalex.org/works?search=india%20water&per-page=1", False, "results"),
    ("Crossref", "https://api.crossref.org/works/10.1038/s41586-020-2649-2", False, "message"),
    ("Econ. Survey", "https://www.indiabudget.gov.in/economicsurvey/", False, None),
    # v0.4
    ("NDAP catalogue", "https://loadqa.ndapapi.com/v1/search?query=groundwater&search=Variables,DatasetInfo&domain=ndap", False,
     "results", "GET", NDAP_HDR, None),
    ("RBI rates", "https://www.rbi.org.in/", False, "Policy Repo Rate"),
    ("RBI WSS (RSS)", "https://www.rbi.org.in/pressreleases_rss.xml", False, "<item>"),
    ("CEA", "https://cea.nic.in/api/dashboard/installed-capacity", False, "categories"),
    ("PPAC", "https://ppac.gov.in/AjaxController/getImportExports", False, "CRUDE OIL", "POST",
     {"X-Requested-With": "XMLHttpRequest"}, {"financialYear": "2025-2026", "reportBy": "1", "pageId": "14"}),
    ("JJM dashboard", "https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx/Bind_table_graph", False, "graph_table_data", "POST-JJM",
     {"Content-Type": "application/json; charset=utf-8", "Referer": "https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx"}, None),
    ("India-WRIS", "https://indiawris.gov.in/wris/", False, None),
    ("HMIS", "https://hmis.mohfw.gov.in/", False, None),
    ("Semantic Scholar", "https://api.semanticscholar.org/graph/v1/paper/search?query=groundwater&limit=1&fields=title", False, "data"),
    ("arXiv", "https://export.arxiv.org/api/query?search_query=all:groundwater&max_results=1", False, "<entry>"),
    ("Shodhganga", "https://shodhganga.inflibnet.ac.in/open-search/?query=groundwater&format=atom&rpp=1", False, "<entry"),
]


def _ping(cfg):
    """Live reachability of each source: (name, ok, detail). Every request goes through net.safe_get / safe_post (SSRF
    guard) on the same guarded session the checks use."""
    import concurrent.futures as cf
    import json as _json
    from .net import make_session, safe_get, safe_post

    def one(item):
        name, url, legacy, marker = item[:4]
        method, headers, body = (item[4:7] if len(item) > 4 else ("GET", None, None))
        url = url.replace("{mospi}", cfg.mospi_base_url.rstrip("/"))
        try:
            sess = make_session(legacy_tls=legacy)
            to = min(cfg.timeout, 15)
            if method == "POST":
                r = safe_post(sess, url, to, headers=headers, data=body)
            elif method == "POST-JJM":
                from .retrievers.ministry import _jjm_enc
                payload = _json.dumps({k: _jjm_enc("0") for k in ("StCode11", "Cat", "SubCat", "Param")})
                r = safe_post(sess, url, to, headers=headers, data=payload)
            else:
                r = safe_get(sess, url, to, headers=headers)
            text = r.text[:400000] if hasattr(r, "text") else ""
            ok = r.status_code < 400 and (marker is None or marker in text)
            detail = f"HTTP {r.status_code}" + ("" if ok or r.status_code >= 400 else " (unexpected body)")
            if "not a bot" in text[:3000]:
                ok, detail = False, f"HTTP {r.status_code} bot-challenge page (JavaScript); not usable"
            if r.status_code == 429:
                detail += " rate-limited" + (" (add S2_API_KEY)" if "semanticscholar" in url else "")
            return name, ok, detail
        except Exception as e:
            return name, False, f"{type(e).__name__}: {str(e)[:80]}"

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        return list(ex.map(one, PING_CHECKS))


def cmd_datagov(args) -> int:
    """truthlens datagov sync | search QUERY | status"""
    from .retrievers.datagovin import CatalogIndex, DataGovInClient, sync_catalog
    cfg = _config(args)
    client = DataGovInClient(cfg)
    index = CatalogIndex(cfg.cache_dir / "datagovin_catalog.sqlite")
    if args.action == "sync":
        if cfg.offline:
            print("truthlens: offline; cannot sync", file=sys.stderr)
            return 2

        def prog(done, total):
            print(f"\r  indexed {done:,} of {total or '?'} resources", end="", file=sys.stderr, flush=True)
        res = sync_catalog(client, index, max_records=args.max, page=args.page, progress=prog)
        print(file=sys.stderr)
        print(f"data.gov.in catalogue: {res['indexed']:,} resources indexed (data.gov.in reports {res['total_reported']}); "
              f"index at {index.path}")
        for e in res["errors"][:3]:
            print("  error:", e, file=sys.stderr)
        return 0 if res["indexed"] else 1
    if args.action == "search":
        for r in index.search(" ".join(args.query), k=10):
            print(f"{r['id']}  {r['updated'][:10]:10s}  {r['title'][:90]}  [{r['org'][:40]}]")
        return 0
    print(f"{index.count():,} resources in {index.path}; last sync {index.meta('synced_at') or 'never'}; "
          f"key: {'yes' if client.key and not client.using_sample_key else ('public sample key (opt-in)' if client.key else 'no')}")
    return 0


def _ask_key(args):
    """Prompt for a key without echoing it; returns the use_keys() mapping or None. v0.6: any provider of --llm."""
    import getpass
    from .config import LLM_KEY_ENV
    from .llm import UNTESTED_LIVE, check_base_url, norm_provider
    prov = norm_provider(args.llm) if args.llm else ""
    names = "Anthropic, OpenAI, DeepSeek, Mistral, xAI Grok, Gemini, Kimi, Qwen, GLM, OpenRouter or a custom endpoint"
    who = prov or names
    key = getpass.getpass(f"Your {who} key (hidden, used for this run only, never saved; Enter to skip): ").strip()
    if not key:
        return None
    if not prov:
        prov = "anthropic" if key.startswith("sk-ant-") else "openai"
        if not key.startswith(("sk-ant-", "sk-proj-")):
            print("truthlens: no --llm given, so the key is used as an OpenAI key; pass --llm deepseek (or another "
                  "provider) for the others", file=sys.stderr)
    out = {LLM_KEY_ENV[prov]: key}
    if prov == "custom":
        try:
            out["TRUTHLENS_CUSTOM_BASE_URL"] = check_base_url(input("Custom base URL (OpenAI-compatible, e.g. https://host/v1): "),
                                                              public=False)
        except Exception as e:
            print(f"truthlens: {e}", file=sys.stderr)
            return None
        model = input("Model name: ").strip()
        if not model:
            print("truthlens: a model name is needed for a custom provider", file=sys.stderr)
            return None
        out["TRUTHLENS_LLM_MODEL"] = model
    if prov in UNTESTED_LIVE:
        print(f"truthlens: note: the {prov} connection is untested live (only checked against mocked answers)",
              file=sys.stderr)
    args.llm = prov
    return out


LLM_CHOICES = ["anthropic", "openai", "ollama", "deepseek", "mistral", "xai", "gemini", "moonshot", "qwen", "zhipu",
               "openrouter", "custom"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="truthlens",
                                 description="Checks the numbers in Indian policy drafts against official data it holds, and lists the claims that need a source.")
    ap.add_argument("--version", action="version", version=f"truthlens {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="check a draft (.docx, .pdf, .txt, .md), a URL, or text")
    c.add_argument("input", help="path, http(s) URL, or '-' to read text from stdin")
    c.add_argument("--text", action="store_true", help="treat INPUT as literal text")
    c.add_argument("-f", "--format", default="md", choices=["html", "md", "markdown", "json", "cite", "csv"],
                   help="report format; 'cite' (v0.5.3) writes only the claims that need a source, as CSV; 'csv' (v0.6) "
                        "writes every claim with its verdict, as CSV")
    c.add_argument("-o", "--output", help="write the report here (default: stdout)")
    c.add_argument("--docx-out", help="also write a corrected copy of the draft (.docx) with comments and suggestions")
    c.add_argument("--offline", action="store_true", help="no network: bundled data, caches and the local index only")
    c.add_argument("--deep", action="store_true",
                   help="v0.5.2: Deep check: also ask the live sources (PIB, Parliament, research databases, live official "
                        "APIs); about a minute for a long draft. Default is Quick: bundled and synced official data, "
                        "cached answers and the deterministic checks, no network")
    c.add_argument("--quick", action="store_true", help="Quick check (the default)")
    c.add_argument("--strict", action="store_true", help="exit with status 1 if any claim is CONTRADICTED")
    c.add_argument("--numbers-only", action="store_true", help="v0.1 mode: only check numbers against India statistics")
    c.add_argument("--no-llm", action="store_true", help="ignore LLM keys (rules + heuristics only)")
    c.add_argument("--llm", choices=LLM_CHOICES,
                   help="AI provider (key from the environment, or --ask-key). v0.6: deepseek, mistral, xai (Grok), "
                        "gemini, moonshot (Kimi), qwen, zhipu (GLM), openrouter and custom are untested live")
    c.add_argument("--ask-key", action="store_true",
                   help="prompt (hidden) for your own AI key (Anthropic, OpenAI, DeepSeek, Mistral, xAI, Gemini, Kimi, "
                        "Qwen, GLM, OpenRouter or custom; pick with --llm), used for this run only and never saved")
    c.add_argument("--search", choices=["brave", "tavily", "serper", "none"], help="web search provider")
    c.add_argument("--retrievers", help="comma list: curated,worldbank,mospi,datagovin,docs,web,citations,pib,parliament,"
                                        "openalex,reports,ndap,rbi,cea,ppac,jjm,semanticscholar,arxiv,shodhganga")
    c.add_argument("--config", help="path to truthlens.toml")

    cm = sub.add_parser("compare", help="v0.6: compare two versions of a document (OLD NEW): near-copied sentences, "
                                       "changed figures, dropped commitments, new sections")
    cm.add_argument("old", help="the earlier version (.pdf, .docx, .txt, .md)")
    cm.add_argument("new", help="the later version")
    cm.add_argument("-f", "--format", default="md", choices=["md", "markdown", "json", "html"])
    cm.add_argument("-o", "--output", help="write the comparison here (default: stdout)")
    cm.add_argument("--threshold", type=float, default=0.85,
                    help="similarity at which a sentence counts as near-copied (0-1, default 0.85)")
    cm.add_argument("--meaning", action="store_true",
                    help="v0.7: also match sentences by meaning (needs: pip install \"truthlens[meaning]\"; the model "
                         "downloads once) and label each change kept / strengthened / weakened / changed figure / new / dropped")
    cm.add_argument("--meaning-threshold", type=float, default=None,
                    help="match score a pair needs to count as the same point (default 0.10; higher = fewer, surer matches)")
    cm.add_argument("--topics", default="auto", choices=["auto", "headings", "clusters", "water"],
                    help="where topics come from: the documents' headings (auto falls back to grouping by similarity), "
                         "clusters, or the optional water-policy keyword preset")
    cm.add_argument("--model", default=None, choices=["english", "multilingual"],
                    help="embedding model: english (bge-small-en-v1.5, 67 MB, default) or multilingual "
                         "(paraphrase-multilingual-MiniLM-L12-v2, 240 MB)")
    cm.add_argument("--ai-summary", action="store_true",
                    help="optional: a 2-3 sentence AI summary per topic, grounded only in the shown quotes (needs --llm and "
                         "a key via --ask-key or the environment, or Ollama); summaries citing text not in the quotes are rejected")
    cm.add_argument("--llm", help="AI provider for --ai-summary (anthropic, openai, ollama, deepseek, ...)")
    cm.add_argument("--ask-key", action="store_true", help="prompt (hidden) for the AI key, used for this run only, never saved")
    cm.add_argument("--config", help="path to truthlens.toml")

    i = sub.add_parser("index", help="add documents to the local evidence index")
    i.add_argument("paths", nargs="*", help="files or folders (.pdf, .html, .docx, .txt, .md)")
    i.add_argument("--url", action="append", help="allow-listed official URL to fetch and index (repeatable)")
    i.add_argument("--pib-rss", action="store_true", help="index the current PIB press releases (RSS)")
    i.add_argument("--max", type=int, default=20, help="max PIB releases to fetch (default 20)")
    i.add_argument("--official", action="store_true", help="treat the local files as official sources")
    i.add_argument("--list", action="store_true", help="list indexed documents")
    i.add_argument("--offline", action="store_true")
    i.add_argument("--config")

    s = sub.add_parser("sources", help="show sources; list/add/test your own plug-in sources (sources.d/*.yaml)")
    s.add_argument("action", nargs="?", choices=["status", "list", "add", "test", "examples"], default="status")
    s.add_argument("target", nargs="?", help="add: a YAML file or bundled example name; test: a plug-in name")
    s.add_argument("--claim", help="test: the sentence to try (default: the config's test.claim)")
    s.add_argument("--yes", action="store_true", help="add: confirm an MCP source that starts a local program")
    s.add_argument("--offline", action="store_true")
    s.add_argument("--config")
    d = sub.add_parser("doctor", help="show configuration and which keys are present (values are never printed)")
    d.add_argument("--ping", action="store_true", help="also test connectivity to the public sources")
    d.add_argument("--offline", action="store_true")
    d.add_argument("--config")
    sub.add_parser("indicators", help="list India indicators covered by the deterministic number checker")
    g = sub.add_parser("datagov", help="data.gov.in catalogue: sync the local index, search it, or show its status")
    g.add_argument("action", choices=["sync", "search", "status"])
    g.add_argument("query", nargs="*")
    g.add_argument("--max", type=int, default=200000, help="sync at most this many resources (newest first)")
    g.add_argument("--page", type=int, default=1000)
    g.add_argument("--offline", action="store_true")
    g.add_argument("--config")

    y = sub.add_parser("sync", help="refresh local knowledge: PIB, reports, Parliament, MoSPI, NDAP, RBI, plug-ins")
    y.add_argument("--schedule", choices=["daily", "weekly"], help="print a cron line / Windows schtasks command (print only)")
    y.add_argument("--os", choices=["windows", "unix"], help="with --schedule: which scheduler (default: this computer's)")
    y.add_argument("--status", action="store_true", help="only say when the local data was last updated")
    y.add_argument("--sources", help="comma list: pib,reports,parliament,mospi,ndap,rbi,plugins (default: all)")
    y.add_argument("--no-index", action="store_true", help="do not add new PIB releases to the local document index")
    y.add_argument("--max-docs", type=int, default=10, help="max new PIB releases to index (default 10)")
    y.add_argument("--offline", action="store_true")
    y.add_argument("--config")

    k = sub.add_parser("corrections", help="review readers' 'this verdict is wrong' reports (never auto-accepted)")
    k.add_argument("action", choices=["list", "review"])
    k.add_argument("--offline", action="store_true")
    k.add_argument("--no-llm", action="store_true")
    k.add_argument("--config")
    e = sub.add_parser("eval", help="score this build on labelled cases")
    e.add_argument("--user-corrections", action="store_true", help="the cases you accepted with `corrections review`")
    e.add_argument("--path", help="any labelled .jsonl test set")
    e.add_argument("--offline", action="store_true")
    e.add_argument("--no-llm", action="store_true")
    e.add_argument("--config")

    args = ap.parse_args(argv)
    if args.cmd == "indicators":
        from .registry import load_registry
        from .sources.curated import CuratedStore
        cov = CuratedStore().coverage()
        for iid, ind in load_registry().items():
            years = sorted({p for k, v in cov.items() if k.split(" [")[0] == iid for p in v})
            print(f"{iid:26s} {ind.name}\n{'':26s} periods: {', '.join(years) or '—'}")
        return 0
    if args.cmd in ("check", "compare") and getattr(args, "ask_key", False):
        from .config import use_keys
        keys = _ask_key(args)
        if keys:
            with use_keys(keys):
                return cmd_check(args) if args.cmd == "check" else cmd_compare(args)
    return {"check": cmd_check, "compare": cmd_compare, "index": cmd_index, "sources": cmd_sources, "doctor": cmd_doctor,
            "datagov": cmd_datagov, "sync": cmd_sync,
            "corrections": cmd_corrections, "eval": cmd_eval}[args.cmd](args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
