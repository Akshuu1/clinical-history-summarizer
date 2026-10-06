import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.routes.extract import router as extract_router

app = FastAPI(
    title="Clinical History Summarizer",
    description="AI-powered structured extraction from clinical notes.",
    version="0.1.0",
)

# Allow CORS so external frontends can call the API easily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extract_router)

@app.get("/health")
def health():
    return {"status": "ok"}

# Mount the modern frontend static files at the root
# Ensure the public directory exists
os.makedirs("public", exist_ok=True)
app.mount("/", StaticFiles(directory="public", html=True), name="public")
