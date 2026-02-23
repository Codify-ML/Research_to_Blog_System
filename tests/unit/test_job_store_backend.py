from __future__ import annotations

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
