"""D4 — page blueprints: a drafting tool with a review gate.

Purpose: prove an unapproved draft can never reach a client, and that the
         grounding check catches BOTH fabrication shapes — the concrete-specific
         one and the one with no proper noun in it.
Spec:    docs/pending/2026-08-29_D4-page-blueprints.md
Tests:   this file

`test_d4_4a_only_approved_drafts_export` comes first (P10) — it is the safety
property. `test_d4_3b_non_specific_fabrication_is_caught` comes second: a
grounding check that only looks for unmatched names and dates sails straight past
an invented stance, and per P20 that is exactly the class an idealised gold set
never contains.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest

from api.models.job import CrawlJob
from api.services.blueprints import (
    Blueprint,
    BlueprintError,
    approve,
    approved_only,
    check_grounding,
    to_dict,
    verbatim_claims,
)
from api.services.report_generator import generate_pdf_report

PAGE_TEXT = (
    "Living Systems is a Canadian nonprofit offering Bowen family systems "
    "counselling and training in North Vancouver. We work with individuals, "
    "couples and families, and offer a sliding fee plan for those who need it. "
    "Our counsellors and faculty teach differentiation, triangles and "
    "multigenerational patterns."
)
URL = "https://livingsystems.ca/counselling"


def _draft(**kw) -> Blueprint:
    base = dict(
        url=URL,
        proposed_title="Bowen Family Systems Counselling | Living Systems",
        proposed_meta_description=(
            "Explore Bowen family systems counselling for individuals, couples "
            "and families, with a sliding fee plan."),
        proposed_h1="Family Systems Counselling at Living Systems",
        proposed_lead=(
            "Living Systems offers Bowen family systems counselling to "
            "individuals, couples and families in North Vancouver. Our "
            "counsellors work with differentiation, triangles and "
            "multigenerational patterns, and a sliding fee plan is available."),
    )
    base.update(kw)
    return Blueprint(**base)


def _summary() -> dict:
    return {"health_score": 90, "agent_health_score": 90, "pages_crawled": 1,
            "total_issues": 0, "by_severity": {}, "by_category": {}}


def _pdf_text(pdf_bytes: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return " ".join((p.extract_text() or "") for p in reader.pages).replace("\n", " ")


def _job(blueprints=None) -> CrawlJob:
    return CrawlJob(job_id="j", target_url="https://livingsystems.ca",
                    status="complete", started_at=datetime.now(timezone.utc),
                    blueprints=blueprints)


# ── D4.4 — the gate (written first, P10) ────────────────────────────────────


class TestTheGate:
    @pytest.mark.asyncio
    async def test_d4_4a_only_approved_drafts_export(self):
        """The safety property. A draft nobody approved must never reach a
        client artifact, even with the include flag on."""
        drafts = [to_dict(_draft()), to_dict(_draft(url=URL + "-2", status="rejected"))]
        pdf = await generate_pdf_report(_job(drafts), [], _summary(),
                                        include_blueprints=True)
        text = _pdf_text(pdf)
        assert "Proposed Page Copy" not in text

    @pytest.mark.asyncio
    async def test_d4_4a_approved_draft_still_needs_the_opt_in(self):
        """Two independent gates: approval AND the caller asking for it. The
        default is off, because AI-drafted copy changes what the document is."""
        approved = to_dict(approve(_draft(), by="Dave"))
        pdf = await generate_pdf_report(_job([approved]), [], _summary())
        assert "Proposed Page Copy" not in _pdf_text(pdf)

    @pytest.mark.asyncio
    async def test_d4_4b_approved_and_opted_in_renders_as_a_proposal(self):
        approved = to_dict(approve(_draft(), by="Dave"))
        text = _pdf_text(await generate_pdf_report(
            _job([approved]), [], _summary(), include_blueprints=True))
        assert "Proposed Page Copy" in text
        assert "DRAFTS" in text
        assert "crisis-language" in text, "the review requirement must be stated"
        assert "Reviewed and approved by Dave" in text

    def test_d4_4a_filter_is_explicit_about_status(self):
        drafts = [
            {"url": "a", "status": "draft"},
            {"url": "b", "status": "approved"},
            {"url": "c", "status": "rejected"},
            {"url": "d"},  # no status at all
        ]
        assert [d["url"] for d in approved_only(drafts)] == ["b"]

    def test_d4_4c_approval_records_who_and_when(self):
        draft = approve(_draft(), by="Dave Galloway")
        assert draft.is_approved
        assert draft.approved_by == "Dave Galloway"
        assert draft.approved_at

    def test_d4_4d_blueprints_never_write_to_wordpress(self):
        """This produces text for a human to paste. The WordPress-safety
        constraints are untouched."""
        import inspect

        from api.services import blueprints

        src = inspect.getsource(blueprints)
        for forbidden in ("WPClient", "wp_client", ".post(", ".patch(", ".put("):
            assert forbidden not in src, f"blueprints must not reference {forbidden}"


# ── D4.3 — grounding ────────────────────────────────────────────────────────


class TestGrounding:
    def test_d4_3b_non_specific_fabrication_is_caught(self):
        """The hard case (P20). "clinically proven" carries no proper noun and no
        number, so a check that only hunts unmatched names sails past it."""
        draft = _draft(proposed_lead=(
            "Living Systems offers clinically proven counselling for individuals, "
            "couples and families in North Vancouver, working with "
            "differentiation and multigenerational patterns."))
        grounding = check_grounding(draft, PAGE_TEXT)
        assert grounding.status == "unverified"
        assert any("clinically proven" in a for a in grounding.unsupported_assertions)

    def test_d4_3a_invented_organisation_is_caught(self):
        draft = _draft(proposed_lead=(
            "Living Systems is accredited by the Canadian Psychological "
            "Association and serves individuals and families."))
        grounding = check_grounding(draft, PAGE_TEXT)
        assert grounding.status == "unverified"
        assert any("Canadian Psychological Association" in c
                   for c in grounding.unsupported_claims)

    def test_d4_3a_invented_location_is_caught(self):
        draft = _draft(proposed_title="Counselling in Toronto | Living Systems")
        grounding = check_grounding(draft, PAGE_TEXT)
        assert grounding.status == "unverified"
        assert any("Toronto" in c for c in grounding.unsupported_claims)

    def test_d4_3c_faithful_draft_passes(self):
        grounding = check_grounding(_draft(), PAGE_TEXT)
        assert grounding.is_grounded, (
            f"a faithful draft was rejected: {grounding.unsupported_claims} "
            f"{grounding.unsupported_assertions}"
        )

    def test_d4_3a_verbatim_floor_covers_every_field_not_just_the_lead(self):
        """A fabrication in the title is as published as one in the lead."""
        draft = _draft(proposed_h1="Counselling in Calgary")
        assert check_grounding(draft, PAGE_TEXT).status == "unverified"

    def test_d4_3a_paraphrase_alone_does_not_fail_the_verbatim_floor(self):
        """Rewording is the point of a draft. Only specific claims are checked
        verbatim; wording is checked by overlap."""
        draft = _draft(proposed_lead=(
            "Bowen family systems counselling at Living Systems supports "
            "individuals, couples and families in North Vancouver, and a "
            "sliding fee plan is available to those who need it."))
        assert check_grounding(draft, PAGE_TEXT).is_grounded

    def test_d4_3a_empty_source_is_unverified_not_grounded(self):
        """P2: no source text means we cannot verify, which is not the same as
        verified-clean."""
        grounding = check_grounding(_draft(), "")
        assert grounding.status == "unverified"

    def test_d4_3a_claim_extraction_finds_names_numbers_and_dates(self):
        claims = verbatim_claims(
            "The charity has served North Vancouver since 1974, with 12 counsellors.")
        joined = " ".join(claims)
        assert "North Vancouver" in joined
        assert "1974" in joined
        assert "12" in joined

    def test_d4_3a_sentence_initial_word_is_dropped_by_design(self):
        """A capitalised word at a sentence start is grammar, not a name.

        The cost is real and accepted: "Living Systems offers…" yields "Systems",
        not "Living Systems". The benefit is that "Explore Bowen family systems…"
        no longer marks a faithful draft unverified — and a check that flags
        everything is a gate the operator learns to click through.
        """
        assert verbatim_claims("Explore Bowen family systems counselling.") == ["Bowen"]
        # Mid-sentence, the full name survives.
        assert "Living Systems" in " ".join(
            verbatim_claims("Counselling from Living Systems in Vancouver."))

    def test_d4_3a_trimming_does_not_let_a_fabrication_through(self):
        """The trade-off must not cost recall on the case that matters: a
        sentence-initial invented organisation is still caught by what remains."""
        draft = _draft(proposed_lead=(
            "Toronto Counselling Centre offers support to individuals and families."))
        grounding = check_grounding(draft, PAGE_TEXT)
        assert grounding.status == "unverified"
        assert any("Counselling Centre" in c for c in grounding.unsupported_claims)

    def test_d4_3a_unsupported_claims_are_listed_not_discarded(self):
        """An unverified draft is SHOWN with its claims — the operator needs to
        see what the model tried to assert."""
        draft = _draft(proposed_h1="Counselling in Calgary")
        grounding = check_grounding(draft, PAGE_TEXT)
        assert grounding.unsupported_claims, "the claims must be reported"


# ── D4.1/D4.2 — generation contract ─────────────────────────────────────────


class TestGeneration:
    @pytest.mark.asyncio
    async def test_d4_1a_routes_through_ai_router(self):
        import inspect

        from api.services import blueprints

        src = inspect.getsource(blueprints)
        assert "ai_router.call_text" in src
        for provider in ("api.openai.com", "generativelanguage", "httpx.post"):
            assert provider not in src, "no direct provider HTTP (Cycle Z)"

    @pytest.mark.asyncio
    async def test_d4_3e_provider_error_is_not_content(self, monkeypatch):
        """P14: a failure raises. Returning the message as draft text would put
        "the model was unavailable" into a client report as page copy."""
        from api.services import blueprints as mod

        class _Boom:
            async def call_text(self, **_kw):
                raise RuntimeError("provider exploded")

        import api.services.ai_router as ai_router_mod

        monkeypatch.setattr(ai_router_mod, "ai_router", _Boom())
        with pytest.raises(BlueprintError) as excinfo:
            await mod.generate_blueprint(URL, PAGE_TEXT)
        assert "unavailable" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_d4_2b_empty_page_text_is_rejected(self):
        from api.services.blueprints import generate_blueprint

        with pytest.raises(BlueprintError):
            await generate_blueprint(URL, "   ")

    @pytest.mark.asyncio
    async def test_d4_3e_unparseable_model_output_is_an_error(self, monkeypatch):
        import api.services.ai_router as ai_router_mod
        from api.services import blueprints as mod

        class _Garbage:
            async def call_text(self, **_kw):
                class R:
                    content = "I'm afraid I can't help with that."
                    truncated = False
                return R()

        monkeypatch.setattr(ai_router_mod, "ai_router", _Garbage())
        with pytest.raises(BlueprintError):
            await mod.generate_blueprint(URL, PAGE_TEXT)

    @pytest.mark.asyncio
    async def test_d4_2a_generated_draft_is_grounded_and_within_bounds(self, monkeypatch):
        import json

        import api.services.ai_router as ai_router_mod
        from api.config import load_config
        from api.services import blueprints as mod

        payload = {
            "title": "Bowen Family Systems Counselling | Living Systems",
            "meta_description": ("Explore Bowen family systems counselling for "
                                 "individuals, couples and families, with a sliding "
                                 "fee plan available."),
            "h1": "Family Systems Counselling at Living Systems",
            "lead": ("Living Systems offers Bowen family systems counselling to "
                     "individuals, couples and families in North Vancouver, working "
                     "with differentiation and multigenerational patterns."),
            "rationale": "Adds a missing description and an answer-first opening.",
        }

        class _Good:
            async def call_text(self, **_kw):
                class R:
                    content = json.dumps(payload)
                    truncated = False
                return R()

        monkeypatch.setattr(ai_router_mod, "ai_router", _Good())
        draft = await mod.generate_blueprint(URL, PAGE_TEXT, findings=["META_DESC_MISSING"])

        cfg = load_config("blueprints", required_keys=("title_max",))
        assert len(draft.proposed_title) <= cfg["title_max"]
        assert draft.status == "draft", "generation never produces an approved draft"
        assert draft.grounding.is_grounded
        assert draft.source_findings == ["META_DESC_MISSING"]

    @pytest.mark.asyncio
    async def test_d4_2a_generation_never_returns_approved(self, monkeypatch):
        """Structural: there is no path from generate to approved."""
        import inspect

        from api.services import blueprints as mod

        src = inspect.getsource(mod.generate_blueprint)
        assert "approved" not in src


# ── D4.4 — the endpoints (P25) ──────────────────────────────────────────────


class TestEndpoints:
    @pytest.mark.asyncio
    async def test_d4_4_unknown_job_is_404(self, api_client, auth_headers):
        resp = await api_client.post(
            "/api/ai/blueprints/no-such-job?url=https://x/", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_d4_4_unverified_draft_cannot_be_approved(
        self, api_client, auth_headers, test_store
    ):
        """The gate the operator meets: an unverified draft is visible but not
        approvable until a human has looked at the listed claims."""
        job_id = "job-bp"
        unverified = to_dict(_draft(proposed_h1="Counselling in Calgary"))
        unverified["grounding"]["status"] = "unverified"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://livingsystems.ca", status="complete",
            started_at=datetime.now(timezone.utc)))
        # `create_job` inserts a fixed column set; blueprints (like web_vitals and
        # wp_audit) are always set later via update_job. Seed the real way.
        await test_store.update_job(job_id, blueprints=[unverified])

        resp = await api_client.post(
            f"/api/ai/blueprints/{job_id}/approve?url={URL}&approved_by=Dave",
            headers=auth_headers)
        assert resp.status_code == 409
        assert "do not appear on the page" in resp.text

    @pytest.mark.asyncio
    async def test_d4_4_grounded_draft_can_be_approved_and_is_audited(
        self, api_client, auth_headers, test_store
    ):
        job_id = "job-bp-2"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://livingsystems.ca", status="complete",
            started_at=datetime.now(timezone.utc)))
        await test_store.update_job(job_id, blueprints=[to_dict(_draft())])

        resp = await api_client.post(
            f"/api/ai/blueprints/{job_id}/approve?url={URL}&approved_by=Dave",
            headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["approved_by"] == "Dave"
        assert body["approved_at"]

        job = await test_store.get_job(job_id)
        assert job.blueprints[0]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_d4_4_reject_keeps_it_out_of_exports(
        self, api_client, auth_headers, test_store
    ):
        job_id = "job-bp-3"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://livingsystems.ca", status="complete",
            started_at=datetime.now(timezone.utc)))
        await test_store.update_job(job_id, blueprints=[to_dict(_draft())])

        resp = await api_client.post(
            f"/api/ai/blueprints/{job_id}/reject?url={URL}", headers=auth_headers)
        assert resp.status_code == 200
        job = await test_store.get_job(job_id)
        assert approved_only(job.blueprints) == []
