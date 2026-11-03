"""Parliament questions and answers as evidence (Lok Sabha and Rajya Sabha), key-free.

Sources (all called live from our test network on 1 Nov 2026; see docs/SOURCES.md):

* Lok Sabha archive, 16th-18th Lok Sabha to March 2026: the OpenSansad dataset on Hugging Face
  (opensansad/lok-sabha-qa, 150,808 answers with full question and answer text and Digital Sansad PDF links),
  searched through the Hugging Face datasets-server full-text search API, no download needed:
    GET https://datasets-server.huggingface.co/search?dataset=opensansad/lok-sabha-qa&config=default&split=train&query=...&offset=0&length=N
* Lok Sabha, recent sessions: the JSON API behind https://sansad.in/ls/questions/questions-and-answers
    GET https://sansad.in/api_ls/question/qetFilteredQuestionsAns?loksabhaNo=18&pageNo=1&pageSize=N&locale=en&keyWord=...
  It lists question no., date, ministry, subject and the answer PDF; the PDF is fetched and its text read on demand.
* Rajya Sabha: the JSON API behind https://sansad.in/rs/questions/questions-and-answers
    GET https://integration.rajyasabha.digital/rsdebate/api/question/search-questions?searchParam=...&searchOn=title
        &matchesOn=allWords&page=1&size=N
  It returns question no., answer date, ministry, title and a PDF link (answer text is in the PDF).

Each item is cited with house, question number and type, ministry, answer date and the PDF link.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import Config, redact
from ..model import Claim, Evidence
from ..net import DiskCache, fetch_bytes, FetchError, make_session, safe_get, with_params
from .base import Retriever, best_window, norm_ws, terms

HF_SEARCH = "https://datasets-server.huggingface.co/search"
HF_DATASET = "opensansad/lok-sabha-qa"
LS_API = "https://sansad.in/api_ls/question/qetFilteredQuestionsAns"
RS_API = "https://integration.rajyasabha.digital/rsdebate/api/question/search-questions"
CURRENT_LOK_SABHA = 18

KEEP_CAPS = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,4})\b")


QUERY_DROP = {"the", "this", "that", "in", "on", "as", "by", "over", "under", "a", "an", "india", "indian", "government",
              "lok", "sabha", "rajya", "parliament", "ministry", "minister", "union", "department", "answer", "question",
              "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
              "november", "december", "shri", "smt", "dr", "it", "its", "of", "and", "for", "to", "per", "cent"}
GENERIC = {"rural", "urban", "total", "number", "state", "states", "country", "data", "report", "said", "says", "percent",
           "crore", "lakh", "year", "years", "took", "addressed", "launched", "implemented", "question", "answer",
           "found", "study", "households"}


def query_terms(text: str, n: int = 5) -> list[str]:
    """A short keyword query: scheme / organisation / place names first, then the claim's rarer content words.
    House names, months and generic words are left out (they match every answer)."""
    from ..claims import _strip_citations
    from .base import STOP
    t = _strip_citations(text)
    words: list[str] = []
    for m in KEEP_CAPS.finditer(t):
        for w in m.group(1).split():
            wl = w.lower()
            if wl not in QUERY_DROP and len(wl) > 2 and wl not in words:
                words.append(wl)
    for w in sorted(set(re.findall(r"[a-z][a-z\-]{3,}", t.lower())), key=len, reverse=True):
        if w not in words and w not in GENERIC and w not in STOP and w not in QUERY_DROP:
            words.append(w)
    return words[:n]


def _human_date(iso: str) -> str:
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat((iso or "")[:10])
        return f"{d.day} {d.strftime('%B')} {d.year}"
    except ValueError:
        return iso or "date not given"


class ParliamentRetriever(Retriever):
    name = "parliament"

    def __init__(self, cfg: Config, session=None, fetcher=None, max_pdfs: int = 2):
        super().__init__(cfg)
        self.session = session or make_session()
        self.cache = DiskCache(cfg.cache_dir, "parliament", ttl=3 * 24 * 3600)
        self.fetcher = fetcher
        self.max_pdfs = max_pdfs

    def status(self) -> dict:
        return self._status(not self.cfg.offline, "Lok Sabha (OpenSansad archive via Hugging Face search; sansad.in for "
                                                  "recent sessions) and Rajya Sabha (sansad.in API), no key")

    def _json(self, url: str, params: dict) -> Optional[object]:
        from urllib.parse import urlencode
        key = f"{url}?{urlencode(params)}"
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        if self.cfg.offline:
            return self.cache.get(key, allow_stale=True)
        try:
            # the Hugging Face search API is sometimes slow or returns 500 while its index reloads: short timeout
            tmo = min(self.cfg.timeout, 12.0) if "huggingface" in url else self.cfg.timeout
            r = safe_get(self.session, with_params(url, params), tmo, stream=False)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            data = r.json()
            self.cache.set(key, data)
            return data
        except Exception as e:
            self.errors.append(redact(f"parliament {url.split('/')[2]}: {type(e).__name__}: {e}"))
            return self.cache.get(key, allow_stale=True)

    # ---------------------------------------------------------------- sources
    def lok_sabha_archive(self, q: str, n: int = 4) -> list[dict]:
        data = self._json(HF_SEARCH, {"dataset": HF_DATASET, "config": "default", "split": "train", "query": q,
                                      "offset": 0, "length": n}) or {}
        out = []
        for r in (data.get("rows") or []) if isinstance(data, dict) else []:
            x = r.get("row") or {}
            out.append({"house": "Lok Sabha", "lok": x.get("lok_no"), "session": x.get("session_no"), "qno": x.get("ques_no"),
                        "type": (x.get("type") or "").title(), "date": x.get("date"), "ministry": (x.get("ministry") or "").title(),
                        "subject": norm_ws(x.get("subject") or ""), "text": norm_ws(x.get("answer_text") or ""),
                        "question": norm_ws(x.get("question_text") or ""), "pdf": x.get("pdf_url"),
                        "via": "OpenSansad dataset (Hugging Face)"})
        return out

    def lok_sabha_recent(self, q: str, n: int = 4) -> list[dict]:
        data = self._json(LS_API, {"loksabhaNo": CURRENT_LOK_SABHA, "pageNo": 1, "pageSize": n, "locale": "en", "keyWord": q})
        out = []
        if isinstance(data, list) and data:
            for x in data[0].get("listOfQuestions") or []:
                d = x.get("date") or ""
                m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", d)
                out.append({"house": "Lok Sabha", "lok": x.get("lokNo"), "session": x.get("sessionNo"), "qno": x.get("quesNo"),
                            "type": (x.get("type") or "").title(), "date": f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else d,
                            "ministry": (x.get("ministry") or "").title(), "subject": norm_ws(x.get("subjects") or ""),
                            "text": norm_ws(x.get("answerText") or ""), "question": norm_ws(x.get("questionText") or ""),
                            "pdf": x.get("questionsFilePath"), "via": "sansad.in"})
        return out

    def rajya_sabha(self, q: str, n: int = 4) -> list[dict]:
        data = self._json(RS_API, {"searchParam": q, "searchOn": "title", "matchesOn": "anyWords" if len(q.split()) > 3 else "allWords",
                                   "page": 1, "size": n}) or {}
        out = []
        for x in (data.get("records") or []) if isinstance(data, dict) else []:
            out.append({"house": "Rajya Sabha", "lok": None, "session": x.get("ses_no"), "qno": x.get("qno"),
                        "type": (x.get("qtype") or "").strip().title(), "date": (x.get("adate") or "")[:10],
                        "ministry": (x.get("min_name") or "").title(), "subject": norm_ws(x.get("qtitle") or ""),
                        "text": norm_ws(re.sub(r"<[^>]+>", " ", x.get("ans_text") or "")),
                        "question": norm_ws(re.sub(r"<[^>]+>", " ", x.get("qn_text") or "")), "pdf": x.get("files"),
                        "via": "sansad.in (Rajya Sabha)"})
        return out

    def _pdf_text(self, url: str) -> str:
        if not url or self.cfg.offline:
            return ""
        key = "pdf:" + url
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        try:
            data, _ctype, _final = fetch_bytes(self.session, url, self.cfg.timeout, 15 * 2 ** 20)
            from .docs import extract_pdf
            _title, passages = extract_pdf(data)
            text = norm_ws(" ".join(p["text"] for p in passages))
        except (FetchError, Exception) as e:  # noqa: B014
            self.errors.append(redact(f"parliament PDF: {type(e).__name__}: {str(e)[:120]}"))
            return ""
        self.cache.set(key, text)
        return text

    # ---------------------------------------------------------------- retrieve
    def retrieve(self, claim: Claim, k: int = 3) -> list[Evidence]:
        words = query_terms(claim.text)
        if len(words) < 2:
            return []
        q = " ".join(words)
        # sansad.in matches the keyword as a phrase: use the longest capitalised name (e.g. "Jal Jeevan Mission")
        phrases = [m.group(1) for m in KEEP_CAPS.finditer(claim.text)]
        phrases = [" ".join(w for w in ph.split() if w.lower() not in QUERY_DROP) for ph in phrases]
        phrase = max((p for p in phrases if len(p.split()) >= 2), key=len, default=" ".join(words[:2]))
        low = claim.text.lower()
        items: list[dict] = []
        if "rajya sabha" not in low:
            items += self.lok_sabha_archive(q)
            items += self.lok_sabha_recent(phrase)
        if "lok sabha" not in low:
            items += self.rajya_sabha(phrase)
        want = terms(claim.text)
        nums = [re.sub(r"[^\d.,]", "", n).strip(".,") for n in claim.numbers]
        scored = []
        for it in items:
            head = f"{it['subject']} {it['ministry']}"
            scored.append((len(want & terms(head + ' ' + it['text'][:3000])) / (len(want) or 1), it))
        scored.sort(key=lambda x: -x[0])
        out, pdfs = [], 0
        for score, it in scored:
            if score < 0.25 or len(out) >= k:
                continue
            body = it["text"]
            if not body and pdfs < self.max_pdfs:
                body = self._pdf_text(it["pdf"])
                pdfs += 1
            if not body:
                continue
            snippet, _ = best_window(body, want, [n for n in nums if n])
            house = it["house"]
            qtype = f"{it['type']} " if it["type"] else ""
            title = f"{house} {qtype}Question No. {it['qno']}, answered {it['date']}: {it['subject']}"
            # the citation header is part of the quoted evidence, so house, date and ministry can be checked
            header = (f"{house} {qtype}Question No. {it['qno']} ({it['subject']}), answered on {_human_date(it['date'])}"
                      + (f" by the Ministry of {it['ministry']}" if it["ministry"] else "") + ".")
            snippet = f"{header} {snippet or body[:800]}"
            out.append(Evidence(retriever=self.name, source_url=it["pdf"] or "", title=title, snippet=snippet,
                                date=it["date"], publisher=f"{house}, Ministry of {it['ministry']}" if it["ministry"] else house,
                                official=True, score=round(score, 3), kind="passage", source_type=house,
                                as_of=it["date"], meta={"house": house, "question_no": it["qno"], "session": it["session"],
                                                        "ministry": it["ministry"], "via": it["via"]}))
        return out
