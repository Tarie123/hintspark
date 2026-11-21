"""Learning analytics. Every event goes to Cloud Logging as structured JSON,
and to BigQuery if BQ_TABLE is set (project.dataset.table).
Privacy: learner code is never stored, only its length and a short hash."""
import json
import os
from datetime import datetime, timezone

BQ_TABLE = os.getenv("BQ_TABLE")
_client = None


def _bq():
    global _client
    if _client is None:
        from google.cloud import bigquery  # imported lazily so local dev works without GCP
        _client = bigquery.Client()
    return _client


def log_event(event: dict) -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
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
    print(json.dumps({"severity": "INFO", "message": "hintspark_event", "hintspark": row}), flush=True)
    if BQ_TABLE:
        try:
            errors = _bq().insert_rows_json(BQ_TABLE, [row])
            if errors:
                print(json.dumps({"severity": "WARNING", "message": f"BigQuery insert errors: {errors}"}))
        except Exception as e:  # analytics must never break learning
            print(json.dumps({"severity": "WARNING", "message": f"BigQuery unavailable: {e}"}))
