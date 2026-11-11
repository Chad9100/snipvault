"""REST endpoints under /api (JSON only)."""
from flask import Blueprint, jsonify, request

from . import db
from .app import get_conn

bp = Blueprint("api", __name__)


def _err(msg, status):
    return jsonify(error=msg), status


@bp.before_request
def _require_json():
    # A cross-site HTML form cannot send application/json, so this doubles as
    # CSRF protection for the API.
    if request.method in ("POST", "PUT", "PATCH") and not request.is_json:
        return _err("Content-Type must be application/json", 415)


def _body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise db.ValidationError("request body must be a JSON object")
    return data


@bp.errorhandler(db.ValidationError)
def _invalid(e):
    return _err(str(e), 400)


@bp.errorhandler(404)
def _nf(_e):
    return _err("not found", 404)


@bp.get("/snippets")
def list_snippets():
    items = db.search(get_conn(), request.args.get("q", ""), request.args.get("tag") or None,
                      request.args.get("language") or None)
    return jsonify(items)


@bp.post("/snippets")
def create_snippet():
    conn = get_conn()
    sid = db.create(conn, _body())
    resp = jsonify(db.get(conn, sid))
    resp.status_code = 201
    resp.headers["Location"] = f"/api/snippets/{sid}"
    return resp


@bp.get("/snippets/<int:sid>")
def get_snippet(sid):
    s = db.get(get_conn(), sid)
    return jsonify(s) if s else _err("not found", 404)


@bp.put("/snippets/<int:sid>")
def put_snippet(sid):
    conn = get_conn()
    data = _body()
    if not db.update(conn, sid, data):
        return _err("not found", 404)
    return jsonify(db.get(conn, sid))


@bp.delete("/snippets/<int:sid>")
def delete_snippet(sid):
    if not db.delete(get_conn(), sid):
        return _err("not found", 404)
    return "", 204


@bp.get("/export")
def export():
    resp = jsonify(db.export_document(get_conn()))
    resp.headers["Content-Disposition"] = 'attachment; filename="snipvault-export.json"'
    return resp


@bp.post("/import")
def import_():
    data = request.get_json(silent=True)
    if data is None:
        raise db.ValidationError("request body must be valid JSON")
    mode = request.args.get("on_duplicate", "add")
    dry = request.args.get("dry_run", "").lower() in ("1", "true", "yes")
    report = db.import_report(get_conn(), data, mode, dry_run=dry)
    return jsonify(report), (200 if dry else 201)


@bp.get("/tags")
def tags():
    return jsonify([{"tag": t, "count": n} for t, n in db.tag_counts(get_conn())])
