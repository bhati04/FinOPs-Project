"""Domain errors for AI advisory generation."""


class AiAdvisorError(Exception):
    """Base error safe for translation at a future authenticated API boundary."""


class AiAdvisorDisabledError(AiAdvisorError):
    """Raised when on-demand AI suggestions are disabled."""


class AiAdvisorProviderError(AiAdvisorError):
    """Raised when the configured model provider cannot return a suggestion."""


class AiAdvisorOutputError(AiAdvisorError):
    """Raised when model output violates the advisory response contract."""
