"""Security regression tests: learner code must not be able to switch off the
sandbox's audit hook and then read files.

Background: the PEP 578 audit hook in runner.py lives in the same process as
the learner's code. Learner code can walk the call stack
(exception traceback -> frame -> f_back) to reach runner.main()'s locals and
runner.py's module globals, including the real `builtins.open`. So the hook
must not depend on ANY state the learner could modify.

Each test plants a harmless canary file, tries one tampering route, then tries
to read the canary with the real `open`. It must never appear in the output.
The tests only read a temp file they created themselves.
"""
import pytest

from app.sandbox import run_code

CANARY = "HINTSPARK-CANARY-7f3a"

# Find runner.main()'s frame, apply one tampering step, then read the file.
ESCAPE_TEMPLATE = """
try:
    raise ValueError("x")
except ValueError as e:
    f = e.__traceback__.tb_frame
while f is not None and "tracer" not in f.f_locals:
    f = f.f_back
{tamper}
real_open = f.f_globals["builtins"].open
print(real_open({path!r}).read())
"""

TAMPER_ROUTES = {
    # A: no tampering, just call the real open() taken from runner's globals.
    "direct_real_open": "pass",
    # B: flip an on/off flag, if one exists (the original bug).
    "flip_active_flag": 'f.f_locals.get("sandbox", {})["active"] = False',
    # C: empty the block list via the write-through frame proxy (Python 3.13+).
    "empty_block_list": 'f.f_locals["blocked_prefixes"] = ()',
    # D: replace the audit hook's code with a function that allows everything.
    "replace_hook_code": 'f.f_locals["audit"].__code__ = (lambda event, args: None).__code__',
}


@pytest.mark.parametrize("tamper", TAMPER_ROUTES.values(), ids=TAMPER_ROUTES.keys())
def test_learner_cannot_disable_audit_hook_and_read_files(tmp_path, tamper):
    canary_file = tmp_path / "canary.txt"
    canary_file.write_text(CANARY)

    result = run_code(ESCAPE_TEMPLATE.format(tamper=tamper, path=str(canary_file)))

    assert CANARY not in result["stdout"], (
        "Sandbox escape: learner code tampered with the audit hook and read a file"
    )


# Reading os.environ raises NO audit event, so the hook cannot protect it.
# The only defence is to never give secrets to the learner process at all.
READ_ENV = """
try:
    raise ValueError("x")
except ValueError as e:
    f = e.__traceback__.tb_frame
while f is not None and "tracer" not in f.f_locals:
    f = f.f_back
env = f.f_globals["sys"].modules["os"].environ
print(sorted(env.items()))
"""


def test_learner_process_gets_no_server_secrets(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://" + CANARY)
    monkeypatch.setenv("HINTSPARK_ANY_OTHER_SECRET", CANARY)

    result = run_code(READ_ENV)

    assert result["error"] is None, result["error"]  # make sure the env really was read
    assert CANARY not in result["stdout"], "Server secrets leaked into the learner process"
