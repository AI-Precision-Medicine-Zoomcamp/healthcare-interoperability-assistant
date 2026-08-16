from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from src.config.config import PDF_UPLOAD_MAX_MB


class InteroperabilityQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="User question or interoperability issue")
    payload: str | None = Field(default=None, description="Optional FHIR JSON or HL7 v2 message")
    profile_url: str | None = Field(default=None, description="Optional FHIR profile URL")
    capability: str | None = Field(default=None, description="Optional UI capability hint for intent routing")


class InteroperabilityQueryResponse(BaseModel):
    intent: str
    validation_result: dict | None = None
    citations: list[str]
    explanation: str
    correction: str


class ConversionRequest(BaseModel):
    source_format: Literal["json", "fhir", "hl7"]
    target_format: Literal["json", "fhir", "hl7"]
    payload: str = Field(..., min_length=2, description="Input payload in source format")
    resource_type: str | None = Field(default=None, description="Optional target FHIR resourceType hint")
    message_type: str | None = Field(default=None, description="Optional target HL7 message type hint (for example ORU^R01)")


class ConversionResponse(BaseModel):
    source_format: Literal["json", "fhir", "hl7"]
    target_format: Literal["json", "fhir", "hl7"]
    converted_payload: str
    converted_json: dict | None = None
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PDFIngestResponse(BaseModel):
    status: str
    reason: str
    filename: str
    doc_hash: str
    pages: int
    chunks_total: int
    chunks_inserted: int
    chunks_skipped_duplicate: int
    collection: str


class HealthResponse(BaseModel):
    status: str
    ready: bool
    agent_loaded: bool
    vector_index_exists: bool
    vector_db_provider: str
    qdrant_url: str | None = None
    qdrant_collection: str | None = None
    qdrant_connected: bool | None = None
    qdrant_collection_exists: bool | None = None
    api_key_configured: bool
    api_key_sources: dict[str, bool]
    last_error: str | None = None
    vector_index_path: str
