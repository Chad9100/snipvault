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
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.host not in LOCAL_HOSTS and not args.allow_remote:
        print(f"error: refusing to bind to {args.host}: snipvault has no login. "
              "Pass --allow-remote if you really mean it.", file=sys.stderr)
        return 2
    from .app import create_app
    db_path = args.db or os.environ.get("SNIPVAULT_DB", "snipvault.db")
    app = create_app(db_path)
    print(f"snipvault {__version__} serving {os.path.abspath(db_path)} "
          f"at http://{args.host}:{args.port}/", flush=True)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
