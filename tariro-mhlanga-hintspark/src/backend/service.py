from .trace.sandbox import run_untrusted
from .learning.annotate import annotate
from .exercises import EXERCISES

def get_exercise(eid):
    return next(e for e in EXERCISES if e["id"] == eid)

def trace_exercise(ex, code):
    res = run_untrusted(code)
    res["expected"] = ex["expected"]
    res["passed"] = (not res["error"]) and res["output"].strip() == ex["expected"].strip()
    return annotate(res)
