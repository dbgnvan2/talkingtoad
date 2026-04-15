"""
AI Analyzer service for TalkingToad (spec §4).

Detects semantic issues and provides remediation suggestions using LLMs (Gemini/OpenAI).
"""

import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

# Ensure environment is loaded
load_dotenv()

logger = logging.getLogger(__name__)

PROMPT_LIBRARY = {
    "title_meta_optimize": (
        "Rewrite this title tag and meta description to be more 'quotable' "
        "for an AI summary while staying under character limits (60 for title, 160 for meta).\n"
        "Title: {title}\n"
        "Meta: {meta_description}\n"
        "Content Summary: {content_summary}"
    ),
    "semantic_alignment": (
        "Compare this page's H1 with its body content. Are there conflicting "
        "semantic signals that would cause an LLM hallucination?\n"
        "H1: {h1}\n"
        "Body Text Snippet: {body_snippet}"
    )
}


async def analyze_with_ai(prompt_key: str, context: dict[str, Any]) -> str:
    """Send a request to the configured LLM using a prompt from the library."""
    # RE-FETCH every time to ensure we aren't stuck with None if imported early
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not gemini_key and not openai_key:
        # One more attempt at loading if they are missing
        load_dotenv()
        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

    if prompt_key not in PROMPT_LIBRARY:
        raise ValueError(f"Unknown prompt key: {prompt_key}")

    prompt_template = PROMPT_LIBRARY[prompt_key]
    prompt = prompt_template.format(**context)

    if openai_key:
        return await _call_openai(prompt, openai_key)
    elif gemini_key:
        return await _call_gemini(prompt, gemini_key)
    else:
        logger.warning("ai_analysis_skipped_no_key")
        return "AI analysis skipped: No API key configured (GEMINI_API_KEY or OPENAI_API_KEY)."


async def _call_gemini(prompt: str, api_key: str) -> str:
    """Call Google Gemini API."""
    # Using v1 stable endpoint
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, timeout=20.0)
            if res.status_code != 200:
                return f"Error calling Gemini: HTTP {res.status_code} - {res.text}"
            data = res.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.error("gemini_call_failed", extra={"error": str(exc)})
        return f"Error calling Gemini: {str(exc)}"


async def _call_openai(prompt: str, api_key: str) -> str:
    """Call OpenAI API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=headers, json=payload, timeout=20.0)
            if res.status_code != 200:
                return f"Error calling OpenAI: HTTP {res.status_code} - {res.text}"
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error("openai_call_failed", extra={"error": str(exc)})
        return f"Error calling OpenAI: {str(exc)}"
