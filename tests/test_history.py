import sqlite3

from snipvault import create_app, db


def mk(client, **kw):
    d = {"title": "reverse", "language": "python", "body": "v1", "tags": "a"}
    d.update(kw)
    return client.post("/api/snippets", json=d).get_json()["id"]


def edit(client, sid, **kw):
    d = {"title": "reverse", "language": "python", "body": "v1", "tags": "a"}
    d.update(kw)
    return client.put(f"/api/snippets/{sid}", json=d)


def test_new_snippet_has_no_history(client):
    sid = mk(client)
    assert client.get(f"/api/snippets/{sid}/history").get_json() == []


def test_edits_are_recorded_newest_first(client):
    sid = mk(client)
    edit(client, sid, body="v2")
    edit(client, sid, body="v3", tags="a,b")
    h = client.get(f"/api/snippets/{sid}/history").get_json()
    assert [v["body"] for v in h] == ["v2", "v1"]
    assert h[0]["tags"] == ["a"]


def test_unchanged_save_adds_no_version(client):
    sid = mk(client)
    edit(client, sid)
    assert client.get(f"/api/snippets/{sid}/history").get_json() == []


def test_diff(client):
    sid = mk(client, body="a\nb\n")
    edit(client, sid, body="a\nc\n")
    vid = client.get(f"/api/snippets/{sid}/history").get_json()[0]["id"]
    v = client.get(f"/api/snippets/{sid}/history/{vid}?diff=1").get_json()
    assert "-b" in v["diff"] and "+c" in v["diff"]
    assert "diff" not in client.get(f"/api/snippets/{sid}/history/{vid}").get_json()


def test_restore_and_undo(client):
    sid = mk(client)
    edit(client, sid, body="v2", tags="z", title="new")
    vid = client.get(f"/api/snippets/{sid}/history").get_json()[0]["id"]
    r = client.post(f"/api/snippets/{sid}/history/{vid}/restore", json={})
    assert r.status_code == 200
    s = r.get_json()
    assert (s["body"], s["title"], s["tags"]) == ("v1", "reverse", ["a"])
    h = client.get(f"/api/snippets/{sid}/history").get_json()
    assert h[0]["body"] == "v2"  # the replaced state is kept, so restore can be undone


def test_missing_things_are_404(client):
    sid = mk(client)
    assert client.get("/api/snippets/99/history").status_code == 404
    assert client.get(f"/api/snippets/{sid}/history/5").status_code == 404
    assert client.post(f"/api/snippets/{sid}/history/5/restore", json={}).status_code == 404


def test_history_is_deleted_with_snippet(app, client):
    sid = mk(client)
    edit(client, sid, body="v2")
    client.delete(f"/api/snippets/{sid}")
    with app.app_context():
        conn = db.connect(app.config["DATABASE"])
        assert conn.execute("SELECT COUNT(*) FROM snippet_versions").fetchone()[0] == 0
        conn.close()


def test_import_replace_records_version(client):
    sid = mk(client)
    client.post("/api/import?on_duplicate=replace",
                json=[{"title": "reverse", "language": "python", "body": "imported"}])
    h = client.get(f"/api/snippets/{sid}/history").get_json()
    assert [v["body"] for v in h] == ["v1"]


def test_version_cap(client):
    sid = mk(client, body="0")
    for i in range(1, db.MAX_VERSIONS + 6):
        edit(client, sid, body=str(i))
    h = client.get(f"/api/snippets/{sid}/history").get_json()
    assert len(h) == db.MAX_VERSIONS
    assert h[0]["body"] == str(db.MAX_VERSIONS + 4)


def test_old_database_is_upgraded(tmp_path):
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE snippets (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,"
        " language TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '',"
        " created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
        "CREATE TABLE tags (snippet_id INTEGER NOT NULL REFERENCES snippets(id) ON DELETE CASCADE,"
        " tag TEXT NOT NULL, PRIMARY KEY (snippet_id, tag));"
        "INSERT INTO snippets (title, body, created_at, updated_at)"
        " VALUES ('old', 'x', '2020-01-01T00:00:00Z', '2020-01-01T00:00:00Z');")
    conn.commit()
    conn.close()
    c = create_app(path, secret_key="t").test_client()
    assert c.get("/api/snippets/1").get_json()["title"] == "old"
    assert c.get("/api/snippets/1/history").get_json() == []
    edit(c, 1, title="old", body="y", tags="", language="")
    assert [v["body"] for v in c.get("/api/snippets/1/history").get_json()] == ["x"]
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    conn.close()
