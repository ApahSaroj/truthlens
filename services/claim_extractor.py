import re


def extract_claims(text: str):

    claims = []

    sentences = re.split(r"[.!?]+", text)

    for sentence in sentences:

        sentence = sentence.strip()

        if not sentence:
            continue

        has_number = bool(re.search(r"\d", sentence))

        if has_number:
            claims.append({
                "claim": sentence,
                "type": "statistical_claim"
            })

    return claims
