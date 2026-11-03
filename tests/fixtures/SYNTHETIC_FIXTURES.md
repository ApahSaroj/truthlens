# Which fixtures are recorded and which are synthetic

Recorded from the live services on 1 Nov 2026 (no keys needed):
- `wb_*.json` World Bank WDI (v0.1)
- `mospi_responses.json` MoSPI eSankhyiki API (PLFS, NAS) responses keyed by request URL
- `crossref/*.json` Crossref works record; the two fake DOIs used in the test sets returned HTTP 404 from both Crossref and OpenAlex
- `docs/*` five PIB press releases (HTML body only) and the MoSPI NAS 2026 press-release PDF
- `web_tavily.json` a Tavily search response (keyless mode)

Synthetic, written in each provider's documented response format because no key was available:
- `web_brave.json`, `web_serper.json`, `datagovin_resource.json`, and the LLM responses built inside `tests/test_v2.py`.
The data.gov.in resource id in the synthetic fixture is a placeholder, not a real resource.

## v0.3

- `datagovin/lists_page1.json`, `datagovin/resource_a1_2025.json`, `datagovin/resource_a2_2026.json`: **synthetic**.
  data.gov.in was unreachable from our test network (proxy 502 on api.data.gov.in, Akamai 503 on www.data.gov.in), so these
  are written in the format the community clients parse: /lists records with `index_name`, `title`, `desc`, `org_type`,
  `org[]`, `sector[]`, `source`, `field[{id,name,type}]`, `created_date`, `updated_date` (datagovindia 1.0.2,
  `compile_record_info`), and /resource responses with `records`, `total`, `count`, `title`, `org`, `updated_date`.
  The values are invented for the tests and are marked "(synthetic test fixture)" in their titles.
- `live/recorded.json`: **recorded** live responses (1 Nov 2026) from api.mospi.gov.in, sansad.in, integration.rajyasabha.digital,
  bucketapi.rajyasabha.digital, datasets-server.huggingface.co, pib.gov.in, indiabudget.gov.in and mospi.gov.in, captured by
  `scripts/record_session.py` during `scripts/run_live_eval.py`. Transient failures (HTTP 500 from Hugging Face, HTTP 429 from
  OpenAlex) were recorded too; one of each is kept as an error example.
- `live/openalex_search_jjm.json`: **recorded** OpenAlex `/works?search=` response (1 Nov 2026), fetched from a different
  network because OpenAlex rate-limited ours (HTTP 429); trimmed to one result.

## v0.4

- `live/recorded_v04.json`: **recorded** live responses (2 Nov 2026) captured by `scripts/run_live_eval.py --record
  recorded_v04.json`: the RBI home page, press-release RSS and Weekly Statistical Supplement extract; the CEA dashboard
  JSON; PPAC import/export and consumption JSON and its home page; the Jal Jeevan Mission dashboard table; NDAP
  catalogue searches (`loadqa.ndapapi.com/v1/search`); arXiv Atom answers; Semantic Scholar HTTP 429 answers (the only
  thing our network ever got from it); the Shodhganga bot-challenge page; and the v0.3 sources touched by the v0.4 sets.
- `v04/ndap_details_synthetic.json`: removed in v0.5.3 together with the NDAP token path it tested (never verified).
- `v04/s2_search_synthetic.json`, `v04/s2_doi_synthetic.json`: **synthetic** Semantic Scholar Graph API search hit and
  DOI record in the documented response format (our network only ever got HTTP 429). DOIs use the `10.5555` test prefix.
- `v04/shodhganga_opensearch_synthetic.xml`: **synthetic** DSpace OpenSearch Atom answer (Shodhganga served a
  JavaScript bot challenge for every URL on 2 Nov 2026).
- In `tests/test_v4_sources.py`, the NDAP catalogue answer for the Rajasthan groundwater query is the **recorded** Punjab
  answer reused (the search result does not depend on the state named; dataset 2227 is state-wise).

