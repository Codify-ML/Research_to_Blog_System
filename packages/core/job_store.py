from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from packages.core.constants import AgentStatus
from packages.core.errors import JobNotFoundError
from packages.core.settings import get_settings

TERMINAL_STATUSES = {
    AgentStatus.COMPLETED.value,
    AgentStatus.FAILED.value,
    AgentStatus.ESCALATED.value,
}

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    AgentStatus.PENDING.value: {
        AgentStatus.RUNNING.value,
        AgentStatus.FAILED.value,
    },
    AgentStatus.RUNNING.value: {
        AgentStatus.RETRYING.value,
        AgentStatus.COMPLETED.value,
        AgentStatus.FAILED.value,
        AgentStatus.ESCALATED.value,
    },
    AgentStatus.RETRYING.value: {
        AgentStatus.RUNNING.value,
        AgentStatus.FAILED.value,
        AgentStatus.ESCALATED.value,
    },
    AgentStatus.COMPLETED.value: set(),
    AgentStatus.FAILED.value: set(),
    AgentStatus.ESCALATED.value: set(),
}


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _status_value(status: AgentStatus | str) -> str:
    if isinstance(status, AgentStatus):
        return status.value
    return status


class SQLiteJobStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """)
            conn.commit()

    def create_job(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        status = _status_value(initial_state["status"])

        record = {
            **initial_state,
            "status": status,
            "created_at": now,
            "updated_at": now,
            "status_transitions": [
                {
                    "from": None,
                    "to": status,
                    "at": now,
                }
            ],
        }

        payload = json.dumps(record)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs(job_id, payload) VALUES (?, ?)",
                (record["job_id"], payload),
            )
            conn.commit()
        return record

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

        if row is None:
            return None
        return json.loads(row["payload"])

    def get_job_or_raise(self, job_id: str) -> dict[str, Any]:
        record = self.get_job(job_id)
        if record is None:
            raise JobNotFoundError(job_id)
        return record

    def set_status(
        self,
        *,
        job_id: str,
        next_status: AgentStatus | str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        record = self.get_job_or_raise(job_id)
        now = _utc_now()

        current_status = _status_value(record["status"])
        next_status_value = _status_value(next_status)

        if current_status != next_status_value:
            self._validate_transition(current_status, next_status_value)
            record["status_transitions"].append(
                {
                    "from": current_status,
                    "to": next_status_value,
                    "at": now,
                }
            )

        record["status"] = next_status_value
        record["error_message"] = error_message
        record["updated_at"] = now

        self._persist(record)
        return record

    def update_job(
        self,
        *,
        job_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        record = self.get_job_or_raise(job_id)
        record.update(updates)
        record["updated_at"] = _utc_now()

        if "status" in record:
            record["status"] = _status_value(record["status"])

        self._persist(record)
        return record

    def _persist(self, record: dict[str, Any]) -> None:
        payload = json.dumps(record)
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET payload = ? WHERE job_id = ?",
                (payload, record["job_id"]),
            )
            conn.commit()

    def _validate_transition(self, current: str, nxt: str) -> None:
        if current in TERMINAL_STATUSES:
            raise ValueError(
                f"Terminal status {current} cannot transition to {nxt}."
            )
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
        if nxt not in allowed:
            raise ValueError(f"Invalid status transition: {current} -> {nxt}.")


@lru_cache(maxsize=1)
def get_job_store() -> SQLiteJobStore:
    settings = get_settings()
    return SQLiteJobStore(settings.job_store_path)
