"""spaCy pipeline with a graceful fallback when the model is not installed."""
import re

try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:  # model not downloaded
        nlp = None
except ImportError:  # spaCy not installed
    nlp = None


class _Sent:
    def __init__(self, text):
        self.text = text
        self.ents = []
        self._tokens = text.split()

    def __iter__(self):
        for t in self._tokens:
            yield type("Tok", (), {"like_num": bool(re.search(r"\d", t))})()


class _Doc:
    def __init__(self, text):
        self.sents = [_Sent(s) for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def process_text(text: str):
    """Process text using spaCy if available, else a regex sentence splitter."""
    if nlp is not None:
        return nlp(text)
    return _Doc(text)
