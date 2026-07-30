"""Application service for explicit, on-demand advisory generation."""

import hashlib

from cloudwise.ai_advisor.errors import AiAdvisorDisabledError, AiAdvisorOutputError
from cloudwise.ai_advisor.prompts import ADVISORY_DISCLAIMER, PROMPT_VERSION
from cloudwise.ai_advisor.providers.base import AdvisoryProvider
from cloudwise.ai_advisor.schemas import AdvisoryContext, OnDemandAdvisoryResult


class AiAdvisorService:
    """Coordinate a single user-requested suggestion with no side effects."""

    def __init__(self, provider: AdvisoryProvider | None, *, enabled: bool) -> None:
        if enabled and provider is None:
            raise ValueError("an AI advisory provider is required when enabled")
        self._provider = provider
        self._enabled = enabled

    async def generate_on_demand(self, context: AdvisoryContext) -> OnDemandAdvisoryResult:
        """Generate only when an authenticated future caller explicitly invokes it."""
        if not self._enabled:
            raise AiAdvisorDisabledError("AI advisory generation is disabled")

        provider = self._provider
        if provider is None:
            raise AiAdvisorDisabledError("AI advisory generation is disabled")
        provider_result = await provider.generate_suggestion(context)
        allowed_references = {item.reference for item in context.evidence}
        returned_references = set(provider_result.suggestion.evidence_references)
        if not returned_references.issubset(allowed_references):
            raise AiAdvisorOutputError("AI suggestion referenced evidence outside the input")

        suggestion = provider_result.suggestion.model_copy(
            update={"disclaimer": ADVISORY_DISCLAIMER}
        )
        canonical_context = context.model_dump_json()
        context_hash = hashlib.sha256(canonical_context.encode("utf-8")).hexdigest()
        return OnDemandAdvisoryResult(
            suggestion=suggestion,
            verified_calculation=context.calculation,
            provider=provider_result.provider,
            model_id=provider_result.model_id,
            provider_request_id=provider_result.provider_request_id,
            context_hash=context_hash,
            prompt_version=PROMPT_VERSION,
        )
