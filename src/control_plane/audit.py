"""SQLite append-only hash-chained audit log for tamper-evidence, not WORM storage."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


class AuditLog:
    def __init__(self, database_path: str) -> None:
        self.path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS audit_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                occurred_at TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            )""")
            # Triggers prevent accidental UPDATE/DELETE through normal SQL paths.
            db.execute("""CREATE TRIGGER IF NOT EXISTS audit_no_update
                BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'append-only audit table'); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS audit_no_delete
                BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'append-only audit table'); END""")

    def append(self, *, event_id: str, actor: str, event_type: str,
               subject_id: str, payload: dict[str, Any]) -> str:
        occurred_at = datetime.now(timezone.utc).isoformat()
        payload_json = canonical_json(payload)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1").fetchone()
            previous_hash = previous["event_hash"] if previous else GENESIS
            material = canonical_json({
                "event_id": event_id, "occurred_at": occurred_at, "actor": actor,
                "event_type": event_type, "subject_id": subject_id,
                "payload_json": payload_json, "previous_hash": previous_hash,
            })
            event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
            db.execute("""INSERT INTO audit_events
                (event_id, occurred_at, actor, event_type, subject_id, payload_json, previous_hash, event_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, occurred_at, actor, event_type, subject_id, payload_json, previous_hash, event_hash))
        return event_hash

    def verify_chain(self) -> tuple[bool, int]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM audit_events ORDER BY sequence ASC").fetchall()
        previous_hash = GENESIS
        for row in rows:
            if row["previous_hash"] != previous_hash:
                return False, int(row["sequence"])
            material = canonical_json({
                "event_id": row["event_id"], "occurred_at": row["occurred_at"],
                "actor": row["actor"], "event_type": row["event_type"],
                "subject_id": row["subject_id"], "payload_json": row["payload_json"],
                "previous_hash": row["previous_hash"],
            })
            expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if expected != row["event_hash"]:
                return False, int(row["sequence"])
            previous_hash = row["event_hash"]
        return True, len(rows)

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM audit_events ORDER BY sequence DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
