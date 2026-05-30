import spacy


nlp = spacy.load("en_core_web_sm")


def process_text(text: str):
    """
    Process text using spaCy NLP pipeline.
    """

    return nlp(text)
