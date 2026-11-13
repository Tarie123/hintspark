"""LEARNER-EXPERIENCE LAYER (owner: Tariro). Turns Ekuka's raw trace into things a beginner can read.
Input: trace dict from tracer.py (+ 'passed'). Adds per-step 'note' and a top-level 'key' (or None)."""

def annotate(res):
    prev = {}
    for s in res["steps"]:
        old, parts = prev.get(s["func"], {}), []
        for k in s["changed"]:
            v = s["vars"][k]
            if k == "<return>": parts.append(f"the function hands back {v}")
            elif k in old: parts.append(f"{k} changed from {old[k]} to {v}")
            else: parts.append(f"{k} now exists, set to {v}")
        s["note"] = "; ".join(parts) or "nothing changed on the previous line"
        prev[s["func"]] = s["vars"]
    res["key"] = None if res.get("passed") else find_key(res)
    return res

def find_key(res):
    """Where did the final (wrong) value get made? Heuristic: the variable equal to the returned value,
    walked back to the first step where it held that value."""
    steps = res["steps"]
    ret = next((s for s in steps if s["event"] == "return" and s["func"] != "<module>" and "<return>" in s["vars"]), None)
    if not ret: return None
    val = ret["vars"]["<return>"]
    var = next((k for k, v in ret["vars"].items() if k != "<return>" and v == val), None)
    if not var: return None
    fs = [s for s in steps if s["func"] == ret["func"] and s["n"] <= ret["n"]]
    idx = len(fs) - 1
    while idx > 0 and fs[idx - 1]["vars"].get(var) == val: idx -= 1
    return {"var": var, "val": val, "n": fs[idx]["n"],
            "cause_line": fs[idx - 1]["line"] if idx > 0 else fs[idx]["line"],
            "stuck": len(fs) - 1 - idx}

def make_hint(res, level):
    """Levels 1-2 are deterministic (no AI, no keys needed). Level 3 = AI explanation via /api/explain."""
    k = res.get("key")
    if res.get("passed"): return "Your output already matches. Nothing to fix!"
    if not k: return "Step through slowly and, at each step, say out loud what you expect each variable to be."
    if level == 1:
        return f"Watch the variable `{k['var']}`. Step through and find where it first becomes {k['val']}."
    return (f"`{k['var']}` first holds {k['val']} at step {k['n']}, right after line {k['cause_line']} ran. "
            f"Read that line out loud: what does it do to `{k['var']}`? Is that what you wanted?")
