"""Command line entry point: ``snipvault serve``."""
import argparse
import os
import sys

from . import __version__

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def build_parser():
    p = argparse.ArgumentParser(prog="snipvault",
                                description="A small local snippet manager (Flask + SQLite).")
    p.add_argument("--version", action="version", version=f"snipvault {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", help="start the web app")
    s.add_argument("--db", default=None,
                   help="database file (default: $SNIPVAULT_DB or ./snipvault.db)")
    s.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    s.add_argument("--port", type=int, default=5000, help="port (default: 5000)")
    s.add_argument("--allow-remote", action="store_true",
                   help="required to bind to a non-local address (there is no login!)")
    s.add_argument("--token", default=None,
                   help="require this access token (default: $SNIPVAULT_TOKEN; "
                        "prefer the variable, arguments show up in process lists)")
    b = sub.add_parser("backup", help="copy the database to a file (safe while serving)")
    b.add_argument("dest", help="backup file to write")
    b.add_argument("--db", default=None,
                   help="database file (default: $SNIPVAULT_DB or ./snipvault.db)")
    b.add_argument("--force", action="store_true", help="overwrite an existing backup file")
    e = sub.add_parser("export-dir", help="write every snippet to a folder of files")
    e.add_argument("folder", help="folder to write (created if missing)")
    e.add_argument("--db", default=None,
                   help="database file (default: $SNIPVAULT_DB or ./snipvault.db)")
    e.add_argument("--force", action="store_true", help="overwrite files that already exist")
    i = sub.add_parser("import-dir", help="import a folder of files as snippets")
    i.add_argument("folder", help="folder to read")
    i.add_argument("--db", default=None,
                   help="database file (default: $SNIPVAULT_DB or ./snipvault.db)")
    i.add_argument("--on-duplicate", choices=("add", "skip", "replace"), default="add",
                   help="what to do with a same title and language (default: add)")
    i.add_argument("--dry-run", action="store_true", help="show the result without saving")
    d = sub.add_parser("duplicates", help="list snippets with similar bodies")
    d.add_argument("--db", default=None,
                   help="database file (default: $SNIPVAULT_DB or ./snipvault.db)")
    d.add_argument("--threshold", type=float, default=0.8,
                   help="minimum similarity, above 0 and at most 1 (default: 0.8)")
    return p


def _duplicates_command(args):
    from . import db
    db_path = args.db or os.environ.get("SNIPVAULT_DB", "snipvault.db")
    if not os.path.exists(db_path):
        print(f"error: database not found: {db_path}", file=sys.stderr)
        return 1
    conn = db.connect(db_path)
    try:
        pairs = db.find_similar(conn, args.threshold)
    except db.ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    for p in pairs:
        a, b = p["a"], p["b"]
        print(f"{p['similarity'] * 100:.1f}%  #{a['id']} {a['title']} ({a['language']})"
              f"  ~  #{b['id']} {b['title']} ({b['language']})")
    print(f"{len(pairs)} similar pair(s) at threshold {args.threshold:g}")
    return 0


def _folder_command(args):
    from . import db
    from .folder import FolderError, export_folder, read_folder
    db_path = args.db or os.environ.get("SNIPVAULT_DB", "snipvault.db")
    try:
        if args.command == "export-dir":
            if not os.path.exists(db_path):
                raise FolderError(f"database not found: {db_path}")
            conn = db.connect(db_path)
            try:
                names = export_folder(conn, args.folder, overwrite=args.force)
            finally:
                conn.close()
            print(f"exported {len(names)} snippet(s) from {db_path} to {args.folder}")
            return 0
        items, skipped = read_folder(args.folder)
        db.init_db(db_path)
        conn = db.connect(db_path)
        try:
            report = db.import_report(conn, items, args.on_duplicate, dry_run=args.dry_run)
        finally:
            conn.close()
    except (FolderError, db.ValidationError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for rel in skipped:
        print(f"warning: skipped {rel} (not UTF-8 text)", file=sys.stderr)
    print(f"{'would import' if args.dry_run else 'imported'} {report['imported']}, "
          f"skipped {report['skipped']}, replaced {report['replaced']} "
          f"from {args.folder}" + (" (dry run, nothing saved)" if args.dry_run else ""))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "duplicates":
        return _duplicates_command(args)
    if args.command in ("export-dir", "import-dir"):
        return _folder_command(args)
    if args.command == "backup":
        from .db import BackupError, backup
        db_path = args.db or os.environ.get("SNIPVAULT_DB", "snipvault.db")
        try:
            n = backup(db_path, args.dest, overwrite=args.force)
        except BackupError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"backed up {n} snippet(s) from {db_path} to {args.dest}")
        return 0
    token = args.token or os.environ.get("SNIPVAULT_TOKEN") or None
    if args.host not in LOCAL_HOSTS and not args.allow_remote:
        print(f"error: refusing to bind to {args.host}: snipvault has no login. "
              "Pass --allow-remote if you really mean it.", file=sys.stderr)
        return 2
    from .app import create_app
    db_path = args.db or os.environ.get("SNIPVAULT_DB", "snipvault.db")
    app = create_app(db_path, token=token)
    print(f"snipvault {__version__} serving {os.path.abspath(db_path)} "
          f"at http://{args.host}:{args.port}/"
          f"{' (access token required)' if token else ''}", flush=True)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
