"""FastAPI app: a minimal upload page plus JSON endpoints.

  GET  /              single-page app: drop a .docx/.pdf/.txt/.md or paste text, see findings in the page
  GET  /sample        the bundled sample policy note (.docx)
  POST /render        JSON report -> static HTML report (?format=html|md), no re-check
  GET  /health
  GET  /sources       configured evidence sources (no secrets)
  POST /check         JSON {"type": "text"|"url", "content": "...", "format": "json"|"md"|"html", "numbers_only": false}
  POST /check/file    multipart upload (?format=json|md|html&numbers_only=false), 15 MB max
  v0.5.1 background jobs (the web app uses these; the endpoints above stay synchronous for the API and CLI):
  POST /jobs          same JSON body as /check -> 202 {"job_id"}
  POST /jobs/file     same upload as /check/file -> 202 {"job_id"}
  GET  /jobs/{id}     progress: status, stage, claims_done, claims_total, elapsed_s
  GET  /jobs/{id}/result   the JSON report once status is "done"
  POST /jobs/{id}/cancel   stop the check
  v0.5.2 Quick / Deep:
  POST /jobs/{id}/deep     Deep check of the claims a Quick check left unchecked -> 202 {"job_id"} (a new job)
  mode=quick|deep          on /jobs and /jobs/file (default quick) and on /check and /check/file (default deep, the
                           v0.5.1 behaviour, kept for API compatibility). Quick sends no request to any source: bundled
                           and synced official data, cached answers and the deterministic checks only.
  Public hosting (TRUTHLENS_PUBLIC=1): per-IP rate limits (TRUTHLENS_RATE_CHECKS per hour, TRUTHLENS_RATE_DEEP per
  hour), at most TRUTHLENS_MAX_JOBS checks running, results kept in memory only for TRUTHLENS_JOB_TTL seconds.
  Uploaded documents are read in memory and never written to disk.

Bring your own AI key (optional): send it in the `X-LLM-Key` header with `X-LLM-Provider: anthropic|openai`
(or the `llm_key`/`llm_provider` fields). It is used for that one check only, never stored or logged,
and redacted from any error. Without a key TruthLens runs key-free.
A free data.gov.in key works the same way: `X-DataGovIn-Key` header or `datagovin_key` field (one check only).
v0.5.3: the NDAP token (`X-NDAP-Token` / `ndap_token`) was removed: it was never verified (no token could be
obtained; its data format was only tested on a made-up sample). The NDAP
catalogue is still searched with no key, only to name the dataset to cite.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import __version__
from .readers import ReaderError
from .config import redact, use_keys

app = FastAPI(title="TruthLens", version=__version__,
              description="Checks the numbers in Indian policy drafts against official data it holds, and lists the claims that need a source.")

MAX_UPLOAD = 15 * 1024 * 1024
ONLINE = os.environ.get("TRUTHLENS_OFFLINE", "") == ""
_PIPE = None


def _pipeline():
    global _PIPE
    from .config import Config
    from .pipeline import Pipeline
    if _PIPE is None or _PIPE.cfg.offline == ONLINE:
        _PIPE = Pipeline(Config.load(offline=not ONLINE))
    return _PIPE


class CheckRequest(BaseModel):
    type: Literal["text", "url"] = "text"
    mode: Literal["quick", "deep", ""] = ""
    content: str = Field(..., description="Draft text, or a URL when type='url'")
    format: Literal["json", "md", "html"] = "json"
    numbers_only: bool = False
    llm_provider: Literal["anthropic", "openai", ""] = ""
    llm_key: str = Field("", repr=False, description="Optional: your own AI key, used for this check only")
    datagovin_key: str = Field("", repr=False, description="Optional: your free data.gov.in key, used for this check only")


_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def _user_keys(provider: str, key: str, datagovin_key: str = ""):
    """Map user-supplied keys to the secret names the pipeline reads. None means run key-free/server keys."""
    key = (key or "").strip()
    dg = (datagovin_key or "").strip()
    if not key and not dg:
        return None
    keys, provider = {}, (provider or "").strip().lower()
    if key:
        if not provider:
            provider = "anthropic" if key.startswith("sk-ant-") else "openai"
        if provider not in _KEY_ENV:
            raise HTTPException(status_code=422, detail="llm_provider must be anthropic or openai")
        keys[_KEY_ENV[provider]] = key
    else:
        provider = ""
    if dg:
        if len(dg) > 200 or not dg.isalnum():
            raise HTTPException(status_code=422, detail="datagovin_key should be the letters and digits data.gov.in gave you")
        keys["DATAGOVIN_API_KEY"] = dg
    return {"provider": provider, "keys": keys}


def _run_with(user, fn, mode: str = "deep"):
    """Run fn(pipeline) on a fresh pipeline for this one check (v0.5.2: nothing from one user's check, not even an
    error message, is kept in a shared object for the next one). The user's keys apply to this request only.
    Quick mode never calls an AI provider (no network at all): rule-based extraction and the heuristic judge."""
    from .config import Config
    from .pipeline import Pipeline

    def build():
        cfg = Config.load(offline=not ONLINE)
        if user and user["provider"]:
            cfg.llm_provider = user["provider"]
        pipe = Pipeline(cfg, llm=None) if mode == "quick" else Pipeline(cfg)
        pipe.mode = mode
        return pipe

    if not user:
        return fn(build())
    with use_keys(user["keys"]):
        return fn(build())


def _mode(value: str, default: str) -> str:
    v = (value or "").strip().lower()
    if v in ("", None):
        return default
    if v not in ("quick", "deep"):
        raise HTTPException(status_code=422, detail="mode must be quick or deep")
    return v


# ---------------------------------------------------------------------------------------------- v0.5.2 limits
def _env_num(name: str, default: float) -> float:
    try:
        v = float(os.environ.get(name, "") or default)
        return v if v > 0 else default
    except ValueError:
        return default


PUBLIC = os.environ.get("TRUTHLENS_PUBLIC", "").strip().lower() in ("1", "true", "yes", "on")


class RateLimiter:
    """Sliding one-hour window per client IP. Off unless TRUTHLENS_PUBLIC=1 (or limits are set explicitly)."""

    def __init__(self):
        import threading
        self.lock = threading.Lock()
        self.hits: dict = {}

    def limits(self) -> dict:
        explicit = any(os.environ.get(k) for k in ("TRUTHLENS_RATE_CHECKS", "TRUTHLENS_RATE_DEEP"))
        if not (PUBLIC or explicit):
            return {}
        return {"check": int(_env_num("TRUTHLENS_RATE_CHECKS", 20)), "deep": int(_env_num("TRUTHLENS_RATE_DEEP", 5))}

    def allow(self, ip: str, kind: str) -> None:
        lim = self.limits().get(kind)
        if not lim:
            return
        import time as _t
        now = _t.time()
        with self.lock:
            key = (ip, kind)
            q = [t for t in self.hits.get(key, []) if now - t < 3600]
            if len(q) >= lim:
                wait = int(3600 - (now - q[0])) + 1
                self.hits[key] = q
                what = "Deep checks" if kind == "deep" else "checks"
                raise HTTPException(status_code=429, detail=f"Limit reached: {lim} {what} per hour from one address. "
                                                            f"Try again in about {max(1, wait // 60)} min.",
                                    headers={"Retry-After": str(wait)})
            q.append(now)
            self.hits[key] = q
            if len(self.hits) > 50000:          # bound memory: forget idle addresses
                for k in [k for k, v in self.hits.items() if not v or now - v[-1] > 3600]:
                    self.hits.pop(k, None)


LIMITER = RateLimiter()


def _client_ip(request) -> str:
    """The caller's address. Behind a reverse proxy (Hugging Face Spaces, Render, Fly) set TRUTHLENS_TRUST_PROXY=1 to
    use the first X-Forwarded-For hop; otherwise the socket peer is used (a client cannot spoof it)."""
    if request is None:
        return "local"
    if os.environ.get("TRUTHLENS_TRUST_PROXY", "").strip() in ("1", "true", "yes"):
        fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if fwd:
            return fwd[:64]
    return (request.client.host if request.client else "unknown")[:64]


def _render(report: dict, fmt: str, v1: bool = False):
    if v1:
        from .report import to_html, to_markdown
    else:
        from .report_v2 import to_html, to_markdown
    if fmt == "html":
        return HTMLResponse(to_html(report))
    if fmt == "md":
        return PlainTextResponse(to_markdown(report), media_type="text/markdown")
    if fmt == "cite" and not v1:
        from .report_v2 import to_cite_csv
        return PlainTextResponse(to_cite_csv(report), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": 'attachment; filename="claims-to-cite.csv"'})
    return report


@app.get("/sw.js")
def service_worker():
    """No service worker: answer 204 so browsers that probe /sw.js stop logging 404s."""
    from fastapi import Response
    return Response(status_code=204)


@app.get("/health")
def health():
    """Liveness plus data freshness (v0.5.2): when the official data was last synced, the bundled data dates, the
    shared live-answer cache, and the check limits in force. No user data."""
    out = {"status": "healthy", "version": __version__, "online": ONLINE, "public": PUBLIC,
           "corrections": (not PUBLIC) or os.environ.get("TRUTHLENS_ALLOW_CORRECTIONS", "").strip() in ("1", "true", "yes"),
           "default_mode": {"web_app_and_jobs": "quick", "check_endpoints": "deep"}}
    try:
        from .config import Config
        from .sync import RUNNING, freshness
        out["data"] = {"synced": freshness(Config.load(offline=not ONLINE)), "sync_running": bool(RUNNING["running"])}
        from .sources.curated import CuratedStore
        from .retrievers.state_data import load_state_data
        out["data"]["bundled"] = {"official_snapshot_accessed": CuratedStore().meta.get("accessed"),
                                  "state_data_accessed": load_state_data()["meta"].get("accessed")}
        from . import livecache
        lc = livecache.shared()
        out["data"]["live_cache"] = lc.stats() if lc is not None else {"enabled": False}
    except Exception as e:          # health must answer even if a data file is damaged
        out["data_error"] = type(e).__name__
    with _JOBS_LOCK:
        running = sum(1 for j in JOBS.values() if j.status == "running")
    out["limits"] = {"max_running_checks": _max_jobs(), "running_now": running, "job_ttl_s": _job_ttl(),
                     "rate_per_hour": LIMITER.limits() or "off (local use)", "upload_mb": MAX_UPLOAD // 2 ** 20}
    return out


@app.get("/sources")
def sources():
    return {"sources": _pipeline().sources_status()}


from .webui import PAGE as UPLOAD_PAGE  # single-page app: start, checking, results

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "sample_policy_note.docx"


@app.get("/sample")
def sample():
    """The bundled sample policy note (.docx), used by the "Try the sample" button."""
    if not SAMPLE.is_file():
        raise HTTPException(status_code=404, detail="sample not bundled with this install")
    return FileResponse(SAMPLE, filename=SAMPLE.name,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


SAMPLE_REPORT_DIR = Path(__file__).resolve().parents[1] / "samples"
SAMPLE_REPORT_NAMES = ("sample_report_v05.html", "sample_report_v041.html", "sample_report_v4.html")


@app.get("/sample-report", response_class=HTMLResponse)
def sample_report():
    """A finished sample report (static HTML, no internet needed), for the "Open sample report" button.
    v0.5 sample first; older bundled samples are the fallback."""
    for name in SAMPLE_REPORT_NAMES:
        f = SAMPLE_REPORT_DIR / name
        if f.is_file():
            return HTMLResponse(f.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="sample report not bundled with this install")


@app.post("/render")
def render(report: dict, format: Literal["html", "md", "cite"] = Query("html")):
    """Render a JSON report returned by /check as the static HTML (or Markdown) report, without re-running the check."""
    if not isinstance(report.get("summary"), dict) or not isinstance(report.get("claims"), list):
        raise HTTPException(status_code=422, detail="not a TruthLens report")
    try:
        return _render(report, format)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="not a TruthLens report")


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(UPLOAD_PAGE)


@app.post("/check")
def check(req: CheckRequest, request: Request, mode: str = Query(""), x_llm_key: str = Header("", include_in_schema=False),
          x_llm_provider: str = Header("", include_in_schema=False),
          x_datagovin_key: str = Header("", include_in_schema=False)):
    user = _user_keys(req.llm_provider or x_llm_provider, req.llm_key or x_llm_key, req.datagovin_key or x_datagovin_key)
    md = _mode(req.mode or mode, "deep")
    if not req.content.strip():
        raise HTTPException(status_code=422, detail="content is empty")
    LIMITER.allow(_client_ip(request), "check")
    if md == "deep":
        LIMITER.allow(_client_ip(request), "deep")
    try:
        if req.numbers_only:
            from .core import check_text as v1_text, check_url as v1_url
            report = v1_url(req.content.strip(), online=ONLINE) if req.type == "url" else v1_text(req.content, online=ONLINE)
            return _render(report, req.format, v1=True)
        from .readers import read_text, read_url
        if req.type == "url":
            blocks, meta = read_url(req.content.strip())
            report = _run_with(user, lambda pipe: pipe.run(blocks, req.content.strip(), meta, mode=md), md)
        else:
            report = _run_with(user, lambda pipe: pipe.run(read_text(req.content), "text input", mode=md), md)
    except ReaderError as e:
        raise HTTPException(status_code=400, detail=redact(str(e)))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"could not read input: {type(e).__name__}")
    return _render(report, req.format)


async def _read_upload(file: UploadFile) -> tuple:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".docx", ".pdf", ".txt", ".md"):
        raise HTTPException(status_code=415, detail="upload a .docx, .pdf, .txt or .md file")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="file too large (15 MB max)")
    return data, suffix


@app.post("/check/file")
async def check_file(request: Request, file: UploadFile = File(...), format: Literal["json", "md", "html"] = Query("json"),
                     numbers_only: bool = Query(False), mode: str = Query(""), llm_provider: str = Form(""),
                     llm_key: str = Form(""), datagovin_key: str = Form(""),
                     x_llm_key: str = Header("", include_in_schema=False),
                     x_llm_provider: str = Header("", include_in_schema=False),
                     x_datagovin_key: str = Header("", include_in_schema=False)):
    user = _user_keys(llm_provider or x_llm_provider, llm_key or x_llm_key, datagovin_key or x_datagovin_key)
    md = _mode(mode, "deep")
    data, suffix = await _read_upload(file)
    LIMITER.allow(_client_ip(request), "check")
    if md == "deep" and not numbers_only:
        LIMITER.allow(_client_ip(request), "deep")
    name = file.filename or f"upload{suffix}"
    try:
        if numbers_only:
            from .core import check_bytes
            report = check_bytes(data, suffix, name, online=ONLINE)
        else:
            from .readers import read_bytes
            blocks = read_bytes(data, suffix)
            report = _run_with(user, lambda pipe: pipe.run(blocks, name, mode=md), md)
    except ReaderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    report["input"] = file.filename
    return _render(report, format, v1=numbers_only)


# ---------------------------------------------------------------------------------------------- v0.5: freshness, sync
@app.get("/sync/status")
def sync_status():
    """When the local data was last updated, whether it is stale (> 7 days), and whether an update is running."""
    from .config import Config
    from .sync import RUNNING, freshness
    f = freshness(Config.load(offline=not ONLINE))
    return {**f, "running": RUNNING["running"], "last_result": RUNNING["result"], "offline": not ONLINE}


@app.post("/sync", status_code=202)
def sync_now():
    """'Update now': run `truthlens sync` in the background (one at a time)."""
    from .config import Config
    from .sync import run_in_background
    if not ONLINE:
        raise HTTPException(status_code=409, detail="TruthLens is running offline; nothing to update")
    if not run_in_background(Config.load(offline=False)):
        raise HTTPException(status_code=409, detail="an update is already running")
    return {"status": "started"}


# ---------------------------------------------------------------------------------------------- v0.5: corrections
class CorrectionRequest(BaseModel):
    claim_text: str = Field(..., max_length=4000)
    sentence: str = Field("", max_length=4000)
    claim_type: str = Field("numeric", max_length=20)
    reported_verdict: str = Field("", max_length=30)
    correct_verdict: str = Field(..., max_length=30)
    note: str = Field("", max_length=2000)
    source_url: str = Field("", max_length=1000)
    document: str = Field("", max_length=300)


@app.post("/corrections", status_code=201)
def corrections_add(req: CorrectionRequest):
    """'This verdict is wrong': stored locally as pending (data/corrections/pending.jsonl) for `truthlens corrections
    review`. Nothing is fetched, learned or changed until a person accepts it."""
    if PUBLIC and os.environ.get("TRUTHLENS_ALLOW_CORRECTIONS", "").strip() not in ("1", "true", "yes"):
        raise HTTPException(status_code=403, detail="corrections are not stored on this public server")
    from .corrections import add_pending
    try:
        rec = add_pending({**req.model_dump(), "tool_version": __version__} if hasattr(req, "model_dump")
                          else {**req.dict(), "tool_version": __version__})
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": rec["id"], "status": "pending"}


# ---------------------------------------------------------------------------------------------- v0.5.1: background jobs
import threading as _threading  # noqa: E402
import time as _time  # noqa: E402
import uuid as _uuid  # noqa: E402

JOBS: dict = {}
_JOBS_LOCK = _threading.Lock()
MAX_JOBS = 32               # most recent kept; finished ones are dropped first
JOB_TTL = 3600              # seconds a finished job's result is kept (TRUTHLENS_JOB_TTL)


def _max_jobs() -> int:
    """Checks allowed to run at the same time (TRUTHLENS_MAX_JOBS, default 4)."""
    return int(_env_num("TRUTHLENS_MAX_JOBS", 4))


def _job_ttl() -> int:
    return int(_env_num("TRUTHLENS_JOB_TTL", JOB_TTL))


class Job:
    def __init__(self, label: str, mode: str = "quick"):
        self.id = _uuid.uuid4().hex
        self.label = label
        self.label_name = label
        self.mode = mode
        self.status = "running"        # running | done | error | cancelled
        self.stage = "reading the document"
        self.done = 0
        self.total = 0
        self.started = _time.monotonic()
        self.finished: float = 0.0
        self.result = None
        self.error = ""
        self.error_code = 0
        self.cancel = _threading.Event()
        # v0.5.2: kept in memory only (never on disk) until the job expires, so "Deep check" can re-run just the
        # claims Quick mode left unchecked without the user uploading the document again
        self.blocks = None
        self.meta = None
        self.state: dict = {}
        self.owner = ""                # client address, so only the same caller can start a Deep check from it

    def progress(self, stage: str, done: int, total: int) -> None:
        self.stage, self.done, self.total = stage, done, total

    def view(self) -> dict:
        end = self.finished or _time.monotonic()
        return {"job_id": self.id, "status": self.status, "stage": self.stage, "claims_done": self.done,
                "claims_total": self.total, "elapsed_s": round(end - self.started, 1), "input": self.label,
                "mode": self.mode, **({"error": self.error} if self.error else {})}

    def drop_data(self) -> None:
        self.blocks = self.meta = self.result = None
        self.state = {}


def _gc_jobs() -> None:
    now = _time.monotonic()
    ttl = _job_ttl()
    with _JOBS_LOCK:
        for jid in [j for j, job in JOBS.items() if job.finished and now - job.finished > ttl]:
            JOBS.pop(jid).drop_data()
        while len(JOBS) >= MAX_JOBS:
            old = sorted(JOBS.values(), key=lambda j: (j.status == "running", j.started))[0]
            if old.status == "running":
                break
            JOBS.pop(old.id).drop_data()


def _start_job(label: str, work, mode: str = "quick", request=None, setup=None) -> dict:
    """Run work(job) in a background thread; work returns the report dict."""
    _gc_jobs()
    job = Job(label, mode)
    job.owner = _client_ip(request) if request is not None else ""
    if setup is not None:
        setup(job)
    with _JOBS_LOCK:
        if sum(1 for j in JOBS.values() if j.status == "running") >= _max_jobs():
            raise HTTPException(status_code=429, detail="Too many checks running right now; please try again in a minute.",
                                headers={"Retry-After": "30"})
        JOBS[job.id] = job
    import contextvars

    def run():
        from .pipeline import CheckCancelled
        try:
            rep = work(job)
            if job.cancel.is_set():
                job.status = "cancelled"
            else:
                job.result, job.status = rep, "done"
                job.stage = "done"
        except CheckCancelled:
            job.status = "cancelled"
        except HTTPException as e:
            job.status, job.error, job.error_code = "error", redact(str(e.detail)), e.status_code
        except ReaderError as e:
            job.status, job.error, job.error_code = "error", redact(str(e)), 400
        except Exception as e:
            job.status, job.error, job.error_code = "error", f"could not check the input: {type(e).__name__}", 502
        finally:
            job.finished = _time.monotonic()
            if job.status != "done":
                job.drop_data()

    _threading.Thread(target=contextvars.copy_context().run, args=(run,), daemon=True, name=f"truthlens-job-{job.id[:8]}").start()
    return {"job_id": job.id, "status": job.status, "mode": mode}


def _job(job_id: str) -> Job:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="no such check (it may have expired)")
    return job


def _pipeline_work(user, mode: str):
    """work(job) that runs the pipeline on job.blocks and keeps the state a later Deep check needs."""
    def work(job: Job):
        state: dict = {}
        rep = _run_with(user, lambda pipe: pipe.run(job.blocks, job.label_name, job.meta, progress=job.progress,
                                                    cancel=job.cancel, mode=mode, state_out=state), mode)
        job.state = state
        return rep
    return work


@app.post("/jobs", status_code=202)
def job_check(req: CheckRequest, request: Request, mode: str = Query(""),
              x_llm_key: str = Header("", include_in_schema=False),
              x_llm_provider: str = Header("", include_in_schema=False),
              x_datagovin_key: str = Header("", include_in_schema=False)):
    """Start a text/URL check in the background (default Quick). Poll GET /jobs/{id}; fetch GET /jobs/{id}/result."""
    user = _user_keys(req.llm_provider or x_llm_provider, req.llm_key or x_llm_key, req.datagovin_key or x_datagovin_key)
    md = _mode(req.mode or mode, "quick")
    if not req.content.strip():
        raise HTTPException(status_code=422, detail="content is empty")
    LIMITER.allow(_client_ip(request), "check")
    if md == "deep":
        LIMITER.allow(_client_ip(request), "deep")
    content, kind, numbers_only = req.content, req.type, req.numbers_only

    if numbers_only:
        def work(job: Job):
            from .core import check_text as v1_text, check_url as v1_url
            rep = v1_url(content.strip(), online=ONLINE) if kind == "url" else v1_text(content, online=ONLINE)
            rep["_v1"] = True
            return rep
    else:
        inner = _pipeline_work(user, md)

        def work(job: Job):
            from .readers import read_text, read_url
            if kind == "url":
                job.stage = "reading the page"
                job.blocks, job.meta = read_url(content.strip())
                job.label_name = content.strip()
            else:
                job.blocks, job.meta, job.label_name = read_text(content), None, "text input"
            return inner(job)

    return _start_job("Pasted text" if kind == "text" else content.strip()[:200], work, md, request)


@app.post("/jobs/file", status_code=202)
async def job_file(request: Request, file: UploadFile = File(...), numbers_only: bool = Query(False),
                   mode: str = Query(""), llm_provider: str = Form(""),
                   llm_key: str = Form(""), datagovin_key: str = Form(""),
                   x_llm_key: str = Header("", include_in_schema=False),
                   x_llm_provider: str = Header("", include_in_schema=False),
                   x_datagovin_key: str = Header("", include_in_schema=False)):
    """Start a file check in the background (default Quick; same limits as /check/file). Read in memory only."""
    user = _user_keys(llm_provider or x_llm_provider, llm_key or x_llm_key, datagovin_key or x_datagovin_key)
    md = _mode(mode, "quick")
    data, suffix = await _read_upload(file)
    LIMITER.allow(_client_ip(request), "check")
    if md == "deep" and not numbers_only:
        LIMITER.allow(_client_ip(request), "deep")
    fname = file.filename or f"upload{suffix}"

    if numbers_only:
        def work(job: Job):
            from .core import check_bytes
            rep = check_bytes(data, suffix, fname, online=ONLINE)
            rep["_v1"] = True
            rep["input"] = fname
            return rep
    else:
        inner = _pipeline_work(user, md)

        def work(job: Job):
            from .readers import read_bytes
            job.blocks, job.meta, job.label_name = read_bytes(data, suffix), None, fname
            rep = inner(job)
            rep["input"] = fname
            return rep

    return _start_job(fname, work, md, request)


@app.post("/jobs/{job_id}/deep", status_code=202)
def job_deep(job_id: str, request: Request, llm_provider: str = Form(""), llm_key: str = Form(""),
             datagovin_key: str = Form(""),
             x_llm_key: str = Header("", include_in_schema=False),
             x_llm_provider: str = Header("", include_in_schema=False),
             x_datagovin_key: str = Header("", include_in_schema=False)):
    """v0.5.2 "Deep check": ask the live sources for the claims a finished Quick check left unchecked. Every other
    claim keeps its result. Starts a new job (poll it like any other); the Quick job is left as it was."""
    src = _job(job_id)
    if src.status != "done" or not src.state or src.blocks is None:
        raise HTTPException(status_code=409, detail="that check is not finished (or it has expired); run it again")
    if PUBLIC and src.owner and src.owner != _client_ip(request):
        raise HTTPException(status_code=404, detail="no such check (it may have expired)")
    user = _user_keys(llm_provider or x_llm_provider, llm_key or x_llm_key, datagovin_key or x_datagovin_key)
    LIMITER.allow(_client_ip(request), "deep")
    import copy as _copy
    prior = _copy.deepcopy(src.state)       # the Quick job's own result stays untouched
    pending = sum(1 for r in prior["results"].values() if r.unchecked_reason == "quick")

    def setup(job: Job):
        job.blocks, job.meta, job.label_name = src.blocks, src.meta, getattr(src, "label_name", src.label)
        job.total = pending

    def work(job: Job):
        state: dict = {}
        rep = _run_with(user, lambda pipe: pipe.run(job.blocks, job.label_name, job.meta, progress=job.progress,
                                                    cancel=job.cancel, mode="deep", prior=prior, state_out=state), "deep")
        job.state = state
        if (src.result or {}).get("input"):
            rep["input"] = src.result["input"]
        rep.setdefault("meta", {})["deep_from_job"] = src.id
        return rep

    return _start_job(src.label, work, "deep", request, setup=setup)


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    return _job(job_id).view()


@app.get("/jobs/{job_id}/result")
def job_result(job_id: str, format: Literal["json", "md", "html", "cite"] = Query("json")):
    job = _job(job_id)
    if job.status == "running":
        raise HTTPException(status_code=409, detail="the check is still running")
    if job.status == "cancelled":
        raise HTTPException(status_code=410, detail="the check was cancelled")
    if job.status == "error":
        raise HTTPException(status_code=job.error_code or 502, detail=job.error)
    rep = dict(job.result)
    v1 = bool(rep.pop("_v1", False))
    return _render(rep, format, v1=v1)


@app.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: str):
    job = _job(job_id)
    job.cancel.set()
    if job.status == "running":
        job.stage = "cancelling"
    return job.view()


# ---------------------------------------------------------------------------------------------- v0.5.2 startup
@app.on_event("startup")
def _startup_sync():
    """Hosted use: refresh the official data in the background at startup when it is stale or missing
    (TRUTHLENS_SYNC_ON_START=1, set in the Dockerfile). Quick mode works on the bundled data meanwhile."""
    if os.environ.get("TRUTHLENS_SYNC_ON_START", "").strip().lower() not in ("1", "true", "yes") or not ONLINE:
        return
    try:
        from .config import Config
        from .sync import freshness, run_in_background
        cfg = Config.load(offline=False)
        if freshness(cfg).get("stale"):
            run_in_background(cfg)
    except Exception:
        pass
