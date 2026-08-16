from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router

app = FastAPI(
    title="Healthcare Interoperability Assistant API",
    version="0.1.0",
    description="Unified interoperability API for RAG assistance, deterministic format conversion, and PDF ingestion to Qdrant.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Healthcare Interoperability Assistant API is running.",
        "docs": "/docs",
        "health": "/api/health",
        "query": "/api/query",
        "convert": "/api/convert",
        "ingest_pdf": "/api/ingest/pdf",
    }
