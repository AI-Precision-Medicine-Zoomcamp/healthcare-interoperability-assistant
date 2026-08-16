from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.api.schemas import (
    ConversionRequest,
    ConversionResponse,
    HealthResponse,
    InteroperabilityQueryRequest,
    InteroperabilityQueryResponse,
    PDFIngestResponse,
)
from src.config.config import PDF_UPLOAD_MAX_MB
from src.services.interoperability_runtime import runtime

router = APIRouter(prefix="/api", tags=["assistant"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(**runtime.health())


@router.post("/query", response_model=InteroperabilityQueryResponse)
def query(request: InteroperabilityQueryRequest) -> InteroperabilityQueryResponse:
    try:
        result = runtime.query(
            query=request.query,
            payload=request.payload,
            profile_url=request.profile_url,
            capability=request.capability,
        )
        return InteroperabilityQueryResponse(**result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"Vector index is missing. Run ingestion first. {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@router.post("/convert", response_model=ConversionResponse)
def convert(request: ConversionRequest) -> ConversionResponse:
    try:
        result = runtime.convert(
            query=request.query,
            source_format=request.source_format,
            target_format=request.target_format,
            payload=request.payload,
            resource_type=request.resource_type,
            message_type=request.message_type,
        )
        return ConversionResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversion error: {exc}") from exc


@router.post("/ingest/pdf", response_model=PDFIngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    doc_type: str = Form("pdf_upload"),
    dedup_mode: str = Form("strict"),
) -> PDFIngestResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are supported for this endpoint.")

    file_bytes = await file.read()
    max_bytes = PDF_UPLOAD_MAX_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=400, detail=f"PDF exceeds {PDF_UPLOAD_MAX_MB}MB max size.")

    try:
        result = runtime.ingest_pdf(
            file_bytes=file_bytes,
            filename=file.filename,
            doc_type=doc_type,
            dedup_mode=dedup_mode,
        )
        return PDFIngestResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF ingest error: {exc}") from exc


@router.post("/reload")
def reload_runtime() -> dict[str, str]:
    runtime.reset()
    return {"message": "Runtime reset. It will be reloaded on the next query."}
