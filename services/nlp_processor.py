import spacy

nlp = spacy.load("en_core_web_sm")


def process_text(text):

    return nlp(text)
