"""SQLite storage for snippets. Tags are stored in a separate table."""
import re
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    snippet_id INTEGER NOT NULL REFERENCES snippets(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (snippet_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
"""

MAX_TITLE = 200
MAX_BODY = 200_000
MAX_LANGUAGE = 40
MAX_TAG = 40
MAX_TAGS = 20


class ValidationError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path):
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def parse_tags(value):
    """Accept a list or a comma separated string; return unique lowercase tags."""
    if value is None:
        return []
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple)):
        raise ValidationError("tags must be a list or a comma separated string")
    out = []
    for t in value:
        if not isinstance(t, str):
            raise ValidationError("each tag must be a string")
        t = re.sub(r"\s+", "-", t.strip().lower())
        if not t:
            continue
        if len(t) > MAX_TAG:
            raise ValidationError(f"tag too long (max {MAX_TAG} characters)")
        if t not in out:
            out.append(t)
    if len(out) > MAX_TAGS:
        raise ValidationError(f"too many tags (max {MAX_TAGS})")
    return out


def clean(data):
    """Validate user input and return a normalised dict."""
    title = data.get("title")
    body = data.get("body", "")
    language = data.get("language", "")
    for name, v in (("title", title), ("body", body), ("language", language)):
        if v is not None and not isinstance(v, str):
            raise ValidationError(f"{name} must be a string")
    title = (title or "").strip()
    language = (language or "").strip().lower()
    body = (body or "").replace("\r\n", "\n")
    if not title:
        raise ValidationError("title is required")
    if len(title) > MAX_TITLE:
        raise ValidationError(f"title too long (max {MAX_TITLE} characters)")
    if len(language) > MAX_LANGUAGE:
        raise ValidationError(f"language too long (max {MAX_LANGUAGE} characters)")
    if len(body) > MAX_BODY:
        raise ValidationError(f"body too long (max {MAX_BODY} characters)")
    return {"title": title, "language": language, "body": body,
            "tags": parse_tags(data.get("tags"))}


def _set_tags(conn, sid, tags):
    conn.execute("DELETE FROM tags WHERE snippet_id = ?", (sid,))
    conn.executemany("INSERT INTO tags (snippet_id, tag) VALUES (?, ?)",
                     [(sid, t) for t in tags])


def _row(conn, r):
    d = dict(r)
    d["tags"] = [x["tag"] for x in conn.execute(
        "SELECT tag FROM tags WHERE snippet_id = ? ORDER BY tag", (r["id"],))]
    return d


def create(conn, data, created_at=None, updated_at=None):
    c = clean(data)
    ts = now()
    cur = conn.execute(
        "INSERT INTO snippets (title, language, body, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (c["title"], c["language"], c["body"], created_at or ts, updated_at or created_at or ts))
    _set_tags(conn, cur.lastrowid, c["tags"])
    conn.commit()
    return cur.lastrowid


def get(conn, sid):
    r = conn.execute("SELECT * FROM snippets WHERE id = ?", (sid,)).fetchone()
    return _row(conn, r) if r else None


def update(conn, sid, data):
    c = clean(data)
    cur = conn.execute(
        "UPDATE snippets SET title=?, language=?, body=?, updated_at=? WHERE id=?",
        (c["title"], c["language"], c["body"], now(), sid))
    if cur.rowcount == 0:
        conn.rollback()
        return False
    _set_tags(conn, sid, c["tags"])
    conn.commit()
    return True


def delete(conn, sid):
    cur = conn.execute("DELETE FROM snippets WHERE id = ?", (sid,))
    conn.commit()
    return cur.rowcount > 0


def _like(term):
    esc = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def search(conn, q="", tag=None, language=None):
    """Case-insensitive search: every word of ``q`` must appear in the title,
    body, language or a tag. Newest-updated first."""
    sql = "SELECT * FROM snippets s WHERE 1=1"
    args = []
    for term in (q or "").split():
        sql += (" AND (s.title LIKE ? ESCAPE '\\' OR s.body LIKE ? ESCAPE '\\'"
                " OR s.language LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM tags t"
                " WHERE t.snippet_id = s.id AND t.tag LIKE ? ESCAPE '\\'))")
        args += [_like(term)] * 4
    if tag:
        sql += " AND EXISTS (SELECT 1 FROM tags t WHERE t.snippet_id = s.id AND t.tag = ?)"
        args.append(tag.strip().lower())
    if language:
        sql += " AND s.language = ?"
        args.append(language.strip().lower())
    sql += " ORDER BY s.updated_at DESC, s.id DESC"
    return [_row(conn, r) for r in conn.execute(sql, args)]


def tag_counts(conn):
    return [(r["tag"], r["n"]) for r in conn.execute(
        "SELECT tag, COUNT(*) AS n FROM tags GROUP BY tag ORDER BY n DESC, tag")]


def export_all(conn):
    return [get(conn, r["id"]) for r in conn.execute("SELECT id FROM snippets ORDER BY id")]


def import_items(conn, items):
    """Import a list of snippet dicts. Validates everything first so a bad file
    imports nothing. Returns the number imported."""
    if not isinstance(items, list):
        raise ValidationError("import data must be a list of snippets")
    cleaned = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise ValidationError(f"item {i} is not an object")
        try:
            cleaned.append((clean(it), it.get("created_at"), it.get("updated_at")))
        except ValidationError as e:
            raise ValidationError(f"item {i}: {e}") from None
    for c, created, updated in cleaned:
        ts = now()
        cur = conn.execute(
            "INSERT INTO snippets (title, language, body, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (c["title"], c["language"], c["body"],
             created if isinstance(created, str) else ts,
             updated if isinstance(updated, str) else (created if isinstance(created, str) else ts)))
        _set_tags(conn, cur.lastrowid, c["tags"])
    conn.commit()
    return len(cleaned)
