from fastapi import FastAPI

from app.routes.extract import router as extract_router

app = FastAPI(
    title="Clinical History Summarizer",
    description="AI-powered structured extraction from clinical notes.",
    version="0.1.0",
)

app.include_router(extract_router)


@app.get("/health")
def health():
    return {"status": "ok"}
