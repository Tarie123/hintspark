"""HintSpark API + static front end (single Cloud Run service)."""
import asyncio
import hashlib
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analytics import log_event
from .exercises import BY_ID, EXERCISES, public_view
from .explain import explain
from .grader import grade
from .sandbox import run_code

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MAX_CODE_CHARS = 2000
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
EVENT_TYPES = {"open", "step_view", "jump_to_divergence", "reset", "nudge_shown"}

app = FastAPI(title="HintSpark", docs_url=None, redoc_url=None, openapi_url=None)


# ---------- security: headers + simple rate limiting ------------------------
@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


class RateLimiter:
    """Per-instance sliding window. Put Cloud Armor in front for real abuse control."""

    def __init__(self, limit: int, window_s: int):
        self.limit, self.window, self.hits = limit, window_s, defaultdict(deque)

    def check(self, key: str):
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(429, "You're going a bit fast - wait a few seconds and try again.")
        q.append(now)


run_limit, explain_limit = RateLimiter(30, 60), RateLimiter(10, 60)


def client_key(req: Request) -> str:
    xff = req.headers.get("x-forwarded-for")
    return xff.split(",")[0].strip() if xff else (req.client.host if req.client else "unknown")


# ---------- models ----------------------------------------------------------
class RunRequest(BaseModel):
    exercise_id: str = Field(max_length=10)
    code: str = Field(max_length=MAX_CODE_CHARS)
    session_id: str = Field(default="anon", max_length=64)


class ExplainRequest(RunRequest):
    step: Optional[int] = Field(default=None, ge=0, le=1000)
    hint_level: int = Field(default=0, ge=0, le=20)


class EventRequest(BaseModel):
    session_id: str = Field(max_length=64)
    exercise_id: str = Field(max_length=10)
    event_type: str = Field(max_length=32)
    step: Optional[int] = Field(default=None, ge=0, le=1000)
    detail: Optional[str] = Field(default=None, max_length=200)


# ---------- helpers ---------------------------------------------------------
def get_exercise(eid: str) -> dict:
    ex = BY_ID.get(eid)
    if not ex:
        raise HTTPException(404, "Unknown exercise")
    return ex


async def run_and_grade(ex: dict, code: str) -> dict:
    results = await asyncio.gather(*[asyncio.to_thread(run_code, code, t["stdin"]) for t in ex["tests"]])
    return grade(ex, list(results))


def code_fingerprint(code: str) -> dict:
    return {"code_hash": hashlib.sha256(code.encode()).hexdigest()[:12], "code_len": len(code)}


# ---------- routes ----------------------------------------------------------
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/exercises")
def list_exercises():
    return [public_view(e) for e in EXERCISES]


@app.post("/api/run")
async def run(req: RunRequest, request: Request, bg: BackgroundTasks):
    run_limit.check(client_key(request))
    ex = get_exercise(req.exercise_id)
    graded = await run_and_grade(ex, req.code)
    div = graded["divergence"]
    bg.add_task(log_event, {
        "session_id": req.session_id, "exercise_id": ex["id"], "event_type": "run",
        "passed": graded["all_passed"], "step": div["step"] if div else None,
        "detail": div["kind"] if div else None, **code_fingerprint(req.code),
    })
    return graded


@app.post("/api/explain")
async def explain_route(req: ExplainRequest, request: Request, bg: BackgroundTasks):
    explain_limit.check(client_key(request))
    ex = get_exercise(req.exercise_id)
    graded = await run_and_grade(ex, req.code)  # re-run server-side: never trust a client-sent trace
    result = await explain(ex, req.code, graded, req.step, req.hint_level)
    bg.add_task(log_event, {
        "session_id": req.session_id, "exercise_id": ex["id"], "event_type": "explain",
        "passed": graded["all_passed"], "step": result["step"], "hint_level": req.hint_level,
        "source": result["source"], **code_fingerprint(req.code),
    })
    return result


@app.post("/api/event")
async def event(req: EventRequest, bg: BackgroundTasks):
    if req.event_type not in EVENT_TYPES or req.exercise_id not in BY_ID:
        raise HTTPException(400, "Unknown event")
    bg.add_task(log_event, req.model_dump())
    return {"ok": True}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
