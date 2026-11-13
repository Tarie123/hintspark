"""Instrumented executor: runs student code under sys.settrace and prints a JSON trace.
Run as a subprocess: python tracer.py < code.py"""
import sys, json, io, contextlib

MAX_STEPS = 400

def run(code):
    steps, out, prev = [], io.StringIO(), {}

    def snap(f):
        return {k: repr(v)[:60] for k, v in f.f_locals.items()
                if not k.startswith("__") and not callable(v)}

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != "<student>":
            return None
        if event in ("call", "line", "return"):
            if len(steps) >= MAX_STEPS:
                raise RuntimeError("Step limit reached (possible infinite loop)")
            v = snap(frame)
            if event == "return":
                v["<return>"] = repr(arg)[:60]
            old = prev.get(id(frame), {})
            changed = [k for k in v if old.get(k) != v[k]]
            prev[id(frame)] = v
            steps.append({"n": len(steps) + 1, "line": frame.f_lineno, "func": frame.f_code.co_name,
                          "event": event, "vars": v, "changed": changed, "out": out.tell()})
        return tracer

    error = None
    sys.settrace(tracer)
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(code, "<student>", "exec"), {"__name__": "__main__"})
    except BaseException as e:
        error = f"{type(e).__name__}: {e}"
    finally:
        sys.settrace(None)
    return {"steps": steps, "output": out.getvalue(), "error": error}

if __name__ == "__main__":
    try:
        import resource  # Linux: cap CPU time and memory
        resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    except Exception:
        pass
    print(json.dumps(run(sys.stdin.read())))
