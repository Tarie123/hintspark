from flask import Blueprint
api = Blueprint("api", __name__, url_prefix="/api")
from . import trace, learning, analytics  # noqa: E402,F401  (each file = one owner's endpoints)
