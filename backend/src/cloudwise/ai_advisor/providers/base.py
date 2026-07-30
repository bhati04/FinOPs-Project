"""Provider contract for advisory-only model calls."""

from typing import Protocol

from cloudwise.ai_advisor.schemas import AdvisoryContext, ProviderAdvisoryResult


class AdvisoryProvider(Protocol):
    """Generate one suggestion from verified context without taking actions."""

    async def generate_suggestion(self, context: AdvisoryContext) -> ProviderAdvisoryResult:
        """Return a strictly validated qualitative suggestion."""
        ...
