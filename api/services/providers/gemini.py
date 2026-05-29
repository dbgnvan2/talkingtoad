"""Gemini provider driver (v2.6 M2.1 / Cycle Z).

Wraps Google Gemini's generateContent HTTP API. Uses ``httpx.AsyncClient``
directly — NO Google SDK import.

Translates:
    - ``usageMetadata.promptTokenCount`` → ``AIResponse.input_token_count``
    - ``usageMetadata.candidatesTokenCount`` → ``AIResponse.output_token_count``
    - ``candidates[0].finishReason == "MAX_TOKENS"`` → ``AIResponse.truncated = True``
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from api.services.ai_router import (
    AIResponse,
    ModelConfig,
    ProviderAPIError,
)

logger = logging.getLogger(__name__)


_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1/models"
_HTTP_TIMEOUT_SECONDS = 60.0


class GeminiDriver:
    """Concrete :class:`ProviderDriver` for Google Gemini."""

    provider_id = "gemini"

    async def call_text(
        self,
        *,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        model_config: ModelConfig,
    ) -> AIResponse:
        gen_config: dict[str, Any] = {"temperature": model_config.temperature}
        if model_config.max_tokens is not None:
            # Gemini uses camelCase
            gen_config["maxOutputTokens"] = model_config.max_tokens
        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": gen_config,
        }
        return await self._post_and_parse(api_key, payload, model_config.model)

    async def call_vision(
        self,
        *,
        api_key: str,
        system_prompt: str,
        image_bytes: bytes,
        image_mime: str,
        model_config: ModelConfig,
    ) -> AIResponse:
        # Gemini vision uses inline_data with base64-encoded bytes and a
        # mime_type. The system instruction goes in the same field as for
        # text calls.
        b64 = base64.b64encode(image_bytes).decode("ascii")
        gen_config: dict[str, Any] = {"temperature": model_config.temperature}
        if model_config.max_tokens is not None:
            gen_config["maxOutputTokens"] = model_config.max_tokens
        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": image_mime, "data": b64}}
                    ]
                }
            ],
            "generationConfig": gen_config,
        }
        return await self._post_and_parse(api_key, payload, model_config.model)

    async def _post_and_parse(
        self, api_key: str, payload: dict, model: str
    ) -> AIResponse:
        # API key goes in the URL for Gemini (yes really — quirky but
        # documented). We still set Content-Type so the request is parsed
        # as JSON by the provider.
        url = f"{_GEMINI_BASE}/{model}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    url, json=payload, headers={"Content-Type": "application/json"}
                )
        except httpx.HTTPError as exc:
            raise ProviderAPIError(
                f"gemini HTTP transport error: {exc!s}"
            ) from exc

        if resp.status_code != 200:
            body_excerpt = resp.text[:200] if resp.text else ""
            raise ProviderAPIError(
                f"gemini HTTP {resp.status_code}: {body_excerpt}"
            )

        data = resp.json()
        try:
            candidate = data["candidates"][0]
            parts = candidate["content"]["parts"]
            # Gemini can return multi-part responses; concatenate text parts.
            content = "".join(
                p.get("text", "") for p in parts if isinstance(p, dict)
            )
            finish_reason = candidate.get("finishReason", "")
            usage = data.get("usageMetadata", {})
            input_tokens = int(usage.get("promptTokenCount", 0))
            output_tokens = int(usage.get("candidatesTokenCount", 0))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderAPIError(
                f"gemini response shape unexpected: {exc!s}"
            ) from exc

        return AIResponse(
            content=content.strip(),
            provider_id=self.provider_id,
            model=model,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            cost_estimate_usd=0.0,  # TODO(M2.2): plug pricing table here.
            truncated=(finish_reason == "MAX_TOKENS"),
        )
