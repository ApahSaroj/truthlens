"""v0.5 `truthlens sync`: keep the *knowledge* fresh (never the code or the rules).

One run refreshes, source by source (each one fails closed and is recorded, never raised):
  pib         PIB English press-release RSS; new releases are added to the local document index (allow-listed fetch)
  reports     official report listing pages (Economic Survey, Budget and the other configured listing pages): new PDFs
  parliament  Lok Sabha recent questions for the tracked keywords (sansad.in)
  mospi       MoSPI eSankhyiki indicator catalogue; and, for the curated PLFS / National Accounts series, whether MoSPI
              now has a newer period (the curated figure is *superseded*) or a revised value for the same period
  ndap        NDAP catalogue entries for the tracked keywords (new datasets, newer "last updated" dates)
  rbi         RBI current rates (repo, SDF, MSF, bank rate, CRR, SLR): a changed rate supersedes the old one
  plugin:*    every plug-in whose config declares `sync: {requests: [...]}`: new periods and revised values

State (per-source last-synced time and the item ids seen) is kept in <data>/sync_state.json; every run appends one
line to <data>/sync_log.jsonl. <data> is $TRUTHLENS_DATA_DIR, else ./data.
Every fetch goes through the same retrievers (net.safe_get / safe_post, SSRF guard) as a check does.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
from pathlib import Path
from typing import Callable, Optional

from .config import Config, redact
from .net import DiskCache

STALE_DAYS = 7
DEFAULT_KEYWORDS = ["jal jeevan mission", "drinking water", "groundwater", "unemployment", "inflation",
                    "gross domestic product", "renewable energy"]
ALL_SOURCES = ["pib", "reports", "parliament", "mospi", "ndap", "rbi", "plugins"]


def data_dir(cfg: Optional[Config] = None) -> Path:
    env = os.environ.get("TRUTHLENS_DATA_DIR")
    if env:
        return Path(env).expanduser()
    tl = (((cfg.toml if cfg else {}) or {}).get("truthlens", {}) if cfg else {}) or {}
    return Path(tl.get("data_dir") or "data").expanduser()


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def load_state(cfg: Optional[Config] = None) -> dict:
    p = data_dir(cfg) / "sync_state.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sources": {}}


def _save_state(cfg, state: dict) -> None:
    d = data_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "sync_state.json.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(d / "sync_state.json")


def freshness(cfg: Optional[Config] = None, now: Optional[dt.datetime] = None) -> dict:
    """{'last_synced': iso|None, 'days': float|None, 'stale': bool, 'message': str} (stale: never or > 7 days)."""
    st = load_state(cfg)
    last = st.get("last_run")
    if not last:
        return {"last_synced": None, "days": None, "stale": True,
                "message": "Local data has never been updated: run `truthlens sync` (or Update now in the web app)."}
    try:
        t = dt.datetime.fromisoformat(last)
    except ValueError:
        return {"last_synced": last, "days": None, "stale": True, "message": "Local data date unknown: run `truthlens sync`."}
    now = now or dt.datetime.now().astimezone()
    days = (now - t).total_seconds() / 86400
    stale = days > STALE_DAYS
    when = f"{t.day} {t.strftime('%B %Y')}"
    msg = (f"Local data last updated {when} ({days:.0f} days ago, older than {STALE_DAYS} days): run `truthlens sync` "
           "or Update now." if stale else f"Local data last updated {when}.")
    return {"last_synced": last, "days": round(days, 2), "stale": stale, "message": msg}


def _force(obj, attr: str = "cache") -> None:
    """Make a retriever's disk cache miss once so this run fetches live (the fresh answer is cached again)."""
    c = getattr(obj, attr, None)
    if isinstance(c, DiskCache):
        setattr(obj, attr, DiskCache(c.dir.parent, c.dir.name, ttl=-1))


def _restore(obj, attr: str, ttl: int) -> None:
    c = getattr(obj, attr, None)
    if isinstance(c, DiskCache):
        setattr(obj, attr, DiskCache(c.dir.parent, c.dir.name, ttl=ttl))


# ------------------------------------------------------------------------------------------------ steps
def _pib(cfg, session, prev, opts):
    from .retrievers.docs import DocFetcher, DocIndex, index_url
    from .retrievers.live_docs import PIBRetriever
    r = PIBRetriever(cfg, session)
    _force(r)
    items = r.feed()
    if r.errors:
        raise RuntimeError(r.errors[0])
    ids = [it["link"] for it in items]
    new = [it for it in items if it["link"] not in set(prev)]
    notes, indexed = [], 0
    lang = items[0].get("lang") if items else "en"
    if lang != "en":
        notes.append(f"PIB served the feed in '{lang}'; new releases were not indexed")
    elif opts.get("index_new", True) and new:
        idx = DocIndex(cfg.cache_dir / "index.sqlite")
        fetcher = DocFetcher(cfg, session)
        for it in new[: int(opts.get("max_docs", 10))]:
            try:
                if not idx.has(it["link"]):
                    index_url(idx, fetcher, it["link"])
                    indexed += 1
            except Exception as e:
                notes.append(redact(f"could not index {it['link']}: {type(e).__name__}"))
        notes.append(f"{indexed} new release(s) added to the local document index")
    return {"items": ids, "new": [f"{it['title']} ({it['link']})" for it in new]}, notes, []


def _reports(cfg, session, prev, opts):
    from .retrievers.live_docs import ReportsRetriever
    r = ReportsRetriever(cfg, session)
    _force(r)
    links = []
    for page in r.pages:
        links += r.links(page)
    if r.errors and not links:
        raise RuntimeError(r.errors[0])
    ids = list(dict.fromkeys(x["url"] for x in links))
    seen = set(prev)
    new = [f"{x['text'] or 'report'} ({x['url']})" for x in {x["url"]: x for x in links}.values() if x["url"] not in seen]
    return {"items": ids, "new": new}, [e for e in r.errors][:3], []


def _parliament(cfg, session, prev, opts):
    from .retrievers.parliament import ParliamentRetriever
    r = ParliamentRetriever(cfg, session)
    _force(r)
    ids, new, seen = [], [], set(prev)
    for kw in opts.get("keywords") or DEFAULT_KEYWORDS:
        for q in r.lok_sabha_recent(kw, n=10):
            qid = f"LS{q.get('lok')}-S{q.get('session')}-Q{q.get('qno')}"
            if qid in ids:
                continue
            ids.append(qid)
            if qid not in seen:
                new.append(f"{q.get('date')}: {q.get('subject') or q.get('question', '')[:80]} ({q.get('ministry')}) [{kw}]")
    if r.errors and not ids:
        raise RuntimeError(r.errors[0])
    return {"items": ids, "new": new}, r.errors[:3], []


def _mospi(cfg, session, prev, opts):
    from .registry import load_registry
    from .retrievers.mospi import MospiClient, MospiStore, SUPPORTED
    from .retrievers.mospi_catalog import MospiCatalog
    from .sources.curated import CuratedStore
    cat = MospiCatalog(cfg, session)
    # the catalogue caches by URL with its own TTL; a sync asks again
    import truthlens.retrievers.mospi_catalog as mc
    orig = mc.DiskCache
    mc.DiskCache = lambda root, ns, ttl=0: orig(root, ns, ttl=-1)
    try:
        inds = cat.indicators()
    finally:
        mc.DiskCache = orig
    ids = [f"{i['dataset']}:{i['code']}" for i in inds if i.get("code") is not None]
    seen = set(prev)
    new = [f"{i['title']}: {i['label']}" for i in inds if i.get("code") is not None and f"{i['dataset']}:{i['code']}" not in seen]
    superseded, notes = [], []
    if cat.errors and not ids:
        notes.append(cat.errors[0])
    # curated figures that MoSPI has superseded (a newer period) or revised (same period, different value)
    curated = CuratedStore()
    store = MospiStore(curated, MospiClient(cfg, session))
    reg = load_registry()
    for iid in sorted(SUPPORTED):
        ind = reg.get(iid)
        if ind is None:
            continue
        for variant in [ind.default_variant] + [v for v in ind.variants if v != ind.default_variant]:
            recs = [r for r in curated.find(iid, variant=variant) if r.get("status") in (None, "current")
                    and re.fullmatch(r"\d{4}-\d{2}", str(r.get("period") or ""))]
            if not recs:
                continue
            latest = max(recs, key=lambda r: r["period"])
            nxt = _next_fy(latest["period"])
            live_new = store.live(iid, nxt, variant)
            if live_new and live_new.get("value") is not None:
                superseded.append({"indicator": iid, "variant": variant, "kind": "newer period",
                                   "curated": {"period": latest["period"], "value": latest["value"]},
                                   "official": {"period": nxt, "value": live_new["value"],
                                                "url": (live_new.get("source") or {}).get("url")}})
            live_same = store.live(iid, latest["period"], variant)
            if live_same and live_same.get("value") is not None and abs(float(live_same["value"]) - float(latest["value"])) > 0.051:
                superseded.append({"indicator": iid, "variant": variant, "kind": "revised",
                                   "curated": {"period": latest["period"], "value": latest["value"]},
                                   "official": {"period": latest["period"], "value": live_same["value"],
                                                "url": (live_same.get("source") or {}).get("url")}})
    notes += store.client.errors[:3]
    return {"items": ids, "new": new}, notes, superseded


def _next_fy(p: str) -> str:
    a = int(p[:4]) + 1
    return f"{a}-{str(a + 1)[-2:]}"


def _ndap(cfg, session, prev, opts):
    from .retrievers.ndap import NDAPCatalog
    r = NDAPCatalog(cfg, session)
    _force(r)
    prev_upd = dict(x.split("@", 1) for x in prev if "@" in x)
    ids, new = [], []
    for kw in opts.get("keywords") or DEFAULT_KEYWORDS:
        for d in r.search(kw):
            key = f"{d['id']}@{d.get('updated') or ''}"
            if key in ids:
                continue
            ids.append(key)
            old = prev_upd.get(str(d["id"]))
            if old is None:
                new.append(f"new dataset: {d['name']} (updated {d.get('updated') or 'n.a.'})")
            elif old != (d.get("updated") or ""):
                new.append(f"updated: {d['name']} ({old or 'n.a.'} -> {d.get('updated')})")
    if r.errors and not ids:
        raise RuntimeError(r.errors[0])
    return {"items": ids, "new": new}, r.errors[:3], []


def _rbi(cfg, session, prev, opts):
    from .retrievers.ministry import RBISource
    r = RBISource(cfg, session)
    _force(r)
    home, _t = r._home()
    if r.errors:          # the live fetch failed (a stale cached answer is not a sync)
        raise RuntimeError(r.errors[0])
    if not home or not home.get("rates"):
        raise RuntimeError(r.errors[0] if r.errors else "RBI current rates not found on the home page")
    ids = [f"{k}={v}" for k, v in sorted(home["rates"].items())]
    old = dict(x.split("=", 1) for x in prev if "=" in x)
    new, superseded = [], []
    for k, v in sorted(home["rates"].items()):
        if k in old and float(old[k]) != float(v):
            new.append(f"{k} changed: {old[k]}% -> {v}%")
            superseded.append({"indicator": f"rbi:{k}", "kind": "changed", "previous": {"value": float(old[k])},
                               "official": {"value": v, "url": "https://www.rbi.org.in/"}})
        elif k not in old:
            new.append(f"{k}: {v}%")
    return {"items": ids, "new": new}, [], superseded


def _plugin(spec):
    def step(cfg, session, prev, opts):
        from .plugins import PluginSource, to_rows
        src = PluginSource(cfg, spec)
        reqs = (spec.get("sync") or {}).get("requests") or []
        inds = {str(i.get("code")): i for i in spec.get("indicators") or []}
        old = {}
        for x in prev:
            if "=" in x:
                k, v = x.rsplit("=", 1)
                old[k] = v
        ids, new, superseded, notes = [], [], [], []
        for rq in reqs:
            vars_ = {"query": "", "indicator": str(rq.get("indicator", "")), "place": str(rq.get("place", "")),
                     "period": str(rq.get("period", (spec.get("period") or {}).get("default", "")))}
            try:
                doc, url = src.fetch_doc(vars_)
            except Exception as e:
                notes.append(redact(f"{vars_['indicator']}: {type(e).__name__}: {str(e)[:120]}"))
                continue
            label = (inds.get(vars_["indicator"]) or {}).get("label") or vars_["indicator"]
            rows, _meta = to_rows(spec, doc, label, vars_)
            for row in rows:
                k = f"{vars_['indicator']}:{row.get('state', '')}:{row.get('year', '')}"
                ids.append(f"{k}={row['value']}")
                if k not in old:
                    if old:
                        new.append(f"{label} {row.get('year') or ''}: {row['value']} (new)")
                elif abs(float(old[k]) - float(row["value"])) > 1e-9:
                    new.append(f"{label} {row.get('year')} revised: {old[k]} -> {row['value']}")
                    superseded.append({"indicator": f"{src.name}:{vars_['indicator']}", "kind": "revised",
                                       "period": row.get("year"), "previous": {"value": float(old[k])},
                                       "official": {"value": row["value"], "url": url}})
        if reqs and not ids and notes:
            raise RuntimeError(notes[0])
        return {"items": ids, "new": new}, notes, superseded
    return step


STEPS: dict[str, Callable] = {"pib": _pib, "reports": _reports, "parliament": _parliament, "mospi": _mospi,
                              "ndap": _ndap, "rbi": _rbi}


# ------------------------------------------------------------------------------------------------ run
_LOCK = threading.Lock()
RUNNING: dict = {"running": False, "started": None, "result": None}


def run_sync(cfg: Optional[Config] = None, session=None, sources: Optional[list] = None, index_new: bool = True,
             max_docs: int = 10, keywords: Optional[list] = None, progress: Optional[Callable[[str], None]] = None) -> dict:
    """Refresh every source; return {started, finished, sources: {name: {...}}, new_total, superseded}."""
    cfg = cfg or Config.load()
    if cfg.offline:
        return {"started": _now(), "finished": _now(), "offline": True, "sources": {}, "new_total": 0, "superseded": [],
                "message": "offline: nothing synced"}
    tl = (cfg.toml or {}).get("sync", {}) if isinstance(cfg.toml, dict) else {}
    opts = {"index_new": index_new, "max_docs": max_docs,
            "keywords": keywords or tl.get("keywords") or DEFAULT_KEYWORDS}
    want = sources or ALL_SOURCES
    steps = {k: v for k, v in STEPS.items() if k in want}
    if "plugins" in want or any(str(w).startswith("plugin:") for w in want):
        from .plugins import load_all, plugin_id
        specs, _problems = load_all(cfg)
        for s in specs:
            if s.get("sync") and ("plugins" in want or plugin_id(s["name"]) in want):
                steps[plugin_id(s["name"])] = _plugin(s)
    state = load_state(cfg)
    state.setdefault("sources", {})
    out = {"started": _now(), "sources": {}, "superseded": []}
    for name, step in steps.items():
        if progress:
            progress(name)
        prev = (state["sources"].get(name) or {}).get("items") or []
        rec = {"source": name, "synced_at": _now()}
        try:
            got, notes, sup = step(cfg, session, prev, opts)
            if not prev:
                # first sync of this source: everything is a baseline, not news
                notes = [f"first sync: baseline of {len(got['items'])} item(s) recorded"] + list(notes)
                got = dict(got, new=[])
            rec.update(status="ok", items=len(got["items"]), new=got["new"][:50], new_count=len(got["new"]),
                       notes=[redact(n) for n in notes][:5])
            if sup:
                rec["superseded"] = sup
                out["superseded"] += [dict(s, source=name) for s in sup]
            state["sources"][name] = {"last_synced": rec["synced_at"], "items": got["items"][-3000:],
                                      "last_new": got["new"][:20], "status": "ok"}
        except Exception as e:
            rec.update(status="error", error=redact(f"{type(e).__name__}: {str(e)[:200]}"), new=[], new_count=0)
            old = state["sources"].get(name) or {}
            state["sources"][name] = dict(old, status="error", last_error=rec["error"], last_attempt=rec["synced_at"])
        out["sources"][name] = rec
    out["finished"] = _now()
    out["new_total"] = sum(r.get("new_count", 0) for r in out["sources"].values())
    ok = [n for n, r in out["sources"].items() if r["status"] == "ok"]
    if ok:
        state["last_run"] = out["finished"]
    state["superseded"] = out["superseded"] or state.get("superseded", [])
    _save_state(cfg, state)
    d = data_dir(cfg)
    with open(d / "sync_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(out, ensure_ascii=False) + "\n")
    return out


def run_in_background(cfg: Optional[Config] = None, **kw) -> bool:
    """Start a sync in a thread (web app 'Update now'). False when one is already running."""
    with _LOCK:
        if RUNNING["running"]:
            return False
        RUNNING.update(running=True, started=_now(), result=None)

    def go():
        try:
            RUNNING["result"] = summary(run_sync(cfg, **kw))
        except Exception as e:  # never kill the server
            RUNNING["result"] = {"error": redact(f"{type(e).__name__}: {e}")}
        finally:
            RUNNING["running"] = False
    threading.Thread(target=go, daemon=True, name="truthlens-sync").start()
    return True


def summary(res: dict) -> dict:
    return {"finished": res.get("finished"), "new_total": res.get("new_total", 0),
            "superseded": len(res.get("superseded") or []),
            "sources": {n: {"status": r["status"], "new": r.get("new_count", 0), "error": r.get("error")}
                        for n, r in (res.get("sources") or {}).items()}}


def format_result(res: dict) -> str:
    if res.get("offline"):
        return "truthlens sync: offline, nothing synced."
    lines = [f"truthlens sync: {res['new_total']} new item(s) across {len(res['sources'])} source(s)."]
    for n, r in res["sources"].items():
        if r["status"] != "ok":
            lines.append(f"  ✘ {n:22s} {r.get('error')}")
            continue
        lines.append(f"  ✔ {n:22s} {r['items']} item(s), {r['new_count']} new")
        for x in r["new"][:5]:
            lines.append(f"      + {x[:150]}")
        if r["new_count"] > 5:
            lines.append(f"      … and {r['new_count'] - 5} more")
        for x in r.get("notes") or []:
            lines.append(f"      note: {x[:150]}")
    for s in res.get("superseded") or []:
        cur = s.get("curated") or s.get("previous") or {}
        lines.append(f"  ! superseded ({s['kind']}): {s['indicator']} {s.get('variant') or ''} "
                     f"{cur.get('period', '')} {cur.get('value')} -> {s['official'].get('period', '')} {s['official'].get('value')}")
    return "\n".join(lines)


def schedule_command(every: str, os_name: Optional[str] = None, exe: str = "truthlens") -> str:
    """The command that would schedule `truthlens sync` (printed only; TruthLens never installs it itself)."""
    if every not in ("daily", "weekly"):
        raise ValueError("daily or weekly")
    os_name = os_name or ("windows" if os.name == "nt" else "unix")
    if os_name == "windows":
        sc = "DAILY" if every == "daily" else "WEEKLY /D MON"
        return f'schtasks /Create /SC {sc} /ST 07:00 /TN "TruthLens sync" /TR "{exe} sync"'
    cron = "0 7 * * *" if every == "daily" else "0 7 * * 1"
    return f"{cron} cd {Path.cwd()} && {exe} sync >> data/sync_cron.log 2>&1"
