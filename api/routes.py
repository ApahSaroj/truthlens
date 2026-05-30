from fastapi import APIRouter
from pydantic import BaseModel

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

    return {
        "received_type": request.type,
        "received_content": request.content,
        "message": "Analysis pipeline coming soon"
    }
