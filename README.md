# TruthLens

**Checks the numbers in Indian policy drafts against official data it holds, and lists the claims that need a source.**

Status: early prototype (v0.7.0, 4 Nov 2026). Open source (MIT). Not hosted
anywhere yet. Feedback and reviews welcome: open an issue.

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
- v0.6: works out a State's **share of India** ("16.17% of the country's population", "7.33% of the country's land
  area") from the bundled Census 2011 State and All India rows, and reads areas given in **hectares** (1 sq km =
  100 ha).
- v0.6: a new verdict, **Dated**, for a figure that is for an earlier year or for a State before a boundary change
  (Uttarakhand from Uttar Pradesh, Jharkhand from Bihar, Chhattisgarh from Madhya Pradesh, Telangana from Andhra
  Pradesh). A dated figure is never called wrong.
- v0.6: **compares two versions** of a document (`truthlens compare OLD NEW`, or the "Compare two versions" tab):
  near-copied sentences, figures that changed between matching sentences, old sentences and commitments that are gone,
  and new section headings. This is a wording comparison only.
- v0.7: **compares two versions by meaning** (optional, `--meaning`, or "Match by meaning" in the web tab), for a
  policy, act, rule, guideline or scheme in any sector. Each old sentence is paired with the new sentence that says
  nearly the same thing, using a small sentence-embedding model that runs on your computer's CPU (no key, no AI
  service; the 67 MB model downloads once). Every pair is labelled by rules, not AI: **kept** (reworded),
  **strengthened** (should → shall, a deadline, figure or named body added), **weakened** (shall → may / endeavour /
  encourage, or one of those removed), **changed figure**, **new** or **dropped**, grouped by topic. Topics come from
  the documents' own section headings (or, with too few headings, from grouping similar sentences). Both quotes are
  shown with page and paragraph. A "why" is shown only when the new document itself states a reason (a quoted
  sentence); otherwise it says "Reason not stated in the document". An optional AI summary per topic (your own key or
  Ollama) is labelled "AI summary, check the quotes" and is rejected if it cites text or figures that are not in the
  quotes.
- Checks DOIs in citations through Crossref (Deep mode; Quick mode only knows a small saved list).
- Lists the claims it has no official data for as "Needs a source", downloadable as a CSV.
- Fails closed: no evidence means "couldn't check", never "supported" or "wrong". Without an AI key, some
  verdicts come from matching words and numbers; those are marked low confidence.
- Two modes: **Quick** (seconds, uses only data already on your computer) and **Deep** (about half a minute to a
  minute, asks live websites about what Quick left open).
- Runs without any API key. An optional AI key (Anthropic, OpenAI or local Ollama) is supported. v0.6 adds DeepSeek,
  Mistral, xAI Grok, Google Gemini, Moonshot Kimi, Alibaba Qwen, Z.ai GLM, OpenRouter and any OpenAI-compatible URL;
  **these new ones are untested live** (only checked against simulated answers). A key typed into the web page or the
  command-line prompt is used for that one check and never stored.

### Example (run on v0.6.0, 4 Nov 2026, Quick mode, no keys)

Input (test sentences; the third is from the Uttar Pradesh State Water Policy 2020 draft, slightly shortened; the
groundwater and Madhya Pradesh figures are made up to show the Dated verdict):

```
According to Census 2011, India's population was 150 crore.
According to Census 2011, Karnataka covers an area of 1,91,791 sq km, i.e., 5.83% of the area of India.
Uttar Pradesh accounts for 16.17 % of the country's population and has 7.33 % of the country's land area.
Uttar Pradesh accounts for 16.17% of India's population as per Census 2011.
In 2009 the annual ground water extraction for all uses in Uttar Pradesh was 49.48 BCM.
The geographical area of Madhya Pradesh is 44.34 million ha.
Please check the 2011 population figure of 199 million for Uttar Pradesh.
```

Output:

| Statement | Verdict | Official value (source) |
|---|---|---|
| India's population was 150 crore | Wrong | 121.09 crore (Census 2011) |
| Karnataka area 1,91,791 sq km, 5.83% of India | Supported | 191,791 sq km; 191,791 / 3,287,469 = 5.83% (Census 2011, Table A-1) |
| UP 16.17% of population, 7.33% of land area (no year given) | Partly supported | 7.33% matches; Census 2011 gives 16.50%, and with no year in the sentence the 16.17% is shown as different, not wrong |
| UP 16.17% of population "as per Census 2011" | Wrong | 199,812,341 / 1,210,854,977 = 16.50% (Census 2011) |
| 2009 groundwater extraction 49.48 BCM | Dated | 46.89 BCM in the CGWB 2025 assessment; a 2009 figure is not compared as right or wrong |
| Madhya Pradesh 44.34 million ha | Dated | equals undivided Madhya Pradesh: 308,252 + 135,192 (Chhattisgarh) = 443,444 sq km |
| "Please check the 2011 population figure ..." | Not a checkable fact | a request to the reader |

## What it does not do (yet)

- **It cannot check most claims in a real policy document.** On nine public state water-policy documents (v0.6.0,
  Deep), 4 of 1,348 checkable claims could be settled or dated against data: 2 supported, 1 partly supported, 1 dated,
  0 wrong (details below). In a hand-labelled sample of 200 claims from five of them (v0.5.3), 4% could be checked
  against an official dataset; 9% were State programme figures found only in the State's own records; 12% needed a
  citation; 75% were not factual claims. Details: [`data/realdocs_v053.md`](data/realdocs_v053.md) and
  [`data/realdocs_v060.md`](data/realdocs_v060.md).
- It does not search the open web unless you add a web-search key (Brave, Tavily or Serper), and that path has not
  been tested with real keys.
- It is not a plagiarism checker and does not detect AI-written text. The compare tool only compares two files you
  give it, by wording and (v0.7, optional) by similarity of meaning.
- **Match by meaning is similarity, not understanding, and it is often wrong.** Hand-checked on 4 Nov 2026 (details:
  [`data/meaning_v070.md`](data/meaning_v070.md)): UP State Water Policy 1999 → 2020, **22 of 29** matched pairs were
  right (76%; the threshold was tuned on this pair, so this is optimistic) and **9 of 15** "dropped" items were truly
  dropped; National Health Policy 2002 → 2017 (not used for tuning), **13 of 19** pairs right and **6 of 12**
  "dropped" items truly dropped. Most wrong "dropped" items do show a weak "possible match"; the rest really are
  missed. On the right matches, 28 of 35 labels were right (5 debatable, 2 wrong). Two sentences on the same subject
  can score high and say different things; a heavily reworded sentence can score low. Check the quotes.
- Match by meaning reads text only: **scanned, image-only PDFs are not read** (there is no OCR), and a PDF whose text
  layer is garbled gives garbled sentences and fragments. The default model is **English only**; `--model
  multilingual` handles about 50 languages including Hindi, Marathi, Gujarati and Urdu, but not Bengali, Tamil,
  Telugu, Kannada, Malayalam, Odia or Punjabi, and it matched English pairs less well in our check.
- Tested on one machine only: the web page and Windows were run on the author's own PC (Windows, Python 3.12,
  3 Nov 2026, v0.5.3; and v0.7.0 on 4 Nov 2026, when the Windows launcher installed the match-by-meaning extra,
  downloaded its model and ran the web page and compare), not yet by anyone else. Not tested: GitHub Codespaces and
  Google Colab (instructions below, not yet run), the Dockerfile (never
  built), data.gov.in, Semantic Scholar and Shodhganga (tested only on sample data), and every AI provider added in
  v0.6 (DeepSeek, Mistral, xAI, Gemini, Kimi, Qwen, GLM, OpenRouter, custom URL), which were only checked against
  simulated answers. Their base URLs and default models were copied from each provider's documentation on
  4 Nov 2026 and may change.
- The not-a-claim filter still lets through about half of non-claims (v0.5.3 blind test: 39 of 71 set aside, 1 of 29
  real claims wrongly dropped). These show as "needs a source", never as "wrong".

### Known limits of the v0.6 features

- **Share of India** is computed only for population and area, only from Census 2011, and only when the sentence says
  "% of the country's / India's / the nation's population or area". Other shares (water resources, GDP) are not
  checked. A share with no year that differs from Census 2011 is shown as different, not wrong; only a share the
  sentence itself dates to Census 2011 can be wrong.
- **Dated** depends on reading years: the sentence's own year, or the document's year from its title lines (for
  example "State Water Policy, 1999"). A document with no year in its first lines gets no document year. A figure in a
  document older than the data is marked Dated when it differs; one in a newer document is left open.
- **Boundary changes** covered: Uttarakhand (9 Nov 2000), Jharkhand (15 Nov 2000), Chhattisgarh (1 Nov 2000) and
  Telangana (2 Jun 2014). The undivided figure is the sum of the two Census 2011 rows (for Andhra Pradesh, the Census
  2011 row itself), not a figure published for the old State. Other reorganisations (Jammu and Kashmir and Ladakh,
  district changes) are not covered.
- **A State's area** in hectares or in lakh/million sq km is never called wrong by the new area check (published
  areas differ by source); a plain sq km figure dated to Census 2011 is still judged by the older table matcher, as in
  v0.5.3.
- **Compare** works on sentences as the PDF text gives them: a sentence broken differently in one file can miss its
  match, a reworded sentence counts as dropped and added, and the similarity is about wording, not meaning.
  "Commitments dropped" are old sentences with words such as shall, should, will or ensure that have no match at 60%
  similarity; some are notes or disclaimers, not commitments. "New section headings" are headings whose wording is
  not in the old file; the section may still be partly copied (the count of new sentences under each says how much).
- **Match by meaning (v0.7)** labels strength from obligation words and from deadlines, figures and named bodies
  added or removed in a commitment. It cannot see a duty that disappears without those words changing (for example
  "shall bear the cost" → "arrangements will be made"), and a negation is only flagged ("may reverse the meaning,
  check"), not labelled. "Changed figure" pairs each old figure with the nearest new figure of the same unit, so when
  the pair itself is wrong, the figure change is meaningless. Reasons are found only from cue phrases ("in view of",
  "due to" in a preamble or introduction, "need for a new ...", "therefore" in a preamble) and linked to a topic by
  similarity; a reason can be attached to the wrong topic. Topic names are only as good as the document's headings;
  contents pages, table rows and PDF fragments add noise. Runtime on a 2-core machine: 22–44 s for the meaning step on
  documents of 230–500 sentences.
- **Request sentences** ("Please check ...", "Kindly verify ...", "Refer to ...") are set aside as not checkable;
  "Please note that ..." is kept, because it usually introduces a fact.

## Measured results (4 Nov 2026, v0.6.0)

| Test | Result |
|---|---|
| Nine real state water-policy documents: Karnataka 2022, Maharashtra 2019, Orissa 2007, Kerala SPB, Andhra Pradesh 2025, and Uttar Pradesh State Water Policy 1999, its 2020 draft, the 2020 policy as published on FAOLEX and the UP groundwater policy 2013 | 0 "wrong" flags, Quick and Deep. Changes from v0.5.3: the Karnataka and Maharashtra area sentences are now supported (the share of India and the area in million sq km are checked); the UP 2020 draft share sentence is partly supported (7.33% matches; 16.17% differs from 16.50% and gives no year); the UP 1999 "29.44 million ha" is dated (undivided UP). All four checked by hand against Census 2011 Table A-1 |
| Unsafe "supported" verdicts on the labelled test sets (v0.5.3, recorded data) | 0 (one live v0.5.0 run had 1; fixed) |
| Compare, UP State Water Policy 1999 → 2020 draft | 32 near-copied sentences (one of them two old sentences joined), 4 figures changed in matching sentences (for example 20 mha → 19.13 mha of culturable land), 194 old sentences with no match. 1999 → the 2020 FAOLEX text: 0 near-copies (best match 59%) |
| Compare by meaning (v0.7.0), UP 1999 → 2020 FAOLEX | 28 old sentences matched (16 kept, 7 strengthened, 1 weakened, 4 changed figure), 194 dropped, 389 new; wording compare found 0 near-copies. Hand-check: 22 of 29 pairs right, 9 of 15 dropped truly dropped |
| Compare by meaning (v0.7.0), National Health Policy 2002 → 2017 | 19 matched (10 kept, 4 strengthened, 2 weakened, 3 changed figure, e.g. State health spending 7% → 8% of budget), 425 dropped, 476 new. Hand-check: 13 of 19 pairs right, 6 of 12 dropped truly dropped |
| Automated tests (offline, fresh `git archive` copy, clean environment) | see [CHANGELOG.md](CHANGELOG.md) (0.7.0) for the counts per Python version |

Per-document counts, Quick and Deep, before and after: [`data/realdocs_v060.md`](data/realdocs_v060.md).

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
  -> v0.6 bundled Census maths: share of India, hectares, undivided States before a split
  -> verdict: supported / partly / wrong / dated / couldn't check (fails closed)
  -> report: HTML, Markdown, JSON, annotated .docx, "needs a source" CSV, all-claims CSV

two versions (old, new) -> compare: near-copies, changed figures, dropped commitments, new sections
                         -> v0.7 optional, by meaning: local sentence embeddings (bge-small-en-v1.5, ONNX)
                            -> best match per old sentence -> rule labels -> topics from headings -> quoted reasons
```

Interfaces: web page (FastAPI), command line, REST API, MCP tool. New sources can be added as small YAML files
([`docs/PLUGINS.md`](docs/PLUGINS.md)). Data refresh: `truthlens sync`.

## Scope

- In scope: factual and numeric claims in Indian policy and research writing, checked against official Indian and
  international data.
- Out of scope for now: opinions, forecasts and targets, plagiarism, AI-text detection, languages other than English
  (except the optional multilingual model for compare by meaning).

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
truthlens compare old_policy.pdf new_draft.pdf -f html -o compare.html   # v0.6
python -m pip install -e ".[api,meaning]"                                 # v0.7 optional extra (about 145 MB)
truthlens compare old_policy.pdf new_draft.pdf --meaning -f html -o compare.html
```

### In the browser, with nothing installed on your PC (not yet tested)

No API key is needed. Both options run TruthLens on a free cloud machine that already has Python.

**GitHub Codespaces** (free monthly hours on a personal GitHub account): on this repository page click
**Code → Codespaces → Create codespace on main**. The included `.devcontainer` installs TruthLens with the
match-by-meaning extra. Then, in the terminal at the bottom:

```bash
uvicorn truthlens.api:app --host 0.0.0.0 --port 8765
```

Click **Open in Browser** in the pop-up (or the **Ports** tab, port 8765). Stop the codespace when done to save hours.

**Google Colab** (free Google account): new notebook, then run these cells. Upload your files with the folder icon
on the left. Files are lost when the session ends.

```python
!git clone -q https://github.com/ApahSaroj/truthlens && pip install -q -e "./truthlens[api,meaning]"
!truthlens compare old_policy.pdf new_draft.pdf --meaning -f html -o compare.html
!truthlens check draft.pdf -f html -o report.html
```

Optional, the web page inside Colab:

```python
import subprocess; subprocess.Popen(["uvicorn", "truthlens.api:app", "--port", "8765"], cwd="truthlens")
from google.colab import output; output.serve_kernel_port_as_window(8765)
```

Full manual, every option and the version history: [`docs/REFERENCE.md`](docs/REFERENCE.md) and
[`CHANGELOG.md`](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).
