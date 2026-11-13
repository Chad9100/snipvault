import pytest

from snipvault import db
from snipvault.cli import main


def _add(client, title, body, language="python"):
    r = client.post("/api/snippets", json={"title": title, "body": body, "language": language})
    assert r.status_code == 201


@pytest.fixture
def filled(client):
    _add(client, "Reverse", "items[::-1]")
    _add(client, "Reverse copy", "items[::-1]  ")
    _add(client, "Reverse list", "items[::-1].copy")
    _add(client, "Other", "SELECT count(*) FROM big_table WHERE x > 10", "sql")
    return client


def test_finds_similar_most_similar_first(filled):
    pairs = filled.get("/api/duplicates").get_json()
    assert pairs[0]["similarity"] == 1.0
    assert (pairs[0]["a"]["id"], pairs[0]["b"]["id"]) == (1, 2)
    ids = {(p["a"]["id"], p["b"]["id"]) for p in pairs}
    assert (1, 3) in ids and (2, 3) in ids
    assert all(4 not in (a, b) for a, b in ids)
    sims = [p["similarity"] for p in pairs]
    assert sims == sorted(sims, reverse=True)


def test_threshold_filters(filled):
    pairs = filled.get("/api/duplicates?threshold=1").get_json()
    assert [(p["a"]["id"], p["b"]["id"]) for p in pairs] == [(1, 2)]


def test_whitespace_is_ignored(client):
    _add(client, "a", "x = 1\ny = 2")
    _add(client, "b", "x   =  1  y = 2\n")
    assert client.get("/api/duplicates?threshold=1").get_json()[0]["similarity"] == 1.0


def test_empty_bodies_ignored(client):
    _add(client, "a", "")
    _add(client, "b", "")
    assert client.get("/api/duplicates").get_json() == []


@pytest.mark.parametrize("bad", ["0", "1.5", "-1", "abc", "nan"])
def test_bad_threshold(client, bad):
    r = client.get("/api/duplicates?threshold=" + bad)
    assert r.status_code == 400
    assert "threshold" in r.get_json()["error"]


def test_cli(tmp_path, capsys):
    p = str(tmp_path / "d.db")
    db.init_db(p)
    conn = db.connect(p)
    db.create(conn, {"title": "A", "body": "hello world"})
    db.create(conn, {"title": "B", "body": "hello world!"})
    conn.close()
    assert main(["duplicates", "--db", p]) == 0
    out = capsys.readouterr().out
    assert "#1 A" in out and "#2 B" in out
    assert out.strip().endswith("1 similar pair(s) at threshold 0.8")
    assert main(["duplicates", "--db", p, "--threshold", "2"]) == 1
    assert main(["duplicates", "--db", str(tmp_path / "nope.db")]) == 1
