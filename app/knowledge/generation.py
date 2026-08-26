from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any, Protocol

import boto3  # type: ignore[import-untyped]
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from app.core.config import Settings
from app.documents.auth import AuthContext
from app.knowledge.contracts import (
    CRANE_INTELLIGENCE_SOURCE_APP,
    KnowledgeGenerateRequest,
    KnowledgeGenerateResponse,
)


LOGGER = logging.getLogger(__name__)

TRANSIENT_ERROR_CODES = {
    "InternalServerException",
    "ModelNotReadyException",
    "ModelTimeoutException",
    "RequestTimeout",
    "ServiceQuotaExceededException",
    "ServiceUnavailableException",
    "ThrottlingException",
    "TooManyRequestsException",
}


class KnowledgeGenerationAccessDeniedError(Exception):
    pass


class KnowledgeGenerationUnavailableError(Exception):
    pass


class KnowledgeGenerationConfigurationError(Exception):
    pass


class KnowledgeGenerationRejectedError(Exception):
    pass


@dataclass(frozen=True)
class KnowledgeGenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    duration_ms: int


class KnowledgeGenerationClient(Protocol):
    def generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        max_output_tokens: int,
    ) -> KnowledgeGenerationResult: ...


class BedrockKnowledgeGenerationClient:
    def __init__(
        self,
        *,
        region_name: str,
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
        client: Any | None = None,
    ) -> None:
        self.client = client or boto3.client(
            "bedrock-runtime",
            region_name=region_name,
            config=Config(
                connect_timeout=connect_timeout_seconds,
                read_timeout=read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        max_output_tokens: int,
    ) -> KnowledgeGenerationResult:
        started = time.monotonic()
        try:
            response = self.client.converse(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={
                    "maxTokens": max_output_tokens,
                    "temperature": 0.2,
                },
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "ClientError"))
            if code in TRANSIENT_ERROR_CODES:
                raise KnowledgeGenerationUnavailableError(
                    "Bedrock generation is temporarily unavailable"
                ) from exc
            raise KnowledgeGenerationRejectedError(
                "Bedrock generation request was rejected"
            ) from exc
        except (
            BotoCoreError,
            ConnectionClosedError,
            EndpointConnectionError,
            ReadTimeoutError,
        ) as exc:
            raise KnowledgeGenerationUnavailableError(
                "Bedrock generation is temporarily unavailable"
            ) from exc

        duration_ms = round((time.monotonic() - started) * 1000)
        try:
            content = response["output"]["message"]["content"]
            text = next(
                block["text"]
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ).strip()
        except (KeyError, StopIteration, TypeError) as exc:
            raise KnowledgeGenerationRejectedError(
                "Bedrock returned an invalid generation response"
            ) from exc
        if not text:
            raise KnowledgeGenerationRejectedError(
                "Bedrock returned an empty generation response"
            )

        usage = response.get("usage", {})
        return KnowledgeGenerationResult(
            text=text,
            input_tokens=int(usage.get("inputTokens", 0)),
            output_tokens=int(usage.get("outputTokens", 0)),
            duration_ms=duration_ms,
        )


class KnowledgeGenerationService:
    def __init__(
        self,
        *,
        settings: Settings,
        client: KnowledgeGenerationClient | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or BedrockKnowledgeGenerationClient(
            region_name=settings.crane_chat_bedrock_region,
            connect_timeout_seconds=settings.crane_chat_connect_timeout_seconds,
            read_timeout_seconds=settings.crane_chat_read_timeout_seconds,
        )

    def generate(
        self,
        *,
        payload: KnowledgeGenerateRequest,
        auth_context: AuthContext,
    ) -> KnowledgeGenerateResponse:
        if auth_context.source_app != CRANE_INTELLIGENCE_SOURCE_APP:
            raise KnowledgeGenerationAccessDeniedError(
                "Credential is not authorized for Crane Intelligence chat"
            )
        if not self.settings.crane_chat_model_id:
            raise KnowledgeGenerationConfigurationError(
                "Crane chat generation is not configured"
            )

        result = self.client.generate(
            model_id=self.settings.crane_chat_model_id,
            system_prompt=payload.system_prompt,
            messages=[
                {
                    "role": message.role,
                    "content": [{"text": message.text}],
                }
                for message in payload.messages
            ],
            max_output_tokens=self.settings.crane_chat_max_output_tokens,
        )
        LOGGER.info(
            "event=knowledge_chat_generated model_id=%s input_tokens=%s "
            "output_tokens=%s duration_ms=%s",
            self.settings.crane_chat_model_id,
            result.input_tokens,
            result.output_tokens,
            result.duration_ms,
        )
        return KnowledgeGenerateResponse(text=result.text)
