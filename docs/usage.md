# Usage Guide

This guide shows common commands, example inputs, and expected outputs for the current prototype.

## Main Workflows

## Workflow 0: Start Unified Assistant Services

Terminal 1 (backend):

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 (frontend):

```bash
streamlit run frontend/app.py
```

Expected outcome:

- Backend reachable at `http://localhost:8000`
- Streamlit frontend reachable at `http://localhost:8501`
- Health endpoint returns runtime status at `GET /api/health`

## Workflow 1: Build Knowledge Base

```bash
python -m src.scripts.download_dataset
python -m src.rag.ingest
```

Expected outcome:

- Data files exist under `data/fhir`, `data/hl7`, `data/terminology`, and `data/organization`
- Vectors are available in the configured Qdrant collection

## Workflow 2: Run Basic LLM Connectivity Check

```bash
python -m src.main
```

Expected output includes:

- Dependency/version print line
- A generated answer for: `What is healthcare interoperability?`

## Workflow 3: Test Retrieval Service

```bash
python -m src.rag.retriever
```

Expected output includes:

- Loaded Qdrant collection confirmation (or FAISS if fallback mode is used)
- Retrieval snippets for sample FHIR and HL7 queries

## Workflow 4: Test RAG Context Formatting

```bash
python -m src.rag.rag_service
```

Expected output includes:

- Formatted context block assembled from retrieved documents

## Workflow 5: Test Agent Orchestration

```bash
python -m src.agents.agent_service
```

Expected output includes:

- Detected intent
- Explanation section
- Correction section

## Example Use Cases

## 1. FHIR Debugging

Input (query):

```text
Why is this US Core Observation invalid? Find the constraint and give me corrected FHIR.
```

Input (payload excerpt):

```json
{
  "resourceType": "Observation",
  "status": "final"
}
```

Expected behavior:

- Validator flags missing mandatory fields (such as `Observation.code`)
- RAG retrieves relevant profile context
- Agent returns explanation + corrected payload suggestion

## 2. HL7 to FHIR Mapping

Input (query):

```text
Map this HL7 ADT message into FHIR resources.
```

Input (payload excerpt):

```text
MSH|^~\&|ST_JUDE_EMR|ST_JUDE_GH|EMR_HUB|REGIONAL_HUB|202608152310||ADT^A08|MSG00001|P|2.4
PID|1||123456^^^STJ_MRN||DOE^JOHN^MIDDLE||19800101|M
PV1|1|O|CLINIC_A|||||||||||||||STJ-998877
```

Expected behavior:

- HL7 parser extracts fields/components
- RAG retrieves HL7-to-FHIR mapping references
- Agent returns mapping rationale and conversion draft

## 3. Terminology Mapping

Input (query):

```text
What is the best standard code for local test code GLU_SERUM?
```

Expected behavior:

- RAG retrieves terminology mapping entries
- Agent explains candidate code choice and alternatives

## Walkthrough for Reviewers

1. Run setup from `docs/setup.md`.
2. Build dataset and vector index.
3. Start backend and frontend (Workflow 0).
4. Submit at least one query per capability in Streamlit.
5. Review output sections: intent, explanation, correction, citations, and validation.
6. Compare outputs with source data under `data/` to validate grounding quality.

## Current Gaps

- No committed automated test suite
- No committed evaluation scripts under `evals/`

## Recommended Demo Sequence

Use this sequence to demonstrate one strong integrated RAG project:

1. Start with a broken HL7 or FHIR integration payload.
2. Run mapping/debugging path (HL7 parsing or FHIR validation).
3. Show retrieved evidence from standards and profile docs.
4. Show terminology candidate reasoning where relevant.
5. Include organization-specific rule checks from internal docs.
6. Present correction and run deterministic validation check.

Demo objective:

```text
Input integration issue
-> retrieve evidence
-> explain exact violation
-> propose correction
-> validate correction
```
