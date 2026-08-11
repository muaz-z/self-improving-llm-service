import sqlite3
from datetime import datetime, timezone
from enum import StrEnum


class ReviewStatus(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"


class ReviewResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ReviewRunStatus(StrEnum):
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"


DB_PATH = "learnwise.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        # sample table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                output_json TEXT NOT NULL,
                prompt_version INTEGER NOT NULL,

                review_status TEXT NOT NULL DEFAULT 'pending',
                review_result TEXT,
                review_feedback TEXT,
                reviewed_at TEXT,
                review_run_id INTEGER,

                created_at TEXT NOT NULL
            )
        """)

        # review runs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_version INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)

        # prompt versions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                version INTEGER PRIMARY KEY,
                reason TEXT,
                is_active INTEGER NOT NULL DEFAULT 0,
                regression_passed INTEGER,
                created_at TEXT NOT NULL
            )
        """)

        # prompt eval table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prompt_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                version INTEGER NOT NULL,
                sample_id INTEGER NOT NULL,

                previous_result TEXT NOT NULL,
                current_result TEXT NOT NULL,

                feedback TEXT,

                created_at TEXT NOT NULL,

                FOREIGN KEY (sample_id)
                    REFERENCES samples(id),

                FOREIGN KEY (version)
                    REFERENCES prompt_versions(version)
            )
            """
        )

        existing = conn.execute("SELECT COUNT(*) FROM prompt_versions").fetchone()[0]

        if existing == 0:
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
                    1,
                    "Initial prompt",
                    1,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
