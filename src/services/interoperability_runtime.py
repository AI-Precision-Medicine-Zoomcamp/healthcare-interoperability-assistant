from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

from src.agents.agent_service import AgentService
from src.config.config import (
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
    VECTOR_DB_PROVIDER,
    has_groq_api_key,
    has_openai_api_key,
    has_qdrant_config,
)
from src.tools.conversion_tools import FormatConverter
from src.services.pdf_ingestion_service import PDFIngestionService

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
VECTORSTORE_DIR = ROOT_DIR / "data" / "vectorstore" / "faiss_index"


class InteroperabilityRuntime:
    """Lazily initializes heavy runtime objects and exposes health/query helpers."""

    def __init__(self) -> None:
        self._agent: AgentService | None = None
        self._pdf_ingestor: PDFIngestionService | None = None
        self._last_error: str | None = None
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._agent = None
            self._pdf_ingestor = None
            self._last_error = None

    def _load_agent(self) -> AgentService:
        if self._agent is not None:
            return self._agent

        with self._lock:
            if self._agent is not None:
                return self._agent
            try:
                self._agent = AgentService()
                self._last_error = None
                return self._agent
            except Exception as exc:
                self._last_error = str(exc)
                raise

    def _load_pdf_ingestor(self) -> PDFIngestionService:
        if self._pdf_ingestor is not None:
            return self._pdf_ingestor

        with self._lock:
            if self._pdf_ingestor is not None:
                return self._pdf_ingestor
            try:
                self._pdf_ingestor = PDFIngestionService()
                self._last_error = None
                return self._pdf_ingestor
            except Exception as exc:
                self._last_error = str(exc)
                raise

    def query(
        self,
        query: str,
        payload: str | None = None,
        profile_url: str | None = None,
        capability: str | None = None,
    ) -> dict[str, Any]:
        agent = self._load_agent()
        return agent.process_query(
            query=query,
            payload=payload,
            profile_url=profile_url,
            capability_hint=capability,
        )

    def convert(
        self,
        source_format: str,
        target_format: str,
        payload: str,
        resource_type: str | None = None,
        message_type: str | None = None,
    ) -> dict[str, Any]:
        return FormatConverter.convert(
            source_format=source_format,
            target_format=target_format,
            payload=payload,
            resource_type=resource_type,
            message_type=message_type,
        )

    def ingest_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str = "pdf_upload",
        dedup_mode: str = "strict",
    ) -> dict[str, Any]:
        ingestor = self._load_pdf_ingestor()
        return ingestor.ingest_pdf(
            file_bytes=file_bytes,
            filename=filename,
            doc_type=doc_type,
            dedup_mode=dedup_mode,
        )

    def health(self) -> dict[str, Any]:
        uses_qdrant = VECTOR_DB_PROVIDER == "qdrant"
        qdrant_connected = None
        qdrant_collection_exists = None

        if uses_qdrant:
            has_index = has_qdrant_config()
            if has_index:
                try:
                    from qdrant_client import QdrantClient

                    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
                    collections = client.get_collections().collections
                    qdrant_connected = True
                    qdrant_collection_exists = any(
                        c.name == QDRANT_COLLECTION_NAME for c in collections
                    )
                    has_index = qdrant_collection_exists
                except Exception as exc:
                    qdrant_connected = False
                    qdrant_collection_exists = False
                    self._last_error = f"Qdrant health check failed: {exc}"
                    has_index = False
        else:
            has_index = VECTORSTORE_DIR.exists()

        key_sources = {
            "openai": has_openai_api_key(),
            "groq": has_groq_api_key(),
        }
        api_key_configured = any(key_sources.values())

        agent_ready = self._agent is not None
        ready = has_index and api_key_configured and self._last_error is None

        return {
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "agent_loaded": agent_ready,
            "vector_index_exists": has_index,
            "vector_db_provider": VECTOR_DB_PROVIDER,
            "qdrant_url": QDRANT_URL if uses_qdrant else None,
            "qdrant_collection": QDRANT_COLLECTION_NAME if uses_qdrant else None,
            "qdrant_connected": qdrant_connected,
            "qdrant_collection_exists": qdrant_collection_exists,
            "api_key_configured": api_key_configured,
            "api_key_sources": key_sources,
            "last_error": self._last_error,
            "vector_index_path": str(VECTORSTORE_DIR) if not uses_qdrant else "qdrant",
        }


runtime = InteroperabilityRuntime()