from flask import jsonify, request
from . import api
from ..exercises import EXERCISES
from ..service import get_exercise, trace_exercise

@api.get("/exercises")
def exercises():
    return jsonify(EXERCISES)

@api.post("/trace")
def trace():
    d = request.get_json()
    return jsonify(trace_exercise(get_exercise(d["exercise_id"]), d["code"]))
