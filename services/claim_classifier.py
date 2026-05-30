def classify_claim(claim: str):

    claim_lower = claim.lower()

    if any(word in claim_lower for word in [
        "percent",
        "%",
        "million",
        "billion"
    ]):
        return "statistical"

    if any(word in claim_lower for word in [
        "study",
        "research",
        "scientist",
        "science"
    ]):
        return "scientific"

    if any(word in claim_lower for word in [
        "government",
        "minister",
        "president",
        "election"
    ]):
        return "political"

    if any(word in claim_lower for word in [
        "vaccine",
        "cancer",
        "disease",
        "health"
    ]):
        return "health"

    return "general"
