# Data contracts (keep stable)
tracer.run(code) / sandbox.run_untrusted(code) -> {steps, output, error}
step = {n, line, func, event: call|line|return, vars: {name: repr}, changed: [name], out: int}
service.trace_exercise() adds expected, passed, per-step note, and key = {var, val, n, cause_line, stuck} | null
API: GET /api/exercises | POST /api/trace, /api/hint (level 1-2), /api/explain, /api/event
Event: {ts, sid, exercise_id, type: run|hint|pass|step_nav|jump, level, attempt, passed, hints}. Anonymous only.
