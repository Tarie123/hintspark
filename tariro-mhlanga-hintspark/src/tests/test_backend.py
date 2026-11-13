import pytest
from backend import create_app
from backend.exercises import EXERCISES
from backend.service import trace_exercise
from backend.trace.sandbox import run_untrusted

@pytest.fixture
def client():
    return create_app().test_client()

@pytest.mark.parametrize("ex", EXERCISES, ids=lambda e: e["id"])
def test_exercise_is_a_real_bug(ex):
    """Every exercise must run, be wrong as shipped, and let HintSpark find the problem."""
    res = trace_exercise(ex, ex["code"])
    assert res["error"] is None and res["steps"]
    assert not res["passed"] and ex["expected"].strip()
    assert res["key"] is not None

def test_sandbox_hides_keys(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "secret")
    res = run_untrusted("import os\nprint(os.environ.get('NVIDIA_API_KEY'))")
    assert res["output"].strip() == "None"

def test_infinite_loop_is_stopped():
    assert run_untrusted("while True:\n    pass", timeout=2)["error"]

def test_api_flow(client):
    ex = client.get("/api/exercises").get_json()[0]
    t = client.post("/api/trace", json={"exercise_id": ex["id"], "code": ex["code"]}).get_json()
    assert t["steps"] and t["key"]
    assert "hint" in client.post("/api/hint", json={"exercise_id": ex["id"], "code": ex["code"], "level": 1}).get_json()
    assert client.post("/api/event", json={"type": "run"}).status_code == 204
