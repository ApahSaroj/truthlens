from services.nlp_processor import process_text


def extract_claims(text: str):

    print("=== NEW SPACY CLAIM EXTRACTOR ===")

    doc = process_text(text)

    claims = []

    for sent in doc.sents:

        sentence = sent.text.strip()

        if not sentence:
            continue

        has_entity = len(sent.ents) > 0

        has_number = any(
            token.like_num
            for token in sent
        )

        if has_entity or has_number:

            claims.append({
                "claim": sentence,
                "type": "potential_claim"
            })

    return claims
