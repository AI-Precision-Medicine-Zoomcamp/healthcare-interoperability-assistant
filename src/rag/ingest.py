import os
import sys
import json
import csv
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_qdrant import QdrantVectorStore
from src.llm.llm_service import LLMService
from src.config.config import (
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
    VECTOR_DB_PROVIDER,
)

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
FHIR_DIR = DATA_DIR / "fhir"
HL7_DIR = DATA_DIR / "hl7"
TERM_DIR = DATA_DIR / "terminology"
ORG_DIR = DATA_DIR / "organization"
VECTORSTORE_DIR = DATA_DIR / "vectorstore" / "faiss_index"

def parse_fhir_structure_definition(file_path: Path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {file_path.name}: {e}")
        return None
    
    resource_type = data.get("resourceType", "")
    if resource_type != "StructureDefinition":
        return None
        
    url = data.get("url", "")
    name = data.get("name", "")
    title = data.get("title", name)
    description = data.get("description", "No description available.")
    fhir_version = data.get("fhirVersion", "")
    base_kind = data.get("type", "")
    
    elements_text = []
    snapshot = data.get("snapshot", {})
    elements = snapshot.get("element", [])
    if not elements:
        differential = data.get("differential", {})
        elements = differential.get("element", [])
        
    for elem in elements:
        path = elem.get("id", elem.get("path", ""))
        min_card = elem.get("min", 0)
        max_card = elem.get("max", "*")
        
        types = []
        for t in elem.get("type", []):
            types.append(t.get("code", ""))
        type_str = ", ".join(types) if types else "N/A"
        
        short = elem.get("short", "")
        
        binding = elem.get("binding", {})
        binding_vs = binding.get("valueSet", "")
        binding_strength = binding.get("strength", "")
        binding_str = f"Binding: {binding_vs} ({binding_strength})" if binding_vs else ""
        
        elem_desc = f"- **{path}** (min: {min_card}, max: {max_card}, type: {type_str})\n  *Description:* {short}"
        if binding_str:
            elem_desc += f"\n  *{binding_str}*"
        
        elements_text.append(elem_desc)
        
    elements_block = "\n".join(elements_text)
    
    markdown = f"""# FHIR StructureDefinition: {title}
**Profile URL:** {url}
**Base Resource Type:** {base_kind}
**FHIR Version:** {fhir_version}

## Description
{description}

## Elements and Constraints
{elements_block}
"""
    return Document(
        page_content=markdown,
        metadata={
            "source": str(file_path.name),
            "doc_type": "fhir_profile",
            "profile_url": url,
            "resource_type": base_kind,
            "title": title
        }
    )

def parse_fhir_valueset(file_path: Path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {file_path.name}: {e}")
        return None
        
    resource_type = data.get("resourceType", "")
    if resource_type != "ValueSet":
        return None
        
    url = data.get("url", "")
    name = data.get("name", "")
    title = data.get("title", name)
    description = data.get("description", "No description available.")
    
    codes = []
    compose = data.get("compose", {})
    for include in compose.get("include", []):
        system = include.get("system", "")
        for concept in include.get("concept", []):
            code = concept.get("code", "")
            display = concept.get("display", "")
            codes.append(f"- System: `{system}`, Code: `{code}`, Display: `{display}`")
            
    expansion = data.get("expansion", {})
    for contains in expansion.get("contains", []):
        system = contains.get("system", "")
        code = contains.get("code", "")
        display = contains.get("display", "")
        codes.append(f"- System: `{system}`, Code: `{code}`, Display: `{display}`")
        
    codes_block = "\n".join(codes) if codes else "*No explicit codes defined in definition file.*"
    
    markdown = f"""# FHIR ValueSet: {title}
**ValueSet URL:** {url}

## Description
{description}

## Included Codes
{codes_block}
"""
    return Document(
        page_content=markdown,
        metadata={
            "source": str(file_path.name),
            "doc_type": "fhir_valueset",
            "profile_url": url,
            "title": title
        }
    )

def parse_hl7_mappings(file_path: Path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {file_path.name}: {e}")
        return []
        
    segments = data.get("segments", {})
    docs = []
    for segment_name, segment_data in segments.items():
        desc = segment_data.get("description", "")
        mappings = segment_data.get("mappings", [])
        
        mapping_rows = []
        for m in mappings:
            v2_f = m.get("v2_field", "")
            name = m.get("name", "")
            fhir_p = m.get("fhir_path", "")
            m_type = m.get("type", "")
            notes = m.get("notes", "None")
            mapping_rows.append(f"| {v2_f} | {name} | {fhir_p} | {m_type} | {notes} |")
            
        mapping_block = "\n".join(mapping_rows)
        
        markdown = f"""# HL7 v2 Segment Mapping: {segment_name}
**Description:** {desc}

## Mappings Table
| HL7 Field | Name | Target FHIR Path | Type Mapping | Notes |
| :--- | :--- | :--- | :--- | :--- |
{mapping_block}
"""
        docs.append(Document(
            page_content=markdown,
            metadata={
                "source": str(file_path.name),
                "doc_type": "hl7_mapping",
                "segment": segment_name
            }
        ))
    return docs

def parse_terminology_mappings(file_path: Path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {file_path.name}: {e}")
        return []
        
    docs = []
    for term in data:
        local_code = term.get("local_code", "")
        local_desc = term.get("local_description", "")
        std_system = term.get("standard_system", "")
        std_code = term.get("standard_code", "")
        std_display = term.get("standard_display", "")
        notes = term.get("notes", "")
        
        alt_codes = []
        for alt in term.get("alternative_codes", []):
            alt_codes.append(f"- System: {alt.get('system')}, Code: {alt.get('code')}, Display: {alt.get('display')}, Reason: {alt.get('reason')}")
        alt_block = "\n".join(alt_codes) if alt_codes else "None"
        
        markdown = f"""# Terminology Mapping: {local_code}
**Local Description:** {local_desc}
**Standard System:** {std_system}
**Standard Code:** {std_code}
**Standard Display Name:** {std_display}

## Notes
{notes}

## Alternative Standard Codes
{alt_block}
"""
        docs.append(Document(
            page_content=markdown,
            metadata={
                "source": str(file_path.name),
                "doc_type": "terminology_map",
                "local_code": local_code,
                "standard_code": std_code,
                "standard_system": std_system
            }
        ))
    return docs

def parse_organization_csv(file_path: Path):
    try:
        rows = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            for row in reader:
                if len(row) < len(header):
                    continue
                row_desc = f"Local Code '{row[0]}' ({row[1]}) maps to LOINC '{row[2]}'."
                if row[3] == "YES":
                    row_desc += " This mapping is mandatory for billing."
                if row[4]:
                    row_desc += f" Note: {row[4]}"
                rows.append(row_desc)
    except Exception as e:
        print(f"Error reading {file_path.name}: {e}")
        return None
            
    markdown = f"""# Hospital Terminology Mapping Rules ({file_path.name})
This table documents St. Jude General Hospital local lab codes mapped to standard LOINC codes.

## Mapping Definitions
{chr(10).join('- ' + r for r in rows)}
"""
    return Document(
        page_content=markdown,
        metadata={
            "source": str(file_path.name),
            "doc_type": "organization_rule",
            "org_name": "ST_JUDE_GH"
        }
    )

def main():
    print("Initializing Ingestion Pipeline...")
    documents = []

    # 1. Process FHIR files
    if FHIR_DIR.exists():
        print(f"Parsing FHIR specifications in {FHIR_DIR}...")
        for p in FHIR_DIR.glob("*.json"):
            if p.name.startswith("StructureDefinition-"):
                doc = parse_fhir_structure_definition(p)
                if doc:
                    documents.append(doc)
            elif p.name.startswith("ValueSet-"):
                doc = parse_fhir_valueset(p)
                if doc:
                    documents.append(doc)

    # 2. Process HL7 mappings
    hl7_map_file = HL7_DIR / "hl7_v2_fhir_mappings.json"
    if hl7_map_file.exists():
        print(f"Parsing HL7 mapping rules in {hl7_map_file.name}...")
        docs = parse_hl7_mappings(hl7_map_file)
        documents.extend(docs)

    # 3. Process Terminology mappings
    term_map_file = TERM_DIR / "terminology_mappings.json"
    if term_map_file.exists():
        print(f"Parsing terminology rules in {term_map_file.name}...")
        docs = parse_terminology_mappings(term_map_file)
        documents.extend(docs)

    # 4. Process Organization rules
    if ORG_DIR.exists():
        print(f"Parsing organization specs in {ORG_DIR}...")
        for p in ORG_DIR.glob("*"):
            if p.suffix == ".csv":
                doc = parse_organization_csv(p)
                if doc:
                    documents.append(doc)
            elif p.suffix == ".md" or p.suffix == ".txt":
                try:
                    text = p.read_text(encoding="utf-8")
                    documents.append(Document(
                        page_content=text,
                        metadata={
                            "source": p.name,
                            "doc_type": "organization_rule"
                        }
                    ))
                except Exception as e:
                    print(f"Error reading {p.name}: {e}")

    print(f"Total structured documents prepared: {len(documents)}")

    # Split documents into chunks for search precision
    print("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Total chunks created: {len(chunks)}")

    # Load LLM embeddings
    print("Loading embedding model from LLMService...")
    llm_service = LLMService()
    embeddings = llm_service.embed_model

    # Create and Save Vector Store
    if VECTOR_DB_PROVIDER == "qdrant":
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise ValueError(
                "Qdrant selected but QDRANT_URL / QDRANT_API_KEY (or QDARNT_API_KEY) is missing."
            )

        print(
            f"Upserting chunks to Qdrant collection '{QDRANT_COLLECTION_NAME}' at {QDRANT_URL}..."
        )
        QdrantVectorStore.from_documents(
            chunks,
            embeddings,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            collection_name=QDRANT_COLLECTION_NAME,
            prefer_grpc=False,
            force_recreate=True,
        )
        print("Qdrant ingestion completed successfully.")
    else:
        print(f"Creating local FAISS index at {VECTORSTORE_DIR}...")
        vectorstore = FAISS.from_documents(chunks, embeddings)
        VECTORSTORE_DIR.parent.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(VECTORSTORE_DIR))
        print("FAISS ingestion completed successfully.")
    
    print("\nIngestion pipeline completed successfully!")

if __name__ == "__main__":
    main()
