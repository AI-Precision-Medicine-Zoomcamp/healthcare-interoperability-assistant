# St. Jude General Hospital - Interface Specification v2.4

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
