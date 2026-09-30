import json
import sqlite3
from pathlib import Path
from typing import Any

from .config import settings


def connection() -> sqlite3.Connection:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runbooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                match_labels TEXT NOT NULL DEFAULT '{}',
                steps TEXT NOT NULL DEFAULT '[]',
                severity TEXT NOT NULL DEFAULT 'warning',
                owner TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL,
                runbook_id INTEGER,
                status TEXT NOT NULL DEFAULT 'received',
                clickup_task_id TEXT,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(runbook_id) REFERENCES runbooks(id)
            );
            """
        )


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def create_event(fingerprint: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    with connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO events (fingerprint, payload) VALUES (?, ?)",
                (fingerprint, json.dumps(payload)),
            )
            row = conn.execute("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return row_dict(row), True
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT * FROM events WHERE fingerprint = ?", (fingerprint,)).fetchone()
            return row_dict(row), False


def get_runbooks() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM runbooks WHERE enabled = 1 ORDER BY id").fetchall()
    return [row_dict(row) for row in rows]  # type: ignore[misc]


def create_runbook(data: dict[str, Any]) -> dict[str, Any]:
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO runbooks (name, description, match_labels, steps, severity, owner) VALUES (?, ?, ?, ?, ?, ?)",
            (data["name"], data.get("description", ""), json.dumps(data.get("match_labels", {})),
             json.dumps(data.get("steps", [])), data.get("severity", "warning"), data.get("owner", "")),
        )
        return row_dict(conn.execute("SELECT * FROM runbooks WHERE id = ?", (cursor.lastrowid,)).fetchone())  # type: ignore[return-value]


def update_event(event_id: int, **fields: Any) -> dict[str, Any] | None:
    fields["updated_at"] = "CURRENT_TIMESTAMP"
    assignments = []
    values = []
    for key, value in fields.items():
        if value == "CURRENT_TIMESTAMP":
            assignments.append(f"{key} = CURRENT_TIMESTAMP")
        else:
            assignments.append(f"{key} = ?")
            values.append(value)
    values.append(event_id)
    with connection() as conn:
        conn.execute(f"UPDATE events SET {', '.join(assignments)} WHERE id = ?", values)
        return row_dict(conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())


def get_event(event_id: int) -> dict[str, Any] | None:
    with connection() as conn:
        return row_dict(conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())


def list_events(limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [row_dict(row) for row in rows]  # type: ignore[misc]
