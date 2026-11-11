import pytest

from snipvault import db


@pytest.fixture
def conn(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(str(p))
    c = db.connect(str(p))
    yield c
    c.close()


def test_init_is_idempotent(tmp_path):
    p = str(tmp_path / "x.db")
    db.init_db(p)
    db.init_db(p)


def test_create_and_get(conn):
    sid = db.create(conn, {"title": "Hello", "language": "Python", "body": "print(1)", "tags": "a, b"})
    s = db.get(conn, sid)
    assert s["title"] == "Hello"
    assert s["language"] == "python"
    assert s["tags"] == ["a", "b"]


def test_get_missing(conn):
    assert db.get(conn, 99) is None


def test_title_required(conn):
    with pytest.raises(db.ValidationError):
        db.create(conn, {"title": "   "})


def test_title_too_long(conn):
    with pytest.raises(db.ValidationError):
        db.create(conn, {"title": "x" * 201})


def test_body_too_long(conn):
    with pytest.raises(db.ValidationError):
        db.create(conn, {"title": "t", "body": "x" * 200_001})


def test_non_string_title(conn):
    with pytest.raises(db.ValidationError):
        db.create(conn, {"title": 5})


def test_crlf_normalised(conn):
    sid = db.create(conn, {"title": "t", "body": "a\r\nb"})
    assert db.get(conn, sid)["body"] == "a\nb"


def test_parse_tags_dedupes_and_lowers():
    assert db.parse_tags("Web, web ,  API,,") == ["web", "api"]


def test_parse_tags_spaces_become_dashes():
    assert db.parse_tags(["big  data"]) == ["big-data"]


def test_parse_tags_list_and_none():
    assert db.parse_tags(["x", "y"]) == ["x", "y"]
    assert db.parse_tags(None) == []


def test_parse_tags_bad_type():
    with pytest.raises(db.ValidationError):
        db.parse_tags(5)
    with pytest.raises(db.ValidationError):
        db.parse_tags([1])


def test_too_many_tags():
    with pytest.raises(db.ValidationError):
        db.parse_tags([f"t{i}" for i in range(21)])


def test_update(conn):
    sid = db.create(conn, {"title": "a", "tags": "x"})
    assert db.update(conn, sid, {"title": "b", "tags": "y,z", "body": "q"})
    s = db.get(conn, sid)
    assert (s["title"], s["tags"], s["body"]) == ("b", ["y", "z"], "q")


def test_update_missing(conn):
    assert db.update(conn, 5, {"title": "b"}) is False


def test_delete_cascades_tags(conn):
    sid = db.create(conn, {"title": "a", "tags": "x"})
    assert db.delete(conn, sid)
    assert conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0] == 0
    assert db.delete(conn, sid) is False


def test_search_all_words_any_field(conn):
    db.create(conn, {"title": "Sort list", "body": "sorted(x)", "language": "python"})
    db.create(conn, {"title": "Other", "body": "sorted", "tags": "list"})
    db.create(conn, {"title": "Nope", "body": "zzz"})
    assert len(db.search(conn, "sorted list")) == 2
    assert len(db.search(conn, "SORTED")) == 2
    assert db.search(conn, "nomatch") == []


def test_search_escapes_wildcards(conn):
    db.create(conn, {"title": "100% done"})
    db.create(conn, {"title": "plain"})
    assert [s["title"] for s in db.search(conn, "%")] == ["100% done"]
    assert db.search(conn, "_") == []


def test_filter_by_tag_and_language(conn):
    db.create(conn, {"title": "a", "tags": "x", "language": "go"})
    db.create(conn, {"title": "b", "tags": "x,y", "language": "c"})
    assert len(db.search(conn, tag="x")) == 2
    assert len(db.search(conn, tag="Y")) == 1
    assert len(db.search(conn, language="go")) == 1
    assert len(db.search(conn, tag="x", language="c")) == 1


def test_tag_counts(conn):
    db.create(conn, {"title": "a", "tags": "x,y"})
    db.create(conn, {"title": "b", "tags": "x"})
    assert db.tag_counts(conn) == [("x", 2), ("y", 1)]


def test_import_roundtrip(conn):
    db.create(conn, {"title": "a", "tags": "x", "body": "b"})
    data = db.export_all(conn)
    assert db.import_items(conn, data) == 1
    assert len(db.export_all(conn)) == 2


def test_import_is_all_or_nothing(conn):
    with pytest.raises(db.ValidationError) as e:
        db.import_items(conn, [{"title": "ok"}, {"title": ""}])
    assert "item 2" in str(e.value)
    assert db.export_all(conn) == []


def test_import_rejects_non_list(conn):
    with pytest.raises(db.ValidationError):
        db.import_items(conn, {"title": "x"})
    with pytest.raises(db.ValidationError):
        db.import_items(conn, ["x"])
