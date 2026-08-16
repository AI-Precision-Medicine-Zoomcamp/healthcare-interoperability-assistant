# EMR Vendor Integration Guide (Epic/Cerner Bridge)

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
