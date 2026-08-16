import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from langchain_community.vectorstores import FAISS
from langchain_qdrant import QdrantVectorStore
from src.llm.llm_service import LLMService
from src.config.config import (
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
    VECTOR_DB_PROVIDER,
)

class HealthcareRetriever:
    def __init__(self):
        self.llm_service = LLMService()
        self.embeddings = self.llm_service.embed_model
        self.vectorstore_path = ROOT_DIR / "data" / "vectorstore" / "faiss_index"

        if VECTOR_DB_PROVIDER == "qdrant":
            if not QDRANT_URL or not QDRANT_API_KEY:
                raise ValueError(
                    "Qdrant selected but QDRANT_URL / QDRANT_API_KEY (or QDARNT_API_KEY) is missing."
                )
            print(
                f"Loading Qdrant collection '{QDRANT_COLLECTION_NAME}' from {QDRANT_URL}..."
            )
            self.vectorstore = QdrantVectorStore.from_existing_collection(
                embedding=self.embeddings,
                collection_name=QDRANT_COLLECTION_NAME,
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
                prefer_grpc=False,
            )
        else:
            if not self.vectorstore_path.exists():
                raise FileNotFoundError(
                    f"FAISS index not found at {self.vectorstore_path}. Please run ingest.py first."
                )

            print(f"Loading FAISS index from {self.vectorstore_path}...")
            self.vectorstore = FAISS.load_local(
                str(self.vectorstore_path),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )

    def retrieve(self, query: str, limit: int = 4, doc_type: str = None, **metadata_filters) -> list:
        """
        Retrieves matching chunks from vector database.
        Applies doc_type and other metadata filters on the search results.
        """
        # If filters are present, do a broader search to filter in memory
        search_k = max(20, limit * 5) if (doc_type or metadata_filters) else limit
        docs = self.vectorstore.similarity_search(query, k=search_k)
        
        filtered_docs = []
        for doc in docs:
            # Check doc_type filter
            if doc_type and doc.metadata.get("doc_type") != doc_type:
                continue
                
            # Check other metadata filters
            match = True
            for k, v in metadata_filters.items():
                if doc.metadata.get(k) != v:
                    match = False
                    break
            if not match:
                continue
                
            filtered_docs.append(doc)
            if len(filtered_docs) >= limit:
                break
                
        # Backfill if we have filters but didn't find enough matches
        if len(filtered_docs) < limit and (doc_type or metadata_filters):
            for doc in docs:
                if doc not in filtered_docs:
                    filtered_docs.append(doc)
                if len(filtered_docs) >= limit:
                    break
                    
        return filtered_docs

if __name__ == "__main__":
    # Test retriever
    print("Testing Retriever...")
    retriever = HealthcareRetriever()
    
    print("\n--- Test 1: US Core Observation Profile ---")
    results = retriever.retrieve("Observation", limit=2, doc_type="fhir_profile")
    for i, r in enumerate(results):
        print(f"Result {i+1} (Source: {r.metadata.get('source')}):")
        print(r.page_content[:200] + "...\n")
        
    print("\n--- Test 2: HL7 PID Mapping ---")
    results = retriever.retrieve("PID segment patient name", limit=1, doc_type="hl7_mapping")
    for i, r in enumerate(results):
        print(f"Result {i+1} (Source: {r.metadata.get('source')}):")
        print(r.page_content[:200] + "...\n")
