"""R7 — JS-render trio wired in (audit remediation, 2026-07-04).

Spec: docs/pending/2026-07-04_r7-js-render.md
The renderer itself needs Playwright; here we test the flag→issue mapping and the
graceful no-op when the render errored / Playwright is absent.
"""

from api.crawler.issue_checker import js_render_issues
from api.services.js_renderer import JSRenderResult


def test_all_flags_emit_three_codes():
    r = JSRenderResult(url="https://e.com/p")
    r.js_rendered_content_differs = True
    r.content_cloaking_detected = True
    r.ua_content_differs = True
    r.added_token_ratio = 0.42
    r.topic_jaccard = 0.2
    codes = {i.code for i in js_render_issues(r)}
    assert codes == {"JS_RENDERED_CONTENT_DIFFERS", "CONTENT_CLOAKING_DETECTED", "UA_CONTENT_DIFFERS"}


def test_no_flags_no_issues():
    assert js_render_issues(JSRenderResult(url="https://e.com/p")) == []


def test_errored_render_emits_nothing():
    """Graceful skip: a failed/absent render (error set — e.g. Playwright missing)
    must NOT be rendered as a finding (no false positives)."""
    r = JSRenderResult(url="https://e.com/p")
    r.error = "Playwright not installed"
    r.js_rendered_content_differs = True  # stale/garbage flag must be ignored when errored
    assert js_render_issues(r) == []


def test_only_cloaking_flag():
    r = JSRenderResult(url="https://e.com/p")
    r.content_cloaking_detected = True
    r.topic_jaccard = 0.1
    codes = [i.code for i in js_render_issues(r)]
    assert codes == ["CONTENT_CLOAKING_DETECTED"]
