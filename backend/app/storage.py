"""Persistent storage for question history (Neon / Postgres).

Deliberately tiny and DB-access is isolated here so the rest of the app never
touches SQL directly - if we ever swap Neon for another Postgres host (or add a
connection pool), only this file changes. Connect-per-call is intentional: at
this app's scale the per-request connect cost is negligible, and it avoids the
complexity of managing a pool.
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")

SCHEMA = """
create table if not exists questions (
    id           bigint generated always as identity primary key,
    study_set_id text        not null,
    question     text        not null,
    answer       text        not null,
    sources      jsonb,
    created_at   timestamptz not null default now()
);
create index if not exists questions_study_set_idx
    on questions (study_set_id, created_at);
"""


def _connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set (see backend/.env)")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db() -> None:
    """Idempotent - safe to call on every startup."""
    with _connect() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def save_question(study_set_id: str, question: str, answer: str, sources: list) -> dict:
    with _connect() as conn:
        row = conn.execute(
            """insert into questions (study_set_id, question, answer, sources)
               values (%s, %s, %s, %s)
               returning id, study_set_id, question, answer, sources, created_at""",
            (study_set_id, question, answer, Jsonb(sources)),
        ).fetchone()
        conn.commit()
        return row


def get_history(study_set_id: str) -> list[dict]:
    """Oldest first, so the frontend can render a top-to-bottom thread."""
    with _connect() as conn:
        return conn.execute(
            """select id, study_set_id, question, answer, sources, created_at
               from questions
               where study_set_id = %s
               order by created_at asc""",
            (study_set_id,),
        ).fetchall()
