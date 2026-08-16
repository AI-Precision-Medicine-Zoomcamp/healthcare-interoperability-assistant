import os
import tarfile
import urllib.request
import json
import csv
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
FHIR_DIR = DATA_DIR / "fhir"
HL7_DIR = DATA_DIR / "hl7"
TERM_DIR = DATA_DIR / "terminology"
ORG_DIR = DATA_DIR / "organization"
CACHE_DIR = DATA_DIR / "cache"

# Core URLs
US_CORE_URL = "https://packages.simplifier.net/hl7.fhir.us.core/6.1.0"
FHIR_R4_URL = "https://packages.simplifier.net/hl7.fhir.r4.core/4.0.1"

def create_dirs():
    for d in [FHIR_DIR, HL7_DIR, TERM_DIR, ORG_DIR, CACHE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    print("Created data directories.")

def download_file(url: str, dest_path: Path):
    if dest_path.exists():
        print(f"File already exists: {dest_path.name}. Skipping download.")
        return
    print(f"Downloading {url} to {dest_path}...")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
            out_file.write(response.read())
        print("Download complete.")
    except Exception as e:
        print(f"Error downloading {url}: {e}")

def extract_profiles(tar_path: Path, output_dir: Path, prefix_filter: list):
    print(f"Extracting profiles from {tar_path.name} to {output_dir.name}...")
    count = 0
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                # FHIR packages store files under package/ directory
                if not member.name.startswith("package/"):
                    continue
                filename = os.path.basename(member.name)
                # Filter for structure definitions and value sets
                if not (filename.startswith("StructureDefinition-") or filename.startswith("ValueSet-")):
                    continue
                
                # Filter for key models to keep it lightweight
                matched = False
                for p in prefix_filter:
                    if p.lower() in filename.lower():
                        matched = True
                        break
                
                if matched:
                    # Extract file
                    member.name = filename # Flatten directory structure
                    tar.extract(member, path=output_dir)
                    count += 1
        print(f"Extracted {count} resources from {tar_path.name}.")
    except Exception as e:
        print(f"Error extracting {tar_path.name}: {e}")

def generate_hl7_mappings():
    print("Generating HL7 v2 to FHIR mapping tables...")
    mappings = {
        "segments": {
            "MSH": {
                "description": "Message Header Segment",
                "mappings": [
                    {"v2_field": "MSH-3", "name": "Sending Application", "fhir_path": "MessageHeader.source.name", "type": "HD -> string"},
                    {"v2_field": "MSH-4", "name": "Sending Facility", "fhir_path": "MessageHeader.source.software", "type": "HD -> string", "notes": "Often maps to an Organization reference in clinical context"},
                    {"v2_field": "MSH-7", "name": "Date/Time of Message", "fhir_path": "MessageHeader.meta.lastUpdated", "type": "TS -> instant"},
                    {"v2_field": "MSH-9", "name": "Message Type", "fhir_path": "MessageHeader.eventCoding.code", "type": "MSG -> code", "notes": "Mapped using Message Type ValueSet (e.g. ADT^A08 -> ADT-A08)"},
                    {"v2_field": "MSH-10", "name": "Message Control ID", "fhir_path": "MessageHeader.id", "type": "ST -> id"}
                ]
            },
            "PID": {
                "description": "Patient Identification Segment",
                "mappings": [
                    {"v2_field": "PID-3", "name": "Patient Identifier List", "fhir_path": "Patient.identifier", "type": "CX -> Identifier", "notes": "Maps PID-3.1 (ID) to identifier.value, and PID-3.4 (Assigning Authority) to identifier.system OID"},
                    {"v2_field": "PID-5", "name": "Patient Name", "fhir_path": "Patient.name", "type": "XPN -> HumanName", "notes": "Maps PID-5.1 (Family Name) to name.family, and PID-5.2 (Given Name) to name.given"},
                    {"v2_field": "PID-7", "name": "Date/Time of Birth", "fhir_path": "Patient.birthDate", "type": "TS -> date", "notes": "Extracts YYYY-MM-DD from TS"},
                    {"v2_field": "PID-8", "name": "Administrative Sex", "fhir_path": "Patient.gender", "type": "IS -> code", "notes": "Mapped: M -> male, F -> female, O -> other, U -> unknown"},
                    {"v2_field": "PID-11", "name": "Patient Address", "fhir_path": "Patient.address", "type": "XAD -> Address", "notes": "Maps PID-11.1 to address.line, PID-11.3 to address.city, PID-11.4 to address.state, PID-11.5 to address.postalCode"}
                ]
            },
            "PV1": {
                "description": "Patient Visit Segment",
                "mappings": [
                    {"v2_field": "PV1-2", "name": "Patient Class", "fhir_path": "Encounter.class", "type": "IS -> Coding", "notes": "Mapped: I -> inpatient, O -> outpatient, E -> emergency, R -> ambulatory"},
                    {"v2_field": "PV1-3", "name": "Assigned Patient Location", "fhir_path": "Encounter.location.location", "type": "PL -> Reference(Location)"},
                    {"v2_field": "PV1-19", "name": "Visit Number", "fhir_path": "Encounter.identifier", "type": "CX -> Identifier", "notes": "Often maps to an encounter or billing account identifier"},
                    {"v2_field": "PV1-44", "name": "Admit Date/Time", "fhir_path": "Encounter.period.start", "type": "TS -> dateTime"}
                ]
            },
            "OBX": {
                "description": "Observation/Result Segment",
                "mappings": [
                    {"v2_field": "OBX-2", "name": "Value Type", "fhir_path": "Observation.value[x]", "type": "ID -> Type choice", "notes": "Determines value type: NM -> valueQuantity, ST/TX -> valueString, CE/CWE -> valueCodeableConcept"},
                    {"v2_field": "OBX-3", "name": "Observation Identifier", "fhir_path": "Observation.code", "type": "CWE -> CodeableConcept", "notes": "Maps OBX-3.1 to code.coding.code, OBX-3.2 to code.coding.display, OBX-3.3 to code.coding.system (e.g. LN for LOINC)"},
                    {"v2_field": "OBX-5", "name": "Observation Value", "fhir_path": "Observation.value[x]", "type": "Varies -> choice", "notes": "Value is formatted based on OBX-2"},
                    {"v2_field": "OBX-6", "name": "Units", "fhir_path": "Observation.valueQuantity.unit", "type": "CWE -> string/Coding", "notes": "Maps OBX-6.1 to valueQuantity.unit and valueQuantity.code, OBX-6.3 to valueQuantity.system (UCUM)"},
                    {"v2_field": "OBX-11", "name": "Observation Result Status", "fhir_path": "Observation.status", "type": "ID -> code", "notes": "Mapped: F -> final, C -> corrected, P -> preliminary, X -> cancelled"}
                ]
            }
        }
    }
    
    with open(HL7_DIR / "hl7_v2_fhir_mappings.json", "w", encoding="utf-8") as f:
        json.dump(mappings, f, indent=2)
    print("HL7 mappings generated.")

def generate_terminology_mappings():
    print("Generating Terminology mapping tables...")
    terminology_db = [
        {
            "local_code": "GLU_SERUM",
            "local_description": "Blood glucose serum",
            "standard_system": "LOINC",
            "standard_code": "15074-8",
            "standard_display": "Glucose [Mass/volume] in Serum or Plasma",
            "notes": "Specimen: Serum/Plasma. Method: Chemistry. Property: Mass concentration.",
            "alternative_codes": [
                {"system": "LOINC", "code": "2339-0", "display": "Glucose [Mass/volume] in Blood", "reason": "Use if specimen is whole blood instead of serum."}
            ]
        },
        {
            "local_code": "WBC_COUNT",
            "local_description": "White blood cell count",
            "standard_system": "LOINC",
            "standard_code": "6690-2",
            "standard_display": "Leukocytes [#/volume] in Blood by Automated count",
            "notes": "Specimen: Blood. Method: Automated. Property: Number concentration.",
            "alternative_codes": []
        },
        {
            "local_code": "RBC_COUNT",
            "local_description": "Red blood cell count",
            "standard_system": "LOINC",
            "standard_code": "789-8",
            "standard_display": "Erythrocytes [#/volume] in Blood by Automated count",
            "notes": "Specimen: Blood. Method: Automated.",
            "alternative_codes": []
        },
        {
            "local_code": "HEMOGLOBIN",
            "local_description": "Hemoglobin test",
            "standard_system": "LOINC",
            "standard_code": "718-7",
            "standard_display": "Hemoglobin [Mass/volume] in Blood",
            "notes": "Specimen: Blood. Method: Chemistry.",
            "alternative_codes": []
        },
        {
            "local_code": "CREATININE",
            "local_description": "Serum Creatinine",
            "standard_system": "LOINC",
            "standard_code": "2160-0",
            "standard_display": "Creatinine [Mass/volume] in Serum or Plasma",
            "notes": "Specimen: Serum/Plasma. Essential for calculating eGFR.",
            "alternative_codes": []
        },
        {
            "local_code": "DIABETES_MELLITUS_T2",
            "local_description": "Type 2 diabetes mellitus",
            "standard_system": "SNOMED CT",
            "standard_code": "44054006",
            "standard_display": "Type 2 diabetes mellitus",
            "notes": "Clinical diagnosis code. Hierarchy: Diabetes mellitus -> Endocrine disorder.",
            "alternative_codes": [
                {"system": "ICD-10-CM", "code": "E11.9", "display": "Type 2 diabetes mellitus without complications", "reason": "Billing diagnosis code mapping."}
            ]
        },
        {
            "local_code": "HYPERTENSION",
            "local_description": "Essential hypertension",
            "standard_system": "SNOMED CT",
            "standard_code": "38341003",
            "standard_display": "Essential hypertension",
            "notes": "Clinical diagnosis code.",
            "alternative_codes": [
                {"system": "ICD-10-CM", "code": "I10", "display": "Essential (primary) hypertension", "reason": "Billing diagnosis code mapping."}
            ]
        },
        {
            "local_code": "METFORMIN_500",
            "local_description": "Metformin 500mg oral tablet",
            "standard_system": "RxNorm",
            "standard_code": "860975",
            "standard_display": "Metformin hydrochloride 500 MG Oral Tablet",
            "notes": "SCD (Semantic Clinical Drug) concept in RxNorm.",
            "alternative_codes": []
        },
        {
            "local_code": "LISINOPRIL_10",
            "local_description": "Lisinopril 10mg oral tablet",
            "standard_system": "RxNorm",
            "standard_code": "311354",
            "standard_display": "Lisinopril 10 MG Oral Tablet",
            "notes": "SCD concept in RxNorm.",
            "alternative_codes": []
        }
    ]

    with open(TERM_DIR / "terminology_mappings.json", "w", encoding="utf-8") as f:
        json.dump(terminology_db, f, indent=2)
    print("Terminology mappings generated.")

def generate_organization_specs():
    print("Generating organization-specific documentation...")
    
    # 1. Hospital Interface Specification
    interface_spec = """# St. Jude General Hospital - Interface Specification v2.4

This document defines the custom data exchange rules and interface parameters for St. Jude General Hospital (ST_JUDE_GH).

## HL7 v2 ADT & ORU Connection Rules

### Sending Facility and Application
- **MSH-3 (Sending Application):** Must be exactly `ST_JUDE_EMR`.
- **MSH-4 (Sending Facility):** Must be exactly `ST_JUDE_GH`.
Messages received with incorrect Sending Facility/Application codes will be automatically rejected.

### Patient Identifiers (PID Segment)
- **PID-3 (Patient Identifier List):** The primary identifier must use the Assigning Authority `STJ_MRN`.
- **Format:** `PID-3.1` must contain the numeric ID, and `PID-3.4` must contain the namespace `STJ_MRN`.
  *Example:* `12345^^^STJ_MRN`

### Visit Numbers (PV1 Segment)
- **PV1-19 (Visit Number):** This field is **mandatory** for all admission and discharge messages (ADT^A01, ADT^A03, ADT^A08).
- **Format constraint:** The Visit Number must start with the prefix `STJ-` followed by 6 digits.
  *Example:* `STJ-998877`
  *Violation Error:* Messages with missing or malformed PV1-19 fields will trigger a `Negative Acknowledgment (NACK)` with error code `102` (Data type error).

### Custom Z-Segments
- **ZPD Segment:** Contains custom patient preferences.
  - `ZPD-1`: Smoking status (Y/N).
  - `ZPD-2`: Preferred language (ISO 639-1).
"""
    with open(ORG_DIR / "hospital_interface_spec.md", "w", encoding="utf-8") as f:
        f.write(interface_spec)
        
    # 2. Local Terminology Mapping CSV
    csv_data = [
        ["LocalCode", "LocalDescription", "MappedLOINC", "MandatoryForBilling", "Comments"],
        ["GLU_SERUM", "Blood glucose serum", "15074-8", "YES", "Billing requires LOINC code matching serum specimen"],
        ["WBC_COUNT", "White blood cell count", "6690-2", "YES", "Auto count method only"],
        ["RBC_COUNT", "Red blood cell count", "789-8", "NO", "Optional panel component"],
        ["HEMOGLOBIN", "Hemoglobin test", "718-7", "YES", "Required for anemia panel validation"],
        ["CREATININE", "Serum Creatinine", "2160-0", "YES", "Must support eGFR calculation triggers"]
    ]
    with open(ORG_DIR / "hospital_terminology_map.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(csv_data)

    # 3. Vendor Integration Guide
    vendor_guide = """# EMR Vendor Integration Guide (Epic/Cerner Bridge)

This guide documents the integration profiles and API parameters required for communicating with the regional EMR Hub.

## API Authentication & Scopes
- **Auth Endpoint:** `https://emr-hub.local/oauth/token`
- **Required OAuth Scopes:**
  - `patient/Patient.read`
  - `patient/Observation.read`
  - `patient/Observation.write`
  - `launch`
  - `openid`

## FHIR Profile Restrictions
The EMR Hub enforces the US Core v6.1.0 profiles.
1. **Observation Category Slicing:** 
   - All Observations must contain a category coding with system `http://terminology.hl7.org/CodeSystem/observation-category` and code `laboratory` to route correctly to the Lab Results module.
2. **Missing Status Codes:**
   - Any Observation payload sent with a status of `preliminary` will be held in queue for 24 hours. A status of `final` triggers immediate provider notification.
"""
    with open(ORG_DIR / "vendor_integration_guide.md", "w", encoding="utf-8") as f:
        f.write(vendor_guide)

    print("Organization specs generated.")

def main():
    print("Initializing dataset preparation...")
    create_dirs()
    
    # Download US Core TGZ
    us_core_path = CACHE_DIR / "us_core_package.tgz"
    download_file(US_CORE_URL, us_core_path)
    
    # Download FHIR R4 Core TGZ
    fhir_r4_path = CACHE_DIR / "fhir_r4_package.tgz"
    download_file(FHIR_R4_URL, fhir_r4_path)
    
    # Filters to keep dataset clean and relevant to our 4 features
    us_core_filters = [
        "StructureDefinition-us-core-patient",
        "StructureDefinition-us-core-observationclinicalresult",
        "StructureDefinition-us-core-encounter",
        "StructureDefinition-us-core-organization",
        "ValueSet-us-core-observation-codes",
        "ValueSet-us-core-clinical-result-observation-category"
    ]
    
    fhir_r4_filters = [
        "StructureDefinition-Patient",
        "StructureDefinition-Observation",
        "StructureDefinition-Encounter",
        "StructureDefinition-Organization"
    ]
    
    # Extract only matching profiles to keep context and processing extremely fast
    extract_profiles(us_core_path, FHIR_DIR, us_core_filters)
    extract_profiles(fhir_r4_path, FHIR_DIR, fhir_r4_filters)
    
    # Generate supporting datasets
    generate_hl7_mappings()
    generate_terminology_mappings()
    generate_organization_specs()
    
    print("\nDataset preparation successfully completed!")

if __name__ == "__main__":
    main()
