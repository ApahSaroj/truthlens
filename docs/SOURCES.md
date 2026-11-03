# Evidence sources

Every source TruthLens reads, how it reads it, and whether it worked from our test network. "Live status" is from
`truthlens doctor --ping` and the live runs on 1 Nov 2026 (v0.3 sources) and 2 Nov 2026 (v0.4 sources), no keys used. Your network may differ: run
`truthlens doctor --ping` to see which sources answer for you.

**Untested live (v0.4.1, updated v0.5.3).** Three data paths have only been tested on synthetic or rate-limited
fixtures, never against the live service from our network: **data.gov.in** (unreachable from our network; synthetic
fixtures), **Semantic Scholar** (HTTP 429 only; synthetic hits) and **Shodhganga** (JavaScript bot challenge;
synthetic OpenSearch answer). A fourth, **NDAP data rows with an "NDAP token"**, was removed in v0.5.3: it was never
verified (no token could be obtained; the row layout was only ever a synthetic sample). `truthlens doctor` lists them, and evidence
from them carries a small **"unverified source"** tag in the reports and the web app. Treat it as a lead.

**Offline citation cache (v0.4.1).** `truthlens/data/offline_citations.json` holds the DOI and arXiv records recorded
from Crossref, OpenAlex and arXiv in `tests/fixtures` (built by `scripts/build_offline_citations.py`; no synthetic
record is used). Offline, a DOI in it is reported "citation exists (offline cache: recorded from … on …)"; any other
DOI is "can't check offline" (the claim is capped at UNVERIFIED and never called fabricated).

**Unreachable-source banner (v0.4.1).** Each report, the CLI summary and the web app list the sources that errored or
timed out during that run and how many claims that affected, so "couldn't check" is not mistaken for "wrong".

Every source fails closed. A source that times out, errors or rate-limits is listed under "Source errors" in the
report and the claim stays UNVERIFIED unless another source decides it. Nothing is guessed to fill the gap.

| Source | Endpoint | Live status (1 Nov 2026) | Key | Limits |
|---|---|---|---|---|
| MoSPI eSankhyiki: PLFS, National Accounts | `https://api.mospi.gov.in/api/plfs/getData`, `/api/nas/getNASData` | ✅ live | none | needs legacy TLS renegotiation (enabled per connection, certificates still checked); curated values are tried first |
| MoSPI eSankhyiki: every listed dataset (HCES, NFHS, gender, AISHE, UDISE+, EnviStats, TUS, IIP) | `/api/<ds>/get<Ds>IndicatorList`, then `/api/<ds>/get<Ds>Records?indicator_code=N&Format=JSON&limit=200&page=N` | ✅ live | none | 200 rows per page (the API refuses more); at most 6 pages per indicator; indicator lists cached 7 days, rows 1 to 7 days |
| data.gov.in catalogue | `https://api.data.gov.in/lists?format=json&notfilters[source]=visualize.data.gov.in&filters[active]=1&sort[updated]=desc&offset=&limit=` | ❌ **not live-verified**: proxy 502 on api.data.gov.in, Akamai 503 on www.data.gov.in from our network (synthetic fixtures only) | optional for the listing | not a documented search API (the parameters are the ones the community `datagovindia` clients send); synced into a local SQLite index with `truthlens datagov sync` |
| data.gov.in resources | `https://api.data.gov.in/resource/{uuid}?api-key=…&format=json&offset=&limit=&filters[field]=value` | ❌ **not live-verified** (as above) | **free `DATAGOVIN_API_KEY`** | rows are matched only when the claim's figure has one clear value column; the key goes to data.gov.in only and is stripped from caches, citations and errors. A public demo key is used only if you set `TRUTHLENS_DATAGOVIN_SAMPLE_KEY=1` (never by default; it is rate-limited and returns at most 10 rows) |
| PIB press releases | English feed `https://pib.gov.in/RssMain.aspx?ModId=6&reg=3&lang=1` (redirects to www.pib.gov.in), then the release pages | ✅ live, English (20 current releases) | none | **no search**: only releases in the current feed are found. PIB's date listing is an ASP.NET postback form that ignored scripted filters; older releases come from Parliament answers, your index (`truthlens index --url`) or web search with a key |
| Lok Sabha questions (recent sessions) | `https://sansad.in/api_ls/question/qetFilteredQuestionsAns?loksabhaNo=18&pageNo=1&pageSize=N&locale=en&keyWord=…`, answer PDFs from `sansad.in/getFile/…` | ✅ live | none | keyword is matched as a phrase; answer text is read from the PDF (at most 2 PDFs per claim) |
| Lok Sabha archive (16th to 18th Lok Sabha, to March 2026) | OpenSansad dataset via Hugging Face: `https://datasets-server.huggingface.co/search?dataset=opensansad/lok-sabha-qa&…` | ⚠️ unreliable: HTTP 500 and read timeouts in our runs | none | short 12-second timeout so a slow answer does not hold up the check |
| Rajya Sabha questions | `https://integration.rajyasabha.digital/rsdebate/api/question/search-questions?searchParam=…&searchOn=title&matchesOn=allWords&page=1&size=N`, PDFs from `bucketapi.rajyasabha.digital` | ✅ live | none | searches question titles only; answer text comes from the PDF |
| Government reports (Economic Survey, Budget, MoSPI press releases) | listing pages `https://www.indiabudget.gov.in/economicsurvey/`, `https://www.indiabudget.gov.in/`, `https://www.mospi.gov.in/press-release` (change under `[reports] listing_pages`) | ✅ live | none | only PDFs on the official allow-list whose link text matches the claim; some statistical-appendix tables are rotated PDFs whose extracted text is unusable |
| OpenAlex (research papers) | `https://api.openalex.org/works?search=…&per-page=N&select=…` | ⚠️ fixture-only: HTTP 429 (daily budget for our network used up) | none; optional `OPENALEX_API_KEY` raises the budget | abstracts only; used for claims that cite or describe a study |
| Crossref / OpenAlex DOI lookup | `https://api.crossref.org/works/{doi}`, then `https://api.openalex.org/works/doi:{doi}` | ✅ Crossref live | none | metadata and abstract, not paywalled full text; a DOI unknown to both is flagged as possibly fabricated |
| World Bank WDI | `https://api.worldbank.org/v2/country/IND/indicator/{code}?format=json` | ✅ live | none | secondary source, used only when no Indian official value is found |
| Curated official snapshot | `truthlens/data/india_official.json` (bundled) | bundled | none | 127 hand-read values with vintages; offline fallback and the basis of the data-trap rules |
| Your documents | local SQLite FTS5 index (`truthlens index ./folder` or `--url`) | local | none | official-domain allow-list for URLs; private and local addresses are refused |
| Web search | Brave, Tavily, Serper | not tested live with keys | your key | results re-ranked with official domains first; top official hits are fetched so the evidence is a verbatim passage |

## v0.4 sources (probed live on 2 Nov 2026, no keys)

Every request below goes through the guarded fetcher (`net.safe_get` / `net.safe_post`): the address is checked
before any byte is sent and at every redirect hop; a POST never follows a redirect. Each source caches on disk and
fails closed: when it is down, the stale cache is used if there is one and the failure is listed under "Source
errors"; the claim stays UNVERIFIED unless another source decides it.

| Source | Endpoint | Live status (2 Nov 2026) | Key / token | Limits |
|---|---|---|---|---|
| **NDAP catalogue** (NITI Aayog) | `GET https://loadqa.ndapapi.com/v1/search?query=…&search=Variables,DatasetInfo&domain=ndap` with the site's `Origin`/`Referer` headers (the call ndap.niti.gov.in's own JavaScript makes) | ✅ live (2 Nov 2026; re-checked 3 Nov 2026: a search for "ground water resources" returned CGWB datasets) | none | not a documented public API (the host is named "loadqa"; it can change or stop without notice); answers `{"Message": "Invalid Request"}` without the site headers. A catalogue hit is a **pointer** ("Dataset to cite"), never evidence: it is not shown to the judge and cannot make a claim SUPPORTED. Cached 7 days |
| **RBI current rates** | `https://www.rbi.org.in/` ("Current Rates" box: policy repo, SDF, MSF, bank rate, CRR, SLR, FBIL reference rates) | ✅ live | none | current values only (snapshot rule: an undated, past-tense figure that differs is UNVERIFIED with the current value, never CONTRADICTED); cached 6 h |
| **RBI Weekly Statistical Supplement** | `https://www.rbi.org.in/pressreleases_rss.xml` → latest "Bulletin Weekly Statistical Supplement - Extract" release | ✅ live | none | forex reserves (total, FCA, gold) for the week named; scheduled commercial banks' credit and deposit growth (y-o-y); only links on www.rbi.org.in are followed |
| RBI DBIE | `data.rbi.org.in` | ❌ not used | — | its gateway needs a browser session token and RSA/AES-encrypted payloads; not a documented public API |
| **CEA** (Ministry of Power) | `https://cea.nic.in/api/dashboard/installed-capacity`, `/api/power-sector-performance`, `/api/dashboard/energy-supply-position` (the JSON calls the CEA home page makes) | ✅ live | none | latest month only; a national total TruthLens derives by adding states is never used to contradict a figure; cached 24 h |
| **PPAC** (Ministry of Petroleum) | `POST https://ppac.gov.in/AjaxController/getImportExports`, `POST …/getConsumptionPetroleumProductsData`; home page "PPAC Tracker" | ✅ live | none | crude/product imports and exports, product consumption by financial year, Delhi retail prices; product names must match (diesel is never checked against petrol); cached 24 h |
| **Jal Jeevan Mission** | `POST https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx/Bind_table_graph` (the dashboard's state table; its `encodeTxt` parameter encoding is reproduced) | ✅ live | none | households with tap connections, rural households, per cent, by state; an all-India per cent computed from state rows never contradicts a figure; cached 24 h |
| India-WRIS | `https://indiawris.gov.in/wris/` | ❌ not reachable from our network (proxy error) | — | not built in v0.4; listed in `doctor --ping` and has a badge only |
| CGWB | bundled file (v0.5.2) | bundled, no network | — | State-level 2025 Dynamic Ground Water Resources figures (recharge, extractable resource, extraction, stage of extraction) bundled in `truthlens/data/state_data.json`; no district or block figures. The NDAP catalogue also names CGWB datasets to cite |
| HMIS | `https://hmis.mohfw.gov.in/` | ❌ not reachable from our network (proxy error) | — | not built in v0.4; listed in `doctor --ping` and has a badge only |
| **arXiv** | `GET https://export.arxiv.org/api/query?search_query=all:…&max_results=N`; `?id_list=<id>` for citations like `arXiv:1908.00255` | ✅ live | none | Atom XML; requests are serialised and spaced 3 s apart (arXiv's guidance); cached 7 days |
| **Semantic Scholar** | `GET https://api.semanticscholar.org/graph/v1/paper/search?query=…&fields=…`; `/paper/DOI:<doi>` as a third DOI registry after Crossref and OpenAlex | ⚠️ **not live-verified** (fixture-only): HTTP 429 on every call from our network | none; optional `S2_API_KEY` (sent as `x-api-key`) | backs off 1 s then 2 s (Retry-After honoured, capped at 5 s), then fails closed with the 429 recorded; tests use **synthetic** search and DOI records |
| **Shodhganga** (INFLIBNET theses) | `GET https://shodhganga.inflibnet.ac.in/open-search/?query=…&format=atom&rpp=N` (DSpace OpenSearch) | ❌ **not live-verified** (fixture-only): every URL on the host answered a JavaScript proof-of-work bot challenge (Anubis) | none | the challenge page is detected and the source fails closed; tests use a **synthetic** OpenSearch Atom answer |

**Papers never decide official statistics.** A research paper or thesis (OpenAlex, Semantic Scholar, arXiv,
Shodhganga) can support a *research* claim through a verbatim abstract quote. For a figure routed to official data
that does not itself present a study finding ("India imported 246.6 million tonnes of crude oil in 2025-26"), paper
records are kept out of the judge and the claim says so: "research papers are not used to confirm or contradict
official data". A paper the draft cites (DOI or arXiv id) is still checked as a citation.

**Several figures in one sentence.** Each figure is matched on its own clause ("the repo rate is 5.5% and the CRR is
3%": 3% is compared with the CRR only). The sentence is SUPPORTED only when every figure is; a figure no source
decided keeps it at PARTLY SUPPORTED, and any mismatch makes it CONTRADICTED.

## How a claim is routed

`truthlens/planner.py` reads the claim's figure, geography, period and unit:

- **a figure**: official data first. v0.4: the ministry source whose subject the claim names (RBI, CEA, PPAC, JJM),
  then the bundled Census 2011 / CGWB 2025 / NFHS-5 state data, the MoSPI eSankhyiki catalogue and the data.gov.in
  catalogue index (with a key; untested live), then
  Parliament answers, which often state scheme and state-level figures; the NDAP catalogue is searched for the dataset
  to cite;
- **a scheme, mission, ministry or policy statement**: PIB releases and Parliament answers;
- **a report** (Economic Survey, Budget, CAG, census, bulletin): the official report listings;
- **a study or thesis**: OpenAlex, Semantic Scholar and arXiv abstracts (Shodhganga when a thesis is named), plus
  Crossref, OpenAlex, Semantic Scholar and arXiv for cited DOIs and arXiv ids;
- **always**: your document index; web search when a key is set.

Sources run in parallel within a per-claim time budget (25 seconds by default). The report lists, for every claim,
which sources were consulted and what each returned.

## Freshness

- **Data as of.** Every evidence item carries the release, update or retrieval date of its source: the dataset's
  `updated_date` on data.gov.in, the retrieval date and latest period in the API for MoSPI, the answer date for
  Parliament, the release date for PIB and reports.
- **Newest first.** When several data.gov.in releases of the same table match, the newest is the reference. When a
  claim names no period, the latest period in a MoSPI or data.gov.in table is the reference.
- **Superseded.** A figure that matches an older release or period while the newer one differs is PARTLY SUPPORTED
  with a "Superseded" notice that gives the newer value; the suggested fix uses the newer value.

## Keys, in short

No key is needed for MoSPI, PIB, Parliament, reports, Crossref, World Bank, OpenAlex, RBI, CEA, PPAC, JJM, the NDAP
catalogue, arXiv or Semantic Scholar (an optional `S2_API_KEY` avoids its shared-pool 429s). data.gov.in rows need a free
key (`DATAGOVIN_API_KEY`, or the data.gov.in field in the web app, or the `X-DataGovIn-Key` header / `datagovin_key`
field on the API, each used for one check only). The catalogue index has to be synced once on the machine that runs
TruthLens (`truthlens datagov sync`); until then the data.gov.in matcher reports "catalogue index empty".

## Recorded and synthetic test fixtures

`pytest` never reaches the network. Recorded responses (MoSPI, sansad.in, Rajya Sabha, PIB, Economic Survey, one
OpenAlex search; v0.4: RBI, CEA, PPAC, JJM, NDAP catalogue, arXiv, Semantic Scholar 429s, the Shodhganga challenge
page) and synthetic ones (data.gov.in, Brave, Serper, LLM APIs; v0.4: Semantic Scholar hits, a
Shodhganga OpenSearch answer) are listed in
[`tests/fixtures/SYNTHETIC_FIXTURES.md`](../tests/fixtures/SYNTHETIC_FIXTURES.md).
