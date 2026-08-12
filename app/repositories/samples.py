import json
import sqlite3
from datetime import datetime, timezone

from app.db import ReviewResult, ReviewStatus, get_connection
from app.schemas.review_schemas import SampleReview


def save_sample(
    message: str,
    output: dict,
    prompt_version: int,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO samples (
                message,
                output_json,
                prompt_version,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                message,
                json.dumps(output),
                prompt_version,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        return cursor.lastrowid


def get_pending_samples(
    prompt_version: int,
) -> list[dict]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM samples
            WHERE review_status = ?
              AND prompt_version = ?
            ORDER BY id ASC
            """,
            (
                ReviewStatus.PENDING.value,
                prompt_version,
            ),
        ).fetchall()

        return [dict(row) for row in rows]


def update_sample_reviews(reviews: list[SampleReview]) -> None:
    reviewed_at = datetime.now(timezone.utc).isoformat()

    rows = [
        (
            ReviewStatus.REVIEWED.value,
            (
                ReviewResult.PASSED.value
                if review.correct
                else ReviewResult.FAILED.value
            ),
            review.feedback,
            reviewed_at,
            review.sample_id,
        )
        for review in reviews
    ]

    with get_connection() as conn:
        conn.executemany(
            """
            UPDATE samples
            SET review_status = ?,
                review_result = ?,
                review_feedback = ?,
                reviewed_at = ?
            WHERE id = ?
            """,
            rows,
        )


def assign_samples_to_review_run(
    sample_ids: list[int],
    review_run_id: int,
) -> None:
    with get_connection() as conn:
        conn.executemany(
            """
            UPDATE samples
            SET review_run_id = ?
            WHERE id = ?
            """,
            [(review_run_id, sample_id) for sample_id in sample_ids],
        )


def get_samples_for_review_run(
    review_run_id: int,
) -> list[dict]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM samples
            WHERE review_run_id = ?
            ORDER BY id ASC
            """,
            (review_run_id,),
        ).fetchall()

        return [dict(row) for row in rows]


def get_successful_samples(
    limit: int,
) -> list[dict]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM samples
            WHERE review_result = ?
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (
                ReviewResult.PASSED.value,
                limit,
            ),
        ).fetchall()

        return [dict(row) for row in rows]


def list_samples(
    *,
    review_status: str | None = None,
    prompt_version: int | None = None,
    limit: int = 50,
) -> list[dict]:
    query = """
        SELECT *
        FROM samples
        WHERE 1 = 1
    """
    params: list = []

    if review_status is not None:
        query += " AND review_status = ?"
        params.append(review_status)

    if prompt_version is not None:
        query += " AND prompt_version = ?"
        params.append(prompt_version)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
