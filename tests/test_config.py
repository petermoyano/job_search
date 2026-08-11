from app.core import config
from app.db.session import _engine_kwargs


def test_settings_resolves_database_url_from_ssm(monkeypatch) -> None:
    parameter_name = "/job-search/database-url"
    secret_url = "postgresql://user:password@example.neon.tech/neondb"

    monkeypatch.setattr(
        config,
        "_get_ssm_parameter",
        lambda name: secret_url if name == parameter_name else "",
    )

    settings = config.Settings(
        _env_file=None,
        database_url="sqlite:///fallback.db",
        database_url_ssm_parameter=parameter_name,
    )

    assert settings.database_url == (
        "postgresql+psycopg://user:password@example.neon.tech/neondb"
    )
    assert secret_url not in repr(settings)


def test_settings_normalizes_postgresql_driver() -> None:
    settings = config.Settings(
        _env_file=None,
        database_url="postgresql://user:password@example.neon.tech/neondb",
        database_url_ssm_parameter=None,
    )

    assert settings.database_url.startswith("postgresql+psycopg://")


def test_sqlite_engine_allows_test_thread_sharing() -> None:
    assert _engine_kwargs("sqlite:///./test.db") == {
        "connect_args": {"check_same_thread": False}
    }


def test_postgres_engine_checks_pooled_connections_before_use() -> None:
    assert _engine_kwargs("postgresql+psycopg://example") == {
        "pool_pre_ping": True
    }
