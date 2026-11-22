"""
HintSpark sandboxed tracer.

Runs ONE learner program inside a fresh, isolated Python process and prints a
JSON execution trace to stdout. Launched by sandbox.py as:

    python -I runner.py   (payload JSON on stdin: {"code": ..., "stdin": ...})

Defence layers in this file (the container / gVisor sandbox is the outer layer):
  * CPU, memory and file-size limits (resource.setrlimit)
  * a restricted set of builtins (no open / eval / exec / compile)
  * an import allow-list
  * a PEP 578 audit hook that blocks file, network, process and ctypes access
  * a hard cap on traced steps (catches infinite loops early)
"""
import builtins
import io
import json
import sys
import types

if sys.platform != "win32":
    import resource

# Modules the learner is allowed to import. Import them now, before the
# sandbox closes, so the learner never triggers file access to load them.
import math, random, string  # noqa: E401,F401

ALLOWED_MODULES = {"math", "random", "string"}
LEARNER = "<learner>"
MAX_STEPS = 600
MAX_REPR = 200


class StepLimit(BaseException):
    """BaseException so a learner's `except Exception:` cannot swallow it."""


def safe_value(v):
    t = type(v).__name__
    try:
        r = repr(v)
    except Exception:
        r = f"<{t}>"
    if len(r) > MAX_REPR:
        r = r[: MAX_REPR - 3] + "..."
    out = {"type": t, "repr": r}
    # Mutable containers carry an object id so the UI can show when two
    # names point at the SAME list (exercise 5: aliasing).
    if isinstance(v, (list, dict, set)):
        out["id"] = id(v)
    return out


def snapshot(namespace):
    res = {}
    for k, v in list(namespace.items()):
        if k.startswith("__") or isinstance(v, types.ModuleType):
            continue
        if isinstance(v, (types.FunctionType, type)):
            res[k] = {"type": "function", "repr": f"function {getattr(v, '__name__', k)}()"}
            continue
        res[k] = safe_value(v)
    return res


def main():
    payload = json.loads(sys.stdin.read())
    code = payload["code"]
    stdin_lines = iter(payload.get("stdin", "").splitlines())

    # ---- resource limits ---------------------------------------------------
    if sys.platform != "win32":
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))

    real_stdout = sys.stdout
    out = io.StringIO()
    steps = []
    error = None

    # ---- learner-facing builtins ------------------------------------------
    def fake_input(prompt=""):
        out.write(str(prompt))
        try:
            return next(stdin_lines)
        except StopIteration:
            raise EOFError("The program asked for more input than was given")

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0 or name.split(".")[0] not in ALLOWED_MODULES:
            raise ImportError(f"Importing '{name}' is not allowed in HintSpark exercises")
        return real_import(name, globals, locals, fromlist, level)

    safe_builtins = dict(builtins.__dict__)
    for name in ("open", "eval", "exec", "compile", "breakpoint", "help", "memoryview", "__loader__", "__spec__"):
        safe_builtins.pop(name, None)
    safe_builtins["input"] = fake_input
    safe_builtins["__import__"] = guarded_import

    # ---- audit hook (cannot be removed once installed) ---------------------
    sandbox = {"active": False}
    blocked_prefixes = (
        "open", "socket.", "subprocess.", "os.system", "os.exec", "os.spawn",
        "os.posix_spawn", "os.fork", "os.kill", "os.remove", "os.rename",
        "os.rmdir", "os.mkdir", "os.chmod", "os.putenv", "os.unsetenv", "ctypes.",
        "shutil.", "urllib.", "http.", "ftplib.", "smtplib.", "webbrowser.",
        "code.__new__", "marshal.", "pickle.",
    )

    def audit(event, args):
        if sandbox["active"] and event.startswith(blocked_prefixes):
            raise PermissionError(f"'{event}' is not allowed in HintSpark exercises")

    # ---- tracer ------------------------------------------------------------
    def record(frame, event, arg):
        stack, f = [], frame
        while f is not None and f.f_code.co_filename == LEARNER:
            if f.f_code.co_name != "<module>":
                stack.append({"func": f.f_code.co_name, "line": f.f_lineno, "locals": snapshot(f.f_locals)})
            f = f.f_back
        stack.reverse()
        step = {
            "event": event,                  # line = about to run; return; exception
            "line": frame.f_lineno,
            "func": frame.f_code.co_name,
            "stack": stack,
            "globals": snapshot(frame.f_globals),
            "stdout_len": len(out.getvalue()),
        }
        if event == "return":
            step["return_value"] = safe_value(arg)
        elif event == "exception":
            step["exception"] = f"{arg[0].__name__}: {arg[1]}"
        steps.append(step)

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != LEARNER:
            return None
        if event in ("line", "return", "exception"):
            if len(steps) >= MAX_STEPS:
                raise StepLimit()
            record(frame, event, arg)
        return tracer

    # ---- compile -----------------------------------------------------------
    try:
        compiled = builtins.compile(code, LEARNER, "exec")
    except SyntaxError as e:
        error = {"type": "SyntaxError", "message": e.msg, "line": e.lineno}
        json.dump({"steps": [], "stdout": "", "error": error}, real_stdout)
        return

    g = {"__name__": "__main__", "__builtins__": safe_builtins}

    # ---- run ---------------------------------------------------------------
    sys.addaudithook(audit)
    sys.stdout = out
    sys.settrace(tracer)
    sandbox["active"] = True  # from here on, the learner cannot touch files/network/processes
    try:
        exec(compiled, g)
    except StepLimit:
        error = {
            "type": "StepLimit",
            "message": f"Stopped after {MAX_STEPS} steps - is there a loop that never ends?",
            "line": steps[-1]["line"] if steps else None,
        }
    except SystemExit:
        pass
    except BaseException as e:  # learner runtime error
        line, tb = None, e.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == LEARNER:
                line = tb.tb_lineno
            tb = tb.tb_next
        error = {"type": type(e).__name__, "message": str(e), "line": line}
    finally:
        sandbox["active"] = False
        sys.settrace(None)
        sys.stdout = real_stdout

    json.dump({"steps": steps, "stdout": out.getvalue(), "error": error}, real_stdout)


if __name__ == "__main__":
    main()
