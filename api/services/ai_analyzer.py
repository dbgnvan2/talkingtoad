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
    ),
    "page_advisor": (
        "You are an SEO consultant for nonprofit organizations. Analyze this page and provide specific, "
        "actionable recommendations with ACTUAL suggested content (not just 'improve this').\n\n"
        "Current Page Data:\n"
        "URL: {url}\n"
        "Title: {title}\n"
        "Meta Description: {meta_description}\n"
        "H1 Tags: {h1_tags}\n"
        "H2 Tags: {h2_tags}\n"
        "Issues Found: {issues}\n\n"
        "For each element that needs improvement, provide:\n"
        "1. Current Value\n"
        "2. Suggested Value (actual content)\n"
        "3. Why (brief explanation)\n\n"
        "Focus ONLY on: Title, Meta Description, H1, and H2 headings. "
        "Respond in JSON format with this structure:\n"
        "{{\n"
        "  \"title\": {{\"current\": \"...\", \"suggested\": \"...\", \"why\": \"...\"}},\n"
        "  \"meta_description\": {{\"current\": \"...\", \"suggested\": \"...\", \"why\": \"...\"}},\n"
        "  \"h1\": {{\"current\": \"...\", \"suggested\": \"...\", \"why\": \"...\"}},\n"
        "  \"h2\": {{\"current\": [...], \"suggested\": [...], \"why\": \"...\"}}\n"
        "}}"
    ),
    "site_advisor": (
        "You are an SEO consultant for nonprofit organizations. Analyze these site-wide patterns and provide "
        "high-level recommendations.\n\n"
        "Site Summary:\n"
        "Total Pages: {total_pages}\n"
        "Common Issues: {common_issues}\n"
        "Sample Pages: {sample_pages}\n\n"
        "Provide top 5 site-wide recommendations in JSON format:\n"
        "[\n"
        "  {{\"priority\": \"high|medium|low\", \"category\": \"...\", \"recommendation\": \"...\", \"impact\": \"...\"}}\n"
        "]"
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


async def analyze_image_with_ai(image_url: str, current_alt: str = "") -> dict[str, Any]:
    """
    Analyze an image using AI vision models.

    Returns:
        {
            "description": "AI-generated description of the image",
            "suggested_alt": "Suggested alt text",
            "accuracy_score": 0-100,
            "quality_score": 0-100,
            "issues": ["list of issues found"],
            "semantic_score": 0-100
        }
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not gemini_key and not openai_key:
        load_dotenv()
        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

    if not gemini_key and not openai_key:
        logger.warning("image_ai_analysis_skipped_no_key")
        return {
            "description": "AI analysis unavailable: No API key configured",
            "suggested_alt": current_alt,
            "accuracy_score": 0,
            "quality_score": 0,
            "issues": ["NO_API_KEY"],
            "semantic_score": 0
        }

    prompt = (
        f"Analyze this image for SEO and accessibility.\n\n"
        f"Current alt text: '{current_alt or '(none)'}'\n\n"
        f"Provide:\n"
        f"1. A detailed description of what you see\n"
        f"2. Whether the current alt text accurately describes the image (score 0-100)\n"
        f"3. The quality of the current alt text for SEO (score 0-100)\n"
        f"4. A suggested improved alt text (max 125 characters)\n"
        f"5. Any issues found (e.g., 'alt text too generic', 'alt text missing key details', 'decorative image has alt text')\n\n"
        f"IMPORTANT: Respond with ONLY valid JSON, no markdown formatting, no code blocks.\n"
        f"Format:\n"
        f"{{\n"
        f'  "description": "detailed description",\n'
        f'  "accuracy_score": 0-100,\n'
        f'  "quality_score": 0-100,\n'
        f'  "suggested_alt": "improved alt text",\n'
        f'  "issues": ["issue1", "issue2"]\n'
        f"}}"
    )

    try:
        if openai_key:
            result = await _call_openai_vision(image_url, prompt, openai_key)
        elif gemini_key:
            result = await _call_gemini_vision(image_url, prompt, gemini_key)
        else:
            return {
                "description": "No vision API available",
                "suggested_alt": current_alt,
                "accuracy_score": 0,
                "quality_score": 0,
                "issues": ["NO_VISION_API"],
                "semantic_score": 0
            }

        # Parse JSON response - strip markdown code blocks if present
        import json
        import re

        # Remove markdown code blocks (```json ... ``` or ``` ... ```)
        cleaned_result = re.sub(r'```(?:json)?\s*\n?(.*?)\n?```', r'\1', result, flags=re.DOTALL)
        cleaned_result = cleaned_result.strip()

        try:
            data = json.loads(cleaned_result)
            # Calculate semantic score (average of accuracy and quality)
            semantic_score = (data.get("accuracy_score", 0) + data.get("quality_score", 0)) // 2
            data["semantic_score"] = semantic_score
            return data
        except json.JSONDecodeError as e:
            logger.error("json_parse_error", extra={"error": str(e), "result": result})
            # Fallback if AI doesn't return valid JSON
            return {
                "description": result,
                "suggested_alt": current_alt,
                "accuracy_score": 50,
                "quality_score": 50,
                "issues": ["AI_RESPONSE_PARSE_ERROR"],
                "semantic_score": 50
            }
    except Exception as exc:
        logger.error("image_ai_analysis_failed", extra={"error": str(exc)})
        return {
            "description": f"Error: {str(exc)}",
            "suggested_alt": current_alt,
            "accuracy_score": 0,
            "quality_score": 0,
            "issues": ["AI_ANALYSIS_ERROR"],
            "semantic_score": 0
        }


async def _call_gemini_vision(image_url: str, prompt: str, api_key: str) -> str:
    """Call Google Gemini Vision API."""
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": await _fetch_image_base64(image_url)
                    }
                }
            ]
        }]
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, timeout=30.0)
            if res.status_code != 200:
                return f"Error calling Gemini Vision: HTTP {res.status_code} - {res.text}"
            data = res.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.error("gemini_vision_call_failed", extra={"error": str(exc)})
        return f"Error calling Gemini Vision: {str(exc)}"


async def _call_openai_vision(image_url: str, prompt: str, api_key: str) -> str:
    """Call OpenAI Vision API (GPT-4V)."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }],
        "max_tokens": 500
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=headers, json=payload, timeout=30.0)
            if res.status_code != 200:
                return f"Error calling OpenAI Vision: HTTP {res.status_code} - {res.text}"
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error("openai_vision_call_failed", extra={"error": str(exc)})
        return f"Error calling OpenAI Vision: {str(exc)}"


async def _fetch_image_base64(image_url: str) -> str:
    """Fetch an image and convert to base64 for Gemini Vision."""
    import base64
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(image_url, timeout=10.0)
            if res.status_code == 200:
                return base64.b64encode(res.content).decode('utf-8')
            else:
                raise ValueError(f"Failed to fetch image: HTTP {res.status_code}")
    except Exception as exc:
        logger.error("image_fetch_failed", extra={"error": str(exc), "url": image_url})
        raise
