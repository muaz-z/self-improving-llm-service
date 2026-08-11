import sqlite3
from datetime import datetime, timezone

from app.db import get_connection


def create_review_run(
    prompt_version: int,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO review_runs (
                prompt_version,
                status,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                prompt_version,
                "running",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        return cursor.lastrowid


def update_review_run_status(
    review_run_id: int,
    status: str,
) -> None:
    completed_at = (
        datetime.now(timezone.utc).isoformat() if status == "completed" else None
    )

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE review_runs
            SET status = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                status,
                completed_at,
                review_run_id,
            ),
        )


def get_resumable_review_run(
    prompt_version: int,
) -> dict | None:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            """
            SELECT *
            FROM review_runs
            WHERE prompt_version = ?
            AND status IN ('running', 'failed')
            ORDER BY id DESC
            LIMIT 1
            """,
            (prompt_version,),
        ).fetchone()

        return dict(row) if row else None
