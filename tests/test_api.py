def mk(client, **kw):
    d = {"title": "T", "language": "python", "body": "x", "tags": ["a", "b"]}
    d.update(kw)
    return client.post("/api/snippets", json=d)


def test_list_empty(client):
    r = client.get("/api/snippets")
    assert r.status_code == 200 and r.get_json() == []


def test_create(client):
    r = mk(client)
    assert r.status_code == 201
    j = r.get_json()
    assert j["id"] == 1 and j["tags"] == ["a", "b"]
    assert r.headers["Location"] == "/api/snippets/1"


def test_create_accepts_comma_tags(client):
    assert mk(client, tags="x, y").get_json()["tags"] == ["x", "y"]


def test_create_needs_title(client):
    r = mk(client, title="")
    assert r.status_code == 400
    assert "title" in r.get_json()["error"]


def test_create_non_json_content_type(client):
    r = client.post("/api/snippets", data={"title": "x"})
    assert r.status_code == 415


def test_create_non_object_body(client):
    assert client.post("/api/snippets", json=[1]).status_code == 400


def test_create_bad_json(client):
    r = client.post("/api/snippets", data="{nope", content_type="application/json")
    assert r.status_code == 400


def test_no_csrf_token_needed_for_json(client):
    assert mk(client).status_code == 201


def test_get(client):
    mk(client)
    r = client.get("/api/snippets/1")
    assert r.status_code == 200 and r.get_json()["title"] == "T"


def test_get_404_is_json(client):
    r = client.get("/api/snippets/5")
    assert r.status_code == 404 and r.get_json() == {"error": "not found"}


def test_unknown_api_path_json_404(client):
    r = client.get("/api/nothing")
    assert r.status_code == 404 and r.is_json


def test_put(client):
    mk(client)
    r = client.put("/api/snippets/1", json={"title": "N", "body": "b", "tags": []})
    assert r.status_code == 200
    j = r.get_json()
    assert j["title"] == "N" and j["tags"] == []


def test_put_404(client):
    assert client.put("/api/snippets/3", json={"title": "N"}).status_code == 404


def test_put_invalid(client):
    mk(client)
    assert client.put("/api/snippets/1", json={"title": ""}).status_code == 400


def test_delete(client):
    mk(client)
    assert client.delete("/api/snippets/1").status_code == 204
    assert client.get("/api/snippets/1").status_code == 404


def test_delete_404(client):
    assert client.delete("/api/snippets/1").status_code == 404


def test_list_search_and_filters(client):
    mk(client, title="Alpha", body="needle", tags=["one"], language="go")
    mk(client, title="Beta", body="hay", tags=["two"], language="c")
    assert [s["title"] for s in client.get("/api/snippets?q=needle").get_json()] == ["Alpha"]
    assert [s["title"] for s in client.get("/api/snippets?tag=two").get_json()] == ["Beta"]
    assert [s["title"] for s in client.get("/api/snippets?language=go").get_json()] == ["Alpha"]


def test_tags_endpoint(client):
    mk(client, tags=["x", "y"])
    mk(client, tags=["x"])
    assert client.get("/api/tags").get_json() == [{"tag": "x", "count": 2}, {"tag": "y", "count": 1}]


def test_method_not_allowed(client):
    r = client.patch("/api/snippets/1", json={})
    assert r.status_code == 405 and r.is_json
