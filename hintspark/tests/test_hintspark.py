"""Run with:  pytest -q"""
import pytest
from fastapi.testclient import TestClient

from app.exercises import BY_ID, EXERCISES
from app.explain import guardrail
from app.main import app
from app.sandbox import run_code

client = TestClient(app)

FIXED = {
    "ex1": "for i in range(1, 6):\n    print(i)\n",
    "ex2": "scores = [3, 5, 2]\ntotal = 0\nfor s in scores:\n    total = total + s\nprint(\"Total:\", total)\n",
    "ex3": "def double(n):\n    return n * 2\n\nresult = double(4)\nprint(\"Result is\", result)\n",
    "ex4": "age = int(input())\nnext_year = age + 1\nprint(\"Next year you will be\", next_year)\n",
    "ex5": "original = [1, 2, 3]\nbackup = original.copy()\nbackup.append(4)\nprint(\"Original:\", original)\nprint(\"Backup:\", backup)\n",
}

EXPECTED_DIVERGENCE = {"ex1": ("missing", None), "ex2": ("output", 5), "ex3": ("output", 2),
                       "ex4": ("error", 2), "ex5": ("output", 4)}


@pytest.mark.parametrize("ex", EXERCISES, ids=lambda e: e["id"])
def test_starter_fails_with_divergence(ex):
    r = client.post("/api/run", json={"exercise_id": ex["id"], "code": ex["starter"]}).json()
    assert not r["all_passed"]
    kind, line = EXPECTED_DIVERGENCE[ex["id"]]
    assert r["divergence"]["kind"] == kind
    if line:
        assert r["divergence"]["line"] == line
    assert r["trace"]["steps"], "trace should not be empty"


@pytest.mark.parametrize("eid", FIXED)
def test_fixed_code_passes(eid):
    r = client.post("/api/run", json={"exercise_id": eid, "code": FIXED[eid]}).json()
    assert r["all_passed"] and r["divergence"] is None


def test_aliasing_shares_object_id():
    r = client.post("/api/run", json={"exercise_id": "ex5", "code": BY_ID["ex5"]["starter"]}).json()
    last = r["trace"]["steps"][-1]["globals"]
    assert last["original"]["id"] == last["backup"]["id"]


@pytest.mark.parametrize("code,kind", [
    ("import os", "ImportError"),
    ("__import__('socket')", "ImportError"),
    ("open('/etc/passwd')", "NameError"),
    ("while True: pass", "StepLimit"),
    ("print(1", "SyntaxError"),
])
def test_sandbox_blocks(code, kind):
    assert run_code(code)["error"]["type"] == kind


def test_explain_fallback_is_grounded(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    r = client.post("/api/explain", json={"exercise_id": "ex3", "code": BY_ID["ex3"]["starter"]}).json()
    assert r["source"] == "fallback"
    assert "step" in r["explanation"].lower()


def test_guardrail_hides_solution():
    text = "Try this:\n```python\nreturn n * 2\n```\nOr just write return n*2 at line 2."
    out = guardrail(text, BY_ID["ex3"])
    assert "return n" not in out


def test_code_too_long_rejected():
    r = client.post("/api/run", json={"exercise_id": "ex1", "code": "x=1\n" * 1000})
    assert r.status_code == 422
