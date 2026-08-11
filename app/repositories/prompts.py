import sqlite3
from datetime import datetime, timezone

from app.db import get_connection


def get_active_prompt_version() -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT version
            FROM prompt_versions
            WHERE is_active = 1
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            raise RuntimeError("No active prompt configured")

        return row[0]


def list_prompt_versions() -> list[dict]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                version,
                reason,
                is_active,
                regression_passed,
                created_at
            FROM prompt_versions
            ORDER BY version ASC
            """
        ).fetchall()

        return [
            {
                "version": row["version"],
                "reason": row["reason"],
                "is_active": bool(row["is_active"]),
                "regression_passed": (
                    None
                    if row["regression_passed"] is None
                    else bool(row["regression_passed"])
                ),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def save_prompt_version(
    version: int,
    reason: str | None = None,
    is_active: bool = False,
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO prompt_versions (
                version,
                reason,
                is_active,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                version,
                reason,
                int(is_active),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def activate_prompt_version(version: int) -> None:
    with get_connection() as conn:
        exists = conn.execute(
            """
            SELECT 1
            FROM prompt_versions
            WHERE version = ?
            """,
            (version,),
        ).fetchone()

        if not exists:
            raise ValueError(f"Prompt version {version} does not exist")

        conn.execute(
            """
            UPDATE prompt_versions
            SET is_active = 0
            """
        )

        conn.execute(
            """
            UPDATE prompt_versions
            SET is_active = 1
            WHERE version = ?
            """,
            (version,),
        )


def update_prompt_regression(
    version: int,
    regression_passed: bool,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE prompt_versions
            SET regression_passed = ?
            WHERE version = ?
            """,
            (
                int(regression_passed),
                version,
            ),
        )
