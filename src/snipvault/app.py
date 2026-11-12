"""Application factory."""
import os
import secrets
import sqlite3

from flask import Flask, current_app, g, jsonify, request

from . import csrf, db


def get_conn():
    if "conn" not in g:
        g.conn = db.connect(current_app.config["DATABASE"])
    return g.conn


def create_app(db_path=None, secret_key=None, token=None):
    app = Flask(__name__)
    app.config["DATABASE"] = db_path or os.environ.get("SNIPVAULT_DB", "snipvault.db")
    app.config["SECRET_KEY"] = secret_key or secrets.token_hex(32)
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    db.init_db(app.config["DATABASE"])

    @app.teardown_appcontext
    def _close(_exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    app.config["ACCESS_TOKEN"] = token or os.environ.get("SNIPVAULT_TOKEN") or None
    csrf.init_app(app)
    from . import auth
    auth.init_app(app)

    from .web import bp as web_bp
    app.register_blueprint(web_bp)
    from .api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.errorhandler(404)
    @app.errorhandler(405)
    def _api_errors(e):
        # Unrouted /api paths never reach the blueprint, so answer in JSON here.
        if request.path.startswith("/api/"):
            return jsonify(error=e.name.lower()), e.code
        return e

    return app


__all__ = ["create_app", "get_conn", "sqlite3"]
