"""Grounded explanations with an NVIDIA-hosted LLM.

"Grounded" means the model only sees facts from the real execution trace
(step numbers, line numbers, variable values, output so far). Answers that
don't cite a step or line are rejected, and the fix is never handed over.
If NVIDIA is unavailable, a rule-based hint built from the same trace is used.
"""
import os
import re

import httpx

NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")

SYSTEM_PROMPT = """You are HintSpark, a patient tutor for complete beginners learning Python.
You explain what the learner's program ACTUALLY did, using ONLY the execution trace provided.
Rules:
- Mention specific step numbers and line numbers from the trace.
- Use plain, friendly words and short sentences. Maximum 110 words.
- NEVER write corrected code and never state the exact fix. Show the moment things went wrong and what the variable values reveal.
- Do not invent values that are not in the trace.
- End with ONE question that helps the learner discover the fix themselves.
- If all tests pass, briefly say what the program did correctly."""


# ---------- trace formatting (shared by prompt and fallback) ---------------
def fmt_vars(step: dict) -> str:
    parts = [f"{k}={v['repr']}" for k, v in step["globals"].items() if v["type"] != "function"]
    for fr in step["stack"]:
        inner = ", ".join(f"{k}={v['repr']}" for k, v in fr["locals"].items())
        parts.append(f"[inside {fr['func']}()] {inner or 'no variables'}")
    return "; ".join(parts) or "no variables yet"


def describe_step(i: int, step: dict, lines: list, stdout: str) -> str:
    src = lines[step["line"] - 1].strip() if 0 < step["line"] <= len(lines) else ""
    if step["event"] == "line":
        s = f"Step {i}: about to run line {step['line']} `{src}`"
    elif step["event"] == "return":
        s = (f"Step {i}: program finished" if step["func"] == "<module>"
             else f"Step {i}: {step['func']}() returns {step['return_value']['repr']} (line {step['line']})")
    else:
        s = f"Step {i}: error on line {step['line']} `{src}` -> {step.get('exception')}"
    return f"{s} | variables: {fmt_vars(step)} | output so far: {stdout[:step['stdout_len']]!r}"


def watch_history(ex: dict, steps: list) -> str:
    out = []
    for name in ex["watch"]:
        changes, last = [], object()
        for i, s in enumerate(steps):
            v = s["globals"].get(name)
            if v is None and s["stack"]:
                v = s["stack"][-1]["locals"].get(name)
            r = v["repr"] if v else None
            if r != last and r is not None:
                changes.append(f"step {i}: {r}")
            last = r
        if changes:
            out.append(f"{name}: " + ", ".join(changes[:14]))
    return "\n".join(out) or "(watched variables never set)"


def build_prompt(ex: dict, code: str, graded: dict, center: int):
    lines = code.split("\n")
    trace = graded["trace"]
    steps = trace["steps"]
    test = graded["tests"][graded["focus_test"]]
    div = graded["divergence"]
    window = list(range(max(0, center - 6), min(len(steps), center + 3)))
    numbered = "\n".join(f"{n + 1:>2} | {l}" for n, l in enumerate(lines))
    trace_txt = "\n".join(describe_step(i, steps[i], lines, trace["stdout"]) for i in window) or "(program did not run)"
    err = test["error"]
    user = f"""EXERCISE GOAL: {ex['goal']}
CONCEPT PRACTISED: {ex['concept']}
LEARNER'S CODE:
{numbered}
INPUT GIVEN: {test['stdin']!r}
EXPECTED OUTPUT: {test['expected']!r}
ACTUAL OUTPUT: {test['actual']!r}
ERROR: {f"{err['type']}: {err['message']} (line {err['line']})" if err else 'none'}
WHERE IT FIRST WENT WRONG: {div['message'] if div else 'nowhere - all tests pass'}
THE LEARNER IS LOOKING AT: step {center}
TRACE EXCERPT:
{trace_txt}
HOW THE KEY VARIABLES CHANGED:
{watch_history(ex, steps)}

Explain what happened around step {center} and why the output is not what was expected."""
    return user, window


# ---------- guardrails ------------------------------------------------------
def guardrail(text: str, ex: dict) -> str:
    text = re.sub(r"```.*?```", "[code removed - try writing this part yourself]", text, flags=re.S)
    squashed = lambda s: re.sub(r"\s+", "", s)
    for marker in ex["solution_markers"]:
        if squashed(marker) in squashed(text):
            pattern = r"\s*".join(map(re.escape, squashed(marker)))
            text = re.sub(pattern, "[the fix - see if you can work it out]", text)
    return text.strip()


def is_grounded(text: str) -> bool:
    return re.search(r"\b(step|line)s?\s+\d+", text, re.I) is not None


# ---------- fallback --------------------------------------------------------
def fallback(ex: dict, graded: dict, center: int, hint_level: int) -> str:
    if graded["all_passed"]:
        return "All tests pass. Step through the trace to see how each line built up the right output."
    steps = graded["trace"]["steps"]
    parts = [graded["divergence"]["message"]] if graded["divergence"] else []
    if steps:
        parts.append(f"At step {center} the variables are: {fmt_vars(steps[center])}.")
    parts.append(ex["hints"][min(hint_level, len(ex["hints"]) - 1)])
    return " ".join(parts)


# ---------- main entry ------------------------------------------------------
async def call_nvidia(user_prompt: str):
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        return None
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.post(
            f"{NVIDIA_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            json={
                "model": NVIDIA_MODEL,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": user_prompt}],
                "temperature": 0.2,
                "max_tokens": 300,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def explain(ex: dict, code: str, graded: dict, step, hint_level: int) -> dict:
    steps = graded["trace"]["steps"]
    div = graded["divergence"]
    if step is None:
        step = div["step"] if div and div.get("step") is not None else max(len(steps) - 1, 0)
    center = min(max(step, 0), max(len(steps) - 1, 0))

    user_prompt, window = build_prompt(ex, code, graded, center)
    source = "nvidia"
    try:
        text = await call_nvidia(user_prompt)
    except Exception:
        text = None
    if text:
        text = guardrail(text, ex)
        if not is_grounded(text):
            text, source = None, "fallback-ungrounded"
    if not text:
        text = fallback(ex, graded, center, hint_level)
        source = "fallback" if source == "nvidia" else source

    return {
        "explanation": text,
        "source": source,
        "step": center,
        "grounded_steps": [window[0], window[-1]] if window else [],
    }
