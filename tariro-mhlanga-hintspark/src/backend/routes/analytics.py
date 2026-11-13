from flask import request
from . import api
from ..analytics import events

@api.post("/event")
def event():
    events.log(request.get_json() or {})
    return "", 204
