from fastapi import FastAPI
from api.routes import router

app = FastAPI(
    title="TruthLens",
    version="0.1"
)

app.include_router(router)

@app.get("/")
def home():
    return {
        "project": "TruthLens",
        "status": "running"
    }
