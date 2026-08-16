from __future__ import annotations

import re

from src.guardrails.nemo_guardrails_service import GuardrailDecision, NeMoGuardrailService


class GuardrailViolation(ValueError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


_nemo_guardrails = NeMoGuardrailService()

OFF_TOPIC_MESSAGE = (
    "Sorry, I can not answer this question. I am a healthcare interoperability assistant. "
    "I can answer questions related to "
    "FHIR, HL7, terminology mapping, validation, format conversion, and integration "
    "debugging. If you have any question related to this, you can ask."
)


HEALTHCARE_KEYWORDS = {
    "fhir",
    "hl7",
    "hl7v2",
    "interoperability",
    "hospital",
    "patient",
    "observation",
    "encounter",
    "condition",
    "allergy",
    "medication",
    "terminology",
    "loinc",
    "snomed",
    "rxnorm",
    "profile",
    "structuredefinition",
    "adt",
    "oru",
    "orm",
    "pid",
    "pv1",
    "msh",
    "obx",
    "resource",
    "bundle",
    "us core",
    "validator",
    "integration",
}

OFF_TOPIC_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bwrite (?:a )?(?:poem|story|essay|song|joke)\b",
        r"\bweather\b",
        r"\bmovie\b",
        r"\bcoffe(?:e)?\b",
        r"\btea\b",
        r"\brestaurant\b",
        r"\bfood\b",
        r"\btravel itinerary\b",
        r"\brecipe\b",
        r"\bcook(?:ing)?\b",
        r"\bsolve (?:my )?homework\b",
        r"\bstock price\b",
        r"\bcrypto\b",
        r"\bcricket\b",
        r"\bfootball\b",
        r"\bmatch score\b",
        r"\bwho won\b",
        r"\bfashion\b",
        r"\boutfit\b",
        r"\bmusic\b",
        r"\bgaming\b",
        r"\bvacation\b",
    ]
]

CONVERSION_INTENT_KEYWORDS = {
    "convert",
    "conversion",
    "transform",
    "translate",
    "mapping",
    "map",
    "json",
    "fhir",
    "hl7",
    "hl7v2",
    "adt",
    "oru",
    "orm",
    "pid",
    "pv1",
    "msh",
    "obx",
    "resource",
}

GENERIC_NON_HEALTHCARE_QUERY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^(how to|how do i|what is|what are|who is|who are|tell me|give me|can you)\b",
        r"\b(make|cook|brew|recipe|coffee|coffe|tea|movie|music|travel|vacation|game|sport|fashion)\b",
    ]
]

SECRET_EXTRACTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\b(show|print|reveal|expose|dump|give|share|display|list)\b.{0,40}\b(api[_ -]?key|token|secret|password|credential|bearer|private key|ssh key|access key)\b",
        r"\b(api[_ -]?key|token|secret|password|credential|bearer|private key|ssh key|access key)\b.{0,40}\b(show|print|reveal|expose|dump|give|share|display|list)\b",
        r"\b(what(?:'s| is)|tell me|which|give me)\b.{0,60}\b(your|the)?\b.{0,20}\b(openai|groq|qdrant|qudarant)?\b.{0,20}\b(api[_ -]?key|token|secret|password|credential|access key|db key|database key|key)\b",
        r"\b(read|open|cat|show)\b.{0,40}\b\.env\b",
    ]
]

PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"forget (all |any |the |your )?(previous|prior|above|system|developer)? ?instructions?",
        r"ignore (all |any |the )?(previous|prior|above) instructions",
        r"disregard (all |any |the )?(previous|prior|above) instructions",
        r"reveal (the )?(system|developer) prompt",
        r"show (the )?(hidden|system|developer) instructions",
        r"bypass (your )?(guardrails|safety|restrictions)",
        r"(from now on|starting now).{0,30}(your name is|you are)",
        r"your name is\s+[a-z0-9_-]{2,30}",
        r"act as (if )?you (have no rules|are unrestricted)",
        r"pretend to be (?:the )?(system|developer)",
        r"do anything now",
        r"jailbreak",
        r"prompt injection",
    ]
]


def enforce_query_guardrails(
    query: str,
    payload: str | None = None,
    capability_hint: str | None = None,
    profile_url: str | None = None,
    enable_nemo: bool = True,
) -> None:
    normalized_query = (query or "").strip()
    normalized_payload = (payload or "").strip()
    normalized_hint = (capability_hint or "").strip().lower()
    normalized_profile = (profile_url or "").strip().lower()

    if _matches_any(normalized_query, SECRET_EXTRACTION_PATTERNS):
        raise GuardrailViolation(
            "secret_request",
            OFF_TOPIC_MESSAGE,
        )

    if _matches_any(normalized_query, PROMPT_INJECTION_PATTERNS):
        raise GuardrailViolation(
            "prompt_injection",
            OFF_TOPIC_MESSAGE,
        )

    if _matches_any(normalized_query, OFF_TOPIC_PATTERNS):
        raise GuardrailViolation(
            "off_topic",
            OFF_TOPIC_MESSAGE,
        )

    if _looks_like_generic_off_topic_query(normalized_query):
        raise GuardrailViolation(
            "off_topic",
            OFF_TOPIC_MESSAGE,
        )

    if not enable_nemo:
        if _is_on_topic(normalized_query, normalized_payload, normalized_hint, normalized_profile):
            return
        raise GuardrailViolation(
            "off_topic",
            OFF_TOPIC_MESSAGE,
        )

    if _is_on_topic(normalized_query, normalized_payload, normalized_hint, normalized_profile):
        # Deterministic rules above already block secret/prompt-injection/off-topic patterns.
        # For clearly on-topic healthcare interoperability requests, avoid NeMo false positives.
        return

    nemo_decision = _nemo_guardrails.evaluate(
        query=normalized_query,
        payload=normalized_payload,
        capability_hint=normalized_hint,
        profile_url=normalized_profile,
    )
    if nemo_decision is not None and not nemo_decision.allowed:
        _raise_on_block(_enrich_block_decision(nemo_decision, normalized_query))
        return

    raise GuardrailViolation(
        "off_topic",
        OFF_TOPIC_MESSAGE,
    )


def _is_on_topic(query: str, payload: str, capability_hint: str, profile_url: str) -> bool:
    combined = " ".join(part for part in [query, payload, capability_hint, profile_url] if part).lower()

    if profile_url:
        return True
    if payload.startswith("{") or payload.startswith("MSH|") or payload.startswith("PID|"):
        return True
    return any(keyword in combined for keyword in HEALTHCARE_KEYWORDS)


def _matches_any(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _looks_like_generic_off_topic_query(query: str) -> bool:
    if not query:
        return False

    lowered = query.lower()
    if any(keyword in lowered for keyword in HEALTHCARE_KEYWORDS):
        return False

    if any(keyword in lowered for keyword in CONVERSION_INTENT_KEYWORDS):
        return False

    return _matches_any(query, GENERIC_NON_HEALTHCARE_QUERY_PATTERNS)


def _raise_on_block(decision: GuardrailDecision) -> None:
    if decision.allowed:
        return

    raise GuardrailViolation(
        decision.category or "guardrail_block",
        decision.message or "Request blocked by guardrail.",
    )


def _enrich_block_decision(decision: GuardrailDecision, query: str) -> GuardrailDecision:
    if decision.allowed or (decision.category and decision.message):
        return decision

    if _matches_any(query, SECRET_EXTRACTION_PATTERNS):
        return GuardrailDecision(
            allowed=False,
            category="secret_request",
            message=OFF_TOPIC_MESSAGE,
        )

    if _matches_any(query, PROMPT_INJECTION_PATTERNS):
        return GuardrailDecision(
            allowed=False,
            category="prompt_injection",
            message=OFF_TOPIC_MESSAGE,
        )

    return GuardrailDecision(
        allowed=False,
        category="off_topic",
        message=OFF_TOPIC_MESSAGE,
    )