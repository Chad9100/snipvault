import io
import json

from conftest import token
from test_transfer import DUP, mk, seed


def titles(client):
    return [s["title"] for s in client.get("/api/snippets").get_json()]


def test_dry_run_reports_plan_and_saves_nothing(client):
    seed(client)
    r = client.post("/api/import?on_duplicate=skip&dry_run=1", json=DUP)
    assert r.status_code == 200
    body = r.get_json()
    assert body["dry_run"] is True
    assert (body["imported"], body["skipped"], body["replaced"]) == (1, 1, 0)
    assert [i["action"] for i in body["items"]] == ["skip", "add"]
    assert titles(client) == ["reverse"]


def test_dry_run_counts_match_real_import(client):
    seed(client)
    docs = DUP + [{"title": "other"}]
    for mode in ("add", "skip", "replace"):
        dry = client.post(f"/api/import?on_duplicate={mode}&dry_run=true", json=docs).get_json()
        assert titles(client) == ["reverse"]
        real = client.post(f"/api/import?on_duplicate={mode}", json=docs).get_json()
        for k in ("imported", "skipped", "replaced"):
            assert dry[k] == real[k]
        for s in client.get("/api/snippets").get_json():
            client.delete(f"/api/snippets/{s['id']}")
        seed(client)


def test_dry_run_does_not_replace_or_consume_ids(client):
    seed(client)
    client.post("/api/import?on_duplicate=replace&dry_run=1", json=DUP)
    assert client.get("/api/snippets/1").get_json()["body"] == "old"
    assert mk(client, title="next").get_json()["id"] == 2


def test_dry_run_within_file_duplicates(client):
    r = client.post("/api/import?on_duplicate=skip&dry_run=1",
                    json=[{"title": "x"}, {"title": "X"}])
    assert [i["action"] for i in r.get_json()["items"]] == ["add", "skip"]
    assert titles(client) == []


def test_dry_run_still_validates(client):
    r = client.post("/api/import?dry_run=1", json=[{"body": "no title"}])
    assert r.status_code == 400


def test_real_import_has_no_dry_run_keys(client):
    r = client.post("/api/import", json=[{"title": "a"}])
    assert r.status_code == 201 and "items" not in r.get_json()


def test_web_dry_run(client):
    data = {"file": (io.BytesIO(json.dumps([{"title": "p"}]).encode()), "x.json"),
            "csrf_token": token(client, "/import"), "dry_run": "1"}
    r = client.post("/import", data=data, content_type="multipart/form-data",
                    follow_redirects=True)
    assert b"Dry run, nothing saved. Would import 1" in r.data
    assert titles(client) == []
