"""OpenAI provider driver (v2.6 M2.1 / Cycle Z).

Wraps OpenAI's Chat Completions HTTP API. Uses ``httpx.AsyncClient``
directly — NO ``openai`` SDK import (enforced by
``test_no_provider_sdk_imports``).

Translates:
    - ``usage.prompt_tokens`` → ``AIResponse.input_token_count``
    - ``usage.completion_tokens`` → ``AIResponse.output_token_count``
    - ``choices[0].finish_reason == "length"`` → ``AIResponse.truncated = True``
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


_OPENAI_TEXT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
_OPENAI_VISION_ENDPOINT = "https://api.openai.com/v1/chat/completions"
_HTTP_TIMEOUT_SECONDS = 60.0


class OpenAIDriver:
    """Concrete :class:`ProviderDriver` for OpenAI."""

    provider_id = "openai"

    async def call_text(
        self,
        *,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        model_config: ModelConfig,
    ) -> AIResponse:
        payload: dict[str, Any] = {
            "model": model_config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": model_config.temperature,
        }
        if model_config.max_tokens is not None:
            payload["max_tokens"] = model_config.max_tokens

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
        # OpenAI vision uses data-URLs embedded in the content array.
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{image_mime};base64,{b64}"
        payload: dict[str, Any] = {
            "model": model_config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": model_config.temperature,
        }
        if model_config.max_tokens is not None:
            payload["max_tokens"] = model_config.max_tokens

        return await self._post_and_parse(api_key, payload, model_config.model)

    async def _post_and_parse(
        self, api_key: str, payload: dict, model: str
    ) -> AIResponse:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    _OPENAI_TEXT_ENDPOINT, headers=headers, json=payload
                )
        except httpx.HTTPError as exc:
            # Network / timeout / DNS — surfaces as a hard failure to the
            # caller. The router's outer try/except will record this in
            # log_usage with success=False before re-raising.
            raise ProviderAPIError(
                f"openai HTTP transport error: {exc!s}"
            ) from exc

        if resp.status_code != 200:
            # Provider returned an error response. Don't surface the body
            # raw to the caller (could leak prompt fragments echoed back);
            # capture just the status + a truncated error string.
            body_excerpt = resp.text[:200] if resp.text else ""
            raise ProviderAPIError(
                f"openai HTTP {resp.status_code}: {body_excerpt}"
            )

        data = resp.json()

        # Defensive extraction — provider response shape is well-known but
        # any of these keys can be missing if the provider rolls out a
        # breaking change. Surface as ProviderAPIError rather than
        # KeyError so the caller's handling path is consistent.
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason", "")
            usage = data.get("usage", {})
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderAPIError(
                f"openai response shape unexpected: {exc!s}"
            ) from exc

        return AIResponse(
            content=content.strip() if isinstance(content, str) else "",
            provider_id=self.provider_id,
            model=model,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            cost_estimate_usd=0.0,  # TODO(M2.2): plug pricing table here.
            truncated=(finish_reason == "length"),
        )
