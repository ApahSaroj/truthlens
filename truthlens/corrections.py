"""v0.5 learning from corrections (human in the loop).

  1. The web page's "This verdict is wrong" button sends the claim, the verdict shown, the verdict the reader says is
     right, an optional note and an optional source URL. `add_pending` validates it and appends one line to
     <data>/corrections/pending.jsonl. Nothing is fetched and nothing changes at this point (local file only).
  2. `truthlens corrections review` shows each pending item, re-runs the claim, and asks: accept, reject or skip.
     Accept writes a labelled case to <data>/testset_user_corrections.jsonl and, only if the URL is on the
     official-domain allow-list or the reviewer explicitly approves it, adds that page to the local document index.
     Reviewed items move to <data>/corrections/reviewed.jsonl.
  3. `truthlens eval --user-corrections` scores the current build on those cases.

TruthLens never changes its code or rules from a correction and never accepts one by itself.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import secrets
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from .config import Config
from .model import VERDICTS
from .sync import data_dir

MAX_TEXT = 2000
MAX_NOTE = 1000
MAX_URL = 500
CORRECTABLE = list(VERDICTS)          # CONTRADICTED, PARTLY SUPPORTED, UNVERIFIED, SUPPORTED
_CTRL_RX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _dir(cfg: Optional[Config] = None) -> Path:
    return data_dir(cfg) / "corrections"


def pending_path(cfg: Optional[Config] = None) -> Path:
    return _dir(cfg) / "pending.jsonl"


def reviewed_path(cfg: Optional[Config] = None) -> Path:
    return _dir(cfg) / "reviewed.jsonl"


def testset_path(cfg: Optional[Config] = None) -> Path:
    return data_dir(cfg) / "testset_user_corrections.jsonl"


def _clean(s, cap: int) -> str:
    s = _CTRL_RX.sub(" ", str(s or "")).strip()
    return s[:cap]


def validate_url(u: str) -> str:
    u = _clean(u, MAX_URL)
    if not u:
        return ""
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("source_url must be an http(s) link without a user name or password")
    return u


def add_pending(item: dict, cfg: Optional[Config] = None) -> dict:
    """Validate and store one correction. Raises ValueError on bad input. Returns the stored record."""
    text = _clean(item.get("claim_text") or item.get("sentence"), MAX_TEXT)
    if len(text) < 3:
        raise ValueError("claim_text is required")
    correct = str(item.get("correct_verdict") or "").upper().strip()
    if correct not in CORRECTABLE:
        raise ValueError(f"correct_verdict must be one of {', '.join(CORRECTABLE)}")
    shown = str(item.get("reported_verdict") or "").upper().strip()
    if shown and shown not in CORRECTABLE + ["SKIPPED"]:
        raise ValueError("reported_verdict is not a TruthLens verdict")
    if shown and shown == correct:
        raise ValueError("the correct verdict is the same as the verdict shown")
    claim_type = str(item.get("claim_type") or "numeric")
    rec = {"id": secrets.token_hex(6), "created": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "claim_text": text, "sentence": _clean(item.get("sentence") or text, MAX_TEXT),
           "claim_type": claim_type if claim_type in ("numeric", "citation", "entity") else "numeric",
           "reported_verdict": shown, "correct_verdict": correct, "note": _clean(item.get("note"), MAX_NOTE),
           "source_url": validate_url(item.get("source_url") or ""),
           "document": _clean(item.get("document"), 200), "tool_version": _clean(item.get("tool_version"), 20),
           "status": "pending"}
    p = pending_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _read(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue          # a damaged line is skipped, never executed or shown raw
    return out


def load_pending(cfg: Optional[Config] = None) -> list[dict]:
    return [r for r in _read(pending_path(cfg)) if r.get("status", "pending") == "pending"]


def _rewrite(p: Path, rows: list[dict]) -> None:
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(p)


def rerun(pipe, text: str) -> dict:
    """The verdict the current build gives the claim now (worst sentence verdict, as in the evaluators)."""
    from .model import SEVERITY
    from .readers import read_text
    rep = pipe.run(read_text(text), "correction")
    judged = [s["verdict"] for s in rep["sentences"] if s.get("verdict")]
    got = max(judged, key=lambda v: SEVERITY.get(v, 0)) if judged else "NOT_EXTRACTED"
    c = rep["claims"][0] if rep["claims"] else {}
    return {"verdict": got, "rationale": c.get("rationale", ""), "method": c.get("method", ""),
            "confidence": c.get("confidence", "")}


def accept(rec: dict, cfg: Optional[Config] = None) -> dict:
    """Write the labelled case (never twice for the same claim text and label)."""
    tp = testset_path(cfg)
    have = _read(tp)
    case = {"id": f"uc-{rec['id']}", "text": rec["claim_text"], "type": rec.get("claim_type") or "numeric",
            "expected": rec["correct_verdict"], "category": "user_correction",
            "source": rec.get("source_url") or rec.get("note") or "reviewer", "note": rec.get("note", ""),
            "reported_verdict": rec.get("reported_verdict", ""), "accepted": dt.date.today().isoformat()}
    if any(h.get("text") == case["text"] and h.get("expected") == case["expected"] for h in have):
        return next(h for h in have if h.get("text") == case["text"] and h.get("expected") == case["expected"])
    tp.parent.mkdir(parents=True, exist_ok=True)
    with open(tp, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(case, ensure_ascii=False) + "\n")
    return case


def add_source(url: str, cfg: Config, approved: bool = False, session=None) -> dict:
    """Index the correction's source page. Allow-listed domains only, unless the reviewer approved this URL."""
    from .net import domain_allowed
    from .retrievers.docs import DocFetcher, DocIndex, index_bytes
    url = validate_url(url)
    if not url:
        raise ValueError("no source URL")
    official = domain_allowed(url, cfg.allowed_domains)
    if not official and not approved:
        raise PermissionError(f"{urlparse(url).hostname} is not on the official-domain allow-list; not added")
    fetcher = DocFetcher(cfg, session)
    data, kind = fetcher.fetch(url, any_domain=not official)      # SSRF guard applies either way
    return index_bytes(DocIndex(cfg.cache_dir / "index.sqlite"), url, data, kind, official=official)


def review(cfg: Config, pipe, decide: Callable[[dict, dict], str],
           approve_source: Callable[[dict], bool] = lambda rec: False,
           out: Callable[[str], None] = print, session=None) -> dict:
    """Walk the pending items. decide(rec, now) -> 'accept' | 'reject' | 'skip' (the reviewer's answer; there is no
    default accept). approve_source(rec) is asked only for a source URL that is not on the allow-list."""
    rows = _read(pending_path(cfg))
    done = {"accepted": 0, "rejected": 0, "skipped": 0, "sources_added": 0}
    reviewed = []
    def out_clean(s):
        out(_CTRL_RX.sub(" ", s.replace("\r", " ")))
    for rec in rows:
        if rec.get("status", "pending") != "pending" or not isinstance(rec.get("claim_text"), str):
            continue
        rec = dict(rec, **{k: _clean(rec.get(k), MAX_TEXT) for k in ("claim_text", "note", "source_url",
                                                                      "reported_verdict", "correct_verdict", "id")})
        now = rerun(pipe, rec["claim_text"])
        out_clean(f"\n[{rec['id']}] {rec['claim_text']}\n  shown: {rec.get('reported_verdict') or '?'}   "
            f"reader says: {rec['correct_verdict']}   now: {now['verdict']} ({now['method']})")
        if rec.get("note"):
            out_clean(f"  note: {rec['note']}")
        if rec.get("source_url"):
            out_clean(f"  source: {rec['source_url']}")
        if now["rationale"]:
            out_clean(f"  why now: {now['rationale'][:300]}")
        ans = (decide(rec, now) or "skip").strip().lower()
        if ans not in ("accept", "reject"):
            done["skipped"] += 1
            continue
        rec = dict(rec, status="accepted" if ans == "accept" else "rejected",
                   reviewed=dt.datetime.now().astimezone().isoformat(timespec="seconds"), verdict_at_review=now["verdict"])
        if ans == "accept":
            accept(rec, cfg)
            done["accepted"] += 1
            if rec.get("source_url"):
                from .net import domain_allowed
                ok = domain_allowed(rec["source_url"], cfg.allowed_domains) or approve_source(rec)
                if ok:
                    try:
                        add_source(rec["source_url"], cfg, approved=True, session=session)
                        done["sources_added"] += 1
                        rec["source_indexed"] = True
                    except Exception as e:
                        out_clean(f"  source not added: {type(e).__name__}: {str(e)[:150]}")
        else:
            done["rejected"] += 1
        reviewed.append(rec)
    if reviewed:
        ids = {r["id"] for r in reviewed}
        rp = reviewed_path(cfg)
        with open(rp, "a", encoding="utf-8") as fh:
            for r in reviewed:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        _rewrite(pending_path(cfg), [r for r in rows if r.get("id") not in ids])
    return done
