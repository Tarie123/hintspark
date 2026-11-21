# ⚡ HintSpark

An interactive execution tracer for beginner Python programmers. Learners replay
what their program actually did, see the first step where the output goes
wrong, and get explanations grounded in the real trace. The AI never hands
over the fix.

**Make the confusion visible first, then make it fixable.**

## What's in the MVP

| Feature | Where |
|---|---|
| 5 exercises, each built around one classic bug | `app/exercises.py` |
| Code runs in a sandbox and every step is traced (`sys.settrace`) | `app/runner.py`, `app/sandbox.py` |
| Visual trace: step slider, current line, variables, changed values, "same list as" badges, output so far | `static/app.js` |
| Expected-vs-actual output with the **first divergence step** | `app/grader.py` |
| Explanations from an NVIDIA-hosted LLM, tied to step and line numbers | `app/explain.py` |
| Guardrails: no code blocks, no fixes, no explanation that doesn't cite the trace | `app/explain.py` |
| Learning analytics → Cloud Logging + BigQuery | `app/analytics.py`, `analytics/` |
| One-command deploy to Cloud Run | `deploy.sh` |

### The five exercises

1. **Count to five**: off-by-one in `range()`
2. **Add up the scores**: running total reset inside the loop
3. **Double a number**: `print` instead of `return`, so the function gives back `None`
4. **Next year's age**: `input()` returns text, which causes a `TypeError`
5. **Keep a backup**: two names point at the same list (aliasing)

## Architecture

```
Browser (static/)  ──►  Cloud Run: FastAPI (app/main.py)
                          ├─ sandbox.py ─► runner.py  (fresh Python process per run:
                          │                           rlimits + audit hook + import allow-list,
                          │                           inside Cloud Run's gVisor sandbox)
                          ├─ grader.py   expected vs actual, first divergence step
                          ├─ explain.py ─► NVIDIA API (OpenAI-compatible) + guardrails
                          │               └─ fallback: rule-based hints from the same trace
                          └─ analytics.py ─► Cloud Logging + BigQuery ─► Looker Studio
Secrets: NVIDIA_API_KEY in Secret Manager, mounted as an env var
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
export NVIDIA_API_KEY=nvapi-...      # optional; without it you get built-in hints
uvicorn app.main:app --reload --port 8080
# open http://localhost:8080
pytest -q                            # 19 tests: exercises, sandbox, guardrails
```

## Deploy to Google Cloud

```bash
gcloud auth login
export PROJECT_ID=your-project-id
export NVIDIA_API_KEY=nvapi-...      # get one at build.nvidia.com
./deploy.sh                          # REGION defaults to us-central1
```

`deploy.sh` enables the APIs, creates a least-privilege service account, stores
the NVIDIA key in Secret Manager, creates the BigQuery table, and deploys to
Cloud Run with the gVisor (gen1) execution environment.

### NVIDIA options

* **Hosted (default):** NVIDIA API at `integrate.api.nvidia.com`. Change the model
  with `NVIDIA_MODEL` (default `meta/llama-3.1-70b-instruct`). Check build.nvidia.com
  for the models currently available to your key.
* **Self-hosted NIM:** run an NVIDIA NIM container on GKE with a GPU node pool and set
  `NVIDIA_BASE_URL=http://<nim-service>/v1`. No code changes are needed because the
  API is OpenAI-compatible.
* **NeMo Guardrails** (stretch goal): put it in front of the model for policy rails.
  `guardrail()` in `explain.py` already blocks code blocks and the exact fixes listed
  in each exercise's `solution_markers`.

## Security model (Mahammed)

The learner's code is untrusted, so there are several layers of protection:

1. **Cloud Run gen1 (gVisor)**: kernel-level isolation for the whole container.
2. **One process per run**, as a non-root user, with an empty environment, so secrets
   such as `NVIDIA_API_KEY` are never visible to learner code.
3. **rlimits**: 2 s CPU, 512 MB memory, 1 MB file writes; a 5 s wall-clock timeout.
4. **Restricted builtins**: no `open`, `eval`, `exec`, `compile`. Imports are limited
   to `math`, `random` and `string`.
5. **PEP 578 audit hook**: blocks file, socket, subprocess, `os.*` and ctypes events,
   even if the learner escapes through object introspection.
6. **Step cap** (600) to catch infinite loops; input limits (2,000 chars).
7. **API**: rate limits, strict CSP (no third-party scripts, since CodeMirror is
   bundled), no `/docs`, and explanations always re-run the code on the server
   instead of trusting a trace sent by the browser.
8. **Privacy**: analytics store a code hash and length, never the code itself.

For production, also add: Cloud Armor (WAF + rate limiting) in front of a load
balancer, Identity Platform sign-in, and VPC egress controls.

## Learning analytics (Rofiah)

`analytics/metrics.sql` holds ready-made BigQuery queries:

1. Solve rate and median time-to-fix per exercise
2. Runs and hints needed before the first pass
3. "About to quit" learners (3+ failed runs, never passed)
4. Solve rate with vs without "Jump to where it went wrong"
5. NVIDIA vs fallback explanation share

Connect the `hintspark.events` table to Looker Studio for the dashboard.

## Team map

| Person | Owns |
|---|---|
| Tariro (learner experience) | `static/`: the step story, the divergence jump, the 3-fail nudge, hint wording in `exercises.py` |
| Ekuka (cloud engineering) | `runner.py`, `sandbox.py`, `grader.py`, `deploy.sh`, NVIDIA integration |
| Mahammed (cybersecurity) | Sandbox layers, Secret Manager, CSP, rate limits, Cloud Armor |
| Rofiah (data analytics) | `analytics.py`, BigQuery schema, `metrics.sql`, dashboard |

## Adding an exercise

Add a dict to `EXERCISES` in `app/exercises.py` with these fields: `starter` (the
buggy code), `tests` (stdin + expected output), `watch` (variables to track),
`hints` (gentle to specific), and `solution_markers` (fixes the AI must not reveal).
Then add the fixed version to `FIXED` in the tests.
