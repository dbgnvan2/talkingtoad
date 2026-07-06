"""FAQPage schema generator (feature C).

Spec: docs/pending/OLD/2026-07-04_faq-schema-generator.md
Generate-and-advise: builds FAQPage JSON-LD from answers present in the HTML,
never fabricates, never writes to WordPress.
"""

import json
import types

import pytest

from api.services.faq_schema_generator import generate_faqpage_schema


def _blk(q, a):
    a = a or ""
    return {"question": q, "answer": a, "answer_char_count": len(a), "container": "details"}


# ── C1: build a valid FAQPage from usable blocks ──────────────────────────────
def test_build_faqpage_from_blocks():
    blocks = [
        _blk("Who is counselling for?", "Counselling can help anyone facing life's challenges here."),
        _blk("How do I get started?", "Complete the intake form and we'll match you with a therapist."),
    ]
    out = generate_faqpage_schema(blocks)
    assert out["refused"] is False
    assert out["question_count"] == 2
    doc = json.loads(out["jsonld"])
    assert doc["@context"] == "https://schema.org"
    assert doc["@type"] == "FAQPage"
    assert len(doc["mainEntity"]) == 2
    q0 = doc["mainEntity"][0]
    assert q0["@type"] == "Question"
    assert q0["acceptedAnswer"]["@type"] == "Answer"
    assert "counselling can help" in q0["acceptedAnswer"]["text"].lower()


def test_build_faqpage_refuses_when_insufficient():
    """Fewer than 2 usable pairs -> refuse, jsonld None (never a shell)."""
    out = generate_faqpage_schema([_blk("Only one?", "A single answer present in the html here.")])
    assert out["refused"] is True
    assert out["jsonld"] is None


def test_build_faqpage_refuses_on_empty():
    out = generate_faqpage_schema([])
    assert out["refused"] is True and out["jsonld"] is None
    assert "no faq" in out["reason"].lower()


# ── C2: exclude JS-only answers; refuse if that leaves < 2 ────────────────────
def test_generator_excludes_js_only_answers():
    blocks = [
        _blk("Who is counselling for?", "Counselling can help anyone facing life's challenges here."),
        _blk("How much does it cost?", ""),          # JS-only: no answer in HTML
        _blk("Is it covered?", "Yes"),               # too short (<40)
    ]
    out = generate_faqpage_schema(blocks)
    assert out["refused"] is True   # only 1 usable -> refuse
    assert out["question_count"] == 1


def test_generator_refuses_when_answers_not_in_html():
    blocks = [_blk("Q one?", ""), _blk("Q two?", ""), _blk("Q three?", "")]
    out = generate_faqpage_schema(blocks)
    assert out["refused"] is True
    assert "javascript" in out["reason"].lower() or "html" in out["reason"].lower()


# ── C3: sanitisation (P14 adversarial) ────────────────────────────────────────
def test_faqpage_output_is_sanitized_and_valid():
    blocks = [
        _blk("What about safety?", "We are safe <script>alert('xss')</script> and secure for everyone."),
        _blk("How do I get started?", "Complete the intake form and we'll match you promptly today."),
    ]
    out = generate_faqpage_schema(blocks)
    assert "<script>" not in out["jsonld"]
    doc = json.loads(out["jsonld"])   # round-trips
    assert "<script>" not in doc["mainEntity"][0]["acceptedAnswer"]["text"]
    assert "alert" in doc["mainEntity"][0]["acceptedAnswer"]["text"]  # text content kept, tag stripped


# ── C4: endpoint contract ─────────────────────────────────────────────────────
_FAQ_HTML_OK = """
  <details><summary>Who is counselling for?</summary><p>Counselling can help anyone facing life's difficulties, no referral needed.</p></details>
  <details><summary>How do I get started?</summary><p>The first step is completing the intake form so we can match you well.</p></details>"""

_FAQ_HTML_JS_ONLY = """
  <details><summary>Who is counselling for?</summary></details>
  <details><summary>How do I get started?</summary></details>
  <details><summary>Is it covered by insurance?</summary></details>"""


def _fake_fetch(html):
    async def _f(url, client, *a, **kw):
        return types.SimpleNamespace(status_code=200, html=html, final_url=url)
    return _f


async def _seed_page(test_store, monkeypatch):
    async def fake_page(job_id, page_url):
        return types.SimpleNamespace(url=page_url), {}
    monkeypatch.setattr(test_store, "get_page_issues_by_url", fake_page)


@pytest.mark.asyncio
async def test_faq_schema_endpoint_response_schema(api_client, auth_headers, test_store, monkeypatch):
    await _seed_page(test_store, monkeypatch)
    monkeypatch.setattr("api.crawler.fetcher.fetch_page", _fake_fetch(_FAQ_HTML_OK))
    r = await api_client.post("/api/ai/faq-schema", headers=auth_headers,
                              json={"job_id": "j1", "page_url": "https://wp.example/counselling/"})
    assert r.status_code == 200
    data = r.json()
    assert set(["jsonld", "question_count", "refused", "reason"]).issubset(data)
    assert data["refused"] is False
    assert data["question_count"] == 2
    assert json.loads(data["jsonld"])["@type"] == "FAQPage"


@pytest.mark.asyncio
async def test_faq_schema_endpoint_refuses_js_only(api_client, auth_headers, test_store, monkeypatch):
    await _seed_page(test_store, monkeypatch)
    monkeypatch.setattr("api.crawler.fetcher.fetch_page", _fake_fetch(_FAQ_HTML_JS_ONLY))
    r = await api_client.post("/api/ai/faq-schema", headers=auth_headers,
                              json={"job_id": "j1", "page_url": "https://wp.example/x/"})
    data = r.json()
    assert data["refused"] is True
    assert data["jsonld"] is None
    assert data["reason"]


@pytest.mark.asyncio
async def test_faq_schema_endpoint_page_not_found(api_client, auth_headers, test_store, monkeypatch):
    async def none_page(job_id, page_url):
        return None, {}
    monkeypatch.setattr(test_store, "get_page_issues_by_url", none_page)
    r = await api_client.post("/api/ai/faq-schema", headers=auth_headers,
                              json={"job_id": "nope", "page_url": "https://wp.example/missing/"})
    assert "error" in r.json()
