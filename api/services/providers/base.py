"""Provider driver contract (v2.6 M2.1 / Cycle Z).

Every concrete driver under ``api/services/providers/`` implements this
Protocol. The AIRouter selects a driver based on which API key is
available and calls one of the two methods below; the driver is
responsible for translating the unified call into a provider-specific
HTTP request and the provider-specific response back into
:class:`AIResponse`.

Why a Protocol (not an ABC):
    Drivers are duck-typed in the AIRouter. Protocol gives us static
    type checking without forcing import-time inheritance. New drivers
    don't need to import base — they just satisfy the shape.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Imports here keep base.py self-contained without circular deps —
# AIResponse and ModelConfig live in ai_router.py but the Protocol
# below only needs them as type annotations.
from api.services.ai_router import AIResponse, ModelConfig


@runtime_checkable
class ProviderDriver(Protocol):
    """Uniform interface every provider driver implements.

    Drivers MUST:
        - Be stateless. The same driver instance is reused across calls.
        - Accept the api_key explicitly per call (no caching).
        - Translate provider-specific token-count fields into the unified
          ``input_token_count`` / ``output_token_count`` on AIResponse.
        - Raise :class:`api.services.ai_router.ProviderAPIError` on any
          hard HTTP failure (4xx, 5xx, network error).
        - Set ``AIResponse.truncated = True`` when the response hit the
          provider's max-tokens limit; do NOT raise for this soft case.

    Drivers MUST NOT:
        - Cache the api_key on the driver instance.
        - Log raw prompt or response text. (Sanitised metadata only.)
        - Import or wrap a provider's official SDK — use httpx.AsyncClient
          directly. (Enforced by ``test_no_provider_sdk_imports``.)
    """

    provider_id: str  # short string identifier, e.g. "openai", "gemini"

    async def call_text(
        self,
        *,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        model_config: ModelConfig,
    ) -> AIResponse:
        ...

    async def call_vision(
        self,
        *,
        api_key: str,
        system_prompt: str,
        image_bytes: bytes,
        image_mime: str,
        model_config: ModelConfig,
    ) -> AIResponse:
        ...
