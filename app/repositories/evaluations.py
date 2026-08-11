from datetime import datetime, timezone

from app.db import get_connection


def save_prompt_evaluations(
    evaluations: list[dict],
) -> None:
    if not evaluations:
        return

    created_at = datetime.now(timezone.utc).isoformat()

    rows = [
        (
            evaluation["version"],
            evaluation["sample_id"],
            evaluation["previous_result"],
            evaluation["current_result"],
            evaluation["feedback"],
            created_at,
        )
        for evaluation in evaluations
    ]

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO prompt_evaluations (
                version,
                sample_id,
                previous_result,
                current_result,
                feedback,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
