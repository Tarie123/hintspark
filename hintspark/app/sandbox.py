"""Launches runner.py in a separate, short-lived Python process per run."""
import json
import os
# subprocess is needed to run learner code in a separate, short-lived process.
import subprocess  # nosec B404
import sys
import tempfile

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runner.py")
WALL_TIMEOUT_S = 5
MAX_OUTPUT_BYTES = 5 * 1024 * 1024


def _child_env() -> dict:
    """Allow-list (not deny-list) of environment variables for learner code.

    Learner code can read os.environ without raising any audit event, so the
    only safe option is to never hand it server secrets (DATABASE_URL,
    NVIDIA_API_KEY, or anything added later). See tests/test_sandbox_escape.py.
    """
    env = {"LANG": "C.UTF-8"}
    if sys.platform == "win32":
        # Python on Windows needs SYSTEMROOT to start and for os.urandom.
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    else:
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    return env


def run_code(code: str, stdin: str = "") -> dict:
    child_env = _child_env()

    try:
        # Fixed argument list, no shell; untrusted code goes in via stdin, never the command line.
        proc = subprocess.run(  # nosec B603
            [sys.executable, "-I", RUNNER],
            input=json.dumps({"code": code, "stdin": stdin}),
            capture_output=True,
            text=True,
            timeout=WALL_TIMEOUT_S,
            env=child_env,
            cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired:
        return _fail("Timeout", f"Your program ran for more than {WALL_TIMEOUT_S} seconds and was stopped.")

    if len(proc.stdout) > MAX_OUTPUT_BYTES:
        return _fail("OutputLimit", "Your program produced too much output.")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        # Killed by the CPU / memory limit, or the sandbox itself failed.
        return _fail("ResourceLimit", "Your program used too much time or memory and was stopped.")


def _fail(kind: str, message: str) -> dict:
    return {"steps": [], "stdout": "", "error": {"type": kind, "message": message, "line": None}}
