"""v0.7: compare two versions of a document by MEANING (local, key-free).

Each sentence of the old version is matched to the sentence(s) of the new version that mean nearly the same, using a
small sentence-embedding model that runs on the CPU (optional extra: ``pip install "truthlens[meaning]"``; the model is
downloaded once to a cache folder). Nothing is sent to any outside service except that one model download.

For every matched pair the change is labelled by rules (no AI):
  * kept          the same commitment in other words;
  * strengthened  a firmer obligation word (should -> shall), or a deadline, figure or named body added;
  * weakened      a softer obligation word (shall -> may / endeavour / encourage), or a deadline, figure or named
                  body removed;
  * changed figure a figure with the same unit and a different value;
  * new           a sentence of the new version that no old sentence comes near;
  * dropped       an old sentence that no new sentence comes near ("truly dropped").

Topics come from the documents themselves: the section headings of the new version (and of the old one for topics
the new version no longer has) or, when a document has too few headings, from grouping the sentences by similarity
(labels = the group's most distinctive words). A water-sector keyword map exists as an optional preset only.

Reasons ("why") are only ever quotes: sentences of the new version that state a motivation (in a preamble /
introduction / "need for" / objectives section, or with an explicit cue such as "because", "due to", "in view of",
"has become necessary"), linked to a topic by similarity. Otherwise the report says "Reason not stated in the document".

Similarity is not understanding: two sentences on the same subject can score high and say different things, and a
sentence can be reworded so much that it scores low. Check the quotes.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from typing import Callable, Optional, Sequence

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
MULTILINGUAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELS = {"english": DEFAULT_MODEL, "multilingual": MULTILINGUAL_MODEL}
MODEL_NOTES = {
    DEFAULT_MODEL: "bge-small-en-v1.5 (ONNX, quantised, about 67 MB; English only; 512-token limit per sentence)",
    MULTILINGUAL_MODEL: "paraphrase-multilingual-MiniLM-L12-v2 (ONNX, quantised, about 240 MB; about 50 languages "
                        "including Hindi, Marathi, Gujarati and Urdu, but not Bengali, Tamil, Telugu, Kannada, "
                        "Malayalam, Odia or Punjabi; 128-token limit; matched English pairs less well in our hand-check)",
}
MATCH = 0.10            # match score threshold, tuned on UP State Water Policy 1999 vs 2020 (README: hand-check)
WEAK = 0.05             # a dropped sentence whose nearest new sentence scores at least this shows it as a possible match
EXTRA_MARGIN = 0.02     # other new sentences within this of the best one are listed too (max 2 extra)
HUB_K = 10              # a sentence's 'usual neighbours': the mean of its 10 highest similarities
LEX_W = 0.10            # weight of shared distinctive words
TOPIC_MIN = 0.40        # an old sentence with no match joins the nearest new-version topic only at this similarity
REASON_MIN = 0.45       # a stated reason is linked to a topic only at this similarity
INSTALL_HINT = 'pip install "truthlens[meaning]"'


class MeaningUnavailable(RuntimeError):
    """The optional embedding model is not installed or could not be loaded (for example offline on first use)."""


# ---------------------------------------------------------------------------------------------- vectors
try:                                    # numpy comes with the [meaning] extra; the fallback keeps tests key-free
    import numpy as _np
except Exception:                       # pragma: no cover - exercised on installs without numpy
    _np = None


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _matrix(vectors) -> list:
    """Unit-normalised rows (list of lists, or a numpy array when numpy is present)."""
    if _np is not None:
        a = _np.asarray(vectors, dtype="float32")
        if a.ndim != 2 or not len(a):
            return _np.zeros((0, 1), dtype="float32")
        n = _np.linalg.norm(a, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return a / n
    return [_unit(list(v)) for v in vectors]


def _sim(A, B) -> list:
    """Cosine similarity matrix as a list of lists."""
    if _np is not None:
        if not len(A) or not len(B):
            return [[] for _ in range(len(A))]
        return (A @ B.T).tolist()
    return [[sum(x * y for x, y in zip(a, b)) for b in B] for a in A]


def _mean(rows: list):
    if not rows:
        return None
    if _np is not None:
        return _matrix([_np.mean(_np.asarray(rows), axis=0)])[0]
    d = len(rows[0])
    return _unit([sum(r[k] for r in rows) / len(rows) for k in range(d)])


def _dot(a, b) -> float:
    if _np is not None:
        return float(_np.dot(a, b))
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------------------------- embedder
def model_cache_dir() -> str:
    from .config import default_cache_dir
    return os.environ.get("TRUTHLENS_EMBED_CACHE") or str(default_cache_dir() / "models")


def model_name(choice: Optional[str] = None) -> str:
    c = (choice or os.environ.get("TRUTHLENS_EMBED_MODEL") or "").strip()
    return MODELS.get(c.lower(), c) if c else DEFAULT_MODEL


def is_installed() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("fastembed") is not None
    except Exception:
        return False


def status() -> dict:
    """Is meaning compare available here, and is the model already downloaded?"""
    name, cache = model_name(), model_cache_dir()
    slug = name.split("/")[-1]
    cached = False
    try:
        cached = any(slug in d for d in os.listdir(cache))
    except OSError:
        pass
    return {"installed": is_installed(), "model": name, "cache_dir": cache, "model_downloaded": cached,
            "install": INSTALL_HINT, "note": MODEL_NOTES.get(name, "")}


class FastEmbedder:
    """Sentence embeddings with fastembed (ONNX runtime, no torch). Loaded on first use."""

    def __init__(self, name: Optional[str] = None, cache_dir: Optional[str] = None):
        self.name = model_name(name)
        self.cache_dir = cache_dir or model_cache_dir()
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from fastembed import TextEmbedding
        except Exception:
            raise MeaningUnavailable(f"Match by meaning needs the optional extra: {INSTALL_HINT} (about 145 MB of "
                                     f"installed packages; the model, about 67 MB, downloads once on first use). The wording "
                                     f"comparison works without it.") from None
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            self._model = TextEmbedding(self.name, cache_dir=self.cache_dir)
        except Exception as e:
            raise MeaningUnavailable(f"Could not load the meaning model {self.name} ({type(e).__name__}). On first use "
                                     f"it is downloaded (67 MB for the English model, 240 MB for the multilingual one) to {self.cache_dir}; if you are offline, run once "
                                     f"online or copy the model folder there (TRUTHLENS_EMBED_CACHE). The wording "
                                     f"comparison works without it.") from None
        return self._model

    def embed(self, texts: Sequence[str]):
        model = self._load()
        return _matrix([list(v) for v in model.embed(list(texts), batch_size=64)])


class HashEmbedder:
    """A tiny deterministic bag-of-words embedder for tests (no download): similarity = shared words."""

    def __init__(self, dim: int = 512, synonyms: Optional[dict] = None):
        self.dim = dim
        self.synonyms = synonyms or {}
        self.name = "test-hash-embedder"

    def embed(self, texts: Sequence[str]):
        import zlib
        rows = []
        for t in texts:
            v = [0.0] * self.dim
            for w in re.findall(r"[a-z]+", (t or "").lower()):
                if w in STOP or len(w) < 3:
                    continue
                w = self.synonyms.get(w, w)
                v[zlib.crc32(w.encode()) % self.dim] += 1.0
            rows.append(v)
        return _matrix(rows)


# ---------------------------------------------------------------------------------------------- obligation rules
STRONG_RX = re.compile(r"\b(?:shall|must|will|is\s+to\s+be|are\s+to\s+be|mandatory|compulsor\w*|obligator\w*|binding|"
                       r"required\s+to|ensure[sd]?|guarantee[sd]?|prohibit\w*|not\s+be\s+permitted)\b", re.I)
MEDIUM_RX = re.compile(r"\b(?:should|would|ought\s+to|needs?\s+to|is\s+expected\s+to|are\s+expected\s+to|it\s+is\s+(?:also\s+)?(?:necessary|essential|imperative)|(?:^|(?<=[\s,(]))to\s+be\s+(?:considered|taken\s+up|undertaken|promoted|ensured|adopted|made|developed|implemented|provided|encouraged)|(?:is|are|be)\s+(?:also\s+|therefore\s+|considered\s+)?(?:necessary|essential|imperative)(?=\s*(?:[.;,]|$|for\b|and\b)))", re.I)
WEAK_RX = re.compile(r"\b(?:may|might|could|endeavou?r\w*|encourag\w*|explor\w*|(?:may|might|could)\s+be\s+considered|strive\w*|attempt\w*|"
                     r"aspir\w*|desirable|as\s+far\s+as\s+possible|wherever\s+(?:possible|feasible)|"
                     r"to\s+the\s+extent\s+(?:possible|feasible)|where(?:ver)?\s+feasible|if\s+feasible|"
                     r"efforts?\s+(?:will|shall|would|should)\s+be\s+made|try\s+to|subject\s+to\s+availability)\b", re.I)
DEADLINE_RX = re.compile(r"\b(?:by\s+(?:the\s+(?:year|end\s+of)\s+)?(?:19|20)\d{2}|before\s+(?:19|20)\d{2}|"
                         r"within\s+(?:a\s+period\s+of\s+)?(?:\d+|one|two|three|four|five|six|ten|twelve)\s+"
                         r"(?:years?|months?|weeks?|days?)|time[-\s]bound|deadline|timeline|in\s+a\s+phased\s+manner\s+by)\b", re.I)
BODY_RX = re.compile(r"\b(?:[A-Z][\w&'’-]*\s+){0,6}(?:Authority|Commission|Board|Council|Committee|Ministry|Department|"
                     r"Agency|Corporation|Regulator|Tribunal|Directorate|Mission|Institute|Bureau|Cell|Secretariat|"
                     r"Nigam|Parishad|Samiti|Society|Fund|Court|Organi[sz]ation)\b")
LEADIN_RX = re.compile(r"[:\u2013\u2014-]\s*(?:\(?[a-z0-9]{1,3}[.)])?\s*$", re.I)
CAPTION_RX = re.compile(r"^\s*(?:box|table|figure|fig\.|chart|annex(?:ure)?|appendix|source)\b[\s\w.-]{0,12}[:.-]", re.I)


def _usable(text: str) -> bool:
    """Leave out lead-ins, table rows and captions: they match everything and mean nothing alone."""
    if LEADIN_RX.search(text) or CAPTION_RX.match(text):
        return False
    toks = text.split()
    nums = sum(1 for t in toks if re.fullmatch(r"[<>~≈(]?[\d.,%]+\)?", t))
    return nums < 3 or nums < 0.4 * len(toks)


UNIT_RAW_RX = re.compile(r"[^\d.,\s]")
LABELS = ("kept", "strengthened", "weakened", "changed figure", "new", "dropped")


BARE_BE_RX = re.compile(r"(?<!\bto )\bbe\s+(?:\w+ed|\w+en|done|made|set\s+up|taken\s+up)\b", re.I)
NEG_RX = re.compile(r"\b(?:not(?!\s+only)|never|no\s+longer|nor|prohibit\w*|ban(?:ned|s)?|forbid\w*|discourag\w*)\b", re.I)


def obligation(text: str) -> int:
    """0 = states nothing, 1 = weak (may / endeavour / encourage / as far as possible), 2 = should / would,
    3 = shall / must / will / ensure. A hedge anywhere caps the sentence at 1 ('will be encouraged' is weak)."""
    t = text or ""
    if WEAK_RX.search(t):
        return 1
    if STRONG_RX.search(t):
        return 3
    if MEDIUM_RX.search(t) or BARE_BE_RX.search(t):     # 'X be promoted' (no modal) reads as should
        return 2
    return 0


def _word(rx, text) -> str:
    m = rx.search(text or "")
    return re.sub(r"\s+", " ", m.group(0)) if m else ""


def _bodies(text: str) -> set:
    out = set()
    for m in BODY_RX.finditer(text or ""):
        b = re.sub(r"^(?:The|A|An|This|That|Such|Each|Every|All|Any)\s+", "", m.group(0).strip())
        if len(b.split()) >= 2 or b.isupper():
            out.add(b.lower())
    return out


def figure_changes(old: str, new: str) -> list:
    """Figures with a unit whose value differs: each old figure is paired with the nearest new figure of the same
    unit, after setting aside figures found unchanged (within 0.5 %, so 24.7 and 24.67 count as the same)."""
    from .compare import _figures
    a = [f for f in _figures(old) if f[1]]
    b = [f for f in _figures(new) if f[1]]
    used, rest = set(), []
    for x in a:
        same = next((k for k, y in enumerate(b) if k not in used and y[1] == x[1]
                     and abs(y[0] - x[0]) <= 0.005 * max(abs(x[0]), abs(y[0]), 1e-9)), None)
        if same is None:
            rest.append(x)
        else:
            used.add(same)
    out = []
    for x in rest:
        cands = [(abs(y[0] - x[0]) / max(abs(x[0]), abs(y[0]), 1e-9), k) for k, y in enumerate(b)
                 if k not in used and y[1] == x[1]]
        if cands:
            _d, k = min(cands)
            used.add(k)
            out.append({"old": x[2], "new": b[k][2]})
    return out


def change_label(old: str, new: str) -> tuple:
    """(label, reasons) for a matched pair, by rules only."""
    from .compare import _figures
    reasons = []
    changed = figure_changes(old, new)
    lo, ln = obligation(old), obligation(new)
    score = 0
    if lo != ln and (lo or ln):
        score += 1 if ln > lo else -1
        names = {0: "no obligation word", 1: "weak", 2: "should/would", 3: "shall/must/will"}
        wo = _word(WEAK_RX, old) or _word(STRONG_RX, old) or _word(MEDIUM_RX, old)
        wn = _word(WEAK_RX, new) or _word(STRONG_RX, new) or _word(MEDIUM_RX, new)
        reasons.append(f"obligation: '{wo or names[lo]}' → '{wn or names[ln]}'")
    if lo or ln:                         # deadlines, figures and named bodies only matter in a commitment
        do, dn = _word(DEADLINE_RX, old), _word(DEADLINE_RX, new)
        if dn and not do:
            score += 1
            reasons.append(f"deadline added: '{dn}'")
        elif do and not dn:
            score -= 1
            reasons.append(f"deadline removed: '{do}'")
        fo, fn = bool(_figures(old)), bool(_figures(new))
        if fn and not fo:
            score += 1
            reasons.append("figure added")
        elif fo and not fn:
            score -= 1
            reasons.append("figure removed")
        bo, bn = _bodies(old), _bodies(new)
        if bn and not bo:
            score += 1
            reasons.append(f"named body added: '{sorted(bn)[0]}'")
        elif bo and not bn:
            score -= 1
            reasons.append(f"named body removed: '{sorted(bo)[0]}'")
    no, nn = NEG_RX.search(old), NEG_RX.search(new)
    if bool(no) != bool(nn):
        w = (no or nn).group(0)
        reasons.append(f"'{w}' only in the {'old' if no else 'new'} version: this may reverse the meaning, check")
    if changed:
        reasons.insert(0, "figure changed: " + "; ".join(f"{c['old']} → {c['new']}" for c in changed[:3]))
        return "changed figure", reasons
    if score > 0:
        return "strengthened", reasons
    if score < 0:
        return "weakened", reasons
    return "kept", reasons


# ---------------------------------------------------------------------------------------------- sections / topics
STOP = set("""a an the of and or to in on for by with from at as is are was were be been being this that these those it
its their there which who whom whose shall will would should may can could must not no nor all any each every such other
also into than then so very more most less least has have had do does did per etc i ii iii iv v vi vii viii ix x
under over about through between within without upon above below up down out off only own same both few further
state states policy government shall be new including include includes need needs various suitable appropriate
ensure ensured provide provided made make being well thereof where while whereas however therefore thus hence""".split())
HEAD_LEVEL_RX = re.compile(r"^\s*(?:chapter|part|section)?\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+", re.I)
ROMAN_RX = re.compile(r"^\s*\(?[ivxlc]{1,5}[.)]\s+|^\s*\(?[a-z][.)]\s+", re.I)
MOTIVE_HEAD_RX = re.compile(r"\b(?:preamble|introduct\w*|need\s+for|background|rationale|context|why|"
                            r"situation\s+analys\w*|current\s+scenario|the\s+challenge\w*|key\s+\w+\s+challenges)\b", re.I)
# any cause word counts inside a preamble / introduction / 'need for' section
CAUSE_RX = re.compile(r"\b(?:because|due\s+to|owing\s+to|in\s+view\s+of|on\s+account\s+of|keeping\s+in\s+view|"
                      r"has\s+(?:now\s+)?become\s+(?:necessary|imperative|essential|important|urgent)|"
                      r"there\s+is\s+(?:now\s+)?(?:an?\s+)?(?:urgent\s+|growing\s+|increasing\s+)?need|"
                      r"need\s+for\s+(?:a\s+)?(?:new|revised|fresh)|(?:the\s+)?context\s+has\s+changed|"
                      r"in\s+the\s+light\s+of|as\s+a\s+result\s+of|ha(?:s|ve)\s+led\s+to|therefore|hence|"
                      r"in\s+order\s+to\s+(?:address|overcome|tackle|meet|reduce|prevent))\b", re.I)
# elsewhere only an explicit statement of motive counts ('due to' alone usually describes a problem, not a reason)
STRONG_CAUSE_RX = re.compile(r"\b(?:in\s+view\s+of|keeping\s+in\s+view|in\s+the\s+light\s+of|"
                             r"has\s+(?:now\s+)?become\s+(?:necessary|imperative|essential|urgent)|"
                             r"need\s+for\s+(?:a\s+)?(?:new|revised|fresh)|(?:the\s+)?context\s+has\s+changed|"
                             r"in\s+order\s+to\s+(?:address|overcome|tackle|meet|reduce|prevent)|recogni[sz]ing\s+(?:the|that))\b", re.I)


def _clean_heading(t: str) -> str:
    t = re.sub(r"\s+\d{1,3}\s*$", "", t.strip())           # trailing page number in a contents line
    t = HEAD_LEVEL_RX.sub("", t)
    t = ROMAN_RX.sub("", t)
    t = t.strip(" :.-–")
    if t.isupper():
        t = t.title()
    return t


def _level(t: str) -> int:
    m = HEAD_LEVEL_RX.match(t or "")
    if m:
        return m.group(1).count(".") + 1
    if ROMAN_RX.match(t or ""):
        return 3
    return 1


SMALL = {"and", "of", "the", "in", "for", "on", "at", "to", "with", "by", "a", "an", "&", "–", "-", "/", "or", "into",
         "from", "its", "their", "as"}
NUM_HEAD_RX = re.compile(r"^\s*(?:(?:chapter|part|section)\s+)?(\d{1,2}(?:\.\d{1,2}){0,3}\.?|[IVXL]{1,5}\.|[A-Z]\.)\s+(?=\S)")


def _title_run(rest: str) -> str:
    """The heading at the start of a block whose heading and first paragraph were read as one line."""
    head = rest.split(":", 1)[0] if ":" in " ".join(rest.split()[:14]) else None
    if head and 1 <= len(head.split()) <= 14:
        return head
    toks = rest.split()
    run = []
    for t in toks[:20]:
        bare = t.strip("()[],;")
        if bare[:1].isupper() or bare[:1].isdigit() or bare.lower() in SMALL:
            run.append(t)
        else:
            break
    if len(run) < len(toks) and run:
        run = run[:-1]                       # the capitalised first word of the paragraph that follows
    while run and run[-1].lower() in SMALL:
        run.pop()
    caps = [t for t in run if t[:1].isupper() and t.lower() not in SMALL]
    if len(run) >= 2 and len(caps) >= 2:
        return " ".join(run)
    return ""


def doc_headings(blocks) -> list:
    """Section headings of a document of any kind: numbered headings ('3.', '3.2', 'IV.', 'Chapter 2'), including
    ones the PDF text joined to their first paragraph, and short ALL-CAPS lines. Contents lines are left out."""
    from .compare import TOC_RX
    out = []
    for i, b in enumerate(blocks):
        t = re.sub(r"\s+", " ", (b.text or "")).strip()
        if not t or TOC_RX.search(t):
            continue
        words = re.findall(r"[A-Za-z][A-Za-z'’\-]*", t)
        m = NUM_HEAD_RX.match(t)
        name, level = None, 1
        if m:
            num = m.group(1)
            rest = t[m.end():]
            if not rest[:1].isupper():
                continue
            if re.fullmatch(r"[\d.]+", num):
                level = num.rstrip(".").count(".") + 1
            else:
                level = 3                    # roman or lettered items are list points, not sections
            if len(rest.split()) <= 16 and not rest.rstrip().endswith((".", ";", ",")):
                name = rest
            elif level <= 2:
                name = _title_run(rest)
        elif 1 <= len(words) <= 12 and len(t) <= 110 and not t.endswith((".", ",", ";")):
            caps = sum(1 for w in words if w.isupper() and len(w) > 1)
            letters = sum(c.isalpha() for c in t) / max(1, len(t.replace(" ", "")))
            if (caps >= 0.6 * len(words) and not re.search(r"\d{3,}", t) and t[:1].isalpha() and t[:1].isupper()
                    and letters >= 0.7 and re.search(r"[A-Za-z]{4,}", t)):
                if out and out[-1]["block"] == i - 1 and out[-1]["raw_caps"]:
                    out[-1]["heading"] = (out[-1]["heading"] + " " + t.strip(" :.-–").title()).strip()
                    out[-1]["block"] = i
                    continue
                name = t
        if not name:
            continue
        name = re.sub(r"\s+\d{1,3}(?=\s|$)", "", name).strip(" :.-–/")
        if len(re.findall(r"[A-Za-z]{3,}", name)) < 1 or len(name) < 4:
            continue
        raw_caps = name.upper() == name
        if raw_caps:
            name = name.title()
        out.append({"heading": name, "level": level, "block": i, "location": b.location, "raw_caps": raw_caps})
    return out


def sections(blocks, sents: list) -> list:
    """[{heading, level, block, sentence indexes}] for headings that have at least one sentence under them."""
    heads = doc_headings(blocks)
    out = []
    for k, h in enumerate(heads):
        end = heads[k + 1]["block"] if k + 1 < len(heads) else 10 ** 9
        idx = [i for i, s in enumerate(sents) if h["block"] <= s["block"] < end]
        out.append({**h, "sentences": idx})
    # a contents page lists the headings again: drop an empty heading that recurs later in the text
    def key(h):
        return re.sub(r"[^a-z]", "", h["heading"].lower())[:24]
    keep = []
    for k, h in enumerate(out):
        if not h["sentences"] and any(key(h) and key(x).startswith(key(h)[:18]) for x in out[k + 1:]):
            continue
        keep.append(h)
    return keep


def _section_of(secs: list, n: int, max_level: int) -> list:
    """Sentence index -> topic name, rolling sub-sections up into their parent at max_level."""
    owner = [None] * n
    current = None
    for sec in secs:
        if sec["level"] <= max_level or current is None:
            current = sec["heading"]
        for i in sec["sentences"]:
            owner[i] = current
    return owner


def heading_topics(blocks, sents: list) -> Optional[list]:
    """Topic per sentence from the document's own headings, or None when it has too few headings to use."""
    secs = sections(blocks, sents)
    if not sents or sum(1 for x in secs if x["sentences"]) < 3:
        return None
    covered = sum(len(s["sentences"]) for s in secs) / len(sents)
    if covered < 0.5:
        return None
    for lvl in (1, 2, 3):
        owner = _section_of(secs, len(sents), lvl)
        cnt = Counter(o for o in owner if o)
        if len(cnt) >= 4 and max(cnt.values()) <= 0.4 * len(sents):
            if lvl < 3:                       # split a very large section into its own sub-sections
                deeper = _section_of(secs, len(sents), lvl + 1)
                big = {name for name, c in cnt.items() if c > max(40, 0.12 * len(sents))}
                owner = [d if (o in big and d) else o for o, d in zip(owner, deeper)]
            return owner
    owner = _section_of(secs, len(sents), 3)
    return owner if len(set(o for o in owner if o)) >= 3 else None


def _kmeans(X, k: int, iters: int = 25) -> list:
    """Deterministic k-means on unit vectors (farthest-point start)."""
    n = len(X)
    k = max(1, min(k, n))
    centers = [X[0]]
    while len(centers) < k:
        far = min(range(n), key=lambda i: max(_dot(X[i], c) for c in centers))
        centers.append(X[far])
    assign = [0] * n
    for _ in range(iters):
        new = [max(range(len(centers)), key=lambda c: _dot(X[i], centers[c])) for i in range(n)]
        if new == assign and _:
            break
        assign = new
        centers = [(_mean([X[i] for i in range(n) if assign[i] == c]) if c in assign else centers[c])
                   for c in range(len(centers))]
    return assign


def _keywords(texts: list, all_counts: Counter, total: int, top: int = 3) -> str:
    c = Counter()
    for t in texts:
        c.update(set(w for w in re.findall(r"[a-z][a-z-]{2,}", t.lower()) if w not in STOP))
    scored = sorted(((n / len(texts)) * math.log((total + 1) / (all_counts[w] + 1)), w) for w, n in c.items() if n >= 2)
    words = [w for _s, w in sorted(scored, reverse=True)[:top]]
    return ", ".join(words) if words else "other"


def cluster_topics(texts: list, X) -> list:
    """Topic label per sentence from grouping by similarity; labels are each group's most distinctive words."""
    n = len(texts)
    if n == 0:
        return []
    k = max(2, min(15, round(math.sqrt(n / 3))))
    assign = _kmeans(X, k)
    allc = Counter()
    for t in texts:
        allc.update(set(w for w in re.findall(r"[a-z][a-z-]{2,}", t.lower()) if w not in STOP))
    labels = {c: _keywords([texts[i] for i in range(n) if assign[i] == c], allc, n) for c in set(assign)}
    return [labels[a] for a in assign]


# optional sector preset (never the default): water policy topics by keyword
WATER_PRESET = [
    ("Drinking water priority", r"drinking|domestic\s+water|potable|first\s+priority"),
    ("Groundwater", r"ground\s*water|aquifer|tube\s*well|recharge"),
    ("Irrigation & agriculture", r"irrigat|agricultur|crop|canal|command\s+area|farm"),
    ("Pricing & tariff", r"pric|tariff|water\s+rate|cost\s+recovery|charges"),
    ("Institutions & regulator", r"authorit|commission|regulat|institution|department|board|secretariat"),
    ("Water quality & pollution", r"pollut|quality|effluent|sewage|waste\s*water|contamina"),
    ("Floods & drought", r"flood|drought|embankment"),
    ("Climate change", r"climat"),
    ("Participation", r"participat|user|panchayat|community|stakeholder|wua"),
    ("Data & information", r"data|information|monitor|database|mis\b"),
    ("Allocation", r"allocat|priorit"),
    ("Industry", r"industr"),
    ("Environmental flows", r"e-?flow|environmental\s+flow|ecolog|aviral"),
    ("Rainwater harvesting", r"rain\s*water|harvest"),
    ("Private sector", r"private"),
    ("Hydropower & navigation", r"hydro|power|navigat"),
]


def preset_topics(texts: list, preset: str) -> list:
    if preset != "water":
        raise ValueError(f"unknown topic preset: {preset}")
    rx = [(n, re.compile(p, re.I)) for n, p in WATER_PRESET]
    out = []
    for t in texts:
        hits = [(len(r.findall(t)), -k, n) for k, (n, r) in enumerate(rx)]
        best = max(hits)
        out.append(best[2] if best[0] else "Other")
    return out


# ---------------------------------------------------------------------------------------------- matching
def _para(sent: dict, blocks) -> str:
    from .compare import LEAD_SECTION_RX
    for t in (sent["text"], (blocks[sent["block"]].text if 0 <= sent["block"] < len(blocks) else "")):
        m = LEAD_SECTION_RX.match(t or "")
        if m:
            return m.group(0).strip().rstrip(".")
    return ""


def _quote(sent: dict, blocks, score: Optional[float] = None) -> dict:
    q = {"text": sent["text"], "location": sent["location"], "para": _para(sent, blocks)}
    if score is not None:
        q["similarity"] = round(score, 3)
    return q


def _reasons(new: list, new_blocks, new_topic: list, Xn, topic_vec: dict) -> dict:
    """Topic -> quotes from the new version that state a motivation, linked by similarity. Never invented."""
    secs = sections(new_blocks, new)
    motive_sec = set()
    for s in secs:
        if MOTIVE_HEAD_RX.search(s["heading"]):
            motive_sec.update(s["sentences"])
    out: dict = {}
    for j, s in enumerate(new):
        t = s["text"]
        strong_cue = CAUSE_RX.search(t) if j in motive_sec else STRONG_CAUSE_RX.search(t)
        if not strong_cue:
            continue
        best, bt = -1.0, None
        for name, vec in topic_vec.items():
            sim = _dot(Xn[j], vec)
            if sim > best:
                best, bt = sim, name
        # a reason inside a topic's own section belongs to that topic; otherwise to the most similar topic
        topic = new_topic[j] if new_topic[j] in topic_vec and j not in motive_sec else bt
        if topic is None or (topic == bt and best < REASON_MIN):
            continue
        out.setdefault(topic, []).append({"text": t, "location": s["location"], "para": _para(s, new_blocks),
                                          "cue": strong_cue.group(0), "similarity": round(best, 3)})
    for k in out:
        out[k] = sorted(out[k], key=lambda r: -r["similarity"])[:2]
    return out


LEX_STOP = set("""the of and to in a for be is are shall will should by with on as from this that which it at or an its
their all any such other also would may can not have has been""".split())


def _lex_tokens(t: str) -> set:
    return {w[:6] for w in re.findall(r"[a-z]{3,}", (t or "").lower()) if w not in LEX_STOP}


def lexical_overlap(old_texts: list, new_texts: list) -> list:
    """Share of distinctive words (idf-weighted, crude 6-letter stems) two sentences have in common, 0-1."""
    To, Tn = [_lex_tokens(t) for t in old_texts], [_lex_tokens(t) for t in new_texts]
    df = Counter(w for d in To + Tn for w in d)
    N = len(To) + len(Tn)
    idf = {w: math.log(N / (1 + c)) for w, c in df.items()}
    wn = [sum(idf[w] for w in b) for b in Tn]
    out = []
    for a in To:
        sa = sum(idf[w] for w in a)
        row = []
        for b, sb in zip(Tn, wn):
            inter = a & b
            row.append(sum(idf[w] for w in inter) / (min(sa, sb) + 1e-9) if inter else 0.0)
        out.append(row)
    return out


def match_scores(S: list, L: list) -> list:
    """match score = cosine - (the old sentence's usual similarity + the new sentence's usual similarity) / 2
    + LEX_W x shared distinctive words. The middle term stops a broad sentence ('Water is a precious resource')
    from being everyone's best match (cross-domain similarity local scaling, CSLS)."""
    if not S or not S[0]:
        return [[] for _ in S]
    n_old, n_new = len(S), len(S[0])
    k1, k0 = min(HUB_K, n_new), min(HUB_K, n_old)
    ro = [sum(sorted(r)[-k1:]) / k1 for r in S]
    cols = [[S[i][j] for i in range(n_old)] for j in range(n_new)]
    rn = [sum(sorted(c)[-k0:]) / k0 for c in cols]
    return [[S[i][j] - (ro[i] + rn[j]) / 2 + LEX_W * L[i][j] for j in range(n_new)] for i in range(n_old)]


def compare_meaning(old_blocks, new_blocks, embedder=None, threshold: float = MATCH, topics: str = "auto",
                    old_sents: Optional[list] = None, new_sents: Optional[list] = None) -> dict:
    """The meaning comparison as a dict (added to the compare report under 'meaning')."""
    import time
    from .compare import _sentences
    t0 = time.time()
    emb = embedder or FastEmbedder()
    old = old_sents if old_sents is not None else _sentences(old_blocks)
    new = new_sents if new_sents is not None else _sentences(new_blocks)
    # a lead-in ('The objectives of the policy are to:') says nothing by itself and would match everything
    old = [x for x in old if _usable(x["text"])]
    new = [x for x in new if _usable(x["text"])]
    Xo = emb.embed([s["text"] for s in old]) if old else _matrix([])
    Xn = emb.embed([s["text"] for s in new]) if new else _matrix([])
    t_embed = time.time() - t0
    S = _sim(Xo, Xn)
    L = lexical_overlap([x["text"] for x in old], [x["text"] for x in new])
    MS = match_scores(S, L)

    # topics of the new version (and the old version, for what the new one no longer covers)
    source = topics
    if topics in ("auto", "headings"):
        new_topic = heading_topics(new_blocks, new)
        old_own = heading_topics(old_blocks, old)
        source = "headings"
        if new_topic is None:
            if topics == "headings":
                new_topic = ["Other"] * len(new)
            else:
                source = "clusters"
    if source == "clusters" or topics == "clusters":
        source = "clusters"
        texts = [s["text"] for s in old] + [s["text"] for s in new]
        X = (list(Xo) + list(Xn))
        lab = cluster_topics(texts, X)
        old_own, new_topic = lab[:len(old)], lab[len(old):]
    elif topics not in ("auto", "headings"):
        source = f"preset:{topics}"
        old_own = preset_topics([s["text"] for s in old], topics)
        new_topic = preset_topics([s["text"] for s in new], topics)
    new_topic = [t or "Opening text (before the first heading)" for t in new_topic]
    old_own = old_own or [None] * len(old)
    tv = {}
    for name in dict.fromkeys(new_topic):
        tv[name] = _mean([Xn[j] for j in range(len(new)) if new_topic[j] == name])

    items_by_topic: dict = {}
    matched_new = set()

    def put(topic, item):
        items_by_topic.setdefault(topic, []).append(item)

    for i, o in enumerate(old):
        row = MS[i] if MS else []
        if not row:
            j, best = None, -1.0
        else:
            j = max(range(len(row)), key=row.__getitem__)
            best = row[j]
        if j is not None and best >= threshold:
            extra = sorted((k for k in range(len(row)) if k != j and row[k] >= max(threshold, best - EXTRA_MARGIN)),
                           key=lambda k: -row[k])[:2]
            js = [j] + extra
            matched_new.update(js)
            label, why = change_label(o["text"], " ".join(new[k]["text"] for k in js) if len(js) > 1 else new[j]["text"])
            if label == "changed figure" and len(js) > 1:
                label, why = change_label(o["text"], new[j]["text"])
            put(new_topic[j], {"label": label, "match_score": round(best, 3), "similarity": round(S[i][j], 3),
                               "rule": why, "old": _quote(o, old_blocks),
                               "new": [_quote(new[k], new_blocks, S[i][k]) for k in js], "_o": i})
        else:
            # truly dropped: file it under the nearest new topic, or under its own old heading
            topic, tsim = None, -1.0
            for name, vec in tv.items():
                if vec is None:
                    continue
                sim = _dot(Xo[i], vec)
                if sim > tsim:
                    topic, tsim = name, sim
            if topic is None or tsim < TOPIC_MIN:
                topic = f"{old_own[i]} (old version only)" if old_own[i] else "Other (old version only)"
            near = _quote(new[j], new_blocks, S[i][j]) if j is not None else None
            put(topic, {"label": "dropped", "possible_match": bool(j is not None and best >= WEAK),
                        "match_score": round(best, 3), "similarity": round(S[i][j], 3) if j is not None else 0.0,
                        "rule": [], "old": _quote(o, old_blocks), "new": [], "nearest_new": near, "_o": i})
    col_best = [max((MS[i][j] for i in range(len(old))), default=-1.0) for j in range(len(new))]
    for j, n in enumerate(new):
        if j in matched_new or col_best[j] >= threshold:
            continue
        put(new_topic[j], {"label": "new", "match_score": round(col_best[j], 3), "rule": [], "old": None,
                           "new": [_quote(n, new_blocks)], "_n": j})

    reasons = _reasons(new, new_blocks, new_topic, Xn, {k: v for k, v in tv.items() if v is not None})
    order = list(dict.fromkeys(new_topic)) + [k for k in items_by_topic if k not in new_topic]
    out_topics, totals = [], Counter()
    for name in order:
        items = items_by_topic.get(name)
        if not items:
            continue
        items.sort(key=lambda x: (LABELS.index(x["label"]), x.get("_o", x.get("_n", 0))))
        for x in items:
            x.pop("_o", None)
            x.pop("_n", None)
        counts = Counter(x["label"] for x in items)
        totals.update(counts)
        out_topics.append({"topic": name, "counts": {k: counts.get(k, 0) for k in LABELS}, "items": items,
                           "why": reasons.get(name, []),
                           "why_note": "" if reasons.get(name) else "Reason not stated in the document"})
    return {
        "model": getattr(emb, "name", type(emb).__name__),
        "model_note": MODEL_NOTES.get(getattr(emb, "name", ""), ""),
        "threshold": threshold, "topic_source": source,
        "seconds": {"embedding": round(t_embed, 2), "total": round(time.time() - t0, 2)},
        "sentences": {"old": len(old), "new": len(new)},
        "summary": {k: totals.get(k, 0) for k in LABELS},
        "topics": out_topics,
        "method": ("Each old sentence is matched to the new sentence with the highest match score, if it is at least "
                   f"{threshold:.3f}. Match score = cosine similarity of the two sentence embeddings, minus the average "
                   f"of each sentence's usual similarity (mean of its {HUB_K} best), plus {LEX_W:.2f} x the share of "
                   "distinctive words they have in common. Other new sentences within "
                   f"{EXTRA_MARGIN:.2f} of the best are listed too. Labels come from rules: obligation words "
                   "(shall/must/will/ensure > should/would > may/endeavour/encourage/as far as possible), and "
                   "deadlines, figures and named bodies added or removed in a commitment. Reasons are quotes from the "
                   "new version that state a motive, linked to a topic by similarity."),
        "caveat": "Similarity is not understanding: check the quotes before relying on a label.",
    }


# ---------------------------------------------------------------------------------------------- optional AI summary
AI_LABEL = "AI summary, check the quotes"
AI_SYSTEM = ("You summarise how one topic changed between two versions of a policy document. Use ONLY the numbered "
             "quotes given. Do not add facts, motives, numbers or names that are not in the quotes. If the quotes do "
             "not say why something changed, do not guess why. Answer as JSON: {\"summary\": \"2-3 sentences\", "
             "\"quote_ids\": [numbers of the quotes you relied on]}.")


def _norm_q(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[“”\"'‘’]", "", (t or "").lower())).strip()


def topic_quotes(topic: dict, limit: int = 12) -> list:
    qs = []
    for it in topic["items"][:limit]:
        if it.get("old"):
            qs.append(("OLD", it["label"], it["old"]["text"]))
        for n in it.get("new") or []:
            qs.append(("NEW", it["label"], n["text"]))
    for w in topic.get("why") or []:
        qs.append(("NEW, stated reason", "why", w["text"]))
    return qs


def validate_summary(summary: str, quotes: list) -> list:
    """Problems with an AI summary: quoted text or figures that are not in the shown quotes."""
    problems = []
    blob = _norm_q(" ".join(q[2] for q in quotes))
    for m in re.finditer(r"[“\"']([^“”\"']{6,})[”\"']", summary or ""):
        if _norm_q(m.group(1)) not in blob:
            problems.append(f"quotes text that is not in the document quotes: “{m.group(1)[:80]}”")
    nums_q = set(re.findall(r"\d+(?:\.\d+)?", blob.replace(",", "")))
    for num in re.findall(r"\d+(?:\.\d+)?", (summary or "").replace(",", "")):
        if num not in nums_q:
            problems.append(f"gives the figure {num}, which is not in the quotes")
    return problems


def ai_summaries(meaning: dict, llm, max_topics: int = 25) -> dict:
    """Add an AI summary to each topic (grounded only in that topic's quotes). Rejected when it cites text or figures
    that are not in the quotes. `llm` is an LLMClient (or anything with complete_json(system, user))."""
    done = rejected = failed = 0
    for t in meaning.get("topics", [])[:max_topics]:
        qs = topic_quotes(t)
        if not qs:
            continue
        user = f"Topic: {t['topic']}\n\n" + "\n".join(f"[{k}] ({side}; label: {lab}) {txt}"
                                                       for k, (side, lab, txt) in enumerate(qs, 1))
        try:
            data = llm.complete_json(AI_SYSTEM, user, max_tokens=400)
        except Exception as e:
            t["ai_summary"] = {"label": AI_LABEL, "status": "failed", "text": "",
                               "problems": [type(e).__name__]}
            failed += 1
            continue
        text = str((data or {}).get("summary") or "").strip() if isinstance(data, dict) else ""
        ids = [i for i in ((data or {}).get("quote_ids") or []) if isinstance(i, int)] if isinstance(data, dict) else []
        problems = validate_summary(text, qs)
        if not text:
            problems.append("empty answer")
        if not ids:
            problems.append("no quote ids given")
        elif any(not 1 <= i <= len(qs) for i in ids):
            problems.append("refers to quote numbers that were not shown")
        if problems:
            t["ai_summary"] = {"label": AI_LABEL, "status": "rejected", "text": "", "rejected_text": text,
                               "problems": problems}
            rejected += 1
        else:
            t["ai_summary"] = {"label": AI_LABEL, "status": "ok", "text": text, "quote_ids": ids}
            done += 1
    meaning["ai"] = {"model": getattr(llm, "label", "custom"), "summaries": done, "rejected": rejected,
                     "failed": failed, "label": AI_LABEL}
    return meaning
