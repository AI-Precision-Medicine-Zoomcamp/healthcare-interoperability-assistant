from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.tools.hl7_tools import HL7Parser


class FormatConverter:
    """Deterministic format conversion helpers for JSON, FHIR, and HL7 payloads."""

    @staticmethod
    def convert(
        source_format: str,
        target_format: str,
        payload: str,
        resource_type: str | None = None,
        message_type: str | None = None,
    ) -> dict[str, Any]:
        source = source_format.lower().strip()
        target = target_format.lower().strip()
        notes: list[str] = []
        warnings: list[str] = []

        if source not in {"json", "fhir", "hl7"}:
            raise ValueError(f"Unsupported source_format: {source_format}")
        if target not in {"json", "fhir", "hl7"}:
            raise ValueError(f"Unsupported target_format: {target_format}")

        if source == target:
            if target in {"json", "fhir"}:
                parsed = FormatConverter._loads_json(payload)
                converted_payload = json.dumps(parsed, indent=2)
                return {
                    "source_format": source,
                    "target_format": target,
                    "converted_payload": converted_payload,
                    "converted_json": parsed,
                    "notes": ["Source and target formats are the same; payload normalized."],
                    "warnings": warnings,
                }
            return {
                "source_format": source,
                "target_format": target,
                "converted_payload": payload.strip(),
                "converted_json": None,
                "notes": ["Source and target formats are the same; payload returned as-is."],
                "warnings": warnings,
            }

        if source == "json" and target == "fhir":
            data = FormatConverter._loads_json(payload)
            fhir = FormatConverter.json_to_fhir(data, resource_type=resource_type)
            notes.append("Converted custom JSON into FHIR resource.")
            return FormatConverter._json_response(source, target, fhir, notes, warnings)

        if source == "json" and target == "hl7":
            data = FormatConverter._loads_json(payload)
            fhir = FormatConverter.json_to_fhir(data, resource_type=resource_type)
            hl7_message = FormatConverter.fhir_to_hl7(fhir, message_type=message_type, warnings=warnings)
            notes.append("Converted JSON -> FHIR -> HL7.")
            return {
                "source_format": source,
                "target_format": target,
                "converted_payload": hl7_message,
                "converted_json": None,
                "notes": notes,
                "warnings": warnings,
            }

        if source == "fhir" and target == "json":
            resource = FormatConverter._loads_json(payload)
            business_json = FormatConverter.fhir_to_json(resource, warnings=warnings)
            notes.append("Converted FHIR resource into simplified business JSON.")
            return FormatConverter._json_response(source, target, business_json, notes, warnings)

        if source == "fhir" and target == "hl7":
            resource = FormatConverter._loads_json(payload)
            hl7_message = FormatConverter.fhir_to_hl7(resource, message_type=message_type, warnings=warnings)
            notes.append("Converted FHIR resource into HL7 v2 message.")
            return {
                "source_format": source,
                "target_format": target,
                "converted_payload": hl7_message,
                "converted_json": None,
                "notes": notes,
                "warnings": warnings,
            }

        if source == "hl7" and target == "json":
            business_json = FormatConverter.hl7_to_json(payload)
            notes.append("Converted HL7 message into simplified JSON.")
            return FormatConverter._json_response(source, target, business_json, notes, warnings)

        if source == "hl7" and target == "fhir":
            fhir = FormatConverter.hl7_to_fhir(payload)
            notes.append("Converted HL7 message into FHIR Bundle.")
            return FormatConverter._json_response(source, target, fhir, notes, warnings)

        raise ValueError(f"Unsupported conversion path: {source} -> {target}")

    @staticmethod
    def json_to_fhir(data: dict[str, Any], resource_type: str | None = None) -> dict[str, Any]:
        keys = {k.lower() for k in data.keys()}
        rtype = (resource_type or "").strip()

        if not rtype:
            if {"test_name", "result_value"}.intersection(keys):
                rtype = "Observation"
            elif {"family_name", "given_name", "birth_date", "dob"}.intersection(keys):
                rtype = "Patient"
            elif {"encounter_id", "visit_number", "encounter_status"}.intersection(keys):
                rtype = "Encounter"
            else:
                rtype = "Observation"

        if rtype == "Patient":
            patient_id = str(data.get("patient_id") or data.get("id") or "generated-patient")
            family_name = data.get("family_name") or data.get("last_name") or "UNKNOWN"
            given_name = data.get("given_name") or data.get("first_name") or "UNKNOWN"
            patient: dict[str, Any] = {
                "resourceType": "Patient",
                "id": patient_id,
                "name": [{"family": str(family_name), "given": [str(given_name)]}],
            }
            birth_date = data.get("birth_date") or data.get("dob")
            if birth_date:
                patient["birthDate"] = str(birth_date)
            if data.get("gender"):
                patient["gender"] = str(data["gender"]).lower()
            return patient

        if rtype == "Encounter":
            patient_id = str(data.get("patient_id") or "unknown")
            encounter = {
                "resourceType": "Encounter",
                "id": str(data.get("encounter_id") or data.get("visit_number") or "enc-1"),
                "status": str(data.get("encounter_status") or "in-progress"),
                "class": {"code": str(data.get("encounter_class") or "AMB")},
                "subject": {"reference": f"Patient/{patient_id}"},
            }
            start = data.get("start_time")
            end = data.get("end_time")
            if start or end:
                encounter["period"] = {}
                if start:
                    encounter["period"]["start"] = str(start)
                if end:
                    encounter["period"]["end"] = str(end)
            return encounter

        patient_id = str(data.get("patient_id") or "unknown")
        observation: dict[str, Any] = {
            "resourceType": "Observation",
            "status": str(data.get("status") or "final"),
            "subject": {"reference": f"Patient/{patient_id}"},
            "code": {"text": str(data.get("test_name") or data.get("code") or "Observation")},
        }
        if data.get("effective_time"):
            observation["effectiveDateTime"] = str(data.get("effective_time"))
        if data.get("result_value") is not None:
            observation["valueQuantity"] = {
                "value": data.get("result_value"),
                "unit": str(data.get("result_unit") or "1"),
            }
        elif data.get("value") is not None:
            observation["valueString"] = str(data.get("value"))
        return observation

    @staticmethod
    def fhir_to_json(resource: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
        warnings = warnings if warnings is not None else []
        rtype = resource.get("resourceType")

        if rtype == "Observation":
            subject_ref = str(resource.get("subject", {}).get("reference", ""))
            patient_id = subject_ref.split("/")[-1] if "/" in subject_ref else subject_ref
            value_qty = resource.get("valueQuantity", {})
            return {
                "patient_id": patient_id or None,
                "test_name": resource.get("code", {}).get("text"),
                "result_value": value_qty.get("value"),
                "result_unit": value_qty.get("unit"),
                "effective_time": resource.get("effectiveDateTime"),
                "status": resource.get("status"),
            }

        if rtype == "Patient":
            first_name = None
            family_name = None
            names = resource.get("name") or []
            if names:
                family_name = names[0].get("family")
                given = names[0].get("given") or []
                if given:
                    first_name = given[0]
            return {
                "patient_id": resource.get("id"),
                "given_name": first_name,
                "family_name": family_name,
                "gender": resource.get("gender"),
                "birth_date": resource.get("birthDate"),
            }

        if rtype == "Encounter":
            subject_ref = str(resource.get("subject", {}).get("reference", ""))
            patient_id = subject_ref.split("/")[-1] if "/" in subject_ref else subject_ref
            period = resource.get("period", {})
            return {
                "encounter_id": resource.get("id"),
                "encounter_status": resource.get("status"),
                "encounter_class": resource.get("class", {}).get("code"),
                "patient_id": patient_id or None,
                "start_time": period.get("start"),
                "end_time": period.get("end"),
            }

        warnings.append(f"Generic flattening used for unsupported FHIR resourceType: {rtype}")
        return {
            "resource_type": rtype,
            "id": resource.get("id"),
            "raw": resource,
        }

    @staticmethod
    def fhir_to_hl7(resource: dict[str, Any], message_type: str | None = None, warnings: list[str] | None = None) -> str:
        warnings = warnings if warnings is not None else []
        rtype = resource.get("resourceType")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        if rtype == "Observation":
            subject_ref = str(resource.get("subject", {}).get("reference", ""))
            patient_id = subject_ref.split("/")[-1] if "/" in subject_ref else (subject_ref or "UNKNOWN")
            code_text = resource.get("code", {}).get("text") or "OBS"
            value_qty = resource.get("valueQuantity", {})
            value = value_qty.get("value", "")
            unit = value_qty.get("unit", "")
            msg_type = message_type or "ORU^R01"
            segments = [
                f"MSH|^~\\&|FHIR_APP|FHIR_SRC|EXT_SYSTEM|EXT_DST|{ts}||{msg_type}|MSG00001|P|2.5",
                f"PID|1||{patient_id}||UNKNOWN^UNKNOWN",
                f"OBR|1||1|{code_text}",
                f"OBX|1|NM|{code_text}||{value}|{unit}",
            ]
            return "\r".join(segments)

        if rtype == "Patient":
            patient_id = resource.get("id") or "UNKNOWN"
            names = resource.get("name") or []
            family = "UNKNOWN"
            given = "UNKNOWN"
            if names:
                family = names[0].get("family") or family
                given_list = names[0].get("given") or []
                if given_list:
                    given = given_list[0]
            birth = resource.get("birthDate") or ""
            sex = (resource.get("gender") or "U").upper()[:1]
            msg_type = message_type or "ADT^A01"
            segments = [
                f"MSH|^~\\&|FHIR_APP|FHIR_SRC|EXT_SYSTEM|EXT_DST|{ts}||{msg_type}|MSG00001|P|2.5",
                f"PID|1||{patient_id}||{family}^{given}||{birth}|{sex}",
            ]
            return "\r".join(segments)

        if rtype == "Encounter":
            subject_ref = str(resource.get("subject", {}).get("reference", ""))
            patient_id = subject_ref.split("/")[-1] if "/" in subject_ref else (subject_ref or "UNKNOWN")
            visit_number = resource.get("id") or "VISIT1"
            msg_type = message_type or "ADT^A01"
            pv1_2 = "I" if (resource.get("class", {}) or {}).get("code") == "IMP" else "O"
            segments = [
                f"MSH|^~\\&|FHIR_APP|FHIR_SRC|EXT_SYSTEM|EXT_DST|{ts}||{msg_type}|MSG00001|P|2.5",
                f"PID|1||{patient_id}||UNKNOWN^UNKNOWN",
                f"PV1|1|{pv1_2}|||||||||||||||{visit_number}",
            ]
            return "\r".join(segments)

        raise ValueError(f"FHIR to HL7 conversion currently supports Observation, Patient, and Encounter. Got: {rtype}")

    @staticmethod
    def hl7_to_json(message: str) -> dict[str, Any]:
        parsed = HL7Parser.parse_message(message)
        return {
            "message_type": HL7Parser.get_field(parsed, "MSH-9"),
            "message_control_id": HL7Parser.get_field(parsed, "MSH-10"),
            "patient_id": HL7Parser.get_field(parsed, "PID-3.1"),
            "family_name": HL7Parser.get_field(parsed, "PID-5.1"),
            "given_name": HL7Parser.get_field(parsed, "PID-5.2"),
            "dob": HL7Parser.get_field(parsed, "PID-7"),
            "sex": HL7Parser.get_field(parsed, "PID-8"),
            "visit_number": HL7Parser.get_field(parsed, "PV1-19"),
            "observation_code": HL7Parser.get_field(parsed, "OBX-3.1"),
            "observation_value": HL7Parser.get_field(parsed, "OBX-5"),
            "observation_unit": HL7Parser.get_field(parsed, "OBX-6"),
        }

    @staticmethod
    def hl7_to_fhir(message: str) -> dict[str, Any]:
        parsed = HL7Parser.parse_message(message)

        patient_id = HL7Parser.get_field(parsed, "PID-3.1") or "unknown"
        family = HL7Parser.get_field(parsed, "PID-5.1") or "UNKNOWN"
        given = HL7Parser.get_field(parsed, "PID-5.2") or "UNKNOWN"
        birth = HL7Parser.get_field(parsed, "PID-7")
        sex = HL7Parser.get_field(parsed, "PID-8")

        patient: dict[str, Any] = {
            "resourceType": "Patient",
            "id": str(patient_id),
            "name": [{"family": str(family), "given": [str(given)]}],
        }
        if birth:
            patient["birthDate"] = str(birth)
        if sex:
            patient["gender"] = str(sex).lower()

        entries = [{"resource": patient}]

        obx_code = HL7Parser.get_field(parsed, "OBX-3.1")
        obx_value = HL7Parser.get_field(parsed, "OBX-5")
        obx_unit = HL7Parser.get_field(parsed, "OBX-6")
        if obx_code or obx_value:
            observation: dict[str, Any] = {
                "resourceType": "Observation",
                "status": "final",
                "code": {"text": str(obx_code or "Observation")},
                "subject": {"reference": f"Patient/{patient_id}"},
            }
            if obx_value is not None and str(obx_value) != "":
                try:
                    numeric_value = float(obx_value)
                    observation["valueQuantity"] = {
                        "value": numeric_value,
                        "unit": str(obx_unit or "1"),
                    }
                except ValueError:
                    observation["valueString"] = str(obx_value)
            entries.append({"resource": observation})

        visit_number = HL7Parser.get_field(parsed, "PV1-19")
        patient_class = HL7Parser.get_field(parsed, "PV1-2")
        if visit_number or patient_class:
            encounter = {
                "resourceType": "Encounter",
                "id": str(visit_number or "enc-1"),
                "status": "in-progress",
                "class": {"code": "IMP" if str(patient_class) == "I" else "AMB"},
                "subject": {"reference": f"Patient/{patient_id}"},
            }
            entries.append({"resource": encounter})

        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": entries,
        }

    @staticmethod
    def _loads_json(payload: str) -> dict[str, Any]:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Payload is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("JSON payload must be an object at the top level.")
        return parsed

    @staticmethod
    def _json_response(
        source: str,
        target: str,
        data: dict[str, Any],
        notes: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "source_format": source,
            "target_format": target,
            "converted_payload": json.dumps(data, indent=2),
            "converted_json": data,
            "notes": notes,
            "warnings": warnings,
        }
