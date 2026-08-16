import os
import sys
import json
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.llm.llm_service import LLMService
from src.rag.rag_service import RAGService
from src.guardrails.query_guardrails import enforce_query_guardrails
from src.tools.hl7_tools import HL7Parser
from src.tools.fhir_tools import FHIRValidator

class AgentService:
    def __init__(self):
        self.llm_service = LLMService()
        self.llm = self.llm_service.llm
        self.rag_service = RAGService()

    def process_query(
        self,
        query: str,
        payload: str = None,
        profile_url: str = None,
        capability_hint: str | None = None,
    ) -> dict:
        """
        Main orchestration endpoint.
        Routes queries, parses inputs with tools, retrieves RAG context, and calls LLM.
        """
        enforce_query_guardrails(
            query=query,
            payload=payload,
            capability_hint=capability_hint,
            profile_url=profile_url,
        )

        # 1. Intent routing
        intent = self._route_intent(query, payload, capability_hint)
        
        # 2. Tool Execution & In-Memory parsing
        parsed_payload_info = ""
        tool_validation_result = None
        
        if payload:
            if payload.strip().startswith("{"):
                # Handle FHIR JSON payload
                try:
                    resource = json.loads(payload)
                    if intent == "json_to_fhir":
                        parsed_payload_info = "Input parsed as generic JSON object (candidate for FHIR conversion).\n"
                        parsed_payload_info += f"Top-level keys: {list(resource.keys())}"
                    else:
                        # Run deterministic validation for FHIR debugging flows
                        tool_validation_result = FHIRValidator.validate_resource(resource, profile_url)
                        parsed_payload_info = f"Parsed Resource Type: {resource.get('resourceType')}\n"
                        parsed_payload_info += f"Initial Validator Errors: {tool_validation_result['errors']}"
                except json.JSONDecodeError:
                    parsed_payload_info = "Payload starts with '{' but is not valid JSON."
            elif any(payload.startswith(seg) for seg in ["MSH", "PID", "PV1", "OBX"]):
                # Handle HL7 message
                parsed = HL7Parser.parse_message(payload)
                parsed_payload_info = f"Parsed HL7 Segments: {list(parsed.keys())}\n"
                parsed_payload_info += f"Sending Facility (MSH-4): {HL7Parser.get_field(parsed, 'MSH-4')}\n"
                parsed_payload_info += f"Visit Number (PV1-19): {HL7Parser.get_field(parsed, 'PV1-19')}\n"
                parsed_payload_info += f"Patient ID (PID-3.1): {HL7Parser.get_field(parsed, 'PID-3.1')}"

        # 3. Context Retrieval (RAG)
        context = ""
        citations = []
        
        if intent == "fhir_debugging":
            # Retrieve profiles and value sets
            search_query = f"{profile_url or ''} {query}"
            context = self.rag_service.get_context(search_query, doc_type="fhir_profile", limit=3)
            citations.append("Official FHIR StructureDefinitions (US Core / Base)")
        elif intent == "json_to_fhir":
            # Retrieve profile context to guide conversion into valid FHIR shapes
            search_query = f"FHIR conversion rules {profile_url or ''} {query}"
            context = self.rag_service.get_context(search_query, doc_type="fhir_profile", limit=3)
            citations.append("FHIR StructureDefinitions and profile examples")
        elif intent == "hl7_mapping":
            # Retrieve segment mappings
            context = self.rag_service.get_context(query, doc_type="hl7_mapping", limit=3)
            citations.append("HL7 v2 to FHIR R4 Mapping Tables")
        elif intent == "terminology_mapping":
            # Retrieve terminology concepts
            context = self.rag_service.get_context(query, doc_type="terminology_map", limit=3)
            citations.append("Standard Terminology Mapping Database (LOINC / SNOMED CT / RxNorm)")
        elif intent == "org_debugging":
            # Retrieve hospital connection specifications & internal mapping tables
            context = self.rag_service.get_context(query, doc_type="organization_rule", limit=4)
            citations.append("St. Jude General Hospital Connection Specs (hospital_interface_spec.md)")
            citations.append("Local Terminology Mappings (hospital_terminology_map.csv)")
            citations.append("EMR Vendor Integration Guide (vendor_integration_guide.md)")

        # 4. Construct prompt and invoke LLM
        prompt = self._build_prompt(intent, query, payload, parsed_payload_info, context)
        
        print(f"Routing to LLM for intent: {intent}...")
        response = self.llm.invoke(prompt)
        
        # Parse the structured sections from the LLM output
        llm_text = response.content
        explanation, correction = self._split_response_sections(llm_text)
        
        # 5. Build final response
        return {
            "intent": intent,
            "validation_result": tool_validation_result,
            "citations": citations,
            "explanation": explanation,
            "correction": correction
        }

    def _route_intent(self, query: str, payload: str = None, capability_hint: str | None = None) -> str:
        """
        Classifies the query and payload into known assistant capabilities.
        """
        q = query.lower()
        hint = (capability_hint or "").lower()

        if "json to fhir" in hint:
            return "json_to_fhir"
        if "fhir validation" in hint:
            return "fhir_debugging"
        if "hl7" in hint:
            return "hl7_mapping"
        if "terminology" in hint:
            return "terminology_mapping"
        if "organization" in hint:
            return "org_debugging"

        # JSON to FHIR conversion indicators
        if (
            "json to fhir" in q
            or "convert json" in q and "fhir" in q
            or "transform json" in q and "fhir" in q
            or "map json" in q and "fhir" in q
        ):
            return "json_to_fhir"
        
        # Org specific indicators
        if "st. jude" in q or "hospital rule" in q or "nack" in q or "rejected" in q or "org-specific" in q:
            return "org_debugging"
            
        # Terminology indicators
        if "loinc" in q or "snomed" in q or "rxnorm" in q or "terminology" in q or "code map" in q or "glu_serum" in q:
            return "terminology_mapping"
            
        # HL7 indicators
        if "hl7" in q or "segment" in q or "translate" in q or "msh" in q or "pid" in q or "pv1" in q or (payload and "MSH|" in payload):
            return "hl7_mapping"
            
        # Default fallback to FHIR debugging (flagship feature)
        return "fhir_debugging"

    def _build_prompt(self, intent: str, query: str, payload: str, parsed_payload_info: str, context: str) -> str:
        base_prompt = f"""You are an expert Healthcare Interoperability AI Assistant.
Use the following retrieved context, specifications, and parsed payload information to resolve the user's inquiry.
Provide your response in two distinct parts:
1. EXPLANATION: Write a clear, cited explanation of the issue, mapping, or error. State references to the source specifications.
2. CORRECTION: Provide the corrected FHIR JSON resource, code segment, mapping table, or configuration. Keep formatting clean.

---
USER QUERY:
{query}

PAYLOAD (IF PROVIDED):
{payload}

PARSED PAYLOAD INFO (FROM DETERMINISTIC TOOLS):
{parsed_payload_info}

RETRIEVED KNOWLEDGE BASE CONTEXT (RAG):
{context}
---
"""
        if intent == "fhir_debugging":
            base_prompt += """
Instruction for FHIR Debugging:
- Analyze the validation error and the JSON payload.
- Contrast the payload with the retrieved StructureDefinition rules.
- Pinpoint the exact element path and cardinality mismatch (e.g. min: 1 but found 0).
- Generate a corrected, fully valid FHIR JSON payload that resolves the errors.
"""
        elif intent == "json_to_fhir":
            base_prompt += """
Instruction for JSON to FHIR Conversion:
- Treat the payload as non-FHIR business JSON and convert it into a valid FHIR JSON resource.
- Choose the most appropriate FHIR resourceType based on the input semantics (for example Patient, Observation, Encounter, or Condition).
- Keep all clinically meaningful values from the source JSON.
- In EXPLANATION, briefly map source fields to target FHIR fields.
- In CORRECTION, return clean FHIR JSON only.
"""
        elif intent == "hl7_mapping":
            base_prompt += """
Instruction for HL7 Mapping:
- Match each parsed segment/field (PID, MSH, PV1, OBX) to the retrieved mapping standard.
- Formulate a clean mapping explanation explaining exactly which v2 field maps to which FHIR resource element.
- Generate the converted FHIR JSON payload representing the input HL7 message.
"""
        elif intent == "terminology_mapping":
            base_prompt += """
Instruction for Terminology Mapping:
- Review the local code, description, and standard candidate concepts.
- Explain the match: specimen type, analyte measured, or clinical concept hierarchy.
- List the candidate LOINC/SNOMED CT/RxNorm codes, give mapping rationale, indicate a confidence score, and explain why other alternatives are less suitable.
"""
        elif intent == "org_debugging":
            base_prompt += """
Instruction for Organization Connection Debugging:
- Contrast the official HL7/FHIR standard with the hospital-specific interface specification.
- Identify where the payload violated the hospital-specific custom rule (e.g. PV1-19 prefix requirement, MSH-4 Sending Facility code).
- Explain the discrepancy clearly, citing the hospital spec, and provide a corrected payload or message that conforms to the hospital interface.
"""
        return base_prompt

    def _split_response_sections(self, llm_text: str) -> tuple:
        """
        Splits LLM response into EXPLANATION and CORRECTION sections based on headers.
        """
        explanation = llm_text
        correction = ""
        
        # Try to find headers
        if "CORRECTION" in llm_text:
            parts = llm_text.split("CORRECTION", 1)
            explanation = parts[0].replace("EXPLANATION", "").strip()
            # Clean up leading colons/dashes in header split
            correction = parts[1].strip()
            if correction.startswith(":") or correction.startswith("-"):
                correction = correction[1:].strip()
        elif "2." in llm_text and "Correction" in llm_text:
            parts = llm_text.split("2.", 1)
            explanation = parts[0].replace("1. Explanation", "").replace("1.", "").strip()
            correction = parts[1].replace("Correction", "").strip()
            if correction.startswith(":") or correction.startswith("-"):
                correction = correction[1:].strip()
                
        return explanation, correction

if __name__ == "__main__":
    print("Testing Agent Service...")
    agent = AgentService()
    
    # Test FHIR Validation Error Debugging
    bad_json = {
        "resourceType": "Observation",
        "status": "final"
    }
    
    res = agent.process_query(
        query="Why is this US Core Observation invalid? Find the constraint and give me corrected FHIR.",
        payload=json.dumps(bad_json),
        profile_url="http://hl7.org/fhir/us/core/StructureDefinition/us-core-observationclinicalresult"
    )
    
    print("\n--- AGENT RESULT ---")
    print("Intent Identified:", res["intent"])
    print("\nExplanation:\n", res["explanation"])
    print("\nCorrection:\n", res["correction"])
