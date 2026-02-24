from __future__ import annotations

import pytest

from packages.core.job_store import SQLiteJobStore, get_job_store
from packages.core.settings import get_settings


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_job_store.cache_clear()


def test_job_store_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("JOB_STORE_PATH", str(tmp_path / "jobs.db"))

    _clear_caches()
    store = get_job_store()
    assert isinstance(store, SQLiteJobStore)
    _clear_caches()


def test_job_store_selects_postgres_backend(monkeypatch):
    marker = object()
    capture: dict[str, str] = {}

    def _fake_postgres_store(dsn: str):
        capture["dsn"] = dsn
        return marker

    monkeypatch.setenv("JOB_STORE_BACKEND", "postgres")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/research_blog",
    )

    _clear_caches()
    monkeypatch.setattr(
        "packages.core.job_store.PostgresJobStore",
        _fake_postgres_store,
    )
    store = get_job_store()
    assert store is marker
    assert capture["dsn"].startswith("postgresql://")
    _clear_caches()


def test_job_store_builds_postgres_dsn_from_db_components(monkeypatch):
    marker = object()
    capture: dict[str, str] = {}

    def _fake_postgres_store(dsn: str):
        capture["dsn"] = dsn
        return marker

    monkeypatch.setenv("JOB_STORE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_HOST", "db.example.internal")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "research_blog")
    monkeypatch.setenv("DB_USER", "app_user")
    monkeypatch.setenv("DB_PASSWORD", "s3cr3t")

    _clear_caches()
    monkeypatch.setattr(
        "packages.core.job_store.PostgresJobStore",
        _fake_postgres_store,
    )
    store = get_job_store()
    assert store is marker
    assert (
        capture["dsn"]
        == "postgresql://app_user:s3cr3t@db.example.internal:5432/research_blog"
    )
    _clear_caches()


def test_job_store_postgres_requires_password_without_database_url(
    monkeypatch,
):
    monkeypatch.setenv("JOB_STORE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_PASSWORD", "")

    _clear_caches()
    with pytest.raises(ValueError, match="DB_PASSWORD is required"):
        get_job_store()
    _clear_caches()
