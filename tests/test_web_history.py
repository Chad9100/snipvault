def make(post):
    r = post("/new", {"title": "Rev", "language": "python", "body": "items[::-1]\n", "tags": "a"})
    assert r.status_code == 302
    r = post("/s/1/edit", {"title": "Rev", "language": "python",
                           "body": "list(reversed(items))\n", "tags": "a"}, tok_path="/s/1/edit")
    assert r.status_code == 302


def test_show_links_to_history(client, post):
    make(post)
    assert "/s/1/history" in client.get("/s/1").get_data(as_text=True)


def test_history_empty(client, post):
    post("/new", {"title": "T", "body": "x"})
    html = client.get("/s/1/history").get_data(as_text=True)
    assert "No earlier versions" in html


def test_history_shows_version_and_diff(client, post):
    make(post)
    html = client.get("/s/1/history").get_data(as_text=True)
    assert "Version 1" in html
    assert "-items[::-1]" in html and "+list(reversed(items))" in html
    assert "/s/1/history/1/restore" in html


def test_history_escapes_html(client, post):
    post("/new", {"title": "T", "body": "<script>a</script>\n"})
    post("/s/1/edit", {"title": "T", "body": "b\n"}, tok_path="/s/1/edit")
    html = client.get("/s/1/history").get_data(as_text=True)
    assert "<script>a" not in html and "&lt;script&gt;" in html


def test_history_404(client):
    assert client.get("/s/99/history").status_code == 404


def test_restore_from_web(client, post):
    make(post)
    r = post("/s/1/history/1/restore", tok_path="/s/1/history")
    assert r.status_code == 302
    assert "items[::-1]" in client.get("/s/1").get_data(as_text=True)
    # the replaced state is kept, so the restore is undoable
    assert "Version 2" in client.get("/s/1/history").get_data(as_text=True)


def test_restore_unknown_version_404(client, post):
    make(post)
    assert post("/s/1/history/9/restore", tok_path="/s/1/history").status_code == 404


def test_restore_needs_csrf(client, post):
    make(post)
    assert client.post("/s/1/history/1/restore").status_code in (400, 403)
