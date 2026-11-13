from ..services.nvidia import ask_nvidia
from ..services.gemini import ask_gemini_json

SYSTEM = ("You are a patient Python tutor for beginners. Explain why the actual output differs from the expected "
          "output using ONLY the trace provided. Cite step numbers like [step 7]. Point to the first step where "
          "behaviour goes wrong and say what the variables show there. NEVER write corrected code or the exact fix; "
          "end with one guiding question. Max 150 words.")

def trace_text(code, res):
    lines = [f"{i+1}: {l}" for i, l in enumerate(code.splitlines())]
    ev = [f"[step {s['n']}] line {s['line']} in {s['func']}: " + ", ".join(f"{k}={s['vars'][k]}" for k in s["changed"])
          for s in res["steps"] if s["changed"]][:120]
    return ("CODE:\n" + "\n".join(lines) + "\n\nTRACE (variables changed at each step):\n" + "\n".join(ev) +
            f"\n\nEXPECTED OUTPUT: {res['expected']}\nACTUAL OUTPUT: {res['output'].strip()}\nERROR: {res['error']}")

def explain(code, res):
    """NVIDIA writes, Gemini verifies; one retry. Raises KeyError if an API key env var is missing."""
    if res["passed"]:
        return {"explanation": "Output matches the expected result. Nothing to debug!", "verification": None}
    ctx, issues, text, v = trace_text(code, res), "", "", None
    for _ in range(2):
        text = ask_nvidia(SYSTEM + issues, ctx)
        v = ask_gemini_json('Return JSON {"grounded": bool, "leaks_solution": bool, "issues": [str]}. grounded = every '
                            'claim and step citation in EXPLANATION is supported by TRACE. leaks_solution = it gives '
                            'corrected code or the exact fix.\n\n' + ctx + "\n\nEXPLANATION:\n" + text)
        if v.get("grounded") and not v.get("leaks_solution"):
            break
        issues = "\nFix these problems from the last attempt: " + "; ".join(v.get("issues", []))
    return {"explanation": text, "verification": v}
