# Plug-in sources (v0.5)

Plug-in sources let you add **your own data APIs (REST) or MCP servers** to TruthLens without changing its code. A
plug-in is one YAML file in a sources directory. TruthLens sends it the numeric claims whose words match its
`keywords`, reads the answer with a JSONPath mapping, and judges the claim's figure exactly as it judges the built-in
ministry sources: the same period, place, sub-group, unit and relevance gates, the same polarity rule ("was not X"),
the change calculator and the deterministic quote. A plug-in cannot make TruthLens say more than an official table
could, and a plug-in with `trust: other` can never do more than PARTLY SUPPORTED with low confidence.

## Quick start

```bash
truthlens sources examples                 # the bundled key-free examples
truthlens sources add worldbank-wdi        # copy an example (or your own file) into the sources directory
truthlens sources test worldbank-wdi       # one live request with the config's test claim, rows and verdict
truthlens sources list                     # loaded plug-ins, broken configs, missing keys
```

Where configs are read from: `$TRUTHLENS_SOURCES_DIR` (one or more folders, separated like `PATH`), else
`sources_dir` under `[truthlens]` in `truthlens.toml`, else `./sources.d` and `~/.config/truthlens/sources.d`.
`truthlens sources add` writes to the first of these that exists (else creates `./sources.d`). Plug-ins are on when
`plugins` is in the retriever list, which it is by default; a custom `retrievers = [...]` in `truthlens.toml` must
include `"plugins"`.

Bundled examples (`truthlens/data/plugin_examples/`, no key, checked live on 2 Nov 2026):

| name | what | notes |
|---|---|---|
| `worldbank-wdi` | World Bank WDI: life expectancy, forest area, access to electricity, urban population, renewable energy share, freshwater withdrawals | indicators the bundled India dataset does not cover |
| `imf-datamapper` | IMF World Economic Outlook: government debt, current account balance, real GDP growth | India is on a fiscal-year basis (2024 = FY 2024-25); `max_offset: -1` drops projection years; imf.org returns HTTP 403 to browser-like user agents, so the example sets its own |

A template with every field is in `truthlens/data/plugin_examples/TEMPLATE.yaml.txt`.

## Schema

| field | required | meaning |
|---|---|---|
| `name` | yes | lowercase letters, digits, `-` (2-41 characters). Shown as `plugin:<name>` in reports. |
| `kind` | | `rest` (default) or `mcp` |
| `enabled` | | `true` (default) / `false`. Must be a real boolean. |
| `trust` | | `official`, `scholarly` or `other` (default `other`). `official`: a match is SUPPORTED (high), a mismatch CONTRADICTED (medium), like a ministry source. `scholarly`: at most medium confidence. `other`: a match is at most PARTLY SUPPORTED (low) and a mismatch is never a contradiction. |
| `publisher`, `badge` | | shown on evidence ("World Bank") |
| `keywords` | yes* | routing words. The planner sends a numeric claim to the plug-in only when it names one of these or an indicator's keywords (*at least one keyword somewhere is required). |
| `timeout` | | seconds per request, more than 0 and at most 120 (default 15) |
| `cache_hours` | | answers are cached on disk this long (default 24) |
| `allow_local` | | `false` (default). `true` lets this plug-in reach a private or local address (a service on your own machine). It applies only to the configured host: a redirect to any other host gets the full check. Local services are reached without the proxy. |
| `auth` | | `{env: VAR_NAME, in: header|query, name: X-API-Key, prefix: "Bearer "}`. The key is read from the environment variable at request time. A key written in the file (`key:`, `token:`, `value:` ...) is refused. Keys never appear in cache keys, stored URLs, reports or error messages. Without the variable set, the plug-in is skipped ("needs the key in $VAR"). |
| `request.url` | rest | URL template, `http(s)` only. Placeholders `{query}` (claim text), `{indicator}` (the matched indicator's `code`), `{period}`, `{place}` are URL-encoded. **Placeholders may not appear in the scheme, host, port or user part**, and the host is checked again after filling. |
| `request.method`, `request.headers`, `request.body` | | `GET` (default) or `POST` (JSON `body` with the same placeholders); extra headers |
| `source_url` | | the public page shown in reports (same placeholder rule); default: the request URL without a query-string key |
| `places` | | TruthLens place -> the API's code, default `{india: IND}`. A claim about a place with no code is not sent (fail closed). State names are lowercase (`kerala: KL`). |
| `place_name` | | the place name for rows whose answer has no place field (e.g. `India`) |
| `period.format` | | `year` (a claim's 2023-24 asks for 2023), `fy` (2023-24) or `range` (first:last year) |
| `period.default` | | `{period}` when the claim names none |
| `period.max_offset` | | drop rows for years after (this year + offset), e.g. `-1` to ignore projections |
| `indicators` | | list of `{code, label, unit, keywords}`. The claim's words pick up to three indicators; `label` is what the claim must share a specific word with; `unit` `%` judges only per-cent figures, any other unit never judges a per-cent figure. |
| `response.records` | | JSONPath to the list of records (`{indicator}`, `{place}` allowed). Omit when the answer is one record. |
| `response.records_mode` | | `items` turns a `{"2023": 7.0, ...}` mapping into records `{key, value}` |
| `response.value` | yes | JSONPath inside a record. Non-numbers, NaN and Infinity are dropped. |
| `response.period`, `place`, `title`, `url`, `unit`, `as_of` | | JSONPaths inside a record (`url` kept only if `http(s)`) |
| `response.as_of_root` | | JSONPath from the document root for the "data as of" date |
| `response.scale` | | divide every value by this |
| `sync.requests` | | list of `{indicator, place, period}` that `truthlens sync` refreshes (new periods, revised values) |
| `test.claim` | | the sentence `truthlens sources test` uses |

JSONPath subset: `$`, `.key`, `['key']`, `[n]`, `[-1]`, `[*]`, `.*`. Anything else is rejected when the config is
loaded.

### MCP servers

```yaml
name: my-stats-mcp
kind: mcp
trust: official
keywords: [unemployment]
server:
  command: [python, /path/to/server.py]      # stdio: TruthLens starts this program
  # url: https://mcp.example.org/mcp          # or a streamable-HTTP server
tool: get_indicator
arguments: {indicator: "{indicator}", place: "{place}", period: "{period}"}
indicators: [{code: unemployment, label: unemployment rate, unit: "%", keywords: [unemployment]}]
response: {records: "$.data[*]", value: "$.value", period: "$.year", place: "$.country"}
source_url: "https://stats.example.org/{indicator}"
```

Needs the `mcp` package (`pip install "truthlens[mcp]"`; tested with mcp 2.3). The tool's text result is parsed as
JSON (else its structured content is used). A remote `server.url` passes the same SSRF guard as every other fetch
(public addresses only unless `allow_local: true`); redirects are not followed off the server's origin. `auth` with
`in: header` sends the key as a header; `in: env` passes it to a stdio server as that environment variable.

**A stdio MCP plug-in runs a program on your computer.** `truthlens sources add` shows the command and asks first
(`--yes` to confirm without a terminal). Only add configs you trust, the same as installing any program; anything
placed in the sources directory is loaded on the next run.

## Safety summary

- All REST fetches use `net.safe_get` / `safe_post` (scheme, embedded-credential and private-address checks on every
  hop, connected-peer re-check, size caps). MCP URLs are checked before connecting.
- Plug-in text (titles, units, URLs) is data: it is escaped in the HTML report and web page, never sent to the LLM
  judge (datapoints are decided deterministically) and never followed as a link unless `http(s)`.
- A plug-in that fails, times out or is refused is recorded as unreachable and shown in the report's banner; its
  claims stay "couldn't check" (fail closed). A broken config is listed (`truthlens sources list`, report errors)
  and not loaded.
