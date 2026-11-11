"""Session-based CSRF protection for the HTML forms (no extra dependency).

Every session gets a random token; every state-changing request to a form
route must send it back as the ``csrf_token`` field. The ``/api`` blueprint is
exempt and instead requires ``Content-Type: application/json`` on writes, which
a cross-site HTML form cannot send.
"""
import hmac
import secrets

from flask import abort, request, session
from markupsafe import Markup, escape

FIELD = "csrf_token"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def init_app(app):
    @app.before_request
    def _check_csrf():
        if request.blueprint == "api" or request.path.startswith("/api/"):
            return
        token = session.get(FIELD)
        if not token:
            token = session[FIELD] = secrets.token_urlsafe(32)
        if request.method in UNSAFE:
            sent = request.form.get(FIELD, "")
            if not hmac.compare_digest(sent.encode(), token.encode()):
                abort(400, description="The form has expired or is invalid. "
                                       "Go back, reload the page and try again.")

    def csrf_field():
        return Markup('<input type="hidden" name="%s" value="%s">'
                      % (FIELD, escape(session.get(FIELD, ""))))

    app.jinja_env.globals["csrf_field"] = csrf_field
