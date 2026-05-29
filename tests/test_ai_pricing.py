"""PriceLookup + AIRouter cost-wiring tests (v2.6 M2.2 / Cycle AA).

Per docs/pending/2026-05-29_m2_pricing_table.md (approved 2026-05-29).

Covers:
    - The three QA-spec evaluator tests: calculation accuracy, unknown
      model safety, AIRouter contract integration.
    - PRICING table immutability via MappingProxyType.
    - Architecture guard: no money math inside provider drivers.

No real HTTP — provider driver calls are mocked at the AIRouter
boundary, same pattern as test_ai_router.py.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api.services.ai_pricing import (
    LAST_REVIEWED,
    PRICING,
    PriceLookup,
    price_lookup,
)
from api.services.ai_router import (
    AIResponse,
    AIRouter,
    ModelConfig,
    SYSTEM_CONTEXT_ID,
    UnknownModelError,
)


# ---------------------------------------------------------------------------
# Helpers — match test_ai_router.py conventions
# ---------------------------------------------------------------------------

def _ai_response_from_driver(provider: str, model: str, *, in_tok: int, out_tok: int) -> AIResponse:
    """Build an AIResponse with `cost_estimate_usd=0.0` — the exact
    shape a driver emits before AIRouter post-processes the cost."""
    return AIResponse(
        content="ok",
        provider_id=provider,
        model=model,
        input_token_count=in_tok,
        output_token_count=out_tok,
        cost_estimate_usd=0.0,  # placeholder — AIRouter overwrites
        truncated=False,
    )


# ---------------------------------------------------------------------------
# Test 1 — Calculation accuracy
# ---------------------------------------------------------------------------

class TestCalculationAccuracy:
    """QA spec Test 1: 1,000 input + 1,000 output tokens for gpt-4o
    must equal the exact USD cost defined in the table.

    For gpt-4o (input $2.50/1M, output $10.00/1M):
        (1000 / 1_000_000) * 2.50 + (1000 / 1_000_000) * 10.00
        = 0.0025 + 0.01
        = 0.0125 USD
    """

    def test_gpt_4o_1k_in_1k_out_is_exactly_0_0125(self):
        cost = price_lookup.calculate_cost("openai", "gpt-4o", 1000, 1000)
        assert cost == Decimal("0.0125"), (
            f"Expected exactly Decimal('0.0125') for 1k/1k gpt-4o; got {cost!r}. "
            f"If the pricing table changed, update LAST_REVIEWED and this test."
        )
        # Type contract: must be Decimal, not float (precision-correct
        # accumulation across many calls depends on this).
        assert isinstance(cost, Decimal)

    def test_zero_tokens_zero_cost(self):
        cost = price_lookup.calculate_cost("openai", "gpt-4o", 0, 0)
        assert cost == Decimal("0")

    def test_negative_tokens_clamped_to_zero(self):
        """Defensive: a driver that fails to extract usage emits 0.
        Negative would be a parser bug — clamp to 0 rather than raise,
        since the upstream caller already handled the missing-usage
        case by emitting 0."""
        cost = price_lookup.calculate_cost("openai", "gpt-4o", -5, -5)
        assert cost == Decimal("0")

    def test_large_token_count_accuracy(self):
        """Sanity check: 1M tokens in / 1M out for gpt-4o = exactly
        $12.50 (2.50 + 10.00). Float math would round; Decimal stays
        exact."""
        cost = price_lookup.calculate_cost(
            "openai", "gpt-4o", 1_000_000, 1_000_000
        )
        assert cost == Decimal("12.50")

    @pytest.mark.parametrize("provider,model,expected", [
        # 1000 tokens each direction for a few entries; values pre-computed
        ("openai", "gpt-4o-mini",          Decimal("0.00075")),   # 0.15 + 0.60 per 1M scaled to 1k
        ("gemini", "gemini-2.0-flash",     Decimal("0.000375")),  # 0.075 + 0.30 per 1M
        ("anthropic", "claude-3-5-haiku",  Decimal("0.0048")),    # 0.80 + 4.00 per 1M
        ("deepseek", "deepseek-chat",      Decimal("0.00137")),   # 0.27 + 1.10 per 1M
    ])
    def test_per_provider_1k_in_1k_out(self, provider, model, expected):
        cost = price_lookup.calculate_cost(provider, model, 1000, 1000)
        assert cost == expected, (
            f"{provider}/{model}: expected {expected}, got {cost}. "
            f"Pricing table may have drifted."
        )


# ---------------------------------------------------------------------------
# Test 2 — Unknown model safety
# ---------------------------------------------------------------------------

class TestUnknownModelSafety:
    """QA spec Test 2: a model not in PRICING must raise UnknownModelError,
    NOT silently return Decimal('0'). Per the M2.2 'no null costs' rule —
    a silent zero would corrupt billing rollups."""

    def test_nonexistent_model_raises(self):
        with pytest.raises(UnknownModelError) as excinfo:
            price_lookup.calculate_cost("gemini", "gemini-9.9-beta", 1, 1)
        # Error message should help the developer fix it.
        msg = str(excinfo.value)
        assert "gemini-9.9-beta" in msg
        assert "ai_pricing.py" in msg

    def test_nonexistent_provider_raises(self):
        with pytest.raises(UnknownModelError):
            price_lookup.calculate_cost("xyz", "fake-model", 1, 1)

    def test_supports_vision_also_raises_on_unknown(self):
        """Cover the second public method too — same contract."""
        with pytest.raises(UnknownModelError):
            price_lookup.supports_vision("openai", "gpt-9999")


# ---------------------------------------------------------------------------
# Test 3 — AIRouter contract: cost_estimate_usd populated post-call
# ---------------------------------------------------------------------------

class TestAIRouterContractIntegration:
    """QA spec Test 3: AIRouter._call() must call PriceLookup and patch
    `cost_estimate_usd` on the returned AIResponse to the float of the
    table-computed cost. The driver's placeholder 0.0 must be
    overwritten."""

    @pytest.mark.asyncio
    async def test_router_overwrites_driver_cost_with_table_value(
        self, monkeypatch
    ):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        router = AIRouter()

        mock_driver = MagicMock()
        mock_driver.provider_id = "openai"

        # Driver emits the placeholder 0.0 cost per the Cycle Z contract.
        async def fake_call_text(**kwargs):
            return _ai_response_from_driver("openai", "gpt-4o", in_tok=1000, out_tok=1000)

        mock_driver.call_text = fake_call_text
        router._drivers = {"openai": mock_driver}

        with patch("api.services.ai_router._log_usage"):
            response = await router.call_text(
                customer_id=SYSTEM_CONTEXT_ID,
                system_prompt="sys",
                user_prompt="hello",
                model_config=ModelConfig(model="gpt-4o"),
            )

        # Per the table: 1000/1M × $2.50 + 1000/1M × $10.00 = $0.0125
        assert response.cost_estimate_usd == 0.0125, (
            f"Expected 0.0125 post-AIRouter; got {response.cost_estimate_usd!r}. "
            f"AIRouter may have failed to call PriceLookup or the dataclasses.replace "
            f"is missing."
        )
        # Driver-emitted fields are still intact (only cost was replaced).
        assert response.content == "ok"
        assert response.provider_id == "openai"
        assert response.input_token_count == 1000
        assert response.output_token_count == 1000

    @pytest.mark.asyncio
    async def test_unknown_model_propagates_unknown_model_error(
        self, monkeypatch
    ):
        """If the driver returns an AIResponse with a model not in
        PRICING, AIRouter's post-processing must surface the
        UnknownModelError to the caller (the calling router can then
        map to HTTP 500 with a clear message)."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        router = AIRouter()
        mock_driver = MagicMock()
        mock_driver.provider_id = "openai"

        async def fake_call_text(**kwargs):
            return _ai_response_from_driver(
                "openai", "gpt-9999-fake", in_tok=10, out_tok=10
            )

        mock_driver.call_text = fake_call_text
        router._drivers = {"openai": mock_driver}

        # Two log_usage calls expected:
        #   1. failure-path log when UnknownModelError raises
        #   2. (none — the success-path log never fires)
        # The error-path log is wired via the existing try/except wrapper.
        with patch("api.services.ai_router._log_usage"):
            with pytest.raises(UnknownModelError):
                await router.call_text(
                    customer_id=SYSTEM_CONTEXT_ID,
                    system_prompt="sys",
                    user_prompt="hello",
                    model_config=ModelConfig(model="gpt-9999-fake"),
                )

    @pytest.mark.asyncio
    async def test_log_usage_receives_real_cost_not_zero(
        self, monkeypatch
    ):
        """The success-path log_usage call must record the post-PriceLookup
        cost, not the driver's placeholder 0.0. Otherwise billing rollups
        from the audit log would always say $0."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        router = AIRouter()
        mock_driver = MagicMock()
        mock_driver.provider_id = "openai"

        async def fake_call_text(**kwargs):
            return _ai_response_from_driver(
                "openai", "gpt-4o", in_tok=1000, out_tok=1000
            )

        mock_driver.call_text = fake_call_text
        router._drivers = {"openai": mock_driver}

        captured = []

        def capture(metadata):
            captured.append(dict(metadata))

        with patch("api.services.ai_router._log_usage", side_effect=capture):
            await router.call_text(
                customer_id=SYSTEM_CONTEXT_ID,
                system_prompt="sys",
                user_prompt="hello",
                model_config=ModelConfig(model="gpt-4o"),
            )

        assert len(captured) == 1
        assert captured[0]["cost_estimate_usd"] == 0.0125, (
            f"log_usage saw cost={captured[0]['cost_estimate_usd']!r} — "
            f"post-processing must run BEFORE log_usage so billing data is correct."
        )


# ---------------------------------------------------------------------------
# Immutability test
# ---------------------------------------------------------------------------

class TestPricingImmutable:
    """PRICING is wrapped in MappingProxyType. Mutating it at runtime
    must raise TypeError. Without this guard a future bug could
    silently overwrite a price during a request, corrupting subsequent
    calls."""

    def test_assignment_raises(self):
        with pytest.raises(TypeError):
            PRICING[("foo", "bar")] = {}  # type: ignore[index]

    def test_delete_raises(self):
        with pytest.raises(TypeError):
            del PRICING[("openai", "gpt-4o")]  # type: ignore[arg-type]

    def test_pop_raises(self):
        with pytest.raises(AttributeError):
            # MappingProxyType doesn't expose .pop (read-only Mapping)
            PRICING.pop(("openai", "gpt-4o"))  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Architecture guard — no money math in provider drivers
# ---------------------------------------------------------------------------

class TestNoMoneyMathInDrivers:
    """Per the M2.2 spec's 'no hardcoded math in driver logic' rule:
    provider driver files must NOT compute money themselves. The
    rule's intent is that drivers only know about tokens; AIRouter
    plus PriceLookup handle the dollar arithmetic.

    Detection: scan driver files for arithmetic operators applied to
    decimal-looking literals, or any reference to the PriceLookup /
    ai_pricing modules. Drivers should also not import Decimal — if
    they need it, they're doing money math.
    """

    @pytest.fixture
    def driver_files(self) -> list[Path]:
        providers_dir = (
            Path(__file__).parent.parent / "api" / "services" / "providers"
        )
        return [p for p in providers_dir.rglob("*.py") if p.name != "__init__.py" and p.name != "base.py"]

    def test_no_decimal_import_in_drivers(self, driver_files):
        """If a driver imports Decimal, it's almost certainly doing
        money math. The legitimate use cases (token-rate parsing) all
        belong in ai_pricing.py, not the driver."""
        offenders = []
        for path in driver_files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), start=1):
                stripped = line.lstrip()
                if stripped.startswith("from decimal") or stripped.startswith("import decimal"):
                    offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        assert not offenders, (
            "Provider drivers should not import Decimal — money math belongs "
            "in api/services/ai_pricing.py:\n  " + "\n  ".join(offenders)
        )

    def test_no_pricing_import_in_drivers(self, driver_files):
        """Drivers must not import ai_pricing. If cost computation
        leaks into a driver, it's an abstraction-layer regression."""
        offenders = []
        for path in driver_files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if "ai_pricing" in line and "import" in line.lower():
                    offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        assert not offenders, (
            "Provider drivers must not import ai_pricing. AIRouter does the "
            "post-call cost calculation; drivers only know tokens:\n  "
            + "\n  ".join(offenders)
        )

    def test_no_dollar_per_million_literals_in_drivers(self, driver_files):
        """Sniff for the common shape of money math: arithmetic on
        small decimal literals like ``* 0.0025`` or ``/ 1000000``. A
        driver that needs these is doing pricing inline."""
        # The pattern: any of the per-1M-token rates from our table
        # appearing as a numeric literal in a driver file.
        suspicious_patterns = [
            r"\*\s*0\.0+\d",            # * 0.0025 etc.
            r"/\s*1[_,]?000[_,]?000",   # / 1_000_000
        ]
        offenders = []
        for path in driver_files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), start=1):
                # Skip comments
                if line.lstrip().startswith("#"):
                    continue
                for pat in suspicious_patterns:
                    if re.search(pat, line):
                        offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        assert not offenders, (
            "Provider drivers contain suspicious money-math patterns. "
            "Move pricing to ai_pricing.py:\n  " + "\n  ".join(offenders)
        )


# ---------------------------------------------------------------------------
# LAST_REVIEWED staleness signal
# ---------------------------------------------------------------------------

class TestLastReviewed:
    def test_last_reviewed_is_iso_date_string(self):
        """LAST_REVIEWED is used by future admin UI to surface
        pricing-table staleness. Lock the format so the UI side can
        rely on it."""
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", LAST_REVIEWED), (
            f"LAST_REVIEWED must be ISO YYYY-MM-DD; got {LAST_REVIEWED!r}"
        )

    def test_last_reviewed_publicly_importable(self):
        """The staleness marker is intentionally module-public; assert
        the symbol exists at the import site future readers expect."""
        from api.services import ai_pricing
        assert hasattr(ai_pricing, "LAST_REVIEWED")
