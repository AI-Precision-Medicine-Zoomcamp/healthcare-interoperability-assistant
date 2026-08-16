import json

class FHIRValidator:
    @staticmethod
    def validate_resource(resource: dict, profile_url: str = None) -> dict:
        """
        Validates a FHIR resource dict against core and profile specifications.
        Returns a dictionary:
        {
            "is_valid": bool,
            "errors": list of error details,
            "profile_checked": str
        }
        """
        errors = []
        
        # 1. Basic resource checks
        if not isinstance(resource, dict):
            return {"is_valid": False, "errors": ["Resource is not a valid JSON object"], "profile_checked": profile_url}
            
        resource_type = resource.get("resourceType")
        if not resource_type:
            return {"is_valid": False, "errors": ["Missing mandatory field: 'resourceType'"], "profile_checked": profile_url}
            
        # Determine profile URL if not explicitly provided
        if not profile_url:
            meta = resource.get("meta", {})
            profiles = meta.get("profile", [])
            if profiles:
                profile_url = profiles[0]
            else:
                profile_url = f"http://hl7.org/fhir/StructureDefinition/{resource_type}"

        # 2. Base resource validation
        if resource_type == "Observation":
            # Observation base fields validation
            if "status" not in resource or not resource["status"]:
                errors.append("Element 'Observation.status': minimum cardinality 1 but found 0")
            if "code" not in resource or not resource["code"]:
                errors.append("Element 'Observation.code': minimum cardinality 1 but found 0")
                
            # Profile US Core Observation Clinical Result / Laboratory Result
            if "us-core-observation" in profile_url or "us-core-laboratory" in profile_url:
                # Category slice check (Laboratory results must have laboratory category coding)
                categories = resource.get("category", [])
                has_lab_category = False
                for cat in categories:
                    codings = cat.get("coding", [])
                    for coding in codings:
                        system = coding.get("system")
                        code = coding.get("code")
                        if system == "http://terminology.hl7.org/CodeSystem/observation-category" and code == "laboratory":
                            has_lab_category = True
                            break
                
                if not has_lab_category:
                    errors.append("Slice 'Observation.category:Laboratory': minimum cardinality 1 but found 0 (Must support category coding with system 'http://terminology.hl7.org/CodeSystem/observation-category' and code 'laboratory')")
                    
        elif resource_type == "Patient":
            # Patient base fields validation
            if "name" not in resource or not resource["name"]:
                errors.append("Element 'Patient.name': minimum cardinality 1 but found 0")
                
            # Profile US Core Patient
            if "us-core-patient" in profile_url:
                if "identifier" not in resource or not resource["identifier"]:
                    errors.append("Element 'Patient.identifier': minimum cardinality 1 but found 0 (Must support patient identifier list)")
                    
        elif resource_type == "Encounter":
            if "status" not in resource or not resource["status"]:
                errors.append("Element 'Encounter.status': minimum cardinality 1 but found 0")
            if "class" not in resource or not resource["class"]:
                errors.append("Element 'Encounter.class': minimum cardinality 1 but found 0")
                
        else:
            # For other resource types, check for basic metadata structures
            pass

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "profile_checked": profile_url
        }

if __name__ == "__main__":
    print("Testing FHIR Validator...")
    # Test invalid observation
    bad_obs = {
        "resourceType": "Observation",
        "status": "final"
        # Missing code
    }
    res = FHIRValidator.validate_resource(bad_obs, "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observationclinicalresult")
    print("Invalid Observation Result:", res)
    
    # Test valid observation
    good_obs = {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "15074-8",
                "display": "Glucose [Mass/volume] in Serum or Plasma"
            }]
        },
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "laboratory",
                "display": "Laboratory"
            }]
        }],
        "subject": {
            "reference": "Patient/example"
        },
        "valueQuantity": {
            "value": 110,
            "unit": "mg/dL",
            "system": "http://unitsofmeasure.org",
            "code": "mg/dL"
        }
    }
    res = FHIRValidator.validate_resource(good_obs, "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observationclinicalresult")
    print("Valid Observation Result:", res)
