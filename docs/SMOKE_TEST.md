# Live smoke tests

No API keys were used. Each run is from our test network; yours may differ (`truthlens doctor --ping`).

## v0.3, Sun 1 Nov 2026, evening IST

`truthlens doctor --ping`:

| Source | Result |
|---|---|
| World Bank | ✅ HTTP 200 |
| MoSPI API (PLFS) | ✅ HTTP 200 |
| MoSPI catalogue (HCES indicator list) | ✅ HTTP 200 |
| data.gov.in | ❌ ProxyError (502 Bad Gateway from the proxy to api.data.gov.in); www.data.gov.in answered Akamai 503 earlier the same day. Untested live |
| PIB English feed | ✅ HTTP 200 (English, after a 301 to www.pib.gov.in) |
| Lok Sabha (sansad.in) | ✅ HTTP 200 |
| Rajya Sabha | ✅ HTTP 200 |
| Lok Sabha archive (OpenSansad on Hugging Face) | ❌ HTTP 500 (read timeouts during the sample run) |
| OpenAlex | ❌ HTTP 429, daily budget for this network used up |
| Crossref | ✅ HTTP 200 |
| Economic Survey listing | ✅ HTTP 200 |

Sample run, live sources (the local index held four official documents fetched in earlier live runs: the NAS 2026
press-release PDF and three PIB releases):

```
python -m truthlens.cli check samples/sample_policy_note.docx -f html -o samples/sample_report_v3.html
python -m truthlens.cli check samples/sample_policy_note.docx -f json -o samples/sample_report_v3.json
TruthLens: verified score 27% · 18 checkable claims · 8 contradicted · 0 partly · 3 unverified · 7 supported (3 low-confidence) · 1 opinions skipped · 1 citation(s) not found · 6 suggested fixes
```

About 40 seconds for the first run. The files in `samples/` are from a second run with warm caches: same counts, but
the Jal Jeevan Mission extension claim quoted a PIB release instead of the first run's Lok Sabha answer (No. 6289,
2 April 2026), because live sources answer within a time budget and the evidence pool can differ between runs. Source errors recorded in the report: the Hugging Face archive timed
out and OpenAlex answered 429; both failed closed.

Three cited findings from that run:

| Claim in the draft | Verdict | Evidence (source type, data as of) |
|---|---|---|
| "In 2024-25, real GDP growth moderated to 6.5%" | CONTRADICTED, high | MoSPI, NAS 2026 press release: real GDP growth 7.2% (2024-25, base 2022-23); 6.5% is the old 2011-12 base. Data as of 31 August 2026 |
| "the fiscal deficit for 2024-25 was ₹157.4 billion" | CONTRADICTED, high | Official data, Union Budget (Budget at a Glance): ₹15,74,431 crore (Actual), a lakh/crore vs billion slip. Data as of 1 February 2026 |
| "The Union Government has extended Jal Jeevan Mission till December 2028" | SUPPORTED, low (word match, no AI judge) | PIB, "Jal Jeevan Mission Clocks Seven Years of Rural Transformation": "the Union Government has extended Jal Jeevan Mission till December 2028". Data as of 14 August 2026. Also listed: Lok Sabha Unstarred Question No. 3018 (Extension of Jal Jeevan Mission), Ministry of Jal Shakti, answered 6 August 2026 |

## v0.2, Sun 1 Nov 2026, 8:05 PM IST

Run with `python scripts/smoke_live.py`.

| Check | Result | Detail | Seconds |
|---|---|---|---|
| MoSPI via official mospi-esankhyiki package | ✅ worked | mospi-esankhyiki 0.2.1: PLFS UR 2023-24 all-India PS+SS = 3.2% (package default base_url was 'http://10.24.89.9:5000'; pointed at https://api.mospi.gov.in with TLS verification on) | 1.6 |
| MoSPI via TruthLens REST client | ✅ worked | REST: PLFS UR 2023-24 = 3.2%; NAS GDP 2025-26 constant prices = ₹32,470,100 crore (Provisional Estimates); https://api.mospi.gov.in/api/plfs/getData?indicator_code=3&frequency_code=1&year_type_code=1&year=2023-24&state_code=99&gender_code=3&age_code=1&sector_code=3&weekly_status_code=1&religion_code=1&social_category_code=1&education_code=0&Format=JSON | 2.0 |
| World Bank WDI API | ✅ worked | SP.POP.TOTL India 2025 = 1,463,865,525 (WDI last updated 2026-10-08) | 0.2 |
| PIB press release fetch + index | ✅ worked | indexed 9 passages, release date 2026-03-23, title “Government has introduced a Model Context Protocol server to facilitate linking ”; top hit: “The Beta version of the MCP server which included 7 key statistical products (such as the Periodic Labour Force Survey, …” | 3.2 |
| PIB RSS feed | ✅ worked | 20 items, language served: hi; first: केन्द्रीय गृह एवं सहकारिता मंत्री श्री अमित शाह ने आज चंडीगढ़ प्रशासन की 258 करो | 1.3 |
| Crossref / OpenAlex DOI lookup | ✅ worked | 10.1038/s41586-020-2649-2 -> found via crossref: “Array programming with NumPy” (2020); fake DOI -> not_found | 0.7 |
| data.gov.in API reachability (no key) | ❌ failed | ProxyError: HTTPSConnectionPool(host='api.data.gov.in', port=443): Max retries exceeded with url: /lists?format=json&limit=1 (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 502 Bad Gateway'))) | 0.6 |
