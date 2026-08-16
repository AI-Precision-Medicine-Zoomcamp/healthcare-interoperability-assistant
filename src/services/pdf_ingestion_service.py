from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from src.config.config import (
    PDF_UPLOAD_MAX_BYTES,
    PDF_UPLOAD_MAX_MB,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)
from src.llm.llm_service import LLMService


class PDFIngestionService:
    """Ingests uploaded PDF files into Qdrant with duplicate protection."""

    def __init__(self) -> None:
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise ValueError("Qdrant is not configured. Set QDRANT_URL and QDRANT_API_KEY.")

        self._llm_service = LLMService()
        self._embeddings = self._llm_service.embed_model
        self._client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    def ingest_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str = "pdf_upload",
        dedup_mode: str = "strict",
    ) -> dict[str, Any]:
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")
        if len(file_bytes) > PDF_UPLOAD_MAX_BYTES:
            raise ValueError(f"File exceeds max allowed size of {PDF_UPLOAD_MAX_MB}MB.")

        dedup_mode = dedup_mode.lower().strip()
        if dedup_mode not in {"strict", "none"}:
            raise ValueError("dedup_mode must be one of: strict, none")

        doc_hash = hashlib.sha256(file_bytes).hexdigest()
        if dedup_mode == "strict" and self._doc_exists(doc_hash):
            return {
                "status": "skipped",
                "reason": "duplicate_document",
                "filename": filename,
                "doc_hash": doc_hash,
                "pages": 0,
                "chunks_total": 0,
                "chunks_inserted": 0,
                "chunks_skipped_duplicate": 0,
                "collection": QDRANT_COLLECTION_NAME,
            }

        pages = self._extract_pages(file_bytes)
        if not pages:
            raise ValueError("No extractable text found in PDF.")

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = splitter.split_text("\n\n".join(pages))
        if not chunks:
            raise ValueError("No text chunks generated from PDF.")

        self._ensure_collection_exists()

        inserted_points: list[PointStruct] = []
        skipped_duplicate = 0
        uploaded_at = datetime.now(timezone.utc).isoformat()

        for idx, chunk in enumerate(chunks):
            normalized = self._normalize_text(chunk)
            if not normalized:
                continue

            chunk_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if dedup_mode == "strict" and self._chunk_exists(chunk_hash):
                skipped_duplicate += 1
                continue

            vector = self._embeddings.embed_documents([chunk])[0]
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_hash}:{idx}:{chunk_hash}"))
            payload = {
                "source": filename,
                "doc_type": doc_type,
                "doc_hash": doc_hash,
                "chunk_hash": chunk_hash,
                "chunk_index": idx,
                "uploaded_at": uploaded_at,
                "content": chunk,
            }
            inserted_points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        if inserted_points:
            self._client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=inserted_points)

        return {
            "status": "ingested",
            "reason": "ok",
            "filename": filename,
            "doc_hash": doc_hash,
            "pages": len(pages),
            "chunks_total": len(chunks),
            "chunks_inserted": len(inserted_points),
            "chunks_skipped_duplicate": skipped_duplicate,
            "collection": QDRANT_COLLECTION_NAME,
        }

    def _extract_pages(self, file_bytes: bytes) -> list[str]:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_texts: list[str] = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                page_texts.append(text)
        return page_texts

    def _ensure_collection_exists(self) -> None:
        if self._client.collection_exists(QDRANT_COLLECTION_NAME):
            return

        sample_vector = self._embeddings.embed_documents(["dimension probe"])[0]
        self._client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(size=len(sample_vector), distance=Distance.COSINE),
        )

    def _doc_exists(self, doc_hash: str) -> bool:
        points, _ = self._client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_hash", match=MatchValue(value=doc_hash))]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        return bool(points)

    def _chunk_exists(self, chunk_hash: str) -> bool:
        points, _ = self._client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="chunk_hash", match=MatchValue(value=chunk_hash))]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        return bool(points)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.split())
