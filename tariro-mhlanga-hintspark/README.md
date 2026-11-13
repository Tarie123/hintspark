# HintSpark: see what your code actually did

**Author:** Tariro Mhlanga (learner experience) · **Team:** Ekuka (execution trace), Mahammed (security), Rofiah (learning analytics)

## The problem
A beginner runs their Python, gets the wrong output, and cannot see why. Typical AI tutors paste a corrected solution instead of showing *how the code executed*, so the learner is confused again at the next bug.

## What HintSpark does
An interactive execution-tracing tool for five predefined Python exercises:
- **Instrumented execution:** every line, call and return is recorded with the variable values.
- **Replay and visual state:** step through with Prev/Next; changed variables are highlighted.
- **Expected vs. actual:** line-by-line output comparison with pass/fail.
- **Make confusion visible:** a banner shows where the wrong value first appears, with a "Jump to the problem" button and plain-language notes ("`total` changed from 6 to 10").
- **Make it fixable:** a hint ladder (where to look, then which line to read, then an AI explanation) that never gives the corrected code, plus an attempts history so learners can change the code and compare.
- **Grounded explanations:** the explanation is written only from the real trace and must cite step numbers.

## Google Cloud and NVIDIA services
| Service | Use |
|---|---|
| **NVIDIA NIM** (`meta/llama-3.1-70b-instruct`) | Writes the explanation from the trace |
| **Google Gemini API** (`gemini-2.5-flash`) | Independently checks the explanation is grounded in the trace and does not reveal the fix; triggers one retry if not |
| **Google Cloud Run** | Hosts the web app (Dockerfile included) |
| *Planned:* BigQuery / Looker Studio | Learning analytics (events are already logged anonymously) |
| *Planned:* Secret Manager | API key storage |

## Architecture
See [docs/architecture.md](docs/architecture.md). Flask backend split into owner areas (`src/backend/`), static web frontend (`src/frontend/`), pytest suite and CI.

## Setup
```bash
cd src
python -m venv venv && source venv/Scripts/activate   # Windows Git Bash; use venv/bin/activate on Mac/Linux
pip install -r requirements-dev.txt
cp .env.example .env            # then export NVIDIA_API_KEY and GEMINI_API_KEY in your shell
python wsgi.py                  # http://localhost:5000
pytest                          # 8 tests
```
Keys: NVIDIA at build.nvidia.com, Gemini at aistudio.google.com. Hints 1 and 2 work without keys.
Deploy: `gcloud run deploy hintspark --source . --region europe-west1 --allow-unauthenticated --set-env-vars NVIDIA_API_KEY=...,GEMINI_API_KEY=...`

## Known limitations
- Learner code runs in a basic subprocess (time limit, API keys hidden). It is **not** a hardened sandbox, so do not expose it publicly without one.
- "Where the problem appears" is a heuristic: it finds where the final wrong value was made, which is not always the root cause.
- Five exercises only; not yet tested with a large group of real learners.

## What's next
Hardened sandbox on Cloud Run, user accounts, a teacher view of where a class gets stuck, BigQuery analytics, more exercises, and a Gemini tool-using coaching agent.

## License
MIT, see [LICENSE](LICENSE).
