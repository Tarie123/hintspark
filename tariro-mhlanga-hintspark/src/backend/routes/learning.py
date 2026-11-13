from flask import jsonify, request
from . import api
from ..service import get_exercise, trace_exercise
from ..learning.annotate import make_hint
from ..learning.explain import explain as run_explain

@api.post("/hint")
def hint():
    d = request.get_json()
    res = trace_exercise(get_exercise(d["exercise_id"]), d["code"])
    return jsonify({"hint": make_hint(res, int(d.get("level", 1)))})

@api.post("/explain")
def explain():
    d = request.get_json()
    res = trace_exercise(get_exercise(d["exercise_id"]), d["code"])  # re-traced server-side
    try:
        return jsonify(run_explain(d["code"], res))
    except KeyError as e:
        return jsonify({"explanation": f"Missing environment variable {e}. See README.", "verification": None}), 503
    except Exception as e:
        return jsonify({"explanation": f"AI service error: {e}", "verification": None}), 502
