import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.rag.retriever import HealthcareRetriever

class RAGService:
    def __init__(self):
        self.retriever = HealthcareRetriever()

    def get_context(self, query: str, doc_type: str = None, limit: int = 4, **filters) -> str:
        """
        Retrieves matching chunks and formats them into a clean string context block.
        """
        docs = self.retriever.retrieve(query, limit=limit, doc_type=doc_type, **filters)
        if not docs:
            return "No matching healthcare specifications or internal guidelines found in the knowledge base."
            
        context_parts = []
        for i, doc in enumerate(docs):
            src = doc.metadata.get("source", "Unknown Source")
            dtype = doc.metadata.get("doc_type", "Unknown Type")
            context_parts.append(f"--- Document [{i+1}]: {src} (Type: {dtype}) ---\n{doc.page_content}")
            
        return "\n\n".join(context_parts)

if __name__ == "__main__":
    print("Testing RAG Service...")
    rag = RAGService()
    context = rag.get_context("How to map PID patient name to FHIR?", doc_type="hl7_mapping")
    print("\nFormatted Context:")
    print(context[:400] + "...")
