"""LEARNING EVENTS (owner: Rofiah). Anonymous only: random session id, no code, no names.
MVP writes JSONL; swap log() for a BigQuery insert (google-cloud-bigquery) to analyse on Google Cloud."""
import json, time
ALLOWED = {"run", "hint", "pass", "step_nav", "jump"}
def log(e):
    if e.get("type") not in ALLOWED: return
    row = {"ts": time.time(), "sid": str(e.get("sid", ""))[:16], "exercise_id": e.get("exercise_id"),
           "type": e["type"], "level": e.get("level"), "attempt": e.get("attempt"),
           "passed": e.get("passed"), "hints": e.get("hints")}
    with open("events.jsonl", "a") as f: f.write(json.dumps(row) + "\n")
