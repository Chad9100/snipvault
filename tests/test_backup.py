import sqlite3

import pytest

from snipvault import db
from snipvault.cli import main


@pytest.fixture
def src(tmp_path):
    p = str(tmp_path / "src.db")
    db.init_db(p)
    conn = db.connect(p)
    db.create(conn, {"title": "A", "tags": ["x"]})
    db.create(conn, {"title": "B"})
    conn.close()
    return p


def test_backup_copies_data(src, tmp_path):
    dest = str(tmp_path / "bak.db")
    assert db.backup(src, dest) == 2
    conn = db.connect(dest)
    assert db.get(conn, 1)["tags"] == ["x"]
    conn.close()
    assert not (tmp_path / "bak.db.part").exists()


def test_backup_refuses_existing_unless_forced(src, tmp_path):
    dest = tmp_path / "bak.db"
    dest.write_text("old")
    with pytest.raises(db.BackupError, match="exists"):
        db.backup(src, str(dest))
    assert dest.read_text() == "old"
    db.backup(src, str(dest), overwrite=True)
    sqlite3.connect(str(dest)).execute("SELECT 1 FROM snippets").fetchall()


def test_backup_missing_source_creates_nothing(tmp_path):
    with pytest.raises(db.BackupError, match="not found"):
        db.backup(str(tmp_path / "nope.db"), str(tmp_path / "b.db"))
    assert list(tmp_path.iterdir()) == []


def test_backup_missing_folder(src, tmp_path):
    with pytest.raises(db.BackupError, match="folder"):
        db.backup(src, str(tmp_path / "nodir" / "b.db"))


def test_backup_onto_itself_refused(src):
    with pytest.raises(db.BackupError, match="itself"):
        db.backup(src, src, overwrite=True)


def test_backup_into_directory_refused(src, tmp_path):
    with pytest.raises(db.BackupError, match="directory"):
        db.backup(src, str(tmp_path))


def test_cli_backup(src, tmp_path, capsys):
    dest = str(tmp_path / "c.db")
    assert main(["backup", dest, "--db", src]) == 0
    assert "backed up 2 snippet(s)" in capsys.readouterr().out
    assert main(["backup", dest, "--db", src]) == 1
    assert "--force" in capsys.readouterr().err
    assert main(["backup", dest, "--db", src, "--force"]) == 0
