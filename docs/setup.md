# Setup Guide

This guide documents how to install and configure the Healthcare Interoperability Assistant prototype.

## Prerequisites

- Python 3.11+
- `uv` package manager installed
- At least one LLM provider API key:
  - `OPENAI_API_KEY`, or
  - `GROQ_API_KEY`
- Qdrant Cloud credentials:
  - `QDRANT_URL`
  - `QDRANT_API_KEY` (or `QDARNT_API_KEY` alias)

## 1. Clone Repository

```bash
git clone <repository-url>
cd healthcare-interoperability-assistant
```

## 2. Create Virtual Environment

```bash
uv venv
```

Activate the environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

```bash
uv sync
```

## 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_key
# Alias also supported:
QDARNT_API_KEY=your_qdrant_key
VECTOR_DB_PROVIDER=qdrant
QDRANT_COLLECTION_NAME=healthcare_interop_assistant
LLM_MODEL=openai/gpt-oss-120b
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

Notes:

- You only need one provider key (`OPENAI_API_KEY` or `GROQ_API_KEY`).
- If both are set, current logic prioritizes Groq.
- `VECTOR_DB_PROVIDER` defaults to `qdrant`.
- The app supports both `QDRANT_API_KEY` and `QDARNT_API_KEY` for compatibility.

## 5. Optional: Configure `config.json`

`src/config/config.py` can read values from `config.json` if present.

Example:

```json
{
  "LLM_PROVIDER": "groq",
  "LLM_MODEL": "llama-3.3-70b-versatile",
  "VECTOR_DB_PROVIDER": "qdrant",
  "QDRANT_COLLECTION_NAME": "healthcare_interop_assistant",
  "EMBEDDING_PROVIDER": "huggingface",
  "EMBEDDING_MODEL": "all-MiniLM-L6-v2"
}
```

## 6. Prepare Dataset

```bash
python -m src.scripts.download_dataset
```

This step:

- Creates data directories
- Downloads selected FHIR package archives
- Extracts selected StructureDefinitions/ValueSets
- Generates HL7 mapping data
- Generates terminology mapping data
- Generates organization-specific spec files

## 7. Build Vector Index

```bash
python -m src.rag.ingest
```

This step parses data files, chunks content, and upserts vectors into your Qdrant collection.

## 8. Run Prototype Entry Point

```bash
python -m src.main
```

## 9. Run API Server

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Open API docs at `http://localhost:8000/docs`.

## 10. Run Streamlit Frontend

In another terminal:

```bash
streamlit run frontend/app.py
```

Open Streamlit at `http://localhost:8501`.

## Troubleshooting

- `No API keys found`:
  - Ensure `.env` exists in the project root and contains a valid key.
- `Qdrant selected but QDRANT_URL / QDRANT_API_KEY is missing`:
  - Ensure `QDRANT_URL` and `QDRANT_API_KEY` (or `QDARNT_API_KEY`) are set in `.env`.
- Import errors after dependency changes:
  - Re-run `uv sync` inside the active virtual environment.
