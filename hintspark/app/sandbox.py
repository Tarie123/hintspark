"""Launches runner.py in a separate, short-lived Python process per run."""
import json
import os
import subprocess
import sys

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runner.py")
WALL_TIMEOUT_S = 5
MAX_OUTPUT_BYTES = 5 * 1024 * 1024


def run_code(code: str, stdin: str = "") -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, "-I", RUNNER],
            input=json.dumps({"code": code, "stdin": stdin}),
            capture_output=True,
            text=True,
            timeout=WALL_TIMEOUT_S,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"},  # no secrets leak in
            cwd="/tmp",
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
