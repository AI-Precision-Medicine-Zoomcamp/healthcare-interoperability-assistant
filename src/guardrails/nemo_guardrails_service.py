from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config.config import GROQ_API_KEY, LLM_MODEL, OPENAI_API_KEY


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    category: str | None = None
    message: str | None = None


class NeMoGuardrailService:
    ALLOW_MARKER = "__ALLOW_HEALTHCARE_INTEROP_QUERY__"
    BLOCK_MARKER = "__BLOCK__"
    CONFIG_ROOT = Path(__file__).resolve().parent / "nemo"

    def __init__(self) -> None:
        self._rails: Any | None = None
        self._load_failed = False

    def evaluate(
        self,
        query: str,
        payload: str | None = None,
        capability_hint: str | None = None,
        profile_url: str | None = None,
    ) -> GuardrailDecision | None:
        rails = self._load_rails()
        if rails is None:
            return None

        message = self._build_input_message(
            query=query,
            payload=payload,
            capability_hint=capability_hint,
            profile_url=profile_url,
        )
        response = rails.generate(messages=[{"role": "user", "content": message}])
        text = self._extract_text(response)

        if text == self.ALLOW_MARKER:
            return GuardrailDecision(allowed=True)

        if text == self.BLOCK_MARKER:
            return GuardrailDecision(allowed=False)

        return GuardrailDecision(
            allowed=False,
            category="guardrail_block",
            message="Request blocked by NeMo Guardrails.",
        )

    def _load_rails(self) -> Any | None:
        if self._rails is not None:
            return self._rails
        if self._load_failed:
            return None

        try:
            from nemoguardrails import LLMRails, RailsConfig

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_root = Path(temp_dir)
                config_template = (self.CONFIG_ROOT / "config.yml").read_text(encoding="utf-8")
                rendered_config = self._render_config(config_template)
                (temp_root / "config.yml").write_text(rendered_config, encoding="utf-8")
                shutil.copy2(self.CONFIG_ROOT / "rails.co", temp_root / "rails.co")

                config = RailsConfig.from_path(str(temp_root))
                self._rails = LLMRails(config)
                return self._rails
        except Exception:
            self._load_failed = True
            return None

    def _render_config(self, template: str) -> str:
        api_key = GROQ_API_KEY or OPENAI_API_KEY
        base_url_line = ""
        if GROQ_API_KEY:
            base_url_line = f"      base_url: {json.dumps('https://api.groq.com/openai/v1')}\n"

        return (
            template.replace("__MODEL_JSON__", json.dumps(LLM_MODEL))
            .replace("__API_KEY_JSON__", json.dumps(api_key))
            .replace("__BASE_URL_LINE__", base_url_line)
        )

    def _build_input_message(
        self,
        query: str,
        payload: str | None,
        capability_hint: str | None,
        profile_url: str | None,
    ) -> str:
        payload_preview = (payload or "").strip()
        if len(payload_preview) > 1200:
            payload_preview = payload_preview[:1200] + "\n...[truncated]"

        return (
            "Capability hint: " + (capability_hint or "") + "\n"
            + "Profile URL: " + (profile_url or "") + "\n"
            + "User query:\n"
            + (query or "")
            + "\n\nPayload preview:\n"
            + payload_preview
        )

    def _extract_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response.strip()

        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content.strip()

        if isinstance(response, dict):
            maybe_content = response.get("content")
            if isinstance(maybe_content, str):
                return maybe_content.strip()

            messages = response.get("messages")
            if isinstance(messages, list) and messages:
                last_message = messages[-1]
                if isinstance(last_message, dict):
                    message_content = last_message.get("content")
                    if isinstance(message_content, str):
                        return message_content.strip()

        return str(response).strip()
