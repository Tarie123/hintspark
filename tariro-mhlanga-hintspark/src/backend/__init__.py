import os
from flask import Flask, send_from_directory

def create_app():
    app = Flask(__name__)
    from .routes import api
    app.register_blueprint(api)
    fe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    app.add_url_rule("/", "index", lambda: send_from_directory(fe, "index.html"))
    return app
