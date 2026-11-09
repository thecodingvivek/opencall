"""Database-backed farming tasks owned by the authenticated user."""
from uuid import uuid4

from app.core.postgres import get_pool


def save_task(user_id: str, room_name: str, task_key: str, title: str, status: str) -> dict:
    with get_pool().connection() as conn:
        row = conn.execute("""
            INSERT INTO opencall.farming_tasks (id, user_id, room_name, task_key, title, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, room_name, task_key) DO UPDATE
            SET title = EXCLUDED.title, status = EXCLUDED.status, updated_at = now()
            RETURNING id::text AS id, title, status
        """, (uuid4(), user_id, room_name, task_key, title, status)).fetchone()
    return dict(row)


def list_tasks(user_id: str) -> list[dict]:
    with get_pool().connection() as conn:
        rows = conn.execute("""
            SELECT id::text AS id, title, status FROM opencall.farming_tasks
            WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT 100
        """, (user_id,)).fetchall()
    return [dict(row) for row in rows]
