# TruthLens: full reference

The detailed manual and version history. For what TruthLens does and does not do, start with the [README](../README.md). Where this page describes a feature, the README's "What it does not do" list still applies: on real state policy documents only a small share of claims can be checked against data.

```
$ truthlens check samples/sample_policy_note.docx --deep -f json -o samples/sample_report_v05.json
```

Result: **8 wrong · 6 supported · 4 couldn't check · 1 skipped**; verified score 32.9% of 14 checked claims (couldn't-check not counted; 2 supported are low-confidence); 1 citation not found; 6 suggested fixes. Citations, OpenAlex, Parliament and Semantic Scholar errored during this run.

(Live sources, no keys, 2 Nov 2026, v0.5.0; from v0.5.2 the CLI needs `--deep` for live sources. The score is confidence-weighted and counts only checked claims, so heuristic "supported" verdicts count for less and "couldn't check" is reported separately, never as wrong.)

- **Verdict per claim:** SUPPORTED, PARTLY SUPPORTED, CONTRADICTED (wrong), DATED (v0.6: a figure for an earlier year or for a State before a boundary change; never wrong) or UNVERIFIED (shown as "couldn't check"). It fails closed: no good evidence means "couldn't check", never a guess. Every report leads with the split, e.g. "8 wrong · 7 supported · 3 couldn't check · 1 skipped", and names the part that failed ("2025-26 Real GDP growth: draft 7.7%, official 7.8% (revised)"). Opinions are skipped, but an opinion-worded sentence that carries a fact ("In my view, the fiscal deficit has been rising every year") is checked and labelled "contains a factual claim".
- **Change claims checked properly (v0.4.1):** "rose from 5.4% to 4.6%" is caught as a contradiction even though both figures are right; "by 0.8 percentage points", "higher than last year", "doubled", "every year" are computed from the official series, and per cent vs percentage points mix-ups are flagged.
- **Evidence you can click and cite:** quoted passage, source type (MoSPI, RBI, CEA, PPAC, JJM, NDAP, data.gov.in, PIB, Lok Sabha, Rajya Sabha, Report, Paper, Thesis, World Bank), "data as of" date, page number, source URL and a copy-citation button.
- **Live official sources, no key:** MoSPI eSankhyiki (every dataset its API lists), RBI current rates and the Weekly Statistical Supplement, CEA power data, PPAC petroleum data, the Jal Jeevan Mission dashboard, PIB press releases, Lok Sabha and Rajya Sabha answers, Economic Survey and Budget documents, Crossref, arXiv, World Bank; the NDAP catalogue only names a dataset to cite. Bundled for Quick checks: Census 2011 (State and district), CGWB 2025 (State) and NFHS-5 Karnataka. **Untested:** data.gov.in (free key), Semantic Scholar and Shodhganga have never answered our test network and are tested only on made-up sample data. See [`docs/SOURCES.md`](SOURCES.md).
- **Suggested fix:** for contradicted or partly supported claims, a corrected sentence with the right figure and its citation.
- **Citations checked:** URLs and DOIs in the draft are fetched (DOIs through Crossref and OpenAlex) and tested for whether they actually contain the claim. A DOI that doesn't exist is flagged as a likely fabricated reference.
- **India statistics pack:** numbers about India are checked deterministically against official series, live from MoSPI, with executable "data trap" rules (2026 base-year revisions, lakh/crore vs million, FY vs calendar year, BE/RE/Actuals, PLFS usual status vs weekly status, per cent vs percentage points).
- **Bring your own keys, or none:** with no keys it still runs (rules, official data, cited sources, your own document index). Add an Anthropic, OpenAI or local Ollama model (v0.6, untested live: DeepSeek, Mistral, xAI, Gemini, Kimi, Qwen, GLM, OpenRouter, or a custom OpenAI-compatible URL) for better claim extraction and an evidence-quoting judge, and a Brave, Tavily or Serper key for web search. Keys stay in your environment and never appear in reports, caches or logs.

See [`samples/sample_report_v05.html`](../samples/sample_report_v05.html) (v0.5.0, live sources; open it in a browser, no internet needed) and its [JSON](../samples/sample_report_v05.json); the v0.4.1 run is [`samples/sample_report_v041.html`](../samples/sample_report_v041.html), the v0.4 run is [`samples/sample_report_v4.html`](../samples/sample_report_v4.html), the v0.3 run [`samples/sample_report_v3.html`](../samples/sample_report_v3.html). The v0.2 [`samples/sample_report.html`](../samples/sample_report.html), its [PDF preview](../samples/sample_report.pdf), the [Markdown version](../samples/sample_report.md) and the [annotated draft](../samples/sample_corrected.docx), all generated from [`samples/sample_policy_note.docx`](../samples/sample_policy_note.docx).

## No terminal? Use the web app

- **On your own PC:** double-click `start_truthlens.bat` (Mac/Linux: `start_truthlens.sh`). The first run creates a private Python environment and installs everything with `python -m pip` (works where `pip.exe` is blocked); then your browser opens the TruthLens page. Drop in a draft, or click **Open sample report** to see a finished report with no internet. Close the window to stop. Step-by-step guide for non-programmers, Windows first: [SETUP.md](../SETUP.md). (The older `Start TruthLens (Windows).bat` and `start-truthlens.sh` still work.)
- **Hosted:** the included `Dockerfile` runs the same web app on any container host, for example a free Hugging Face Space (Docker SDK, port 7860), so anyone could use it in the browser with nothing to install. **The Dockerfile has not been built or tested yet, and TruthLens is not hosted anywhere.** Settings, limits and measured memory: [HOSTING.md](../HOSTING.md).

### Quick check and Deep check (v0.5.2)

- **Quick check** (what the web app does first): takes seconds. It checks your draft against the official figures
  TruthLens already has on your computer (bundled with it, or fetched by **Update now**) and against answers it saved
  from earlier checks. It contacts no website. Claims it cannot settle this way are marked "not checked in Quick mode"
  — that is not a verdict.
- **Deep check** (the button that appears after a Quick check): takes about half a minute to a minute. It asks the live
  government and research websites (MoSPI, RBI, CEA, Parliament, Crossref and others) about only the claims the Quick
  check left open; everything else keeps its Quick result. A website that is down or slow is named in the report, and
  the claims it affects say "couldn't check", never "wrong".
- Neither mode ever guesses: no evidence means "couldn't check". Sentences that only describe a programme, its aims or
  its procedures ("The Gram Panchayat is responsible for operation and maintenance") are shown as "Not a checkable
  fact" instead of being counted.

On a 51-claim test draft (3 Nov 2026, Linux sandbox via a US proxy): Quick 0.4 s, Deep 33 s with an empty cache and
13 s when the same answers were saved from an earlier check. Details: [`data/perf_v052.md`](../data/perf_v052.md).

## Install

```bash
git clone https://github.com/ApahSaroj/truthlens && cd truthlens
python -m pip install -e ".[api]"  # CLI + web upload page
python -m pip install -e ".[all]"  # + MCP server, official MoSPI package, PDF export
truthlens doctor --ping            # what is configured, and can we reach the public sources?
```

Python 3.10 or later.

## Keys and configuration

**No key needed.** TruthLens runs key-free: rules, heuristics and live official sources (MoSPI, RBI, CEA, PPAC, Jal Jeevan Mission, the NDAP catalogue, PIB, Lok Sabha, Rajya Sabha, official reports, Crossref/OpenAlex, arXiv, World Bank). It fails closed, so without a key it says UNVERIFIED rather than guess.

**Removed in v0.5.3: the "NDAP token".** Earlier versions said a free token "from your NDAP profile" would let TruthLens read NDAP data rows. That was never verified (no token could be obtained, and the data format was only tested on a made-up sample), so the token, `NDAP_API_TOKEN`, the web page field, the `X-NDAP-Token` header and the `ndap_token` API field are gone. The NDAP catalogue is still searched with no key, only to name the dataset to cite.

**Optional: a free data.gov.in key** lets TruthLens read rows from data.gov.in datasets. **Untested:** data.gov.in has never answered our test network, so this path has only been tested on made-up sample data. Same rules as the AI key: the web page's data.gov.in field, `X-DataGovIn-Key` header or `datagovin_key` field on the API, each used for one check only and never stored. Sync the catalogue index once with `truthlens datagov sync`.

**Optional: bring your own AI key** for sharper verdicts on non-numeric claims and better suggested fixes:
- **Web page:** open "Optional: your own AI key or data.gov.in key", pick a provider and paste the key (v0.6: an optional model name, and a base URL for "Custom"). It is sent with that one check only, never stored or logged, and redacted from errors.
- **CLI, one run:** `truthlens check draft.docx --llm deepseek --ask-key` prompts for it (hidden) and forgets it afterwards (without `--llm` the key is taken as Anthropic when it starts with `sk-ant-`, otherwise OpenAI).
- **API:** send `X-LLM-Key` and `X-LLM-Provider: anthropic|openai|deepseek|mistral|xai|gemini|moonshot|qwen|zhipu|openrouter|custom` headers (or `llm_key`/`llm_provider` fields); v0.6 adds `X-LLM-Model` / `llm_model` and, for custom, `X-LLM-Base-URL` / `llm_base_url`.
- **Free and local:** Ollama, below.

New to the command line? [SETUP.md](../SETUP.md) walks through installing and using TruthLens in plain steps, Windows first.

To keep keys permanently, set them as environment variables; TruthLens picks the first configured provider.

| What | Environment variable | Used for |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` (model: `TRUTHLENS_ANTHROPIC_MODEL`, default `claude-sonnet-4-5`) | claim extraction, evidence judge, corrected sentences |
| OpenAI or compatible | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `TRUTHLENS_OPENAI_MODEL` (default `gpt-4o-mini`) | same |
| Ollama (local) | `OLLAMA_HOST=http://localhost:11434`, `TRUTHLENS_OLLAMA_MODEL` (default `llama3.1`) | same, nothing leaves your machine |
| v0.6 providers (untested live) | see "AI providers (v0.6)" below | same |
| Brave Search | `BRAVE_API_KEY` | web evidence |
| Tavily | `TAVILY_API_KEY` (or `TRUTHLENS_TAVILY_KEYLESS=1`, off by default) | web evidence |
| Serper | `SERPER_API_KEY` | web evidence |
| data.gov.in | `DATAGOVIN_API_KEY` (free; `TRUTHLENS_DATAGOVIN_SAMPLE_KEY=1` opts in to the public demo key, rate-limited) | rows from datasets found in the local catalogue index (`truthlens datagov sync`) or mapped in `truthlens.toml`; **untested** against the live service |
| OpenAlex | `OPENALEX_API_KEY` (optional) | a larger daily budget for research-paper search |
| Semantic Scholar | `S2_API_KEY` (optional) | avoids the shared key-free pool's HTTP 429s |
| Choose | `TRUTHLENS_LLM`, `TRUTHLENS_SEARCH` | force a provider, or `none` |
| Other | `TRUTHLENS_OFFLINE=1`, `TRUTHLENS_CACHE`, `TRUTHLENS_MOSPI=0`, `TRUTHLENS_CONTACT_EMAIL` | offline mode, cache location, live MoSPI on/off, Crossref polite pool |

### AI providers (v0.6)

All of these use the provider's OpenAI-compatible chat completions endpoint. The base URL and default model were
read from each provider's own documentation on 4 Nov 2026 (links below). **None of them has been tried with a live
account**: the test suite checks each request against simulated answers only (URL, key header, model, JSON mode, the
fallback below). Override the model with `TRUTHLENS_<PROVIDER>_MODEL` (or the model field / `X-LLM-Model`) and the base
URL with `TRUTHLENS_<PROVIDER>_BASE_URL`.

| `--llm` / `X-LLM-Provider` | Key variable | Base URL | Default model | Documentation |
|---|---|---|---|---|
| `deepseek` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-flash` | https://api-docs.deepseek.com/ |
| `mistral` | `MISTRAL_API_KEY` | `https://api.mistral.ai/v1` | `mistral-small-latest` | https://docs.mistral.ai/api/ |
| `xai` (Grok) | `XAI_API_KEY` | `https://api.x.ai/v1` | `grok-4.7` | https://docs.x.ai/docs/overview |
| `gemini` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3.8-flash` | https://ai.google.dev/gemini-api/docs/openai |
| `moonshot` (Kimi) | `MOONSHOT_API_KEY` | `https://api.moonshot.ai/v1` | `kimi-k3.1-pro` | https://platform.moonshot.ai/docs/guide/start-using-kimi-api |
| `qwen` (DashScope international) | `DASHSCOPE_API_KEY` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope |
| `zhipu` (Z.ai GLM) | `ZAI_API_KEY` | `https://api.z.ai/api/paas/v4` | `glm-5.3` (temperature 0.1: the docs say 0 is not accepted) | https://docs.z.ai/guides/develop/openai/python |
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `~openai/gpt-sol-latest` (the docs' example alias; set your own) | https://openrouter.ai/docs/quickstart |
| `custom` | `TRUTHLENS_CUSTOM_API_KEY` | `TRUTHLENS_CUSTOM_BASE_URL` | `TRUTHLENS_CUSTOM_MODEL` (required) | your provider's |

Notes, from the same documentation pages:
- Alibaba now recommends workspace-specific hosts (`https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`); the older `dashscope-intl` host is the default here because it needs no workspace id. Set `TRUTHLENS_QWEN_BASE_URL` to your workspace host if the default stops answering. A DashScope key works only in the region it was created in.
- xAI lists Chat Completions as legacy (its docs lead with the Responses API); TruthLens uses Chat Completions.
- Aliases: `grok` = `xai`, `kimi` = `moonshot`, `glm` / `zai` = `zhipu`, `dashscope` = `qwen`, `google` = `gemini`.

Behaviour shared by every OpenAI-compatible provider:
- The request asks for `response_format: {"type": "json_object"}`. If the provider answers HTTP 400, TruthLens asks once more without it (and without a temperature), with "Answer with one JSON object only" added to the instructions, and parses the JSON out of the text.
- Redirects are not followed. Keys are read at call time from the environment or the per-request keys, never written to reports, caches or logs; error text is redacted (the key itself, `Bearer ...` and key-shaped strings).
- The provider hosts are on the live-answer cache's never-cache list, and any URL ending in `/chat/completions` is never cached, whatever its host.
- **Custom base URL:** on a hosted TruthLens (`TRUTHLENS_PUBLIC=1`) only `https` URLs to public addresses are accepted, checked with the same guard as every other outbound request (every resolved address must be public; no embedded credentials, no query string), and the connection itself goes through the guarded session that refuses private peers. Locally, `http` and local addresses (a model server on your own machine) are allowed.

Non-secret settings (retrievers, allow-listed domains, data.gov.in resource map, MoSPI backend) go in `truthlens.toml`; copy [`truthlens.example.toml`](truthlens.example.toml). TruthLens refuses to start if that file contains a key. `truthlens doctor` shows which keys are present as yes/no, never their values.

## Usage

### CLI

```bash
truthlens check draft.docx -f html -o report.html          # HTML report (self-contained, printable)
truthlens check draft.pdf -f md                             # Markdown to stdout; -f json for machines
truthlens check draft.docx --docx-out draft.reviewed.docx   # Word comments + [suggested: ...] insertions
truthlens check https://example.org/brief -f html -o r.html
truthlens check --text "Real GDP grew 6.5% in 2024-25." -f md
truthlens check draft.docx --strict                         # exit 1 if anything is CONTRADICTED (for CI)
truthlens check draft.docx --offline                        # no network: bundled data, caches, your index
truthlens check draft.docx --deep                           # v0.5.2: Deep check (live sources); Quick is the default
truthlens check draft.docx --numbers-only                   # v0.1 behaviour: India numbers only
truthlens check policy.pdf -f cite -o claims_to_cite.csv   # v0.5.3: only the claims that need a source, as CSV
truthlens check policy.pdf -f csv -o all_claims.csv         # v0.6: every claim with its verdict (including DATED), as CSV
truthlens compare old.pdf new.pdf -f html -o compare.html   # v0.6: compare two versions (-f md|json|html, --threshold 0.85)
truthlens compare old.pdf new.pdf --meaning -f html -o compare.html   # v0.7: also by meaning (pip install "truthlens[meaning]")
truthlens compare old.pdf new.pdf --meaning --topics clusters --model multilingual --meaning-threshold 0.12
truthlens compare old.pdf new.pdf --meaning --ai-summary --llm anthropic --ask-key   # optional AI summary per topic

truthlens index ./reports                    # add your own folder (.pdf .html .docx .txt .md) as evidence
truthlens index --url https://www.pib.gov.in/PressReleasePage.aspx?PRID=2243781
truthlens index --pib-rss --max 20           # current PIB press releases
truthlens index --list
truthlens sources                            # which evidence sources are active
truthlens sources list|add|test|examples     # your own plug-in sources (v0.5, docs/PLUGINS.md)
truthlens sync                               # refresh local knowledge; --schedule daily|weekly prints a cron/schtasks line
truthlens corrections review                 # review "this verdict is wrong" reports; eval --user-corrections
truthlens doctor --ping                      # configuration + live reachability of every source
truthlens datagov sync                       # index the data.gov.in catalogue locally (key optional for the listing)
truthlens datagov search "tap water Bihar"   # search that index
truthlens datagov status
truthlens indicators                         # India series covered by the deterministic checker
```

### Web upload page and API

```bash
uvicorn truthlens.api:app        # then open http://localhost:8000: drop a file, paste text or try the sample
```

| Method | Path | Body |
|---|---|---|
| GET | `/` | one-page app: drop a file or paste text, then click any highlighted sentence to see its verdict, evidence and fix (accept fixes, copy the corrected text, download the report) |
| GET | `/sample` | the bundled sample policy note (.docx) |
| POST | `/render?format=html` | a JSON report from `/check` rendered as the static HTML report, without re-checking |
| GET | `/health`, `/sources` | status, configured sources (no secrets) |
| POST | `/check` | `{"type": "text" or "url", "content": "...", "format": "json" or "md" or "html", "numbers_only": false}`; optional `llm_key`/`llm_provider` (or `X-LLM-Key`/`X-LLM-Provider`) and `datagovin_key` (or `X-DataGovIn-Key`), used for that check only |
| POST | `/check/file?format=html` | multipart upload of `.docx`, `.pdf`, `.txt` or `.md` (15 MB max) |
| POST | `/compare/file?format=json` | v0.6: two multipart uploads, `old` and `new` (15 MB each); `format=json`, `md` or `html`; `threshold` 0.5 to 1.0 (default 0.85). No network, no AI. v0.7: `meaning=true` adds the match by meaning (optional extra), `topics=auto\|headings\|clusters\|water`, `meaning_threshold`, `ai_summary=true` with `X-LLM-Key`/`X-LLM-Provider` (or form fields `llm_key`/`llm_provider`), used for that request only |
| GET | `/compare/meaning-status` | v0.7: `installed`, `model`, `model_downloaded`, `install` hint, `note` (no server paths) |
| POST | `/jobs`, `/jobs/file` | v0.5.1: the same bodies as `/check` and `/check/file`, run in the background; answers `202 {"job_id"}` (the web app uses these) |
| GET | `/jobs/{id}` | progress: `status` (running, done, error, cancelled), `stage`, `claims_done`, `claims_total`, `elapsed_s` |
| GET | `/jobs/{id}/result?format=json` | the report once `status` is `done` (409 while running, 410 if cancelled) |
| POST | `/jobs/{id}/cancel` | stop a running check |
| POST | `/jobs/{id}/deep` | v0.5.2: Deep check of the claims a finished Quick job left unchecked; answers `202 {"job_id"}` (a new job) |

v0.5.2: `mode=quick` or `mode=deep` on `/jobs`, `/jobs/file`, `/check` and `/check/file`. The jobs endpoints (the web
app) default to Quick; `/check` and `/check/file` default to Deep, as in v0.5.1, so existing scripts keep working.
| GET | `/sync/status` | when the local data was last updated, whether it is stale (> 7 days), whether an update is running |
| POST | `/sync` | "Update now": start `truthlens sync` in the background (one at a time; 409 when offline or already running) |
| POST | `/corrections` | `{"claim_text", "reported_verdict", "correct_verdict", "note", "source_url"}`: saved as pending, locally |

### MCP tool

`truthlens-mcp` starts a stdio MCP server with `check_claims(text)` (v0.2, all claims) and `verify_india_stat(statement)` (v0.1, India numbers):

```json
{"mcpServers": {"truthlens": {"command": "truthlens-mcp"}}}
```

### Python

```python
from truthlens.pipeline import Pipeline
from truthlens.readers import read_file
report = Pipeline().run(read_file("draft.docx"), "draft.docx")
report["summary"]["verified_score"], report["claims"][0]["verdict"], report["claims"][0]["suggested_fix"]
```

## Add your own sources

Plug in **your own data API (REST) or MCP server** with one YAML file; no code changes (v0.5). TruthLens routes a
numeric claim to it when the claim names one of its keywords, reads the answer with a JSONPath mapping and judges the
figure exactly like a built-in official source (period, place, sub-group and unit must match or the claim stays
"couldn't check"; "was not" claims, change claims and quotes get the same checks).

```bash
truthlens sources examples                 # bundled, key-free: worldbank-wdi, imf-datamapper
truthlens sources add worldbank-wdi        # or: truthlens sources add my-api.yaml
truthlens sources test worldbank-wdi       # one live request: rows found and the verdict for the test claim
truthlens sources list
```

```yaml
# sources.d/my-api.yaml
name: my-api
kind: rest                     # or mcp (server: {command: [...]} or {url: ...}, tool:, arguments:)
trust: official                # official | scholarly | other ('other' = at most PARTLY SUPPORTED, low confidence)
keywords: [life expectancy]
auth: {env: MY_API_KEY, in: header, name: X-API-Key}    # optional; the key stays in your environment
request: {url: "https://api.example.org/{place}/{indicator}?year={period}"}
indicators: [{code: LE, label: life expectancy at birth, unit: years, keywords: [life expectancy]}]
response: {records: "$.data[*]", value: "$.value", period: "$.year", place: "$.country"}
```

Safety: every request goes through the same SSRF guard as the rest of TruthLens (public addresses only, checked on
every redirect; `allow_local: true` in your own config is the only way to reach a local service, and only its own
host); placeholders can never change the host; keys are never stored in caches or reports; plug-in text is escaped
on the page; a plug-in that fails or times out is shown in the "unreachable" banner and its claims stay "couldn't
check". A stdio MCP plug-in starts a program on your computer, so `sources add` asks first. Full schema and examples:
[`docs/PLUGINS.md`](PLUGINS.md).

## Keeping data fresh

```bash
truthlens sync                     # refresh what TruthLens knows, then say what is new
truthlens sync --status            # "Local data last updated 2 November 2026."
truthlens sync --schedule daily    # prints a cron line (or, on Windows, a schtasks command); installs nothing
```

`truthlens sync` refreshes the PIB English press-release feed (new releases go into your local document index),
the official report listing pages (Economic Survey, Budget), recent Lok Sabha questions for tracked keywords
(`[sync] keywords = [...]` in `truthlens.toml`), the MoSPI indicator catalogue, NDAP catalogue entries, RBI current
rates, and every plug-in that declares `sync:`. It records each source's last-synced time and what is new in
`data/sync_state.json` and `data/sync_log.jsonl` (`$TRUTHLENS_DATA_DIR` to move them), and flags **superseded**
figures: a curated PLFS / National Accounts figure for which MoSPI now has a newer period or a revised value, a
changed RBI rate, a revised plug-in value. A source that is down is reported and its previous state kept. Reports
carry the data's age, and say so when it is more than 7 days old. The web app shows "Last updated" and an
**Update now** button that runs the same sync in the background. Sync updates knowledge only; it never changes
TruthLens' code or rules.

## Correcting verdicts

Every finding in the web app has a **This verdict is wrong** button: pick the right verdict, optionally add a note
and a source link. The report is saved on your computer only (`data/corrections/pending.jsonl`); nothing changes yet.

```bash
truthlens corrections list
truthlens corrections review       # re-runs each claim, then asks: accept / reject / skip
truthlens eval --user-corrections  # how the current build does on the corrections you accepted
```

Accepting writes a labelled test case to `data/testset_user_corrections.jsonl` and, if you gave a source link on the
official-domain allow-list (or you approve that link when asked), adds the page to your local evidence index.
TruthLens never accepts a correction by itself and never changes its code or rules from one.

## Share of India, hectares and the Dated verdict (v0.6)

All from the bundled Census 2011 Table A-1 (State and All India rows) and the CGWB 2025 assessment; no network.

- **Share of India.** "Uttar Pradesh accounts for 16.17% of the country's population ... 7.33% of the country's land area": the percentage is followed by "of the country's / India's / the nation's population or area" (or "of the area of India"). The share is the State's row divided by the All India row (199,812,341 / 1,210,854,977 = 16.50%; 240,928 / 3,287,469 = 7.33%), never a sum of States. It is compared at the draft's own precision (7.33 against 7.3287). The State is the one the sentence names, or the document's State when the sentence says "the State". Result: a match is SUPPORTED. A difference is CONTRADICTED only when the sentence itself dates the figure to Census 2011; with no year the reason says the comparison year is 2011 and the claim stays open ("needs a source"); with an earlier year (Census 2001) it is DATED.
- **Hectares.** A State's geographical area in ha, hectares, mha, lakh ha or million ha is converted (1 sq km = 100 ha) and compared at the draft's precision. Areas in lakh or million sq km are scaled the same way. The area check only takes a figure tied to the State's own area ("29.44 million ha. of geographical area of the state", "covers an area of"), not irrigated, flood-prone, cultivable or basin areas. A different area is never called wrong by this check.
- **DATED** (label: "Dated: figure is for an earlier year or boundary"). Never counted as wrong and not in the verified score; listed in the claims-to-cite CSV with "cite the year it is for, or a current figure". A figure is DATED when:
  - it equals the State before a split: Uttar Pradesh + Uttarakhand (formed 9 Nov 2000), Bihar + Jharkhand (15 Nov 2000), Madhya Pradesh + Chhattisgarh (1 Nov 2000), each the sum of the two Census 2011 rows; or the Census 2011 row of undivided Andhra Pradesh (Telangana formed 2 Jun 2014) in a document not older than 2014. Example: UP State Water Policy 1999, "29.44 million ha" = 240,928 + 53,483 = 294,411 sq km;
  - the sentence names a year earlier than the bundled data (a 2009 groundwater figure against the CGWB 2025 assessment);
  - the sentence names no year, the document's year (read from its first 12 blocks, for example "State Water Policy, 1999" or "Government Order no.-280/62-1-2013") is earlier than the data, and the figure differs.
  A figure in a document newer than the data, with no year, is left open, never DATED or wrong.
- Reports: the verdict is `DATED` in JSON (`summary.dated`, `summary.verdicts.DATED`, number findings with `verdict: "DATED"`), a "Dated" column in Markdown, a blue-grey highlight and count in HTML and the web app, a Word comment in `--docx-out`, and a row in `-f csv`.

## Compare two versions (v0.6)

`truthlens compare OLD NEW`, `POST /compare/file`, or the web app's "Compare two versions" tab. Local text comparison, no network and no AI.

- Sentences of 6 or more words are compared (headings, table rows, contact details and contents lines left out). Similarity is Python's `difflib.SequenceMatcher` ratio on lower-cased text without list markers or section numbers. Each old sentence is matched at most once, best pairs first. Two adjacent old sentences joined into one new sentence (or one split in two) are also matched.
- **Near-copied:** similarity at least 0.85 (`--threshold`). **Matched:** at least 0.60. **Figures changed:** within a matched pair, figures with the same unit at the same place and a different value (`20 mha → 19.13 mha`); figures only in one side are listed as removed or added (for example unit conversions in brackets that the new version dropped). Leading section numbers are not figures.
- **Dropped:** old sentences with no match at 0.60; **commitments dropped** are those with shall, should, will, must, ensure, target, priority and similar words.
- **New section headings:** short numbered or capitalised lines in the new file whose wording is not among the old file's headings or sentences, with how many sentences sit under each and how many of those are new.
- Output: Markdown (default), JSON, or a self-contained HTML page with word-level differences.

## Compare by meaning (v0.7)

`truthlens compare OLD NEW --meaning`, `POST /compare/file?meaning=true`, or the "Match by meaning" box in the web app's compare tab (ticked by default when the extra is installed). Optional extra: `pip install "truthlens[meaning]"` (fastembed with ONNX Runtime, no torch; about 145 MB installed). Works for any kind of policy document: nothing in it is specific to a sector.

- **Model.** Default `BAAI/bge-small-en-v1.5` (ONNX, quantised, 67 MB download, English only). `--model multilingual` (or `TRUTHLENS_EMBED_MODEL=multilingual`) uses `paraphrase-multilingual-MiniLM-L12-v2` (240 MB; about 50 languages incl. Hindi, Marathi, Gujarati, Urdu; not Bengali, Tamil, Telugu, Kannada, Malayalam, Odia, Punjabi; it separated right from wrong pairs less well on our English hand-check). The model downloads on first use to `TRUTHLENS_EMBED_CACHE` (default: the TruthLens cache folder + `/models`). Not installed or offline on first use: the report says so in a "Not run" line and the wording comparison is unchanged.
- **Sentences.** The same sentences as the wording compare, minus lead-ins ending in ":", table rows (3+ numbers making up 40%+ of the words) and captions ("Table 2: ...").
- **Matching.** Match score = cosine similarity of the two sentence embeddings − (the old sentence's usual similarity + the new sentence's usual similarity) / 2 + 0.10 × the share of distinctive words they share. "Usual similarity" is the mean of a sentence's 10 highest similarities; subtracting it stops broad sentences from matching everything (CSLS). Each old sentence is matched to the new sentence with the highest score if it is at least **0.10** (`--meaning-threshold`); other new sentences within 0.02 are listed too (2 at most). A new sentence that no old sentence reaches is **new**; an old sentence with no match is **dropped**, and if its nearest new sentence scores 0.05 or more it is shown as a weak "possible match".
- **Labels (rules, not AI).** Obligation level of each sentence: 3 = shall / must / will / is to be / ensure / mandatory / prohibited; 2 = should / would / needs to / it is essential / "X be promoted" (no modal); 1 = may / might / could / endeavour / encourage / explore / as far as possible / wherever feasible / efforts will be made; 0 = none. A hedge anywhere caps a sentence at 1 ("will be encouraged" is weak). In a commitment (level ≥ 1 on either side), +1 / −1 for a deadline ("by 2025", "within 3 years", "time-bound"), a figure or a named body ("... Authority / Commission / Board / Ministry / Department / Mission ...") added / removed. Net > 0 **strengthened**, < 0 **weakened**, 0 **kept**. A figure with the same unit and a different value (each old figure paired with the nearest new figure of that unit; within 0.5% counts as the same) makes it **changed figure**. A "not / never / prohibit / ban" on one side only adds the note "may reverse the meaning, check".
- **Topics.** From the new version's section headings: numbered headings (`3.`, `3.2`, `Chapter 2`), headings the PDF joined to their first paragraph, and short ALL-CAPS lines; contents-page entries that recur later are dropped. Sub-sections are rolled into their top-level section unless that gives fewer than 4 topics or one topic with more than 40% of the sentences; a top-level section with more than 40 sentences and more than 12% of the document is split into its sub-sections. A dropped old sentence goes under the most similar new topic (similarity ≥ 0.40 to the topic's average), else under its own old heading marked "(old version only)". With fewer than 3 headings that have sentences under them, or headings covering less than half of the sentences, sentences are grouped by k-means on the embeddings and each group is named by its 3 most distinctive words. `--topics water` uses an optional water-policy keyword preset; it is never the default.
- **Why.** Only quotes from the new version: a sentence in a preamble / introduction / "need for" / background / context / challenges section with a cause word ("because", "due to", "in view of", "therefore", "there is a need", ...), or anywhere with an explicit motive ("in view of", "keeping in view", "has become necessary", "need for a new ...", "in order to address ...", "recognising that ..."). It is attached to the topic of its own section, or (from a preamble) to the most similar topic at similarity ≥ 0.45; at most 2 per topic. Otherwise: "Reason not stated in the document". Motives are never inferred.
- **AI summary (optional).** `--ai-summary` with `--llm` and a key (`--ask-key`, or the environment) or Ollama; on the API `ai_summary=true` with the usual key headers. Per topic, the model sees only the numbered quotes shown for that topic and must return a 2–3 sentence summary and the quote numbers it used. The summary is **rejected** (not shown) when it puts in quotation marks any text that is not in the quotes, gives a figure that is not in the quotes, gives no quote numbers or numbers that were not shown. Shown summaries are labelled "AI summary, check the quotes". Errors are reported by type only; keys are never stored or written to the report. Tested only with mocked models.
- **Output.** Markdown, JSON and HTML lead with "Match by meaning": the summary line, a topic table (topic | kept | strengthened | weakened | changed figure | new | dropped), then per topic (expandable in HTML) the reason or "Reason not stated in the document", the AI summary if any, and every item with both quotes, page and paragraph number, score and the rule behind the label. The wording comparison follows as before.
- **Accuracy.** Hand-check (4 Nov 2026): UP State Water Policy 1999 → 2020, 22 of 29 matched pairs right, 9 of 15 dropped items truly dropped; National Health Policy 2002 → 2017, 13 of 19 and 6 of 12. Details, the tuning steps and runtimes: [`data/meaning_v070.md`](../data/meaning_v070.md).

## How it works

1. **Read** `.docx` (paragraphs and table rows), `.pdf`, `.txt`/`.md` or a URL; split into sentences. PDFs (v0.5.3) are read line by line: two-column pages one column at a time, running headers and footers dropped, short heading lines kept apart from the text after them.
2a. **Set aside what is not a claim (v0.5.3).** Headings and contents entries, rows of figures from tables, rules ("shall", "should", "must"), plans, targets and projections ("will be", "by 2030", "likely to reach"), contact details and programme descriptions are shown as "Not a checkable fact" with the reason, and are not counted. A sentence that also states a past or present figure is kept.
2. **Extract claims.** With an LLM key the model splits sentences into atomic claims and types them; without one (or if the model fails) rules do it. Types: *numeric/statistical*, *citation-backed* (URL, DOI, `[n]` or author-year reference), *factual-entity*, *opinion* (skipped).
3. **Changes and trends (v0.4.1).** A sentence about how a figure moved ("rose from X to Y", "by N percentage points", "higher than last year", "doubled", "every year") goes through the change calculator: the direction word is checked against the sentence's own figures, each endpoint against the official value, and the direction and size against the change computed from the official series (percentage points and per cent kept apart). "Last year" means the year before the claim's own period.
4. **Numbers first, deterministically.** Every number is run through the India statistics checker (below). A number it can resolve to an official series and period gets MATCH / CLOSE / MISMATCH, mapped to SUPPORTED / PARTLY SUPPORTED / CONTRADICTED with high confidence, plus any data-trap warnings. The LLM can't overrule these.
5. **Retrieve evidence** for everything else, each retriever cached on disk and returning source URL, verbatim snippet and date: the local document index, data.gov.in, web search, and the sources the draft itself cites.
6. **Judge.** With a key, the model sees only the retrieved snippets and must quote them verbatim; every quote is checked against the snippet text, and a verdict without a valid quote becomes UNVERIFIED. No evidence means UNVERIFIED without asking the model. Without a key, lexical and number-overlap heuristics decide, marked **low confidence**: SUPPORTED needs an official, cited or user-indexed passage with the claim's figures, dates and names; CONTRADICTED needs such a passage on the same subject stating a different figure or date. Anything weaker is UNVERIFIED.
7. **Fix.** Contradicted numbers are replaced with the official value in the draft's own wording ("4.9 per cent" becomes "3.2 per cent"; "an increase of 4.7%" becomes "4.7 percentage points") and the source is appended. Other fixes come from the LLM judge (only with a valid quote), or from the evidence passage when it holds exactly one candidate figure or date.
8. **Report.** The headline (v0.5.3) leads with what was checked against data: "12 claims checked against official data · 1 wrong · 40 need a source you should cite" (illustrative numbers); the split ("1 wrong · 11 supported · 40 couldn't check · 300 skipped") follows it. "Needs a source" means no official dataset in TruthLens covers the claim; it is not a finding that the claim is wrong, and the list of those claims downloads as a CSV ("Claims to cite" in the web app, `-f cite` on the CLI, `format=cite` on `/render` and `/jobs/{id}/result`). With fewer than 5 checked claims no score is shown as the headline number. Verified score = confidence-weighted SUPPORTED ÷ checked claims (supported + partly + contradicted); "couldn't check" (UNVERIFIED) and opinions are shown separately and are not in the score. A banner lists sources unreachable during the run and how many claims that affected. HTML with the draft highlighted sentence by sentence and an evidence side panel; Markdown; JSON (includes the v0.1 `findings` list); annotated `.docx`.

## Where the evidence comes from

Full list with endpoints, limits and live status: [`docs/SOURCES.md`](SOURCES.md). In short (live status from our network on 1 Nov 2026, and 2 Nov 2026 for the v0.4 sources, no keys):

| Source | What it gives | Key | Live |
|---|---|---|---|
| **MoSPI eSankhyiki** (`api.mospi.gov.in`) | PLFS and National Accounts (curated values first, live values fill gaps), plus discovery across HCES, NFHS, gender statistics, AISHE, UDISE+, EnviStats, Time Use Survey and IIP | No | ✅ |
| **data.gov.in** (`api.data.gov.in`) | a local index of the catalogue (`truthlens datagov sync`), then rows from the matching resources, newest release first; hand-mapped resources in `truthlens.toml` still work | free key for rows | ❌ **not live-verified**: not reachable from our network (proxy 502, Akamai 503); tested with synthetic fixtures only |
| **PIB** | current English press releases from the feed, fetched and quoted | No | ✅ (no search: only releases in the current feed) |
| **Lok Sabha, Rajya Sabha** | questions and answers from sansad.in and the Rajya Sabha API, quoted from the answer PDFs | No | ✅ (the OpenSansad archive on Hugging Face is unreliable: 500s and timeouts) |
| **Official reports** | Economic Survey, Budget and MoSPI documents found on their listing pages | No | ✅ |
| **OpenAlex, Crossref** | research abstracts for study claims; DOI checks for citations | No | Crossref ✅; OpenAlex fixture-only (HTTP 429 on our network) |
| **RBI** (`rbi.org.in`) | current policy rates, CRR, SLR, FBIL reference rates; forex reserves and bank credit/deposit growth from the latest Weekly Statistical Supplement | No | ✅ (DBIE not used: encrypted session API) |
| **CEA** (`cea.nic.in`) | installed capacity by state, all-India peak demand met, energy supplied, generation, PLF (latest month) | No | ✅ |
| **PPAC** (`ppac.gov.in`) | crude and product imports/exports, product consumption by financial year, Delhi retail fuel prices | No | ✅ |
| **Jal Jeevan Mission** (`ejalshakti.gov.in`) | tap-water connections and rural households by state | No | ✅ |
| **NDAP** (NITI Aayog) | catalogue only: the dataset to cite (a pointer, never evidence). Undocumented endpoint (the one the NDAP site calls itself), so it can change without notice | No | catalogue ✅ (re-checked 3 Nov 2026). The v0.4 "data rows with your token" path was never verified and was removed in v0.5.3 |
| **arXiv, Semantic Scholar, Shodhganga** | research abstracts and theses for study claims; arXiv ids and DOIs in citations | No (`S2_API_KEY` optional) | arXiv ✅; Semantic Scholar **not live-verified** (HTTP 429; synthetic hits); Shodhganga **not live-verified** (JavaScript bot challenge; synthetic answer) |
| **World Bank WDI** | secondary figures when no Indian official value exists | No | ✅ |
| **Curated snapshot** | 127 hand-read official values with vintages, for offline use and the data-trap rules | No | bundled |
| **Your documents** | `truthlens index ./reports` or `--url` | No | local |
| **Web search** | Brave, Tavily, Serper, official domains ranked first | Yes | not tested with keys |

Sources marked **not live-verified** are listed by `truthlens doctor`, and evidence from them carries an "unverified source" tag in the reports and the web app. Offline, DOIs are checked against a small shipped cache of recorded Crossref/OpenAlex/arXiv records ("citation exists (offline cache)"); any other DOI is "can't check offline", never "fake".

Not built: India-WRIS and HMIS (not reachable from our network) and RBI DBIE. CGWB: only the State-level 2025 assessment figures are bundled (v0.5.2); district and block figures are not. Research papers never decide an official-statistics figure: for a figure routed to official data, paper records are shown as context but kept out of the judge.

### How citing works

Each finding quotes the passage or table row that decided it. Parliament answers are cited with house, question number and type, subject, answer date and ministry ("Lok Sabha Unstarred Question No. 6289 (Restructuring of Jal Jeevan Mission), answered on 2 April 2026 by the Ministry of Jal Shakti"); the header is part of the quoted evidence, so a claim about the wrong house, date or ministry can be checked against it. Table rows are quoted field by field with the dataset title and publisher. Every evidence item shows its source type and a "data as of" date, links to the source, and has a copy-citation button in the web app that copies publisher, title, source type, page, date and URL as one line.

### Freshness

A figure is checked against the newest data that fits it. When the claim names no period, the latest period in the table is the reference; when several data.gov.in releases of a table match, the newest wins. A figure that matches an older release or period while the newer one differs comes back PARTLY SUPPORTED with a **Superseded** notice that gives the newer value, and the suggested fix uses it. The curated snapshot keeps vintages, so a figure from a revised estimate or an old base year is flagged the same way.

Live test log: [`docs/SMOKE_TEST.md`](SMOKE_TEST.md).

## India statistics pack (the deterministic number checker)

Inherited from v0.1 and extended with live MoSPI data. It covers 16 indicators: real and nominal GDP (growth and level), CPI and WPI inflation, PLFS unemployment and LFPR (usual status and CWS; youth and female variants), the Union fiscal and revenue deficits (BE, RE, Actuals), population (Census 2011), NFHS stunting, wasting and underweight, and IIP growth. State-level and rural/urban PLFS figures are now checked live. Run `truthlens indicators`. The registry with aliases, tolerances and trap rules is [`truthlens/data/indicators.yaml`](../truthlens/data/indicators.yaml).

| Trap | What TruthLens catches |
|---|---|
| Old base series | 6.5% for 2024-25 is the 2011-12-base estimate; the 2022-23 base gives 7.2% |
| Revised estimate | a figure matching an earlier, since-revised vintage |
| PLFS status | 4.9% is the CWS figure; usual status is 3.2% |
| % vs percentage points | "an increase of 4.7%" when the rate rose 4.7 points |
| lakh/crore vs million/billion | ₹157.4 billion is off by 100×: the deficit was ₹15,74,431 crore |
| FY vs calendar year, BE/RE/Actuals, registrations vs beneficiaries, survey vs admin data | see v0.1 notes in `CHANGELOG.md` |

On the 2026 revisions: MoSPI moved GDP to a 2022-23 base (27 Feb 2026, revised again in NAS 2026 on 31 Aug 2026), CPI to 2024=100 (12 Feb 2026) and IIP to 2022-23 (1 June 2026, re-released with an Output-PPI deflator on 29 June 2026). The curated values were read from the official documents on 1 Nov 2026; [`scripts/build_dataset.py`](../scripts/build_dataset.py) documents each source.

## Accuracy and safety, honestly

`pytest` runs fully offline: 557 tests (v0.7.0, Linux, 4 Nov 2026, fresh `git archive` copy in a clean environment: 552 pass and 5 skip on Python 3.10, 3.11 and 3.12 without optional extras (4 need the `mcp` package, 1 needs the downloaded meaning model); with the `meaning` extra and its model on Python 3.12, 553 pass and 4 skip). The meaning tests use a tiny bag-of-words embedder, so they need no download and no numpy. Every external source is a recorded response (World Bank, MoSPI, Crossref, PIB, sansad.in, Rajya Sabha, Economic Survey, one OpenAlex search; v0.4: RBI, CEA, PPAC, JJM, the NDAP catalogue, arXiv, Semantic Scholar's 429s, Shodhganga's bot-challenge page) or, where no key, account or connection was available, a fixture written in the provider's documented format (data.gov.in, Brave, Serper, the LLM APIs; v0.4: Semantic Scholar hits, a Shodhganga OpenSearch answer). [`tests/fixtures/SYNTHETIC_FIXTURES.md`](../tests/fixtures/SYNTHETIC_FIXTURES.md) says which is which.

### v0.5.3 (real documents)

Run on five real, public state water-policy documents (Karnataka 2022, Maharashtra 2019, Orissa 2007, Kerala State
Planning Board, Andhra Pradesh 2025 rural O&M), Quick then Deep, 3 Nov 2026, no keys:

- **False alarms:** v0.5.2 Deep called 7 statements wrong. All 7 were false: a contents entry, merged PDF columns, and
  State or city figures compared with all-India rows. v0.5.3 calls **0** wrong.
- **Settled against data:** 2 of 1,058 checkable claims, both partly supported and both right (Karnataka's area and
  Maharashtra's population, Census 2011). **0 unsafe SUPPORTED.** On these documents TruthLens mostly tells you what
  needs a source (`-f cite`); it does not verify them.
- **Why (200 hand labels):** of what v0.5.2 called checkable, 4% can be checked against an official dataset, 9% are
  State programme figures, 12% need a citation and 75% are not claims at all.
- **Not-a-claim filter, blind held-out** (100 new claims, labelled before the filter ran): 39 of 71 non-claims set
  aside, 1 of 29 real claims wrongly dropped. A label transcription slip was found after the first scoring; as first
  transcribed it was 37 of 71 and 3 of 29.
- **Regression (recorded fixtures):** unchanged except adversarial 50/50 (was 48/50); 0 unsafe SUPPORTED everywhere.

Details, per-document before/after and each false contradiction: [`data/realdocs_v053.md`](../data/realdocs_v053.md).

### v0.5.2 (Quick and Deep)

Regression on recorded fixtures is unchanged from v0.5.1 (v4 gave 24/25 in every run on 3 Nov 2026, missing 619, also
with the code before the v0.5.2 descriptive-text change; it gave 25/25 earlier, a known flaky row), 0 unsafe SUPPORTED
everywhere. **Withdrawn as evidence (v0.5.3):** v0.5.2 reported 86/86 known-true claims supported on a "Karnataka rural
water draft". That draft was generated from the same bundled data it was checked against, so the result is circular
and says nothing about real documents; see v0.5.3 above for real documents. The timings on that draft (Quick 1.0 s,
Deep 10.6 s) were measured and stand. See [`CHANGELOG.md`](../CHANGELOG.md) and
[`data/perf_v052.md`](../data/perf_v052.md).

### v0.5.1 (speed)

A 51-claim draft (`tests/fixtures/long_policy_draft.docx`), live, no keys, empty cache: v0.5.0 took 59-84 s, v0.5.1 36-38 s;
with six servers hanging until timeout (simulated) v0.5.0 took 377.6 s and v0.5.1 60.2 s, with the same verdicts. A
whole-document live budget (60 s by default) bounds a check; claims that run out of time are marked, never counted as
supported or wrong. Regression results are unchanged. Numbers and method: [`data/perf_v051.md`](../data/perf_v051.md).

### v0.5.0

The clean estimate is still the v0.4.1 held-out set's first run (below): **live 22/25, offline 20/25, 0 unsafe SUPPORTED**. v0.5 fixed misses found on that set and in live runs, so the numbers after the fixes are tuned, **not a clean estimate**: held-out live 24/25 (723 missed; [run](../data/testset_v041_heldout_live_v05.md)), offline 21/25, recorded fixtures 24/25, 0 unsafe SUPPORTED.

| Regression on recorded fixtures, after the final 619 fix | Result | Unsafe SUPPORTED |
|---|---|---|
| v0.1 numbers / v0.1 hold-out | 64/65 / 25/25 | — |
| v0.2 dev | 43/45 | 0 |
| v0.2 hold-out | 21/28 | 0 |
| Adversarial (50) | 48/50 | 0 |
| India v3 | 24/25 | 0 |
| India v4 | 25/25 | 0 |

| Live, 2 Nov 2026, no keys, once each (before the final 619 fix) | v0.4.1 live | v0.5 live | Unsafe SUPPORTED (v0.5) |
|---|---|---|---|
| India v3 ([run](../data/testset_v3_india_live_live_v05.md)) | 23/25 | 23/25 | 0 |
| India v4 ([run](../data/testset_v4_india_sources_live_v05.md)) | 22/25 | 21/25 | **1** (619) |

The India v4 live run called "The repo rate was 6.5%." (619) SUPPORTED: the first 619 fix did not reach the full pipeline. It is now fixed and tested; re-checked live on its own it is PARTLY SUPPORTED (label UNVERIFIED, so still a miss, not unsafe). The full v4 live set was not re-run after the fix. An adversarial probe of the v0.5 features (16 tests) found six gaps, all fixed. Details: [`CHANGELOG.md`](../CHANGELOG.md).

### v0.4.1: clean estimate first

A new 25-sentence India set ([`data/testset_v041_heldout.jsonl`](../data/testset_v041_heldout.jsonl): period changes, opinion-hedged facts, rounding, acronyms) was labelled and committed **before** it was run, run once live and once offline, and **not tuned on**:

| v0.4.1 held-out set, first run | Correct | Unsafe SUPPORTED |
|---|---|---|
| live sources, no keys, 2 Nov 2026 ([run](../data/testset_v041_heldout_live_first.md)) | **22/25 (88%)** | **0** |
| offline ([run](../data/testset_v041_heldout_offline_first.md)) | **20/25 (80%)** | **0** |

Its misses are left in: the acronym "CRR" alone does not reach the RBI source; "Female LFPR on usual status" is read as the all-persons series, so correct figures are called wrong (a false contradiction); a month-on-month comparison (peak demand August vs July) has no series. Re-runs of the older sets on v0.4.1: adversarial set with 16 new period-change cases 47/50 on the first run (48/50 after one fix), India v3 live 23/25, India v4 live 22/25 (three RBI weekly figures have since moved to a newer week), v0.2 dev 43/45, v0.2 hold-out 21/28, all with 0 unsafe SUPPORTED except one pre-existing case on recorded fixtures. Everything is in [`data/regression_v041.md`](../data/regression_v041.md); the fixes and their tests are in [`docs/REVIEW_V041.md`](REVIEW_V041.md).

### Earlier sets

All results below are **without any key** (rule-based extraction, heuristic judge). Each set was labelled before the engine was run on it. "Unsafe SUPPORTED" means a false or unverifiable sentence was called SUPPORTED, the error that matters most.

| Set | Sentences | First run | Unsafe SUPPORTED |
|---|---|---|---|
| v0.4 India sources ([`data/testset_v4_india_sources.jsonl`](../data/testset_v4_india_sources.jsonl)): RBI, CEA, PPAC, JJM, NDAP, arXiv, Shodhganga; labelled before the first run | 25 | **18/25 live** ([first run](../data/testset_v4_india_sources_live_first.md)), 5/25 without live sources | **1** live ("The repo rate was 6.5%." called SUPPORTED) |
| v0.3 adversarial ([`data/testset_v3_adversarial.jsonl`](../data/testset_v3_adversarial.jsonl)): negation, superlatives, causal and comparison claims, direction words, prompt injection, private-address citations | 34 | **30/34 (88%)**; 32/34 on v0.4 | **0** (v0.4: 0) |
| the same set on the v0.2 engine, before the security and correctness fixes | 34 | 8/34 (24%) | 9 |
| v0.3 India live set ([`data/testset_v3_india_live.jsonl`](../data/testset_v3_india_live.jsonl)): MoSPI datasets, Census, Parliament, PIB, Budget, a research paper | 25 | **17/25 live**, 10/25 offline; v0.4 engine: 23/25 live ([run](../data/testset_v3_india_live_live_v04.md)) | 0 |
| v0.2 all claims ([`data/testset_v2.jsonl`](../data/testset_v2.jsonl)), after tuning on it | 45 | 43/45 | 0 |
| v0.2 hold-out ([`data/testset_v2_holdout.jsonl`](../data/testset_v2_holdout.jsonl)) | 28 | 18/28 first run; 21/28 now (looked at since, so not a clean estimate) | 0 |
| v0.1 numbers ([`data/testset.jsonl`](../data/testset.jsonl)) / hold-out | 65 / 25 | 65/65 / 20/25 | — |

**v0.4, after the first run.** The v0.4 India-sources set was then used to tune the new sources on its seven misses: forex reserves and gold (wrongly CONTRADICTED), bank credit growth (left UNVERIFIED, now CONTRADICTED), total petroleum consumption (wrongly CONTRADICTED), the unsafe "The repo rate was 6.5%." (now UNVERIFIED with today's rate, because an undated past-tense figure may be an older one), an NDAP figure with no data rows (now UNVERIFIED, with the dataset to cite), and a "study" citing an arXiv id that does not exist (wrongly CONTRADICTED, now UNVERIFIED). Also in v0.4: several figures in one sentence are each matched on their own clause, and research papers never decide an official-statistics figure. It now scores 25/25 live with 0 unsafe SUPPORTED ([after tuning](../data/testset_v4_india_sources_live_after_tuning.md)); that is a tuned number, **not a clean estimate**. Without live sources it scores 4/25: the new sources hold current values that the bundled snapshot does not have, so offline they correctly fall back to UNVERIFIED. On recorded fixtures, after the v0.4 fixes: adversarial 32/34 (0 unsafe), v0.2 dev 43/45, v0.2 hold-out 21/28, all with 0 unsafe SUPPORTED.

After the first runs: the India live set reached 24/25 once the live sources were tuned on it ([`data/testset_v3_india_live_live_after_tuning.md`](../data/testset_v3_india_live_live_after_tuning.md)), which is no longer a clean estimate. The adversarial set scores 32/34 after an evaluator fix (multi-sentence items are now scored by their most severe sentence, not the first one; see [`data/testset_v3_adversarial_first_run.md`](../data/testset_v3_adversarial_first_run.md)). The headline numbers stay the first runs. No injected instruction changed a verdict, and no private or link-local address was fetched.

What is still weak:

- **Wrong-actor claims without a key.** "Released by the Reserve Bank of India" when it was another body, or "implemented by the Ministry of Education" for a Jal Shakti scheme: the heuristic judge catches these only when the quoted evidence names the right actor in a recognisable way (Parliament headers help). Otherwise they come back UNVERIFIED, not CONTRADICTED.
- **Limits of the rule judge.** It compares words, figures and dates. It cannot follow paraphrase, long sentences with several facts (judged as one claim), or reasoning across two passages. "Supported" from the rule judge is always marked low confidence and counts 0.3 in the score.
- **Coverage.** A claim is only as checkable as the sources that answer that day: data.gov.in is untested live, PIB has no search, the Hugging Face archive and OpenAlex were unreliable from our network; Semantic Scholar answered only HTTP 429 and Shodhganga only a bot challenge. On real state policy documents most factual sentences have no official dataset in TruthLens (see v0.5.3 above).
- **Snapshot sources.** RBI, CEA and JJM publish the current value. A figure about an earlier date that the draft does not date is reported UNVERIFIED with today's value, not checked. When an older passage states the undated figure, it is at most PARTLY SUPPORTED, with today's value named (v0.5; only when RBI's page answers in time).
- **Month-on-month comparisons** ("peak demand in August was higher than in July") have no series and stay "couldn't check".
- **The web app** is tested with FastAPI's test client and by starting the server; it has not been tested in a browser.
- **The LLM judge has not been measured.** No key was used to build this release.

These sets are small, in-domain and written by the developers. They catch regressions; they do not measure accuracy on real drafts. Regenerate with `python scripts/run_eval.py` (offline) and `python scripts/run_live_eval.py` (live).

## Limitations

- **Without an LLM key**, non-numeric claims are judged lexically (low confidence): entity swaps ("released by RBI" when it was DPIIT) come back UNVERIFIED rather than CONTRADICTED, and paraphrases can be missed. Long sentences with several facts are judged as one claim.
- **Evidence coverage is the ceiling.** With no web-search key and an empty index, most non-numeric claims will be UNVERIFIED. Index the reports your draft relies on (`truthlens index ./reports`) or add a search key.
- **LLM judging is only as good as the retrieved snippets.** The judge must quote them, but it can still misread a quote. Treat medium-confidence verdicts as leads.
- **The India number checker** covers 16 all-India annual series (state-level and rural/urban PLFS when MoSPI is reachable). Quarterly and monthly figures, other states' indicators and US-dollar values fall through to document evidence.
- **MoSPI's API** needs legacy TLS renegotiation (enabled per connection, with certificate checks on). Version 0.2.1 of the official package defaults to a private test address and turns certificate checks off; TruthLens corrects both when you use it. The API is young and may change.
- **PIB** has no key-free search, so only releases in the current English feed are found live; index older ones with `truthlens index --url`. **data.gov.in** needs a free key for rows and a one-time `truthlens datagov sync`; it has not been tested against the live service.
- **Citation checks** read DOI metadata (title, authors, abstract), not paywalled full text. Author-year references need a reference list with a URL or DOI.
- **Word export** adds comments and coloured `[suggested: …]` insertions, not real tracked changes. Legacy `.doc` files and scanned PDFs are not read.
- **v0.6 AI providers** (DeepSeek, Mistral, xAI, Gemini, Moonshot, Qwen, Z.ai, OpenRouter, custom) are untested live; their base URLs and default models come from their documentation as read on 4 Nov 2026 and can change.
- **Share of India and Dated** cover Census 2011 population and area and the CGWB 2025 State figures only, and four boundary changes. Years are read from the sentence or the document's first lines; a document without a year in its first lines gets none.
- **Compare** is a wording comparison of the text the readers extract; it says nothing about meaning, and PDF sentence breaks can hide a match. **Compare by meaning** (v0.7) is similarity of sentence embeddings: about a quarter to a third of its matches and up to half of its "dropped" items were wrong in our hand-check; scanned PDFs are not read (no OCR).
- TruthLens is a checking aid, not an authority. Open the linked source before relying on a verdict.

## Contributing

The most useful contributions are labelled sentences (any claim type) with the evidence that settles them, India indicators with official sources, and retrievers for new official data APIs (each must cache, return URL + verbatim snippet + date, and ship recorded fixtures). See [`CONTRIBUTING.md`](../CONTRIBUTING.md).

```bash
pip install -e ".[dev,api]" && pytest && python scripts/run_eval.py
```

## Acknowledgements

- UI polished using unslop by Damir Sokolovsky (@heydamir), https://github.com/heydamir/unslop (CC BY 4.0)
- Web app design guided by UI UX Pro Max by Next Level Builder, https://github.com/nextlevelbuilder/ui-ux-pro-max-skill (MIT): design system (Swiss minimal, trust palette, academic type pairing), UX guidelines and pre-delivery checklist.
- Motion values (easing curves, durations, reduced-motion and keyboard rules) follow Emil Kowalski's skills, https://github.com/emilkowalski/skills (MIT).
- Final design audit against Impeccable by Paul Bakaus, https://github.com/pbakaus/impeccable (Apache-2.0), and Taste Skill by Leonxlnx, https://github.com/Leonxlnx/taste-skill (MIT).
- `DESIGN.md` follows the DESIGN.md format by Google Labs, https://github.com/google-labs-code/design.md (Apache-2.0).
- Icons drawn from Lucide, https://lucide.dev (ISC).

## License

MIT. See [LICENSE](../LICENSE). Official statistics and documents belong to their publishers; cite the original release.
