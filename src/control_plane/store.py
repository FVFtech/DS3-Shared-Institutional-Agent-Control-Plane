"""Durable task and approval store with idempotency constraints."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from .models import ApprovalRequest, TaskRecord, TaskStatus


class ConflictError(RuntimeError):
    pass


class NotFoundError(RuntimeError):
    pass


class TaskStore:
    def __init__(self, database_path: str) -> None:
        self.path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                record_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS approvals (
                approval_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(task_id),
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                decided_by TEXT,
                justification TEXT,
                created_at TEXT NOT NULL,
                decided_at TEXT
            )""")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 10000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_task(self, record: TaskRecord) -> tuple[TaskRecord, bool]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT record_json FROM tasks WHERE idempotency_key=?", (record.idempotency_key,)).fetchone()
            if existing:
                old = TaskRecord.model_validate_json(existing["record_json"])
                if (old.objective != record.objective or old.platform != record.platform or
                    old.requested_by != record.requested_by or old.agent_profile != record.agent_profile or
                    old.action != record.action or old.risk_tier != record.risk_tier or
                    old.requested_tools != record.requested_tools):
                    raise ConflictError("Idempotency key was already used for a different request")
                return old, False
            payload = record.model_dump_json()
            db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)", (
                str(record.task_id), record.idempotency_key, record.status.value, payload,
                record.created_at.isoformat(), record.updated_at.isoformat()))
        return record, True

    def get_task(self, task_id: UUID) -> TaskRecord:
        with self._connect() as db:
            row = db.execute("SELECT record_json FROM tasks WHERE task_id=?", (str(task_id),)).fetchone()
        if not row:
            raise NotFoundError("Task not found")
        return TaskRecord.model_validate_json(row["record_json"])

    def update_task(self, record: TaskRecord) -> None:
        record.updated_at = datetime.now(timezone.utc)
        with self._connect() as db:
            cur = db.execute("UPDATE tasks SET status=?, record_json=?, updated_at=? WHERE task_id=?", (
                record.status.value, record.model_dump_json(), record.updated_at.isoformat(), str(record.task_id)))
            if cur.rowcount != 1:
                raise NotFoundError("Task not found")

    def create_approval(self, approval_id: UUID, request: ApprovalRequest) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO approvals VALUES (?, ?, 'pending', ?, NULL, NULL, ?, NULL)", (
                str(approval_id), str(request.task_id), request.model_dump_json(), datetime.now(timezone.utc).isoformat()))

    def decide_approval(self, approval_id: UUID, decision: str, actor: str, justification: str) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM approvals WHERE approval_id=?", (str(approval_id),)).fetchone()
            if not row:
                raise NotFoundError("Approval not found")
            if row["status"] != "pending":
                raise ConflictError("Approval has already been decided")
            db.execute("UPDATE approvals SET status=?, decided_by=?, justification=?, decided_at=? WHERE approval_id=? AND status='pending'",
                       (decision, actor, justification, datetime.now(timezone.utc).isoformat(), str(approval_id)))
            return dict(db.execute("SELECT * FROM approvals WHERE approval_id=?", (str(approval_id),)).fetchone())

    def get_approval(self, approval_id: UUID) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM approvals WHERE approval_id=?", (str(approval_id),)).fetchone()
        if not row:
            raise NotFoundError("Approval not found")
        return dict(row)
