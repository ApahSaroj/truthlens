"""Polarity, direction words and extra assertions in a claim (v0.3 correctness rules).

* `negated(text)`: does the clause deny something ("was not", "never", "denied that", "it is false that")?
  Comparator phrases that are not denials ("not less than", "no more than", "not only") are ignored.
* `direction(text, number_start)`: a decline/rise verb directly governing a figure ("fell 0.7 per cent"
  -> -1, "rose 0.7 per cent" -> +1). "fell to 3.2%" / "rose from" describe a level, not a signed change,
  and return 0.
* `extra_assertions(text)`: parts of a sentence beyond its figures that need their own evidence:
  superlatives and records ("the lowest in a decade", "first", "all-time high"), causal links
  ("because", "due to", "driven by") and comparisons ("higher than", "outpaced"). A sentence can only be
  SUPPORTED when these parts are supported too.
"""
from __future__ import annotations

import re

# phrases that contain a negation word but are not denials
_NOT_DENIAL = re.compile(
    r"\b(?:not|no)\s+(?:less|more|fewer|lower|higher|greater|later|earlier|before|after)\s+than\b|"
    r"\bnot\s+only\b|\bnot\s+just\b|\bno\s+(?:doubt|wonder|longer)\b|\bnot\s+(?:least|surprisingly)\b|"
    r"\bno\.\s*\d|\bnone\s+other\s+than\b|\bif\s+not\b|\bwhether\s+or\s+not\b|\bnot\s+to\s+mention\b",
    re.I)
_NEG = re.compile(
    r"\b(?:not|never|neither|nor|no|none|nobody|nothing|cannot|can't|won't|wasn't|weren't|isn't|aren't|hasn't|"
    r"haven't|hadn't|didn't|doesn't|don't|shouldn't|couldn't|wouldn't|denied|denies|deny|refuted|refutes|rejected "
    r"(?:claims|reports) that|untrue|false that|incorrect that|wrong that|failed to|fails to|did\s+n[o']t)\b|n't\b",
    re.I)


def negation_cues(text: str) -> list[str]:
    t = _NOT_DENIAL.sub(" ", (text or "").replace("’", "'"))
    return [m.group(0).lower() for m in _NEG.finditer(t)]


def negated(text: str) -> bool:
    """Odd number of denial cues = the clause denies its content ("not untrue" counts as affirmative)."""
    return len(negation_cues(text)) % 2 == 1


DECLINE = r"fell|fall(?:s|en|ing)?|declin(?:ed|es|ing|e)|decreas(?:ed|es|ing|e)|dropp(?:ed|ing)|drops?|contract(?:ed|ing|s)?|" \
          r"shr[ua]nk|shrinks?|slipp(?:ed|ing)|dipp(?:ed|ing)|plunged|plummeted|tumbled|eased|slid"
RISE = r"rose|ris(?:es|en|ing)|rise|increas(?:ed|es|ing|e)|grew|grow(?:s|n|ing)?|climb(?:ed|ing|s)?|jump(?:ed|ing|s)?|" \
       r"surg(?:ed|es|ing)|expand(?:ed|ing|s)?|gain(?:ed|s)?|went up|was up|were up"
_DIR_RX = re.compile(rf"\b(?P<d>{DECLINE})|\b(?P<r>{RISE})", re.I)
_NEG_WORDS_RX = re.compile(r"\b(?:negative|deflation|contraction|a decline of|a fall of|a drop of|down)\b", re.I)


def direction(text: str, number_start: int) -> int:
    """-1 / +1 when a decline / rise word directly governs the figure at `number_start`; else 0."""
    before = text[max(0, number_start - 40):number_start]
    # stay inside the clause that holds the figure
    before = re.split(r"[;:]|,\s+(?:while|but|and|whereas)\b|\b(?:while|whereas|but)\b", before)[-1]
    m = None
    for m in _DIR_RX.finditer(before):
        pass
    if m is None:
        if re.search(r"\b(?:negative|contraction of|decline of|fall of|drop of|deflation of)\s*(?:of\s*)?$", before, re.I):
            return -1
        return 0
    gap = before[m.end():]
    # "fell to 3.2%", "rose from", "grew at 7%"... describe levels or rates, not the sign of the figure
    if re.search(r"\b(?:to|from|at|than|for|with|over|in|since)\b", gap, re.I):
        return 0
    if len(gap.split()) > 3:
        return 0
    return -1 if m.group("d") else 1


SUPERLATIVE_RX = re.compile(
    r"\b(?:the\s+)?(?:lowest|highest|largest|biggest|smallest|fastest|slowest|strongest|weakest|best|worst|"
    r"steepest|sharpest|first|only|most\s+(?!recent\b|of\b|likely\b)\w+|least\s+(?!of\b)\w+)\b[^.;,]{0,40}|"
    r"\b(?:record(?:\s+(?:high|low|level))?|all-time\s+(?:high|low)|unprecedented|never\s+before)\b[^.;,]{0,30}",
    re.I)
CAUSAL_RX = re.compile(
    r"\b(?:because(?:\s+of)?|due\s+to|owing\s+to|driven\s+by|thanks\s+to|as\s+a\s+result\s+of|caused\s+by|"
    r"led\s+by|on\s+account\s+of|attributed\s+to|resulting\s+from|which\s+(?:led|caused)|leading\s+to|helped\s+by)\b[^.;]{0,80}",
    re.I)
COMPARE_RX = re.compile(
    r"\b(?:higher|lower|faster|slower|more|less|fewer|better|worse|larger|smaller|greater|bigger)\s+than\b[^.;,]{0,60}|"
    r"\b(?:outpac\w*|outperform\w*|surpass\w*|overt(?:ook|ake|aken)|ahead\s+of|exceed\w*|doubl\w*|tripl\w*|"
    r"twice\s+(?:as|the))\b[^.;,]{0,60}",
    re.I)
# comparators that only qualify the figure itself ("more than 5%") are not extra assertions
_NUMERIC_COMPARATOR = re.compile(r"^\s*(?:more|less|fewer|higher|lower|greater)\s+than\s+[₹$]?\s*[\d(]", re.I)


def extra_assertions(text: str) -> list[dict]:
    """Assertions in a sentence beyond its figures: [{'kind': 'superlative'|'causal'|'comparison', 'text': ...}]."""
    out = []
    for kind, rx in (("superlative", SUPERLATIVE_RX), ("causal", CAUSAL_RX), ("comparison", COMPARE_RX)):
        for m in rx.finditer(text or ""):
            frag = m.group(0).strip(" ,")
            if kind == "comparison" and _NUMERIC_COMPARATOR.match(frag):
                continue
            if kind == "superlative" and re.fullmatch(r"(?:the\s+)?(?:first|last)\s+(?:quarter|half|week|month|phase|round|edition|advance|revised)\b.*", frag, re.I):
                continue   # "first quarter" is a period, not a record
            if kind == "superlative" and re.match(r"first\s+\w+(?:ed|en)\b", frag, re.I):
                continue   # "first released on", "first published in": when, not a record
            if kind == "superlative" and re.match(r"(?:the\s+)?only\b", frag, re.I) and len(frag.split()) < 3:
                continue
            if not any(frag.lower() in o["text"].lower() or o["text"].lower() in frag.lower() for o in out):
                out.append({"kind": kind, "text": frag})
    return out


_STOP = {"the", "a", "an", "in", "of", "to", "by", "than", "since", "over", "more", "for", "on", "and", "was", "were",
         "its", "which", "as", "at", "is", "are", "be", "been", "with", "that", "this", "all"}


def cue_head(extra: dict) -> str:
    """The word that makes the assertion: 'lowest', 'first', 'due', 'faster', 'record'..."""
    words = [w for w in re.findall(r"[a-z][a-z\-]+", extra["text"].lower()) if w not in _STOP]
    return words[0] if words else ""


def cue_words(extra: dict) -> set:
    """Content words of an extra assertion other than its head word."""
    words = re.findall(r"[a-z][a-z\-]+", extra["text"].lower())
    head = cue_head(extra)
    return {w for w in words if w not in _STOP and w != head and len(w) > 2}


def stated_in(extra: dict, passage: str) -> bool:
    """Does the passage state this extra assertion? Its head word (or its stem) must appear, plus at least
    half of its other content words."""
    low = (passage or "").lower()
    head = cue_head(extra)
    if not head or not re.search(rf"\b{re.escape(head[:max(4, len(head) - 2)])}", low):
        return False
    rest = cue_words(extra)
    if not rest:
        return True
    hit = sum(1 for w in rest if re.search(rf"\b{re.escape(w[:max(4, len(w) - 2)])}", low))
    return hit / len(rest) >= 0.5
