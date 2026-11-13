# Contributing to HintSpark
Setup: `python -m venv venv && source venv/Scripts/activate && pip install -r requirements-dev.txt`
Run: copy `.env.example` to `.env`, export the keys, `python wsgi.py`. Test: `pytest`. CI runs the same tests on every PR.

## Where your work goes (one owner per area, so PRs rarely collide)
| Area | Folder / files | Owner | Swap point |
|---|---|---|---|
| Learner experience | frontend/, backend/learning/, exercises.py | Tariro | annotate(), make_hint() |
| Execution trace | backend/trace/tracer.py | Ekuka | run(code) in tracer.py |
| Security | backend/trace/sandbox.py, Dockerfile | Mahammed | run_untrusted(code) |
| Analytics | backend/analytics/ | Rofiah | log(event) (e.g. BigQuery) |
| AI services | backend/services/ | shared | ask_nvidia(), ask_gemini_json() |

## Rules
1. Branch `yourname/topic`, change your own area, open a PR to `main`. Tests must pass.
2. Don't change the data shapes in CONTRACT.md without telling the people who consume them.
3. Never commit keys. No learner code or names in analytics events.
4. Add an exercise: append a dict to `backend/exercises.py` (id, title, description, expected, buggy code). `pytest` checks it is genuinely buggy.
