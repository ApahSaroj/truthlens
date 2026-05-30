from fastapi import APIRouter
from pydantic import BaseModel
from services.claim_extractor import extract_claims

router = APIRouter()

class AnalyzeRequest(BaseModel):
    type: str
    content: str


@router.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@router.post("/analyze")
def analyze(request: AnalyzeRequest):

    claims = extract_claims(request.content)

    return {
        "input_type": request.type,
        "claims_found": len(claims),
        "claims": claims
    }
        "message": "Analysis pipeline coming soon"
    }
