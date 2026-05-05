"""
Rewriter service (Tool B) — Apply rewrite prompt to content.

Takes page content + rewrite prompt, produces one rewrite.
No iteration, no scoring, no variants. Simple and straightforward.

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md
"""

import json
import logging
import os

import httpx
from dotenv import load_dotenv

from api.models.advisor import RewriterRequest, RewriterResult

load_dotenv()
load_dotenv(".env-ttoad", override=True)

logger = logging.getLogger(__name__)

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={key}"
_TIMEOUT = 60.0  # Rewrites can be slow


def _get_model() -> tuple[str, str]:
    """Resolve LLM model (prefers OpenAI, falls back to Gemini)."""
    if _OPENAI_API_KEY:
        return "openai", "gpt-4o"
    if _GEMINI_API_KEY:
        return "gemini", "gemini-2.0-flash"
    raise RuntimeError("No OPENAI_API_KEY or GEMINI_API_KEY configured")


def _call_openai_rewriter(prompt: str, content: str) -> str:
    """Call OpenAI API to rewrite content."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                _OPENAI_ENDPOINT,
                headers={"Authorization": f"Bearer {_OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Please rewrite the following content:\n\n{content}"},
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            data = response.json()
            rewrite = data["choices"][0]["message"]["content"]

            # Check if response was truncated
            stopped_by_limit = data["choices"][0].get("finish_reason") == "length"

            return rewrite, stopped_by_limit
    except Exception as e:
        logger.error(f"OpenAI rewriter call failed: {e}")
        raise


def _call_gemini_rewriter(prompt: str, content: str) -> str:
    """Call Gemini API to rewrite content."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                _GEMINI_ENDPOINT.format(model="gemini-2.0-flash", key=_GEMINI_API_KEY),
                json={
                    "system_instruction": {"parts": [{"text": prompt}]},
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": f"Please rewrite the following content:\n\n{content}"
                                }
                            ]
                        }
                    ],
                    "generationConfig": {"temperature": 0.2},
                },
            )
            response.raise_for_status()
            data = response.json()
            rewrite = data["candidates"][0]["content"]["parts"][0]["text"]

            # Check if response was truncated
            stopped_by_limit = data["candidates"][0].get("finishReason") == "MAX_TOKENS"

            return rewrite, stopped_by_limit
    except Exception as e:
        logger.error(f"Gemini rewriter call failed: {e}")
        raise


async def rewrite_page(request: RewriterRequest) -> RewriterResult:
    """
    Rewrite page content using LLM.

    Args:
        request: RewriterRequest with content and prompt

    Returns:
        RewriterResult with rewritten content
    """
    provider, model = _get_model()

    if provider == "openai":
        rewrite, stopped_by_limit = _call_openai_rewriter(request.prompt, request.content)
    else:
        rewrite, stopped_by_limit = _call_gemini_rewriter(request.prompt, request.content)

    return RewriterResult(
        rewrite=rewrite,
        stopped_by_limit=stopped_by_limit,
    )
