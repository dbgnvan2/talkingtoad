"""Provider drivers for the AIRouter abstraction (v2.6 M2.1 / Cycle Z).

Each driver wraps one LLM provider's HTTP API and returns a unified
:class:`api.services.ai_router.AIResponse` regardless of underlying
provider quirks. Drivers are the only place in the codebase that knows
provider-specific request/response shapes; everything else talks to
:class:`api.services.ai_router.AIRouter`.

See ``base.py`` for the contract. Add a new provider by:
    1. Implementing ``ProviderDriver`` in a new module here.
    2. Registering it in ``api/services/ai_router.py`` ``_DRIVERS`` table.
"""
