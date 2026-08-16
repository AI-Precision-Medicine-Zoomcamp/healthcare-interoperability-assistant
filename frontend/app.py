from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

DEFAULT_API = "http://localhost:8000/api"
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _read_positive_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, str(default)).strip()
    try:
        parsed = int(raw)
        return parsed if parsed > 0 else default
    except Exception:
        return default


MAX_PDF_UPLOAD_MB = _read_positive_int_env("PDF_UPLOAD_MAX_MB", 5)
MAX_PDF_UPLOAD_BYTES = MAX_PDF_UPLOAD_MB * 1024 * 1024
os.environ["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] = str(MAX_PDF_UPLOAD_MB)

import streamlit as st

st.set_page_config(page_title="Healthcare Interoperability Assistant", page_icon="🩺", layout="wide")

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');

    :root {
        --brand-ink: #0f2437;
        --brand-accent: #0ea5a1;
        --brand-soft: #e6f7f6;
        --brand-warm: #f59e0b;
        --panel: #ffffff;
    }

    html, body, [class*="css"] {
        font-family: 'Space Grotesk', sans-serif;
    }

    .stApp {
        background: radial-gradient(circle at 15% 20%, #f1fbfb 0%, #f9f7f2 45%, #ffffff 100%);
    }

    .hero-card {
        background: linear-gradient(120deg, #0f2437 0%, #1f425d 58%, #0ea5a1 100%);
        padding: 1.1rem 1.2rem;
        border-radius: 0.9rem;
        color: #f6fbff;
        margin-bottom: 1rem;
        box-shadow: 0 8px 24px rgba(15, 36, 55, 0.22);
    }

    .hero-title {
        font-size: 1.45rem;
        font-weight: 700;
        margin: 0 0 0.3rem 0;
        letter-spacing: 0.2px;
    }

    .hero-sub {
        font-size: 0.95rem;
        margin: 0;
        opacity: 0.96;
    }

    .pill-row {
        display: flex;
        gap: 0.45rem;
        margin-top: 0.65rem;
        flex-wrap: wrap;
    }

    .pill {
        font-size: 0.76rem;
        background: rgba(255, 255, 255, 0.16);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 999px;
        padding: 0.22rem 0.62rem;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f9ffff 0%, #f7fafc 100%);
        border-right: 1px solid #e8eef5;
    }

    .sample-hint {
        background: var(--brand-soft);
        border-left: 4px solid var(--brand-accent);
        color: var(--brand-ink);
        border-radius: 8px;
        padding: 0.55rem 0.7rem;
        font-size: 0.86rem;
        margin-bottom: 0.55rem;
    }

    /* Material-like elevated buttons */
    .stButton > button,
    [data-testid="stBaseButton-secondary"] {
        border-radius: 12px !important;
        border: 1px solid #cfe4e8 !important;
        background: linear-gradient(180deg, #ffffff 0%, #eef9f8 100%) !important;
        color: #12384a !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 6px rgba(15, 36, 55, 0.14), 0 10px 22px rgba(15, 36, 55, 0.08) !important;
        transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease !important;
    }

    .stButton > button:hover,
    [data-testid="stBaseButton-secondary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(15, 36, 55, 0.18), 0 14px 28px rgba(15, 36, 55, 0.1) !important;
        background: linear-gradient(180deg, #ffffff 0%, #e7f7f5 100%) !important;
    }

    .stButton > button:active,
    [data-testid="stBaseButton-secondary"]:active {
        transform: translateY(1px);
        box-shadow: 0 1px 4px rgba(15, 36, 55, 0.16), 0 6px 14px rgba(15, 36, 55, 0.09) !important;
    }

    .stButton > button[kind="primary"],
    button[kind="primary"],
    [data-testid="stBaseButton-primary"],
    [data-testid="baseButton-primary"] {
        border: 0 !important;
        background: linear-gradient(135deg, #7f1d1d 0%, #b91c1c 52%, #ef4444 100%) !important;
        color: #f7fcff !important;
        box-shadow: 0 6px 14px rgba(220, 38, 38, 0.32), 0 12px 30px rgba(127, 29, 29, 0.24) !important;
    }

    .stButton > button[kind="primary"]:hover,
    button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover,
    [data-testid="baseButton-primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 20px rgba(220, 38, 38, 0.36), 0 18px 36px rgba(127, 29, 29, 0.28) !important;
    }

    .stButton > button[kind="primary"]:active,
    button[kind="primary"]:active,
    [data-testid="stBaseButton-primary"]:active,
    [data-testid="baseButton-primary"]:active {
        transform: translateY(1px);
        box-shadow: 0 4px 10px rgba(220, 38, 38, 0.3), 0 10px 20px rgba(127, 29, 29, 0.22) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero-card">
  <div class="hero-title">Healthcare Interoperability Assistant</div>
        <p class="hero-sub">Unified workflow for FHIR debugging, bidirectional JSON/FHIR/HL7 conversion, HL7 mapping, terminology mapping, and organization-specific integration debugging.</p>
  <div class="pill-row">
    <span class="pill">FHIR Validation</span>
                <span class="pill">JSON ↔ FHIR ↔ HL7</span>
    <span class="pill">HL7 v2 ↔ FHIR</span>
    <span class="pill">Terminology Mapping</span>
    <span class="pill">Org-Specific Rules</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


CAPABILITIES = [
    "FHIR Validation & Debugging",
    "Universal Format Conversion",
    "JSON to FHIR Conversion",
    "HL7 v2 ↔ FHIR Mapping",
    "Terminology Mapping",
    "Organization-Specific Integration Debugging",
]

SAMPLE_INPUTS = {
    "FHIR Validation & Debugging": {
        "query": "Why is this US Core Observation invalid? Find the exact constraint and provide a corrected FHIR payload.",
        "payload": """{
  \"resourceType\": \"Observation\",
  \"status\": \"final\"
}""",
        "profile_url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observationclinicalresult",
    },
    "JSON to FHIR Conversion": {
        "query": "Convert this business JSON into a valid FHIR Observation resource and explain field mapping.",
        "payload": """{
  \"patient_id\": \"12345\",
  \"test_name\": \"Blood glucose\",
  \"result_value\": 98,
  \"result_unit\": \"mg/dL\",
  \"effective_time\": \"2026-08-15T10:30:00Z\"
}""",
        "profile_url": "http://hl7.org/fhir/StructureDefinition/Observation",
    },
    "Universal Format Conversion": {
        "query": "Convert between JSON, FHIR, and HL7 formats.",
        "payload": """{
  \"patient_id\": \"12345\",
  \"test_name\": \"Blood glucose\",
  \"result_value\": 98,
  \"result_unit\": \"mg/dL\",
  \"effective_time\": \"2026-08-15T10:30:00Z\"
}""",
        "profile_url": "",
    },
    "HL7 v2 ↔ FHIR Mapping": {
        "query": "Convert this ADT message into FHIR resources and explain each field-level mapping.",
        "payload": """MSH|^~\\&|ST_JUDE_EMR|ST_JUDE_GH|EMR_HUB|REGIONAL_HUB|202608152310||ADT^A08|MSG00001|P|2.4
PID|1||123456^^^STJ_MRN||DOE^JOHN^MIDDLE||19800101|M|||123 MAIN ST^^MEMPHIS^TN^38101
PV1|1|O|CLINIC_A|||||||||||||||STJ-998877""",
        "profile_url": "",
    },
    "Terminology Mapping": {
        "query": "Map local code GLU_SERUM to standard terminology candidates and explain confidence.",
        "payload": "Local code: GLU_SERUM\nDescription: Blood glucose serum",
        "profile_url": "",
    },
    "Organization-Specific Integration Debugging": {
        "query": "Why is our hospital rejecting this ADT message? Check both official standards and ST_JUDE_GH-specific rules.",
        "payload": """MSH|^~\\&|EXT_VENDOR|WRONG_FACILITY|EMR_HUB|REGIONAL_HUB|202608152310||ADT^A08|MSG00001|P|2.4
PID|1||123456^^^STJ_MRN||DOE^JOHN^MIDDLE||19800101|M
PV1|1|O|CLINIC_A|||||||||||||||998877""",
        "profile_url": "",
    },
}


if "query_input" not in st.session_state:
    st.session_state["query_input"] = ""
if "payload_input" not in st.session_state:
    st.session_state["payload_input"] = ""
if "profile_url_input" not in st.session_state:
    st.session_state["profile_url_input"] = ""
if "capability" not in st.session_state:
    st.session_state["capability"] = CAPABILITIES[0]
if "source_format_input" not in st.session_state:
    st.session_state["source_format_input"] = "json"
if "target_format_input" not in st.session_state:
    st.session_state["target_format_input"] = "fhir"
if "resource_type_hint" not in st.session_state:
    st.session_state["resource_type_hint"] = "Observation"
if "message_type_hint" not in st.session_state:
    st.session_state["message_type_hint"] = "ORU^R01"


def load_sample(capability_name: str) -> None:
    sample = SAMPLE_INPUTS[capability_name]
    st.session_state["capability"] = capability_name
    st.session_state["query_input"] = sample["query"]
    st.session_state["payload_input"] = sample["payload"]
    st.session_state["profile_url_input"] = sample["profile_url"]


def safe_json(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {"detail": resp.text or f"HTTP {resp.status_code}"}


with st.sidebar:
    st.header("Backend")
    api = st.text_input("API base URL", value=DEFAULT_API)

    if st.button("Check Health", use_container_width=True):
        try:
            health_resp = requests.get(f"{api}/health", timeout=6)
            health = safe_json(health_resp)
            if health_resp.status_code == 200:
                status = "ready" if health.get("ready") else "degraded"
                st.success(f"Backend reachable ({status})")
                if not health.get("vector_index_exists"):
                    provider = health.get("vector_db_provider", "vector store")
                    st.warning(
                        f"{provider} store not ready. Run: python -m src.rag.ingest"
                    )
                if not health.get("api_key_configured"):
                    st.warning("No API key configured. Set OPENAI_API_KEY or GROQ_API_KEY in .env")
                if health.get("last_error"):
                    st.info(f"Last runtime error: {health['last_error']}")
            else:
                st.error(health.get("detail", "Health check failed"))
        except requests.exceptions.RequestException as exc:
            st.error(f"Cannot reach backend: {exc}")

    st.divider()
    st.markdown("### PDF Ingest to Qdrant")
    st.caption(
        f"Upload a PDF (max {MAX_PDF_UPLOAD_MB}MB). It will be chunked, embedded, deduplicated, and ingested."
    )

    pdf_file = st.file_uploader("Upload PDF", type=["pdf"], accept_multiple_files=False)
    dedup_mode = st.selectbox(
        "Dedup Mode",
        ["strict", "none"],
        index=0,
        help=(
            "strict: skips re-ingesting the same document and duplicate chunks across uploads.\n"
            "none: ingests all chunks even if duplicates already exist."
        ),
    )

    if st.button("Ingest PDF", use_container_width=True):
        if pdf_file is None:
            st.error("Please choose a PDF file first.")
        else:
            file_bytes = pdf_file.getvalue()
            if len(file_bytes) > MAX_PDF_UPLOAD_BYTES:
                st.error(f"PDF exceeds {MAX_PDF_UPLOAD_MB}MB limit.")
            else:
                try:
                    files = {
                        "file": (pdf_file.name, file_bytes, "application/pdf"),
                    }
                    data = {
                        "doc_type": "pdf_upload",
                        "dedup_mode": dedup_mode,
                    }
                    ingest_resp = requests.post(f"{api}/ingest/pdf", files=files, data=data, timeout=180)
                    ingest_data = safe_json(ingest_resp)
                    if ingest_resp.status_code == 200:
                        st.success(f"PDF ingest status: {ingest_data.get('status', 'ok')}")
                        st.write(f"- File: {ingest_data.get('filename')}")
                        st.write(f"- Chunks inserted: {ingest_data.get('chunks_inserted')}")
                        st.write(f"- Duplicate chunks skipped: {ingest_data.get('chunks_skipped_duplicate')}")
                    else:
                        st.error(ingest_data.get("detail", "PDF ingest failed."))
                except requests.exceptions.RequestException as exc:
                    st.error(f"Cannot reach backend for PDF ingest: {exc}")

    st.divider()
    st.markdown("### Quick Examples")
    st.code(
        """FHIR Debugging Query:\nWhy is this US Core Observation invalid?\n\nUniversal Conversion Query:\nConvert JSON <-> FHIR <-> HL7 with selected source and target.\n\nHL7 Mapping Query:\nConvert this ADT message to FHIR resources.\n\nTerminology Query:\nMap GLU_SERUM to a standard code and explain confidence.""",
        language="text",
    )

st.markdown("<div class='sample-hint'>Load a starter scenario to test each capability quickly.</div>", unsafe_allow_html=True)

sample_cols = st.columns(6)
with sample_cols[0]:
    if st.button("Load FHIR Sample", use_container_width=True):
        load_sample("FHIR Validation & Debugging")
        st.rerun()
with sample_cols[1]:
    if st.button("Load Convert Sample", use_container_width=True):
        load_sample("Universal Format Conversion")
        st.rerun()
with sample_cols[2]:
    if st.button("Load JSON Sample", use_container_width=True):
        load_sample("JSON to FHIR Conversion")
        st.rerun()
with sample_cols[3]:
    if st.button("Load HL7 Sample", use_container_width=True):
        load_sample("HL7 v2 ↔ FHIR Mapping")
        st.rerun()
with sample_cols[4]:
    if st.button("Load Terminology Sample", use_container_width=True):
        load_sample("Terminology Mapping")
        st.rerun()
with sample_cols[5]:
    if st.button("Load Org Debug Sample", use_container_width=True):
        load_sample("Organization-Specific Integration Debugging")
        st.rerun()

capability = st.selectbox("Capability", CAPABILITIES, key="capability")

query = st.text_area(
    "Question",
    height=120,
    placeholder="Describe the issue or task...",
    key="query_input",
)
payload = st.text_area(
    "Payload (optional)",
    height=220,
    placeholder="Paste custom JSON, FHIR JSON, or HL7 v2 message...",
    key="payload_input",
)
profile_url = st.text_input(
    "FHIR Profile URL (optional)",
    placeholder="http://hl7.org/fhir/us/core/StructureDefinition/us-core-observationclinicalresult",
    key="profile_url_input",
)

is_conversion_mode = capability == "Universal Format Conversion"
if is_conversion_mode:
    fmt_col1, fmt_col2 = st.columns(2)
    with fmt_col1:
        source_format = st.selectbox(
            "Source Format",
            ["json", "fhir", "hl7"],
            key="source_format_input",
        )
    with fmt_col2:
        target_format = st.selectbox(
            "Target Format",
            ["json", "fhir", "hl7"],
            key="target_format_input",
        )

    hint_col1, hint_col2 = st.columns(2)
    with hint_col1:
        resource_type_hint = st.text_input(
            "FHIR Resource Type Hint (optional)",
            key="resource_type_hint",
            placeholder="Observation / Patient / Encounter",
        )
    with hint_col2:
        message_type_hint = st.text_input(
            "HL7 Message Type Hint (optional)",
            key="message_type_hint",
            placeholder="ORU^R01 / ADT^A01",
        )

left, right = st.columns([1, 5])
with left:
    run_clicked = st.button("Run", type="primary", use_container_width=True)
with right:
    st.caption(f"Selected mode: {capability}")

if run_clicked:
    if is_conversion_mode and (st.session_state["source_format_input"] == st.session_state["target_format_input"]):
        st.error("Source and target formats must be different for conversion mode.")
    elif not is_conversion_mode and not query.strip():
        st.error("Please enter a question.")
    elif not payload.strip():
        st.error("Please provide payload content.")
    else:
        with st.spinner("Calling Interoperability Assistant API..."):
            try:
                if is_conversion_mode:
                    body = {
                        "query": query.strip() or None,
                        "source_format": st.session_state["source_format_input"],
                        "target_format": st.session_state["target_format_input"],
                        "payload": payload.strip(),
                        "resource_type": (st.session_state.get("resource_type_hint") or "").strip() or None,
                        "message_type": (st.session_state.get("message_type_hint") or "").strip() or None,
                    }
                    resp = requests.post(f"{api}/convert", json=body, timeout=180)
                else:
                    body = {
                        "query": query.strip(),
                        "payload": payload.strip() or None,
                        "profile_url": profile_url.strip() or None,
                        "capability": capability,
                    }
                    resp = requests.post(f"{api}/query", json=body, timeout=180)
                data = safe_json(resp)
            except requests.exceptions.RequestException as exc:
                st.error(f"Request failed: {exc}")
                data = None
                resp = None

        if resp is not None and resp.status_code == 200 and data is not None:
            st.subheader("Result")
            if is_conversion_mode:
                st.markdown(
                    f"**Conversion:** {data.get('source_format', '').upper()} -> {data.get('target_format', '').upper()}"
                )
                converted_json = data.get("converted_json")
                if isinstance(converted_json, dict):
                    st.markdown("### Converted Output")
                    st.json(converted_json)
                else:
                    st.markdown("### Converted Output")
                    st.code(data.get("converted_payload", ""), language="text")

                notes = data.get("notes") or []
                if notes:
                    st.markdown("### Notes")
                    for n in notes:
                        st.write(f"- {n}")

                warnings = data.get("warnings") or []
                if warnings:
                    st.markdown("### Warnings")
                    for w in warnings:
                        st.warning(w)
            else:
                st.markdown(f"**Intent:** {data.get('intent', 'unknown')}")

                validation = data.get("validation_result")
                if validation:
                    is_valid = validation.get("is_valid")
                    st.markdown(f"**Validation:** {'Valid' if is_valid else 'Invalid'}")
                    errors = validation.get("errors") or []
                    if errors:
                        st.markdown("**Validation Errors**")
                        for err in errors:
                            st.write(f"- {err}")

                st.markdown("### Explanation")
                st.write(data.get("explanation", ""))

                st.markdown("### Suggested Correction")
                correction = data.get("correction", "")
                if correction.strip().startswith("{"):
                    try:
                        parsed = json.loads(correction)
                        st.json(parsed)
                    except Exception:
                        st.code(correction, language="json")
                else:
                    st.code(correction)

                citations = data.get("citations") or []
                if citations:
                    with st.expander("Citations"):
                        for c in citations:
                            st.write(f"- {c}")
        elif data is not None:
            st.error(data.get("detail", "Query failed."))
