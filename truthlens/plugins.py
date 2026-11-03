"""v0.5 plug-in sources: your own REST APIs and MCP servers as official-data matchers.

One YAML file per source in a sources directory (`sources.d/`; see docs/PLUGINS.md for the full schema):

    name: worldbank-wdi            # lowercase letters, digits, '-' ; shown as plugin:worldbank-wdi
    kind: rest                     # rest | mcp
    trust: official                # official | scholarly | other   ('other' never decides more than PARTLY, low)
    badge: World Bank              # badge text in reports
    publisher: World Bank
    keywords: [unemployment, inflation]    # routing: the planner sends a numeric claim here when it names one
    timeout: 15                    # seconds, per request
    auth: {env: MY_KEY, in: header, name: X-API-Key}     # optional; the key is read from the environment only
    request: {url: "https://.../{place}/indicator/{indicator}?date={period}"}
    indicators: [{code: SL.UEM.TOTL.ZS, label: unemployment rate, keywords: [unemployment], unit: "%"}]
    places: {india: IND}
    response: {records: "$[1][*]", value: "$.value", period: "$.date", place: "$.country.value"}

Every plug-in answer goes through the same machinery as the built-in ministry sources (tables.match_rows: period,
place, sub-group and relevance gates; polarity; the change calculator; the deterministic quote), so a plug-in cannot
say more than an official table could. All HTTP goes through net.safe_get/safe_post (SSRF guard); a remote MCP URL
is checked the same way. `allow_local: true` in the user's own config is the only way to reach a local address.
Keys never enter URLs that are stored (cache keys, source URLs in reports) and are redacted from error messages.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import shutil
from importlib import resources
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode, urlparse, urlunparse, parse_qsl

import yaml

from . import jsonpath
from .config import Config, redact
from .net import DiskCache, FetchError, check_public_url, get_json, make_session, safe_post
from .retrievers.base import terms
from .retrievers.ministry import GroupedSource
from .retrievers.official_api import kw_hits
from .retrievers.tables import claim_geo, claim_periods

NAME_RX = re.compile(r"^[a-z0-9][a-z0-9\-]{1,40}$")
TRUST = ("official", "scholarly", "other")
KINDS = ("rest", "mcp")
SECRET_FIELDS = ("value", "key", "token", "password", "secret", "api_key")

# name -> routing keywords of the plug-ins a Pipeline loaded (read by the planner)
ROUTES: dict = {}
TRUST_OF: dict = {}


def plugin_id(name: str) -> str:
    return f"plugin:{name}"


# ------------------------------------------------------------------------------------------- loading and validation
def source_dirs(cfg: Optional[Config] = None) -> list[Path]:
    env = os.environ.get("TRUTHLENS_SOURCES_DIR")
    if env:
        return [Path(p).expanduser() for p in env.split(os.pathsep) if p]
    tl = ((cfg.toml if cfg else {}) or {}).get("truthlens", {}) if cfg else {}
    if tl.get("sources_dir"):
        return [Path(tl["sources_dir"]).expanduser()]
    return [Path("sources.d"), Path(os.path.expanduser("~/.config/truthlens/sources.d"))]


def default_add_dir(cfg: Optional[Config] = None) -> Path:
    dirs = source_dirs(cfg)
    for d in dirs:
        if d.is_dir():
            return d
    return dirs[0]


def validate(spec: Any) -> list[str]:
    """Problems with a plug-in config (empty list = valid)."""
    errs = []
    if not isinstance(spec, dict):
        return ["the file must be a YAML mapping"]
    name = str(spec.get("name") or "")
    if not NAME_RX.match(name):
        errs.append("name: lowercase letters, digits and '-' only (2-41 characters)")
    kind = spec.get("kind", "rest")
    if kind not in KINDS:
        errs.append(f"kind: one of {', '.join(KINDS)}")
    if spec.get("trust", "other") not in TRUST:
        errs.append(f"trust: one of {', '.join(TRUST)}")
    auth = spec.get("auth") or {}
    if auth:
        if not isinstance(auth, dict) or not auth.get("env"):
            errs.append("auth: give the *name* of an environment variable as auth.env")
        elif any(k in auth for k in SECRET_FIELDS):
            errs.append("auth: never put the key itself in the file; set auth.env to an environment variable name")
        elif auth.get("in", "header") not in (("header", "env") if kind == "mcp" else ("header", "query")):
            errs.append("auth.in: header or query (REST); header or env (MCP)")
    for key, val in (("enabled", spec.get("enabled", True)), ("allow_local", spec.get("allow_local", False))):
        if not isinstance(val, bool):
            errs.append(f"{key}: true or false")
    try:
        t = float(spec.get("timeout", 15))
        if not 0 < t <= 120:
            errs.append("timeout: seconds, more than 0 and at most 120")
    except (TypeError, ValueError):
        errs.append("timeout: a number of seconds")
    try:
        float(spec.get("cache_hours", 24))
    except (TypeError, ValueError):
        errs.append("cache_hours: a number")
    if spec.get("source_url"):
        e = _template_problem(str(spec["source_url"]))
        if e:
            errs.append(f"source_url: {e}")
    if kind == "rest":
        url = str((spec.get("request") or {}).get("url") or "")
        if not url.startswith(("https://", "http://")):
            errs.append("request.url: an http(s) URL template is required")
        else:
            e = _template_problem(url)
            if e:
                errs.append(f"request.url: {e}")
        if (spec.get("request") or {}).get("method", "GET").upper() not in ("GET", "POST"):
            errs.append("request.method: GET or POST")
    else:
        srv = spec.get("server") or {}
        if not (srv.get("command") or srv.get("url")):
            errs.append("server: give server.command (stdio) or server.url (streamable HTTP)")
        if srv.get("url") and not str(srv["url"]).startswith(("https://", "http://")):
            errs.append("server.url: http(s) URL")
        elif srv.get("url") and "{" in str(srv["url"]):
            errs.append("server.url: no placeholders allowed in an MCP server URL")
        if not spec.get("tool"):
            errs.append("tool: the MCP tool name to call")
    resp = spec.get("response") or {}
    if not resp.get("value"):
        errs.append("response.value: JSONPath of the value in each record (e.g. $.value)")
    for k in ("records", "value", "period", "place", "unit", "title", "url", "as_of", "as_of_root", "indicator"):
        if resp.get(k):
            try:
                jsonpath.parse(_fill(str(resp[k]), {"indicator": "X", "place": "X", "period": "X", "query": "X"}, False))
            except ValueError as e:
                errs.append(f"response.{k}: {e}")
    if not (spec.get("keywords") or any((i or {}).get("keywords") for i in spec.get("indicators") or [])):
        errs.append("keywords: routing keywords are required (the planner only sends claims that name one)")
    for i, ind in enumerate(spec.get("indicators") or []):
        if not isinstance(ind, dict) or not ind.get("code") or not ind.get("label"):
            errs.append(f"indicators[{i}]: code and label are required")
    return errs


def _authority(url: str) -> str:
    """'https://host:port' part of a URL (or URL template)."""
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]*://[^/?#]*)", url)
    return m.group(1) if m else url


def _template_problem(url: str) -> str:
    if not url.startswith(("https://", "http://")):
        return "must start with https:// or http://"
    if "{" in _authority(url) or "}" in _authority(url):
        return "a placeholder ({query}, {indicator}, {period}, {place}) may not be in the scheme, host, port or user part"
    return ""


def load_file(path: Path) -> dict:
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    errs = validate(spec)
    if errs:
        raise ValueError(f"{Path(path).name}: " + "; ".join(errs))
    spec = dict(spec)
    spec["_file"] = str(path)
    return spec


def load_all(cfg: Optional[Config] = None) -> tuple[list[dict], list[str]]:
    """(valid enabled specs, problems). A broken file is reported, never loaded."""
    specs, problems, seen = [], [], set()
    for d in source_dirs(cfg):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
            try:
                s = load_file(p)
            except Exception as e:
                problems.append(redact(f"{p}: {e}")[:300])
                continue
            if s.get("enabled", True) is False or s["name"] in seen:
                continue
            seen.add(s["name"])
            specs.append(s)
    return specs, problems


def examples() -> dict:
    """Bundled example configs: {name: text}."""
    out = {}
    root = resources.files("truthlens.data").joinpath("plugin_examples")
    for f in sorted(root.iterdir(), key=lambda x: x.name):
        if f.name.endswith((".yaml", ".yml")):
            out[f.name.rsplit(".", 1)[0]] = f.read_text(encoding="utf-8")
    return out


def add(src: str, cfg: Optional[Config] = None, dest: Optional[Path] = None) -> Path:
    """Validate a config (a file path or a bundled example name) and copy it into the sources directory."""
    ex = examples()
    if Path(src).is_file():
        text = Path(src).read_text(encoding="utf-8")
    elif src in ex:
        text = ex[src]
    else:
        raise ValueError(f"not a file or a bundled example: {src} (examples: {', '.join(ex)})")
    spec = yaml.safe_load(text)
    errs = validate(spec)
    if errs:
        raise ValueError("; ".join(errs))
    d = dest or default_add_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{spec['name']}.yaml"
    out.write_text(text, encoding="utf-8")
    return out


# ------------------------------------------------------------------------------------------- request building
def _fmt_period(fmt: str, periods: set) -> Optional[str]:
    ys = sorted({p[:4] for p in periods if re.match(r"(19|20)\d{2}", p)})
    if not ys:
        return None
    if fmt == "fy":
        fy = sorted(p for p in periods if re.match(r"(19|20)\d{2}-\d{2}$", p))
        return fy[0] if fy else f"{ys[0]}-{str(int(ys[0]) + 1)[-2:]}"
    if fmt == "range":
        return f"{ys[0]}:{ys[-1]}"
    return ys[0]


def template_vars(spec: dict, claim_text: str, ind: Optional[dict]) -> Optional[dict]:
    """{query, indicator, period, place} for a claim, or None when the claim's place has no mapping (fail closed)."""
    geo = claim_geo(claim_text)
    places = {str(k).lower(): v for k, v in (spec.get("places") or {"india": "IND"}).items()}
    place = places.get(geo)
    if place is None:
        return None
    per = spec.get("period") or {}
    p = _fmt_period(per.get("format", "year"), claim_periods(claim_text))
    if p is None:
        p = str(per.get("default", ""))
    words = " ".join(sorted(terms(re.sub(r"[\d.,%₹]+", " ", claim_text)))[:8])
    return {"query": claim_text[:300], "indicator": (ind or {}).get("code") or words, "period": p, "place": place}


def _fill(template: str, vars_: dict, encode: bool = True) -> str:
    def rep(m):
        v = str(vars_.get(m.group(1), ""))
        return quote(v, safe=":,;") if encode else v
    return re.sub(r"\{(query|indicator|period|place)\}", rep, template)


def _fill_obj(obj, vars_: dict):
    if isinstance(obj, str):
        return _fill(obj, vars_, encode=False)
    if isinstance(obj, dict):
        return {k: _fill_obj(v, vars_) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fill_obj(v, vars_) for v in obj]
    return obj


def _strip_auth(url: str, auth: dict) -> str:
    if not auth or auth.get("in") != "query":
        return url
    u = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k != auth.get("name")]
    return urlunparse(u._replace(query=urlencode(q)))


def _key(spec: dict) -> Optional[str]:
    from .config import _env
    env = (spec.get("auth") or {}).get("env")
    return _env(env) if env else None


def _redact_key(spec: dict, text: str) -> str:
    k = _key(spec)
    text = redact(text or "")
    return text.replace(k, "[redacted]") if k and len(k) >= 4 else text


# ------------------------------------------------------------------------------------------- response mapping
def to_rows(spec: dict, doc: Any, label: str, vars_: Optional[dict] = None) -> tuple[list[dict], dict]:
    """Records -> table rows {indicator, value, year, state} plus source fields (title, url, as_of, unit).
    response.records may use {indicator} and {place} (e.g. $.values.{indicator}.{place})."""
    resp = spec.get("response") or {}
    if resp.get("records"):
        recs = jsonpath.find(doc, _fill(resp["records"], vars_ or {}, encode=False))
        if resp.get("records_mode") == "items":       # {"2023": 7.0, ...} -> [{"key": "2023", "value": 7.0}]
            flat = []
            for r in recs:
                if isinstance(r, dict):
                    flat += [{"key": k, "value": v} for k, v in r.items()]
            recs = flat
    else:
        recs = doc if isinstance(doc, list) else [doc]
    rows, meta = [], {}
    # period.max_offset: drop rows for years after (this year + offset), e.g. -1 drops projections for this year on
    max_off = (spec.get("period") or {}).get("max_offset")
    max_year = dt.date.today().year + int(max_off) if isinstance(max_off, int) and not isinstance(max_off, bool) else None
    for r in recs[:5000]:
        v = jsonpath.first(r, resp["value"])
        if isinstance(v, (dict, list, bool)) or v is None:
            continue
        try:
            v = float(str(v).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v):
            continue                      # NaN / Infinity never become an "official value"
        scale = resp.get("scale")
        if scale:
            v = v / float(scale)
        row = {"indicator": label, "value": v}
        per = jsonpath.first(r, resp.get("period") or "")
        if per not in (None, ""):
            row["year"] = str(per)
            ym = re.match(r"((?:19|20)\d{2})", row["year"])
            if max_year is not None and ym and int(ym.group(1)) > max_year:
                continue
        place = jsonpath.first(r, resp.get("place") or "")
        if place not in (None, ""):
            row["state"] = str(place)
        elif spec.get("place_name"):
            row["state"] = spec["place_name"]
        rows.append(row)
        for k in ("title", "url", "unit", "as_of"):
            if k not in meta and resp.get(k):
                x = jsonpath.first(r, resp[k])
                if isinstance(x, (str, int, float)) and str(x).strip():
                    x = str(x)[:500]
                    if k == "url" and not x.lower().startswith(("https://", "http://")):
                        continue          # only http(s) links from a source's answer
                    meta[k] = x
    if resp.get("as_of_root"):
        x = jsonpath.first(doc, resp["as_of_root"])
        if x not in (None, ""):
            meta["as_of"] = str(x)
    return rows, meta


def _unit_ok(unit: str, claim_text: str, raw: str) -> bool:
    """A '%' indicator only judges figures written as per cent; any other unit never judges a per cent figure."""
    pct = bool(re.search(r"%|per ?cent|percentage", raw or "", re.I))
    if not unit:
        return True
    return pct if unit.strip() in ("%", "percent", "per cent") else not pct


# ------------------------------------------------------------------------------------------- MCP client
def call_mcp(spec: dict, arguments: dict, timeout: float) -> Any:
    """Call one MCP tool (stdio or streamable HTTP) and return its result as JSON (parsed text content, else the
    structured content). Runs its own event loop in a worker thread; raises FetchError on any failure."""
    import concurrent.futures as cf
    srv = spec.get("server") or {}
    url = srv.get("url")
    if url:
        check_public_url(url, bool(spec.get("allow_local", False)))
    with cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_run_mcp, spec, arguments, timeout)
        try:
            return fut.result(timeout=timeout + 5)
        except cf.TimeoutError:
            raise FetchError(f"MCP call timed out after {timeout:.0f}s") from None


def _run_mcp(spec: dict, arguments: dict, timeout: float):
    import asyncio
    try:
        return asyncio.run(asyncio.wait_for(_mcp_async(spec, arguments, timeout), timeout))
    except FetchError:
        raise
    except asyncio.TimeoutError:
        raise FetchError(f"MCP call timed out after {timeout:.0f}s") from None
    except BaseException as e:      # anyio task groups wrap errors in ExceptionGroup
        inner = e
        while getattr(inner, "exceptions", None):
            inner = inner.exceptions[0]
        raise FetchError(f"MCP: {type(inner).__name__}: {str(inner)[:160]}") from None


async def _mcp_async(spec: dict, arguments: dict, timeout: float):
    try:
        from mcp import ClientSession
    except ImportError:
        raise FetchError("MCP plug-ins need the 'mcp' package: pip install 'truthlens[mcp]'") from None
    srv = spec.get("server") or {}
    headers = {}
    auth = spec.get("auth") or {}
    if auth and _key(spec):
        headers[auth.get("name") or "Authorization"] = (auth.get("prefix") or "") + _key(spec)
    if srv.get("url"):
        transport = _http_transport(srv["url"], headers, timeout, bool(spec.get("allow_local", False)))
    else:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        cmd = srv["command"]
        cmd = cmd if isinstance(cmd, list) else [cmd]
        env = None
        if auth and _key(spec) and auth.get("in", "header") == "env":
            try:      # the SDK's safe default environment (PATH etc., no secrets) plus this one key
                from mcp.client.stdio import get_default_environment
                env = dict(get_default_environment())
            except ImportError:
                env = {}
            env[auth["env"]] = _key(spec)
        transport = stdio_client(StdioServerParameters(command=str(cmd[0]), args=[str(a) for a in cmd[1:]], env=env,
                                                       cwd=srv.get("cwd")))
    async with transport as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(spec["tool"], arguments)
    if getattr(res, "is_error", None) or getattr(res, "isError", None):
        raise FetchError("the MCP tool returned an error")
    texts = [getattr(c, "text", None) for c in (getattr(res, "content", None) or [])]
    for t in texts:
        if t:
            try:
                return json.loads(t)
            except ValueError:
                continue
    sc = getattr(res, "structured_content", None) or getattr(res, "structuredContent", None)
    if isinstance(sc, dict) and set(sc) == {"result"} and isinstance(sc["result"], str):
        try:
            return json.loads(sc["result"])
        except ValueError:
            pass
    if sc is not None:
        return sc
    raise FetchError("the MCP tool returned no JSON")


def _http_transport(url: str, headers: dict, timeout: float, local: bool = False):
    try:      # mcp >= 2: same-origin redirects only
        from mcp.client.streamable_http import streamable_http_client
        import httpx2
        client = httpx2.AsyncClient(headers=headers, timeout=httpx2.Timeout(timeout), follow_redirects=False,
                                    trust_env=not local)
        return streamable_http_client(url, http_client=client)
    except ImportError:
        pass
    from mcp.client.streamable_http import streamablehttp_client     # mcp 1.x
    import httpx

    def factory(headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(headers=headers, timeout=timeout, auth=auth, follow_redirects=False, trust_env=not local)
    return streamablehttp_client(url, headers=headers, timeout=timeout, httpx_client_factory=factory)


# ------------------------------------------------------------------------------------------- the matcher
class PluginSource(GroupedSource):
    """A user-configured REST or MCP source, judged exactly like a built-in ministry source."""
    kind = "plugin"

    def __init__(self, cfg: Config, spec: dict, session=None):
        self.spec = spec
        self.name = plugin_id(spec["name"])
        self.badge = spec.get("badge") or spec["name"]
        self.publisher = spec.get("publisher") or self.badge
        self.portal = (urlparse((spec.get("request") or {}).get("url") or (spec.get("server") or {}).get("url") or "").hostname
                       or ("local MCP server" if spec.get("kind") == "mcp" else ""))
        self.trust = spec.get("trust", "other")
        self.allow_local = bool(spec.get("allow_local", False))
        self.timeout = float(spec.get("timeout", min(cfg.timeout, 15.0)))
        kws = list(spec.get("keywords") or [])
        for ind in spec.get("indicators") or []:
            kws += list(ind.get("keywords") or [])
        self.keywords = list(dict.fromkeys(str(k) for k in kws))
        self.ttl = int(spec.get("cache_hours", 24)) * 3600
        super().__init__(cfg, session if session is not None else make_session(allow_local=self.allow_local))
        self.cache = DiskCache(cfg.cache_dir, "plugin_" + spec["name"], ttl=self.ttl)

    def status(self) -> dict:
        detail = f"plug-in ({self.spec.get('kind', 'rest')}, trust {self.trust}) {self.publisher}"
        env = (self.spec.get("auth") or {}).get("env")
        if env:
            detail += f"; key from ${env}: {'present' if _key(self.spec) else 'MISSING'}"
        return {"name": self.name, "configured": not self.offline, "detail": detail}

    def unavailable(self) -> Optional[str]:
        if self.offline:
            return "skipped: offline"
        env = (self.spec.get("auth") or {}).get("env")
        if env and not _key(self.spec) and not (self.spec.get("auth") or {}).get("optional"):
            return f"skipped: needs the key in ${env}"
        return None

    def cached(self, key, fetch, ttl=None):
        hit = self.cache.get(key)
        if hit is not None:
            return hit.get("v"), hit.get("t")
        try:
            v = fetch()
            rec = {"v": v, "t": dt.date.today().isoformat()}
            self.cache.set(key, rec)
            return v, rec["t"]
        except Exception as e:
            self.errors.append(_redact_key(self.spec, f"{self.name}: {type(e).__name__}: {str(e)[:160]}"))
            st = self.cache.get(key, allow_stale=True)
            return (st.get("v"), st.get("t")) if st else (None, None)

    # --- transport
    def _indicators(self, claim_text: str) -> list[dict]:
        inds = self.spec.get("indicators") or []
        if not inds:
            return [{"code": None, "label": self.spec.get("label") or " ".join(self.keywords[:4]),
                     "keywords": self.keywords, "unit": self.spec.get("unit", "")}]
        scored = [(kw_hits(claim_text, i.get("keywords") or []), n, i) for n, i in enumerate(inds)]
        return [i for h, _n, i in sorted(scored, key=lambda x: (-x[0], x[1])) if h > 0][:3]

    def fetch_doc(self, vars_: dict):
        """(json document, public source url) for one request; raises FetchError."""
        spec, auth = self.spec, self.spec.get("auth") or {}
        if spec.get("kind") == "mcp":
            args = _fill_obj(spec.get("arguments") or {}, vars_)
            doc = call_mcp(spec, args, self.timeout)
            src_url = _fill(spec.get("source_url") or (spec.get("server") or {}).get("url") or "", vars_)
            return doc, src_url
        req = spec.get("request") or {}
        url = _fill(req["url"], vars_)
        if _authority(url).lower() != _authority(req["url"]).lower():
            raise FetchError("the filled URL changed host; refused")
        public = _strip_auth(url, auth)
        headers = {str(k): _fill(str(v), vars_, encode=False) for k, v in (req.get("headers") or {}).items()}
        key = _key(spec)
        if auth and key:
            if auth.get("in", "header") == "query":
                url += ("&" if "?" in url else "?") + urlencode({auth.get("name") or "api_key": key})
            else:
                headers[auth.get("name") or "Authorization"] = (auth.get("prefix") or "") + key
        if req.get("method", "GET").upper() == "POST":
            r = safe_post(self.session, url, self.timeout, headers, json_body=_fill_obj(req.get("body") or {}, vars_),
                          allow_local=self.allow_local)
            if getattr(r, "status_code", 200) >= 400:
                raise FetchError(f"HTTP {r.status_code}")
            doc = r.json()
        else:
            doc = get_json(self.session, url, self.timeout, headers, allow_local=self.allow_local)
        src_url = _fill(spec.get("source_url"), vars_) if spec.get("source_url") else public
        return doc, src_url

    def groups(self, claim_text: str):
        groups, sources = {}, {}
        for ind in self._indicators(claim_text):
            vars_ = template_vars(self.spec, claim_text, ind)
            if vars_ is None:
                continue
            cache_key = json.dumps({k: vars_[k] for k in ("indicator", "period", "place")} |
                                   ({"query": vars_["query"]} if "{query}" in json.dumps(self.spec.get("request") or
                                                                                         self.spec.get("arguments") or {}) else {}),
                                   sort_keys=True)

            def get(vars_=vars_):
                doc, src_url = self.fetch_doc(vars_)
                return {"doc": doc, "url": src_url}
            rec, fetched = self.cached(cache_key, get)
            if not rec:
                continue
            label = str(ind.get("label"))
            rows, meta = to_rows(self.spec, rec.get("doc"), label, vars_)
            if not rows:
                continue
            groups[label] = rows
            sources[label] = {"url": meta.get("url") or rec.get("url") or "", "publisher": self.publisher,
                              "title": meta.get("title") or f"{self.publisher}: {label}",
                              "published": meta.get("as_of"), "unit": ind.get("unit") or meta.get("unit") or "",
                              "as_of": meta.get("as_of") or (f"retrieved {fetched}" if fetched else None)}
        return groups, sources

    def match(self, claim_text: str, numbers: list, label_ok=None) -> list[dict]:
        units = {str(i.get("label")): str(i.get("unit") or "") for i in self.spec.get("indicators") or []}
        out = []
        for n in numbers:
            okl = (lambda lab, n=n: _unit_ok(units.get(lab, self.spec.get("unit", "")), claim_text, n.raw))
            out += super().match(claim_text, [n], label_ok=okl) if len(numbers) == 1 else \
                [f for f in super().match(claim_text, numbers, label_ok=okl) if f["claimed"] == n.raw]
        seen, fs = set(), []
        for f in out:
            k = (f["claimed"], f["verdict"], f["official"]["display"])
            if k not in seen:
                seen.add(k)
                fs.append(f)
        return [self._mark(f) for f in fs]

    def _mark(self, f: dict) -> dict:
        off = f.setdefault("official", {})
        off["trust"] = self.trust
        off["badge"] = self.badge
        off["plugin"] = self.spec["name"]
        off["retriever"] = self.name
        if not f.get("indicator", "").startswith("plugin:"):
            f["indicator"] = f"{self.name}:{f.get('indicator', '')}"
        if self.trust == "other":
            # an unofficial source never decides a figure: a match is at most PARTLY (low), a mismatch is not proof
            if f["verdict"] == "MATCH":
                f["verdict"] = "CLOSE"
                f["reason"] += f" Capped at partly supported: {self.badge} is a plug-in source with trust 'other'."
                f.setdefault("warnings", []).append({"code": "plugin_untrusted", "severity": "warn",
                                                     "message": f"Only an unofficial plug-in source ({self.badge}) states this figure."})
            elif f["verdict"] == "MISMATCH":
                f["verdict"] = "UNVERIFIED"
                f["reason"] = f"{self.badge} (plug-in, trust 'other') gives {off.get('display')}; not used to contradict a figure."
        return f


def build_sources(cfg: Config, session=None) -> tuple[dict, list[str]]:
    """{matcher name: PluginSource} for every valid enabled plug-in, plus load problems. Registers routes."""
    specs, problems = load_all(cfg)
    out = {}
    for s in specs:
        try:
            src = PluginSource(cfg, s, session)
        except Exception as e:
            problems.append(f"{s.get('name')}: {e}")
            continue
        out[src.name] = src
        ROUTES[src.name] = src.keywords
        TRUST_OF[src.name] = src.trust
    return out, problems


def routes_for(text: str, available: set) -> list[str]:
    """Plug-in matchers whose keywords the claim names: official first, then scholarly, then other; most hits first."""
    rank = {"official": 0, "scholarly": 1, "other": 2}
    scored = [(rank.get(TRUST_OF.get(n, "other"), 2), -kw_hits(text, kws), n) for n, kws in ROUTES.items()
              if n in available and kw_hits(text, kws) > 0]
    return [n for _r, _h, n in sorted(scored)]


def test_source(spec: dict, cfg: Config, claim: Optional[str] = None, session=None) -> dict:
    """`truthlens sources test`: one live request with the config's test claim; returns rows and findings."""
    from .claims import checkable_numbers
    src = PluginSource(cfg, spec, session)
    text = claim or (spec.get("test") or {}).get("claim") or ""
    out = {"name": src.name, "claim": text, "unavailable": src.unavailable(), "groups": {}, "findings": [], "errors": []}
    if not text:
        out["errors"].append("no test claim: add `test: {claim: ...}` to the config or pass --claim")
        return out
    if out["unavailable"]:
        return out
    groups, sources = src.groups(text)
    out["groups"] = {k: {"rows": v[:5], "rows_total": len(v), "source": sources.get(k)} for k, v in groups.items()}
    out["findings"] = [{"claimed": f["claimed"], "verdict": f["verdict"], "reason": f["reason"]}
                       for f in src.match(text, checkable_numbers(text))]
    out["errors"] = list(src.errors)
    return out
