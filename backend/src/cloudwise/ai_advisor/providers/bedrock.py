"""Amazon Bedrock implementation of the advisory provider contract."""

import asyncio
import json
from typing import Any, Protocol

import boto3
from botocore.config import Config
from pydantic import ValidationError

from cloudwise.ai_advisor.errors import AiAdvisorOutputError, AiAdvisorProviderError
from cloudwise.ai_advisor.prompts import SYSTEM_PROMPT, build_user_prompt
from cloudwise.ai_advisor.schemas import (
    AdvisoryContext,
    AdvisorySuggestion,
    ProviderAdvisoryResult,
)


class BedrockRuntimeClient(Protocol):
    """Small structural type that supports fake clients in unit tests."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        """Invoke Bedrock's Converse API."""
        ...


class BedrockAdvisoryProvider:
    """Generate structured text with no tools or remediation functions."""

    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        max_output_tokens: int,
        timeout_seconds: int,
        client: BedrockRuntimeClient | None = None,
    ) -> None:
        self.model_id = model_id
        self.max_output_tokens = max_output_tokens
        self._client = client or boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=timeout_seconds,
                read_timeout=timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    async def generate_suggestion(self, context: AdvisoryContext) -> ProviderAdvisoryResult:
        """Make one bounded model call initiated by the application service."""
        request: dict[str, Any] = {
            "modelId": self.model_id,
            "system": [{"text": SYSTEM_PROMPT}],
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": build_user_prompt(context)}],
                }
            ],
            "inferenceConfig": {
                "maxTokens": self.max_output_tokens,
                "temperature": 0.0,
            },
        }
        try:
            response = await asyncio.to_thread(self._client.converse, **request)
        except Exception as exc:
            raise AiAdvisorProviderError("Bedrock could not generate a suggestion") from exc

        text = self._extract_text(response)
        try:
            payload = json.loads(text)
            suggestion = AdvisorySuggestion.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise AiAdvisorOutputError("Bedrock returned an invalid advisory response") from exc

        metadata = response.get("ResponseMetadata", {})
        request_id = metadata.get("RequestId") if isinstance(metadata, dict) else None
        return ProviderAdvisoryResult(
            suggestion=suggestion,
            provider="bedrock",
            model_id=self.model_id,
            provider_request_id=request_id if isinstance(request_id, str) else None,
        )

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        try:
            content = response["output"]["message"]["content"]
            text_blocks = [
                block["text"]
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ]
        except (KeyError, TypeError) as exc:
            raise AiAdvisorOutputError("Bedrock response did not contain text output") from exc
        if len(text_blocks) != 1:
            raise AiAdvisorOutputError("Bedrock response must contain exactly one text block")
        text_block = text_blocks[0]
        if not isinstance(text_block, str):
            raise AiAdvisorOutputError("Bedrock response text was not a string")
        return text_block
