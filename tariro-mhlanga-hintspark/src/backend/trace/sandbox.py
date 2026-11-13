"""SECURITY (owner: Mahammed). run_untrusted() is the ONLY place learner code is executed.
Replace the internals (container, gVisor, nsjail, Cloud Run job...) but keep the signature and return shape."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))

def safe_env():
    bad = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    return {k: v for k, v in os.environ.items() if not any(w in k.upper() for w in bad)}

def run_untrusted(code, timeout=5):
    """-> {"steps": [...], "output": str, "error": str|None}  (see CONTRACT.md)"""
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "tracer.py")], input=code[:4000],
                           capture_output=True, text=True, timeout=timeout, env=safe_env())
        return json.loads(r.stdout)
    except subprocess.TimeoutExpired:
        return {"steps": [], "output": "", "error": "Timed out (possible infinite loop)"}
    except Exception:
        return {"steps": [], "output": "", "error": "Tracer failed"}
