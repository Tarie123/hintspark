"""Learning analytics stored in Supabase PostgreSQL.

Learner code is never stored, only its length and a short hash.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
_pool = None
_pool_url = None


def _connection_pool(database_url: str):
    """Get a small process-local pool; recreate it if configuration changes."""
    global _pool, _pool_url

    if _pool is not None and _pool_url == database_url:
        return _pool

    if _pool is not None:
        try:
            _pool.close()
        except Exception as exc:
            # Log only the error TYPE: the message could contain connection details.
            print(json.dumps({"severity": "WARNING", "message": f"Closing old DB pool failed: {type(exc).__name__}"}), flush=True)

    from psycopg_pool import ConnectionPool

    _pool = ConnectionPool(
        conninfo=database_url,
        min_size=0,
        max_size=4,
        timeout=3,
        open=True,
        kwargs={"connect_timeout": 3},
    )
    _pool_url = database_url
    return _pool


def log_event(event: dict) -> bool:
    row = {
        "ts": datetime.now(timezone.utc),
        "session_id": str(event.get("session_id", "anon"))[:64],
        "exercise_id": event.get("exercise_id"),
        "event_type": event.get("event_type"),
        "passed": event.get("passed"),
        "step": event.get("step"),
        "hint_level": event.get("hint_level"),
        "source": event.get("source"),
        "code_hash": event.get("code_hash"),
        "code_len": event.get("code_len"),
        "detail": (event.get("detail") or "")[:200] or None,
    }

    print(json.dumps({"severity": "INFO", "message": "hintspark_event", "hintspark": row}, default=str), flush=True)

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print(json.dumps({"severity": "WARNING", "message": "DATABASE_URL is not configured; event logged locally only"}), flush=True)
        return False

    try:
        import psycopg

        values = (
            row["ts"], row["session_id"], row["exercise_id"], row["event_type"],
            row["passed"], row["step"], row["hint_level"], row["source"],
            row["code_hash"], row["code_len"], row["detail"],
        )

        pool = _connection_pool(database_url)

        with pool.connection(timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.learning_events
                        (ts, session_id, exercise_id, event_type, passed, step,
                         hint_level, source, code_hash, code_len, detail)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    values,
                )
        return True
    except ImportError:
        print(json.dumps({"severity": "WARNING", "message": "PostgreSQL driver is not installed; event logged locally only"}), flush=True)
    except Exception as exc:
        print(json.dumps({"severity": "WARNING", "message": f"Supabase unavailable; event logged locally only: {type(exc).__name__}"}), flush=True)

    return False


def record_event(
    event_type: str,
    session_id: str = "anon",
    exercise_id: str | None = None,
    payload: dict | None = None,
) -> bool:
    """Record a learner event using the application's existing event schema."""
    payload = payload or {}
    return log_event({
        "session_id": session_id,
        "exercise_id": exercise_id,
        "event_type": event_type,
        "passed": payload.get("passed"),
        "step": payload.get("step"),
        "hint_level": payload.get("hint_level"),
        "source": payload.get("source"),
        "code_hash": payload.get("code_hash"),
        "code_len": payload.get("code_len"),
        "detail": payload.get("detail"),
    })
