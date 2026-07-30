"""Composition helpers kept separate from the HTTP application."""

from cloudwise.ai_advisor.providers.bedrock import BedrockAdvisoryProvider
from cloudwise.ai_advisor.service import AiAdvisorService
from cloudwise.core.config import Settings


def build_ai_advisor_service(settings: Settings) -> AiAdvisorService:
    """Build the disabled-by-default advisor for a future authenticated route."""
    if not settings.ai_advisor_enabled:
        return AiAdvisorService(None, enabled=False)
    if not settings.ai_advisor_model_id:
        raise ValueError("AI advisor model ID is required to build the provider")
    provider = BedrockAdvisoryProvider(
        model_id=settings.ai_advisor_model_id,
        region=settings.ai_advisor_aws_region,
        max_output_tokens=settings.ai_advisor_max_output_tokens,
        timeout_seconds=settings.ai_advisor_timeout_seconds,
    )
    return AiAdvisorService(provider, enabled=settings.ai_advisor_enabled)
