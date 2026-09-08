import json
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.core import config


@pytest.fixture(autouse=True)
def clear_cache():
    config._get_external_api_keys.cache_clear()
    yield
    config._get_external_api_keys.cache_clear()


def settings(**kwargs):
    return config.Settings(_env_file=None, database_url_ssm_parameter=None, **kwargs)


def test_aggregate_one_read_environment_precedence_and_redaction(monkeypatch):
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "TAVILY_API_KEY": "aws-tavily",
                "SERPER_API_KEY": "aws-serper",
                "UNRELATED": "ignored",
            }
        )
    }
    factory = Mock(return_value=client)
    monkeypatch.setattr("boto3.client", factory)
    for _ in range(2):
        result = settings(
            job_search_external_api_secret_name="test/keys",
            tavily_api_key="local-tavily",
        )
        assert result.tavily_api_key == "local-tavily"
        assert result.serper_api_key == "aws-serper"
        assert not result.serpapi_api_key and not result.rapidapi_key
        assert "aws-serper" not in repr(result) and "local-tavily" not in repr(result)
    client.get_secret_value.assert_called_once_with(SecretId="test/keys")
    assert factory.call_args.kwargs["region_name"] == "sa-east-1"


def test_local_settings_do_not_call_aws(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Local settings must not call AWS")

    monkeypatch.setattr("boto3.client", forbidden)
    result = settings(tavily_api_key="local", serper_api_key="local-serper")
    assert result.serper_api_key == "local-serper"


@pytest.mark.parametrize(
    "payload", ["not-json", "[]", "null", '{"SERPER_API_KEY": {}, "RAPIDAPI_KEY": ""}']
)
def test_malformed_or_missing_fields_preserve_local(monkeypatch, caplog, payload):
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": payload}
    monkeypatch.setattr("boto3.client", Mock(return_value=client))
    result = settings(
        job_search_external_api_secret_name="test/keys", tavily_api_key="local"
    )
    assert result.tavily_api_key == "local"
    assert not result.serper_api_key
    assert payload not in caplog.text


def test_missing_secret_nonfatal(monkeypatch, caplog):
    client = Mock()
    client.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "sensitive-detail"}},
        "GetSecretValue",
    )
    monkeypatch.setattr("boto3.client", Mock(return_value=client))
    result = settings(job_search_external_api_secret_name="test/missing")
    assert not result.serper_api_key
    assert "sensitive-detail" not in caplog.text


def test_production_aggregate_takes_precedence_over_legacy_environment(monkeypatch):
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": '{"TAVILY_API_KEY": "aggregate-tavily"}'
    }
    monkeypatch.setattr("boto3.client", Mock(return_value=client))
    result = settings(
        app_env="production",
        job_search_external_api_secret_name="test/keys",
        tavily_api_key="legacy-tavily",
    )
    assert result.tavily_api_key == "aggregate-tavily"
