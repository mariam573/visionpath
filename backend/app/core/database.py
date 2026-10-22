"""Small SQLite persistence layer for scene description history."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List

from app.core.config import settings


def _connect() -> sqlite3.Connection:
    database_path = Path(settings.DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the application tables if this is a fresh database."""
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT,
                role TEXT NOT NULL DEFAULT 'blind_person'
                    CHECK (role IN ('blind_person', 'supervisor', 'admin')),
                preferred_language TEXT NOT NULL DEFAULT 'en',
                accessibility_preferences_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scene_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                scene_context TEXT NOT NULL,
                narrative TEXT NOT NULL,
                priority_alert TEXT NOT NULL DEFAULT '',
                objects_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_scene_descriptions_created_at "
            "ON scene_descriptions(created_at DESC)"
        )


def create_user(
    *,
    full_name: str,
    email: str,
    role: str = "blind_person",
    phone: str | None = None,
    preferred_language: str = "en",
    accessibility_preferences: Dict[str, Any] | None = None,
) -> int:
    """Store a user profile; callers must authorize privileged role changes."""
    if role not in {"blind_person", "supervisor", "admin"}:
        raise ValueError("Unsupported user role")
    with _connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users
                (full_name, email, phone, role, preferred_language,
                 accessibility_preferences_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                full_name.strip(),
                email.strip().lower(),
                phone,
                role,
                preferred_language,
                json.dumps(accessibility_preferences or {}, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def get_user(user_id: int) -> Dict[str, Any] | None:
    """Load a stored profile by ID for use by an authorized caller."""
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT id, full_name, email, phone, role, preferred_language,
                   accessibility_preferences_json, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "phone": row["phone"],
        "role": row["role"],
        "preferred_language": row["preferred_language"],
        "accessibility_preferences": json.loads(
            row["accessibility_preferences_json"]
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def save_scene_description(
    *,
    scene_context: str,
    narrative: str,
    priority_alert: str,
    objects: List[Any],
) -> int:
    """Persist a scene result without storing the audio query or any image."""
    objects_json = json.dumps(
        [obj.model_dump(mode="json") for obj in objects],
        ensure_ascii=False,
    )
    with _connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO scene_descriptions
                (scene_context, narrative, priority_alert, objects_json)
            VALUES (?, ?, ?, ?)
            """,
            (scene_context, narrative, priority_alert, objects_json),
        )
        return int(cursor.lastrowid)


def list_scene_descriptions(limit: int = 20) -> List[Dict[str, Any]]:
    """Return newest saved scene descriptions first."""
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, scene_context, narrative, priority_alert, objects_json
            FROM scene_descriptions
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "scene_context": row["scene_context"],
            "narrative": row["narrative"],
            "priority_alert": row["priority_alert"],
            "objects": json.loads(row["objects_json"]),
        }
        for row in rows
    ]
