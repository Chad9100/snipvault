# snipvault

A small local web app for storing code snippets. Flask is the only dependency;
data lives in a single SQLite file (stdlib `sqlite3`).

Features (v0.1): create / edit / delete snippets (title, language, body, tags),
tag and language filters, search, a copy button, JSON export and import, and a
REST API under `/api`. The UI is plain server-rendered HTML with one small
vanilla-JS file for the copy button.

## Install and run

```
pip install -e .
snipvault serve              # http://127.0.0.1:5000/, database ./snipvault.db
snipvault serve --port 8000 --db my-snippets.db
```

The database file is created in the current directory (or `$SNIPVAULT_DB`).
Python 3.10+.

## Backups

```
snipvault backup nightly.db              # copies ./snipvault.db (or --db FILE)
snipvault backup nightly.db --force      # overwrite an existing backup
```

This uses SQLite's online backup API, so it is safe to run while `serve` is
running. It refuses to overwrite an existing file without `--force`, never
touches the source, and writes to a temporary file first so a failed backup
cannot leave a half-written copy. Real output from a database with two
snippets (run in an empty temporary directory):

```
$ snipvault backup nightly.db
backed up 2 snippet(s) from snipvault.db to nightly.db
$ snipvault backup nightly.db
error: destination exists (use --force to overwrite): nightly.db
$ snipvault backup nightly.db --force
backed up 2 snippet(s) from snipvault.db to nightly.db
$ snipvault backup x.db --db missing.db
error: database not found: missing.db
```

A backup is a normal snipvault database; restore it by pointing `--db` at it
or copying it back over the original (with the server stopped).

## Security notes

snipvault is a **local-only tool with no login**.

- It binds to `127.0.0.1` by default and refuses any other address unless you
  pass `--allow-remote`. Do not expose it to a network you do not trust.
- HTML forms are protected with a per-session CSRF token; a POST without it is
  rejected with 400.
- `/api` writes require `Content-Type: application/json`, which a cross-site
  HTML form cannot send (so a malicious web page cannot forge them).
- Snippet text is always HTML-escaped when displayed.

## Search

Search is case-insensitive substring matching: every word you type must appear
in the title, body, language or a tag. It is not SQLite FTS5 (see ROADMAP).

## REST API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/snippets?q=&tag=&language=` | list / search |
| POST | `/api/snippets` | create, 201 |
| GET / PUT / DELETE | `/api/snippets/<id>` | 404 as JSON if missing |
| GET | `/api/tags` | tags with counts |
| GET | `/api/export` | export document |
| POST | `/api/import` | export document or a bare list; all-or-nothing |

Timestamps are UTC, taken from the machine's clock.

## Real output

Captured by starting `snipvault serve --port 5057` in an empty temporary
directory, running these curl commands against it, and stopping it. Nothing
below was edited by hand.

```
$ curl -s -X POST /api/snippets (create)
{"body":"items[::-1]","created_at":"2026-11-11T15:38:33Z","id":1,"language":"python","tags":["lists","python"],"title":"Reverse a list","updated_at":"2026-11-11T15:38:33Z"}
$ curl -s "/api/snippets?q=reverse"
[{"body":"items[::-1]","created_at":"2026-11-11T15:38:33Z","id":1,"language":"python","tags":["lists","python"],"title":"Reverse a list","updated_at":"2026-11-11T15:38:33Z"}]
$ curl -s "/api/snippets?tag=shell"
[{"body":"find . -size +100M","created_at":"2026-11-11T15:38:33Z","id":2,"language":"bash","tags":["shell"],"title":"Find big files","updated_at":"2026-11-11T15:38:33Z"}]
$ curl -s /api/tags
[{"count":1,"tag":"lists"},{"count":1,"tag":"python"},{"count":1,"tag":"shell"}]
$ curl -si -X POST /api/snippets (form content type)
HTTP/1.1 415 UNSUPPORTED MEDIA TYPE
$ curl -si -X POST /new (no CSRF token)
HTTP/1.1 400 BAD REQUEST
$ curl -s -X DELETE -w http %{http_code} /api/snippets/2
204
$ curl -s /api/export
{"format":"snipvault","snippets":[{"body":"items[::-1]","created_at":"2026-11-11T15:38:33Z","id":1,"language":"python","tags":["lists","python"],"title":"Reverse a list","updated_at":"2026-11-11T15:38:33Z"}],"version":1}
```

## Development

```
python -m venv .venv
.venv/Scripts/pip install -e . pytest     # Scripts -> bin on Linux/macOS
pytest
```

Tests use Flask's test client and a temporary database per test.

## License

MIT, see LICENSE.
