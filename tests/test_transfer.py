import io
import json

from conftest import token


def mk(client, title="T", **kw):
    d = {"title": title, "language": "python", "body": "x\ny", "tags": ["a"]}
    d.update(kw)
    return client.post("/api/snippets", json=d)


def test_api_export_shape(client):
    mk(client)
    r = client.get("/api/export")
    j = r.get_json()
    assert j["format"] == "snipvault" and j["version"] == 1
    assert j["snippets"][0]["title"] == "T"
    assert "attachment" in r.headers["Content-Disposition"]


def test_api_export_empty(client):
    assert client.get("/api/export").get_json()["snippets"] == []


def test_api_import_document(client):
    doc = {"format": "snipvault", "version": 1, "snippets": [{"title": "I", "tags": ["z"]}]}
    r = client.post("/api/import", json=doc)
    assert r.status_code == 201 and r.get_json() == {"imported": 1}
    assert client.get("/api/snippets/1").get_json()["tags"] == ["z"]


def test_api_import_bare_list(client):
    r = client.post("/api/import", json=[{"title": "a"}, {"title": "b"}])
    assert r.get_json() == {"imported": 2}


def test_api_import_bad_item_imports_nothing(client):
    r = client.post("/api/import", json=[{"title": "a"}, {"body": "no title"}])
    assert r.status_code == 400 and "item 2" in r.get_json()["error"]
    assert client.get("/api/snippets").get_json() == []


def test_api_import_bad_json(client):
    r = client.post("/api/import", data="nope", content_type="application/json")
    assert r.status_code == 400


def test_api_import_wrong_shape(client):
    assert client.post("/api/import", json={"x": 1}).status_code == 400


def test_roundtrip_preserves_content(client):
    mk(client, title="One", body="line1\nline2", tags=["p", "q"], language="sh")
    exported = client.get("/api/export").get_json()
    client.post("/api/import", json=exported)
    snips = client.get("/api/snippets").get_json()
    assert len(snips) == 2
    a, b = sorted(snips, key=lambda s: s["id"])
    for k in ("title", "body", "tags", "language", "created_at"):
        assert a[k] == b[k]


def test_import_keeps_timestamps(client):
    client.post("/api/import", json=[{"title": "old", "created_at": "2020-01-01T00:00:00Z"}])
    s = client.get("/api/snippets/1").get_json()
    assert s["created_at"] == "2020-01-01T00:00:00Z"


def test_web_export_download(client):
    mk(client)
    r = client.get("/export")
    assert r.status_code == 200 and r.mimetype == "application/json"
    assert json.loads(r.data)["snippets"][0]["title"] == "T"


def test_web_import_page(client):
    assert b"Import" in client.get("/import").data


def upload(client, content, name="x.json", csrf=True):
    data = {"file": (io.BytesIO(content), name)}
    if csrf:
        data["csrf_token"] = token(client, "/import")
    return client.post("/import", data=data, content_type="multipart/form-data")


def test_web_import_upload(client):
    r = upload(client, json.dumps([{"title": "up"}]).encode())
    assert r.status_code == 302
    assert client.get("/api/snippets").get_json()[0]["title"] == "up"


def test_web_import_requires_csrf(client):
    client.get("/import")
    r = upload(client, b"[]", csrf=False)
    assert r.status_code == 400


def test_web_import_invalid_json(client):
    r = upload(client, b"not json")
    assert r.status_code == 400 and b"not valid" in r.data


def test_web_import_no_file(client):
    r = client.post("/import", data={"csrf_token": token(client, "/import")})
    assert r.status_code == 400 and b"choose a JSON file" in r.data


def test_web_import_bom(client):
    r = upload(client, b"\xef\xbb\xbf" + json.dumps([{"title": "bom"}]).encode())
    assert r.status_code == 302


def test_web_import_validation_message(client):
    r = upload(client, json.dumps([{"title": ""}]).encode())
    assert r.status_code == 400 and b"item 1" in r.data
