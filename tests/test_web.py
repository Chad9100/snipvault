import re

from snipvault import db
from snipvault.cli import build_parser, main

from conftest import token


def make(app, **kw):
    d = {"title": "T", "language": "python", "body": "print('hi')", "tags": "a,b"}
    d.update(kw)
    conn = db.connect(app.config["DATABASE"])
    sid = db.create(conn, d)
    conn.close()
    return sid


def test_index_empty(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"No snippets found" in r.data


def test_new_form_has_csrf(client):
    assert 'name="csrf_token"' in client.get("/new").get_data(as_text=True)


def test_create_via_form(client, post):
    r = post("/new", {"title": "Hello", "language": "py", "body": "x=1", "tags": "t1"})
    assert r.status_code == 302
    page = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "Hello" in page and "x=1" in page and "t1" in page


def test_create_without_csrf_rejected(client):
    client.get("/new")
    r = client.post("/new", data={"title": "x"})
    assert r.status_code == 400


def test_create_wrong_csrf_rejected(client):
    client.get("/new")
    r = client.post("/new", data={"title": "x", "csrf_token": "bad"})
    assert r.status_code == 400


def test_create_without_session_rejected(app):
    r = app.test_client().post("/new", data={"title": "x"})
    assert r.status_code == 400


def test_create_validation_error_keeps_input(client, post):
    r = post("/new", {"title": "", "body": "keepme"})
    assert r.status_code == 400
    assert b"title is required" in r.data
    assert b"keepme" in r.data


def test_html_is_escaped(client, post, app):
    sid = make(app, title="<script>alert(1)</script>", body="<b>x</b>")
    html = client.get(f"/s/{sid}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html


def test_show_404(client):
    assert client.get("/s/99").status_code == 404


def test_show_has_copy_button(client, app):
    sid = make(app)
    html = client.get(f"/s/{sid}").get_data(as_text=True)
    assert 'data-copy-target="snippet-body"' in html
    assert 'id="snippet-body"' in html


def test_copy_js_served(client):
    r = client.get("/static/copy.js")
    assert r.status_code == 200
    assert b"clipboard" in r.data


def test_edit_prefills(client, app):
    sid = make(app, tags="x,y")
    html = client.get(f"/s/{sid}/edit").get_data(as_text=True)
    assert 'value="x, y"' in html
    assert "print(&#39;hi&#39;)" in html


def test_edit_saves(client, post, app):
    sid = make(app)
    r = post(f"/s/{sid}/edit", {"title": "New", "body": "b", "tags": "z"}, tok_path=f"/s/{sid}/edit")
    assert r.status_code == 302
    conn = db.connect(app.config["DATABASE"])
    s = db.get(conn, sid)
    assert (s["title"], s["tags"]) == ("New", ["z"])


def test_edit_invalid(client, post, app):
    sid = make(app)
    r = post(f"/s/{sid}/edit", {"title": ""}, tok_path=f"/s/{sid}/edit")
    assert r.status_code == 400


def test_edit_404(client, post):
    assert post("/s/9/edit", {"title": "x"}).status_code == 404
    assert client.get("/s/9/edit").status_code == 404


def test_delete(client, post, app):
    sid = make(app)
    r = post(f"/s/{sid}/delete", tok_path=f"/s/{sid}")
    assert r.status_code == 302
    assert client.get(f"/s/{sid}").status_code == 404


def test_delete_requires_csrf(client, app):
    sid = make(app)
    client.get("/")
    assert client.post(f"/s/{sid}/delete").status_code == 400
    assert client.get(f"/s/{sid}").status_code == 200


def test_delete_get_not_allowed(client, app):
    sid = make(app)
    assert client.get(f"/s/{sid}/delete").status_code == 405


def test_delete_404(post):
    assert post("/s/5/delete").status_code == 404


def test_tag_filter(client, app):
    make(app, title="Alpha", tags="one")
    make(app, title="Beta", tags="two")
    html = client.get("/?tag=one").get_data(as_text=True)
    assert "Alpha" in html and "Beta" not in html.split("<section>")[1]


def test_language_filter(client, app):
    make(app, title="Alpha", language="go")
    make(app, title="Beta", language="rust")
    html = client.get("/?language=go").get_data(as_text=True).split("<section>")[1]
    assert "Alpha" in html and "Beta" not in html


def test_search(client, app):
    make(app, title="Alpha", body="needle here")
    make(app, title="Beta", body="hay")
    html = client.get("/?q=needle").get_data(as_text=True).split("<section>")[1]
    assert "Alpha" in html and "Beta" not in html


def test_search_value_escaped_in_box(client):
    html = client.get('/?q="><script>x</script>').get_data(as_text=True)
    assert "<script>x</script>" not in html


def test_sidebar_lists_tags(client, app):
    make(app, tags="alpha,beta")
    html = client.get("/").get_data(as_text=True)
    assert ">alpha<" in html and ">beta<" in html


def test_flash_message_after_create(client, post):
    r = post("/new", {"title": "F"}, follow_redirects=True)
    assert b"Snippet saved." in r.data


def test_csrf_token_stable_in_session(client):
    assert token(client) == token(client)


def test_cli_parser_defaults():
    a = build_parser().parse_args(["serve"])
    assert (a.host, a.port, a.allow_remote) == ("127.0.0.1", 5000, False)


def test_cli_refuses_remote_bind(capsys):
    assert main(["serve", "--host", "0.0.0.0"]) == 2
    assert "refusing" in capsys.readouterr().err


def test_cli_requires_command():
    import pytest
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
