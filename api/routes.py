from fastapi import APIRouter
from pydantic import BaseModel

from services.claim_extractor import extract_claims
from services.content_extractor import extract_from_url

router = APIRouter()


class AnalyzeRequest(BaseModel):
    type: str
    content: str


@router.post("/analyze", tags=["legacy"])
def analyze(request: AnalyzeRequest):
    """Original generic endpoint: lists sentences that contain an entity or a number."""
    if request.type == "url":
        extracted = extract_from_url(request.content)
        if not extracted["success"]:
            return extracted
        claims = extract_claims(extracted["content"])
        return {"input_type": "url", "title": extracted["title"], "claims_found": len(claims), "claims": claims}
    claims = extract_claims(request.content)
    return {"input_type": "text", "claims_found": len(claims), "claims": claims}
