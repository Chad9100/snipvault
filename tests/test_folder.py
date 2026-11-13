import pytest

from snipvault import db, folder
from snipvault.cli import main


@pytest.fixture
def dbp(tmp_path):
    p = str(tmp_path / "s.db")
    db.init_db(p)
    conn = db.connect(p)
    db.create(conn, {"title": "Reverse a list", "language": "python",
                     "body": "items[::-1]\n", "tags": ["lists", "python"]})
    db.create(conn, {"title": "Reverse a list", "language": "python", "body": "x\n"})
    db.create(conn, {"title": "CON", "language": "weird lang", "body": "y"})
    conn.close()
    return p


def test_export_names_and_content(dbp, tmp_path):
    conn = db.connect(dbp)
    names = folder.export_folder(conn, str(tmp_path / "out"))
    conn.close()
    assert names == ["reverse-a-list.py", "reverse-a-list-2.py", "con-snippet.txt"]
    text = (tmp_path / "out" / "reverse-a-list.py").read_text(encoding="utf-8")
    assert text == ("---\ntitle: Reverse a list\nlanguage: python\n"
                    "tags: lists, python\n---\nitems[::-1]\n")


def test_export_refuses_overwrite(dbp, tmp_path):
    out = tmp_path / "out"
    conn = db.connect(dbp)
    folder.export_folder(conn, str(out))
    with pytest.raises(folder.FolderError, match="already exist"):
        folder.export_folder(conn, str(out))
    folder.export_folder(conn, str(out), overwrite=True)
    conn.close()


def test_round_trip(dbp, tmp_path):
    out = str(tmp_path / "out")
    assert main(["export-dir", out, "--db", dbp]) == 0
    other = str(tmp_path / "o.db")
    assert main(["import-dir", out, "--db", other]) == 0
    a, b = db.connect(dbp), db.connect(other)

    def key(s):
        return (s["title"], s["language"], s["body"], s["tags"])

    assert sorted(map(key, db.export_all(a))) == sorted(map(key, db.export_all(b)))
    a.close()
    b.close()


def test_plain_files_without_header(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "find_big-files.sh").write_text("find . -size +100M\n")
    (src / "sub" / "notes.txt").write_text("---\nnot a header\n")
    (src / ".hidden").write_text("no")
    (src / "bin.dat").write_bytes(b"\xff\xfe\x00\x01")
    items, skipped = folder.read_folder(str(src))
    assert skipped == ["bin.dat"]
    assert items[0]["title"] == "find big files" and items[0]["language"] == "bash"
    assert items[1]["title"] == "notes" and items[1]["body"] == "---\nnot a header\n"


def test_import_dry_run_and_duplicates(dbp, tmp_path, capsys):
    out = str(tmp_path / "out")
    main(["export-dir", out, "--db", dbp])
    capsys.readouterr()
    assert main(["import-dir", out, "--db", dbp, "--dry-run",
                 "--on-duplicate", "skip"]) == 0
    assert "would import 0, skipped 3, replaced 0" in capsys.readouterr().out
    conn = db.connect(dbp)
    assert len(db.export_all(conn)) == 3
    conn.close()


def test_errors(tmp_path, capsys):
    assert main(["import-dir", str(tmp_path / "nope"), "--db", str(tmp_path / "a.db")]) == 1
    assert main(["export-dir", str(tmp_path / "o"), "--db", str(tmp_path / "nodb.db")]) == 1
    err = capsys.readouterr().err
    assert "folder not found" in err and "database not found" in err
