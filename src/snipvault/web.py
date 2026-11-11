"""HTML views."""
import json

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, url_for)

from . import db
from .app import get_conn

bp = Blueprint("web", __name__)


@bp.get("/")
def index():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    language = request.args.get("language", "").strip()
    conn = get_conn()
    snippets = db.search(conn, q, tag or None, language or None)
    return render_template("index.html", snippets=snippets, q=q, tag=tag,
                           language=language, tags=db.tag_counts(conn))


@bp.get("/export")
def export():
    body = json.dumps(db.export_document(get_conn()), indent=2, ensure_ascii=False)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": 'attachment; filename="snipvault-export.json"'})


@bp.get("/import")
def import_form():
    return render_template("import.html", error=None)


@bp.post("/import")
def import_upload():
    f = request.files.get("file")
    try:
        if f is None or not f.filename:
            raise db.ValidationError("choose a JSON file to import")
        try:
            data = json.loads(f.read().decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError):
            raise db.ValidationError("file is not valid UTF-8 JSON") from None
        r = db.import_report(get_conn(), data, request.form.get("on_duplicate", "add"))
    except db.ValidationError as e:
        return render_template("import.html", error=str(e)), 400
    msg = f"Imported {r['imported']} snippet(s)."
    if r["skipped"]:
        msg += f" Skipped {r['skipped']} duplicate(s)."
    if r["replaced"]:
        msg += f" Replaced {r['replaced']} duplicate(s)."
    flash(msg)
    return redirect(url_for("web.index"))


@bp.get("/new")
def new():
    return render_template("form.html", snippet={}, action=url_for("web.create"), error=None)


@bp.post("/new")
def create():
    form = request.form
    try:
        sid = db.create(get_conn(), form)
    except db.ValidationError as e:
        return render_template("form.html", snippet=form, action=url_for("web.create"),
                               error=str(e)), 400
    flash("Snippet saved.")
    return redirect(url_for("web.show", sid=sid))


@bp.get("/s/<int:sid>")
def show(sid):
    s = db.get(get_conn(), sid)
    if s is None:
        abort(404)
    return render_template("show.html", s=s)


@bp.get("/s/<int:sid>/edit")
def edit(sid):
    s = db.get(get_conn(), sid)
    if s is None:
        abort(404)
    s = dict(s, tags=", ".join(s["tags"]))
    return render_template("form.html", snippet=s, action=url_for("web.update", sid=sid), error=None)


@bp.post("/s/<int:sid>/edit")
def update(sid):
    conn = get_conn()
    if db.get(conn, sid) is None:
        abort(404)
    try:
        db.update(conn, sid, request.form)
    except db.ValidationError as e:
        return render_template("form.html", snippet=request.form,
                               action=url_for("web.update", sid=sid), error=str(e)), 400
    flash("Snippet updated.")
    return redirect(url_for("web.show", sid=sid))


@bp.post("/s/<int:sid>/delete")
def remove(sid):
    if not db.delete(get_conn(), sid):
        abort(404)
    flash("Snippet deleted.")
    return redirect(url_for("web.index"))
