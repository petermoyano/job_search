from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any

import boto3  # type: ignore[import-untyped]
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)


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


class BedrockTransientError(Exception):
    pass


class BedrockPermanentError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class BedrockInvocation:
    payload: dict[str, Any]
    input_tokens: int
    output_tokens: int
    duration_ms: int


class BedrockStructuredClient:
    def __init__(
        self,
        *,
        region_name: str,
        model_id: str,
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
        client: Any | None = None,
    ) -> None:
        self.model_id = model_id
        self.client = client or boto3.client(
            "bedrock-runtime",
            region_name=region_name,
            config=Config(
                connect_timeout=connect_timeout_seconds,
                read_timeout=read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema_description: str,
        json_schema: dict[str, Any],
        max_tokens: int,
    ) -> BedrockInvocation:
        started = time.monotonic()
        try:
            response = self.client.converse(
                modelId=self.model_id,
                system=[{"text": system_prompt}],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_prompt}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": 0,
                },
                outputConfig={
                    "textFormat": {
                        "type": "json_schema",
                        "structure": {
                            "jsonSchema": {
                                "schema": json.dumps(
                                    json_schema,
                                    separators=(",", ":"),
                                ),
                                "name": schema_name,
                                "description": schema_description,
                            }
                        },
                    }
                },
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "ClientError"))
            if code in TRANSIENT_ERROR_CODES:
                raise BedrockTransientError(
                    "Bedrock is temporarily unavailable"
                ) from exc
            raise BedrockPermanentError(
                code=code,
                message="Bedrock request was rejected",
            ) from exc
        except (
            ConnectionClosedError,
            EndpointConnectionError,
            ReadTimeoutError,
        ) as exc:
            raise BedrockTransientError("Bedrock is temporarily unavailable") from exc
        except BotoCoreError as exc:
            raise BedrockTransientError("Bedrock request failed") from exc

        duration_ms = round((time.monotonic() - started) * 1000)
        if response.get("stopReason") == "max_tokens":
            raise BedrockPermanentError(
                code="MODEL_OUTPUT_TRUNCATED",
                message="Bedrock response exceeded the configured output limit",
            )
        try:
            content = response["output"]["message"]["content"]
            text = next(block["text"] for block in content if "text" in block)
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError("structured response must be an object")
        except (
            KeyError,
            StopIteration,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise BedrockPermanentError(
                code="INVALID_MODEL_RESPONSE",
                message="Bedrock returned an invalid structured response",
            ) from exc

        usage = response.get("usage", {})
        return BedrockInvocation(
            payload=payload,
            input_tokens=int(usage.get("inputTokens", 0)),
            output_tokens=int(usage.get("outputTokens", 0)),
            duration_ms=duration_ms,
        )
