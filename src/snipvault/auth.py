"""Optional shared access token.

When a token is configured (``--token``, ``$SNIPVAULT_TOKEN`` or
``create_app(token=...)``) every page and API call requires it. Browsers sign in
once on ``/login`` (the result is kept in the session cookie); API clients send
``Authorization: Bearer <token>``. Without a token nothing changes.
"""
import hmac

from flask import (Blueprint, current_app, jsonify, redirect, render_template,
                   request, session, url_for)

bp = Blueprint("auth", __name__)
SESSION_KEY = "authed"


def _matches(sent):
    expected = current_app.config.get("ACCESS_TOKEN")
    return bool(expected) and hmac.compare_digest(sent.encode(), expected.encode())


def _bearer():
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" else ""


def _safe_next(target):
    # Only follow local paths, never an absolute or protocol-relative URL.
    if target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return "/"


def init_app(app):
    app.register_blueprint(bp)

    @app.before_request
    def _require_token():
        if not app.config.get("ACCESS_TOKEN"):
            return None
        if request.endpoint in ("auth.login", "auth.login_post", "static"):
            return None
        if session.get(SESSION_KEY) or _matches(_bearer()):
            return None
        if request.path.startswith("/api/"):
            resp = jsonify(error="authentication required")
            resp.status_code = 401
            resp.headers["WWW-Authenticate"] = "Bearer"
            return resp
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


@bp.get("/login")
def login():
    return render_template("login.html", error=None, next=request.args.get("next", "/"))


@bp.post("/login")
def login_post():
    if _matches(request.form.get("token", "")):
        session[SESSION_KEY] = True
        return redirect(_safe_next(request.form.get("next", "/")))
    return render_template("login.html", error="That token is not right.",
                           next=request.form.get("next", "/")), 401


@bp.post("/logout")
def logout():
    session.pop(SESSION_KEY, None)
    return redirect(url_for("auth.login"))
