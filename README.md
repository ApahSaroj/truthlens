# TruthLens

**Checks the numbers in Indian policy drafts against official data it holds, and lists the claims that need a source.**

Status: early prototype (v0.5.3, 3 Nov 2026). Open source (MIT). Not hosted anywhere yet. Feedback and reviews welcome:
open an issue.

## Objective

Policy drafts, reports and AI-written text often carry wrong or unsourced figures. TruthLens aims to catch a wrong
official figure before a draft goes out, show the official value with a link to its source, and tell the writer
which statements still need a citation.

## What it does

- Reads a `.docx`, `.pdf`, `.txt` or `.md` file, or pasted text, and splits it into statements.
- Sets aside text that is not a factual claim (headings, rules, plans, targets, descriptions) and says why.
- Checks numbers against official data it holds or can fetch, for example Census 2011 (State and district),
  CGWB 2025 groundwater (State), NFHS-5 (Karnataka), and live sources such as MoSPI, RBI, CEA, PPAC and
  Jal Jeevan Mission. The full list, with what was tested live and what was not, is in
  [`docs/SOURCES.md`](docs/SOURCES.md).
- For a wrong figure: shows the official value, the source link and a corrected sentence.
- Checks DOIs in citations through Crossref (Deep mode; Quick mode only knows a small saved list).
- Lists the claims it has no official data for as "Needs a source", downloadable as a CSV.
- Fails closed: no evidence means "couldn't check", never "supported" or "wrong". Without an AI key, some
  verdicts come from matching words and numbers; those are marked low confidence.
- Two modes: **Quick** (seconds, uses only data already on your computer) and **Deep** (about half a minute to a
  minute, asks live websites about what Quick left open).
- Runs without any API key. An optional AI key (Anthropic, OpenAI or local Ollama) is supported. A key typed into the
  web page or the command-line prompt is used for that one check and never stored.

### Example (run on v0.5.3, 3 Nov 2026, Quick mode, no keys)

Input:

```
According to Census 2011, India's population was 150 crore.
According to Census 2011, Karnataka's population was 6.11 crore.
According to Census 2011, Karnataka covers an area of 1,91,791 sq km.
According to Census 2011, Karnataka covers an area of 2,50,000 sq km.
```

Output:

| Statement | Verdict | Official value (source) |
|---|---|---|
| India's population was 150 crore | Wrong | 121.09 crore (Census 2011, Table C-16) |
| Karnataka's population was 6.11 crore | Supported | 6.11 crore (Census 2011, Table A-1) |
| Karnataka area 1,91,791 sq km | Supported | 191,791 sq km (Census 2011, Table A-1) |
| Karnataka area 2,50,000 sq km | Wrong | 191,791 sq km (Census 2011, Table A-1) |

## What it does not do (yet)

- **It cannot check most claims in a real policy document.** On five public state water-policy documents, only 2 of
  1,058 checkable claims could be settled against data. In a hand-labelled sample of 200 claims, 4% could be checked
  against an official dataset; 9% were State programme figures found only in the State's own records; 12% needed a
  citation; 75% were not factual claims. Details: [`data/realdocs_v053.md`](data/realdocs_v053.md).
- It does not search the open web unless you add a web-search key (Brave, Tavily or Serper), and that path has not
  been tested with real keys.
- It is not a plagiarism checker and does not detect AI-written text.
- Tested on one machine only: the web page and Windows were run on the author's own PC (Windows, Python 3.12,
  3 Nov 2026), not yet by anyone else. Not tested: the Dockerfile (never built), data.gov.in, Semantic Scholar and
  Shodhganga (tested only on sample data).
- The not-a-claim filter still lets through about half of non-claims (blind test: 39 of 71 set aside, 1 of 29 real
  claims wrongly dropped). These show as "needs a source", never as "wrong".

## Measured results (3 Nov 2026)

| Test | Result |
|---|---|
| Five real state water-policy documents (Karnataka 2022, Maharashtra 2019, Orissa 2007, Kerala SPB, Andhra Pradesh 2025) | 0 false "wrong" flags (v0.5.2 had 7, all false); 2 claims partly supported, both correct when checked by hand |
| Unsafe "supported" verdicts on the labelled test sets (v0.5.3, recorded data) | 0 (one live v0.5.0 run had 1; fixed) |
| Automated tests (offline, fresh copy, clean environment) | 479 passed, 4 skipped |
| Speed, 51-claim test draft (v0.5.2, Linux sandbox via a US proxy, not a home connection) | Quick 0.4 s; Deep 33 s with an empty cache |

Older test sets and their numbers: [`docs/REFERENCE.md`](docs/REFERENCE.md#accuracy-and-safety-honestly).

## Architecture

```
draft (.docx / .pdf / .txt / text)
  -> reader: sentences, PDF columns, headers dropped
  -> claim filter: "not a checkable fact" set aside with a reason
  -> claim extractor: rules (or an optional AI model)
  -> router: sends each claim only to sources that could answer it
       Quick: bundled official data + saved answers (no network)
       Deep:  live official sources, Parliament, PIB, Crossref, arXiv (time-limited)
  -> deterministic number checker: India data rules (lakh/crore, FY vs calendar year,
     base-year revisions, per cent vs percentage points)
  -> verdict: supported / partly / wrong / couldn't check (fails closed)
  -> report: HTML, Markdown, JSON, annotated .docx, "needs a source" CSV
```

Interfaces: web page (FastAPI), command line, REST API, MCP tool. New sources can be added as small YAML files
([`docs/PLUGINS.md`](docs/PLUGINS.md)). Data refresh: `truthlens sync`.

## Scope

- In scope: factual and numeric claims in Indian policy and research writing, checked against official Indian and
  international data.
- Out of scope for now: opinions, forecasts and targets, plagiarism, AI-text detection, languages other than English.

## Plan (not built yet)

1. Collect reviews from people who write or check policy documents.
2. Add the State department sources reviewers need most, one at a time, each tested live before it is listed.
3. Optional web search with an AI reader for claims no dataset covers, clearly labelled and off by default.
4. Get it tested on other people's PCs and browsers.
5. Free hosted version, only after the above.

## Try it

- **Windows, no terminal:** download this repository as a ZIP, unzip it, double-click `start_truthlens.bat`. Needs
  Python from python.org (3.12 was used in testing). Step-by-step guide: [SETUP.md](SETUP.md).
- **Command line:**

```bash
git clone https://github.com/ApahSaroj/truthlens && cd truthlens
python -m pip install -e ".[api]"
truthlens check draft.docx -f html -o report.html   # Quick
truthlens check draft.docx --deep -f cite -o to_cite.csv
```

Full manual, every option and the version history: [`docs/REFERENCE.md`](docs/REFERENCE.md) and
[`CHANGELOG.md`](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).
