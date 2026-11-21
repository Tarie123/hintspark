"""Expected-vs-actual comparison and divergence detection.

The divergence is the trace step that produced the first wrong (or missing)
output line, or the step where the error happened. The UI jumps straight to
it, so the learner sees the moment the confusion starts."""


def _lines(text: str) -> list:
    text = (text or "").rstrip()
    return [l.rstrip() for l in text.split("\n")] if text else []


def passed(expected: str, actual: str, error) -> bool:
    return error is None and _lines(expected) == _lines(actual)


def _first_mismatch(expected: str, actual: str):
    e, a = _lines(expected), _lines(actual)
    for i in range(max(len(e), len(a))):
        el = e[i] if i < len(e) else None
        al = a[i] if i < len(a) else None
        if el != al:
            return i, el, al
    return None


def _step_that_printed(steps: list, actual: str, line_idx: int) -> int:
    """Each step records stdout length BEFORE its line runs, so the culprit is
    the line event just before output first grows past this line's start."""
    raw = actual.split("\n")
    offset = sum(len(l) + 1 for l in raw[:line_idx])
    j = next((k for k, s in enumerate(steps) if s["stdout_len"] > offset), len(steps))
    k = max(j - 1, 0)
    while k > 0 and steps[k]["event"] != "line":
        k -= 1
    return k


def find_divergence(trace: dict, expected: str):
    steps, actual, error = trace["steps"], trace["stdout"], trace["error"]
    mm = _first_mismatch(expected, actual)

    if mm and mm[2] is not None and steps:
        i, el, al = mm
        idx = _step_that_printed(steps, actual, i)
        exp_txt = "nothing" if el is None else repr(el)
        return {
            "kind": "output", "step": idx, "line": steps[idx]["line"],
            "expected": el, "actual": al,
            "message": f"Output line {i + 1} is wrong: expected {exp_txt} but got {al!r}. "
                       f"It was printed by line {steps[idx]['line']} (step {idx}).",
        }

    if error:
        idx = None
        if steps:
            exc = [k for k, s in enumerate(steps) if s["event"] == "exception"]
            idx = exc[0] if exc else len(steps) - 1
        where = f" on line {error['line']}" if error.get("line") else ""
        at_step = f" (step {idx})" if idx is not None else ""
        return {
            "kind": "error", "step": idx, "line": error.get("line"),
            "expected": mm[1] if mm else None, "actual": None,
            "message": f"Your program stopped with {error['type']}{where}{at_step}: {error['message']}",
        }

    if mm:  # output missing at the end
        i, el, _ = mm
        idx = len(steps) - 1 if steps else None
        return {
            "kind": "missing", "step": idx, "line": steps[idx]["line"] if steps else None,
            "expected": el, "actual": None,
            "message": f"Your program finished without printing expected line {i + 1}: {el!r}.",
        }
    return None


def grade(ex: dict, results: list) -> dict:
    tests = []
    for t, r in zip(ex["tests"], results):
        tests.append({
            "stdin": t["stdin"], "expected": t["expected"], "actual": r["stdout"],
            "error": r["error"], "passed": passed(t["expected"], r["stdout"], r["error"]),
        })
    all_passed = all(t["passed"] for t in tests)
    focus = 0 if all_passed else next(i for i, t in enumerate(tests) if not t["passed"])
    trace = results[focus]
    return {
        "all_passed": all_passed,
        "tests": tests,
        "focus_test": focus,
        "trace": trace,
        "divergence": None if all_passed else find_divergence(trace, ex["tests"][focus]["expected"]),
    }
