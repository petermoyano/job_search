from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.documents.auth import credential_store
from app.knowledge.api import get_knowledge_generation_service
from app.knowledge.generation import (
    KnowledgeGenerationClient,
    KnowledgeGenerationResult,
    KnowledgeGenerationService,
)
from app.main import app


CRANE_HEADERS = {"Authorization": "Bearer test-crane-secret"}
JOB_HEADERS = {"Authorization": "Bearer test-job-search-secret"}


class FakeGenerationClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        messages: list[dict],
        max_output_tokens: int,
    ) -> KnowledgeGenerationResult:
        self.calls.append(
            {
                "model_id": model_id,
                "system_prompt": system_prompt,
                "messages": messages,
                "max_output_tokens": max_output_tokens,
            }
        )
        return KnowledgeGenerationResult(
            text="El documento indica requisitos de presentacion.",
            input_tokens=12,
            output_tokens=8,
            duration_ms=34,
        )


@pytest.fixture(autouse=True)
def generation_test_environment() -> None:
    settings = get_settings()
    original_keys = settings.document_client_keys_json
    original_model = settings.crane_chat_model_id
    settings.document_client_keys_json = json.dumps(
        {
            "test-job-search-secret": {
                "source_app": "job-search",
                "tenant_ids": ["job-search"],
            },
            "test-crane-secret": {
                "source_app": "crane-intelligence",
                "tenant_ids": ["creactis"],
            },
        }
    )
    settings.crane_chat_model_id = "mistral.ministral-3-3b-instruct"
    credential_store.clear_cache()
    yield
    app.dependency_overrides.pop(get_knowledge_generation_service, None)
    credential_store.clear_cache()
    settings.document_client_keys_json = original_keys
    settings.crane_chat_model_id = original_model


def override_generation_client(client: KnowledgeGenerationClient) -> None:
    app.dependency_overrides[get_knowledge_generation_service] = lambda: (
        KnowledgeGenerationService(settings=get_settings(), client=client)
    )


def generation_payload() -> dict:
    return {
        "system_prompt": "Responde en espanol con informacion verificada.",
        "messages": [
            {"role": "user", "text": "Que dice el reglamento?"},
            {"role": "assistant", "text": "Voy a revisar la documentacion."},
            {"role": "user", "text": "Resume lo importante."},
        ],
    }


def test_generate_invokes_bedrock_with_authorized_crane_credential() -> None:
    client = FakeGenerationClient()
    override_generation_client(client)

    with TestClient(app) as http_client:
        response = http_client.post(
            "/knowledge/generate",
            headers=CRANE_HEADERS,
            json=generation_payload(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "text": "El documento indica requisitos de presentacion."
    }
    assert client.calls == [
        {
            "model_id": "mistral.ministral-3-3b-instruct",
            "system_prompt": "Responde en espanol con informacion verificada.",
            "messages": [
                {"role": "user", "content": [{"text": "Que dice el reglamento?"}]},
                {
                    "role": "assistant",
                    "content": [{"text": "Voy a revisar la documentacion."}],
                },
                {"role": "user", "content": [{"text": "Resume lo importante."}]},
            ],
            "max_output_tokens": 700,
        }
    ]


def test_generate_rejects_a_credential_for_another_source_app() -> None:
    client = FakeGenerationClient()
    override_generation_client(client)

    with TestClient(app) as http_client:
        response = http_client.post(
            "/knowledge/generate",
            headers=JOB_HEADERS,
            json=generation_payload(),
        )

    assert response.status_code == 403
    assert client.calls == []


def test_generate_rejects_input_above_the_total_limit() -> None:
    client = FakeGenerationClient()
    override_generation_client(client)
    payload = generation_payload()
    payload["system_prompt"] = "x" * 60_000
    payload["messages"] = [{"role": "user", "text": "hola"}]

    with TestClient(app) as http_client:
        response = http_client.post(
            "/knowledge/generate",
            headers=CRANE_HEADERS,
            json=payload,
        )

    assert response.status_code == 422
    assert client.calls == []
