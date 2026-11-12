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
- Optional access token: start with `SNIPVAULT_TOKEN=... snipvault serve` (or
  `--token`, though arguments show up in process lists). Browsers sign in at
  `/login`; API clients send `Authorization: Bearer <token>`. It is one shared
  secret over plain HTTP, so it is not a substitute for HTTPS on an untrusted
  network. See "Access token" below.
- HTML forms are protected with a per-session CSRF token; a POST without it is
  rejected with 400.
- `/api` writes require `Content-Type: application/json`, which a cross-site
  HTML form cannot send (so a malicious web page cannot forge them).
- Snippet text is always HTML-escaped when displayed.

## Access token

Captured from a real run (`SNIPVAULT_TOKEN=hunter2 snipvault serve --port 5061`
in an empty temporary directory, since stopped):

```
$ SNIPVAULT_TOKEN=hunter2 snipvault serve --port 5061
snipvault 0.1.0 serving snipvault.db at http://127.0.0.1:5061/ (access token required)
$ curl -si /api/tags
HTTP/1.1 401 UNAUTHORIZED
Content-Type: application/json
WWW-Authenticate: Bearer
Vary: Cookie

{"error":"authentication required"}
$ curl -si -H "Authorization: Bearer wrong" /api/tags
HTTP/1.1 401 UNAUTHORIZED
$ curl -s -H "Authorization: Bearer hunter2" /api/tags
[]
$ curl -si /
HTTP/1.1 302 FOUND
Location: /login?next=/
```

Static files stay public; everything else needs the token.

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
| GET | `/api/snippets/<id>/history` | previous versions, newest first |
| GET | `/api/snippets/<id>/history/<vid>[?diff=1]` | one version, optionally with a unified diff against the current body |
| POST | `/api/snippets/<id>/history/<vid>/restore` | make a version current again |
| GET | `/api/export` | export document |
| POST | `/api/import` | export document or a bare list; all-or-nothing |

Import takes `?on_duplicate=add|skip|replace` (default `add`; the web import
page has the same choice). A duplicate is a snippet with the same title
(case-insensitive) and language as one already stored or earlier in the file.
`skip` keeps the stored one, `replace` overwrites its body and tags. The
response is `{"imported", "skipped", "replaced"}`.

Timestamps are UTC, taken from the machine's clock.

## Real output

Captured by starting `snipvault serve --port 5057` in an empty temporary
directory, running these curl commands against it, and stopping it. Nothing
below was edited by hand. (The timestamps in this first block come from the
machine clock of the capture PC, which ran about three hours fast, so they are
not real UTC. The dry-run block further down does not show timestamps.)

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

### Snippet history

Every edit that changes a snippet (via the API, the web form, or an import with
`on_duplicate=replace`) first stores the previous title, language, body and tags
as a version. Saving without changes stores nothing. At most 50 versions are
kept per snippet and they are deleted with the snippet. Restoring saves the
state it replaces first, so a restore can be undone. History is not part of
JSON export.

In the web UI, the **History** button on a snippet opens `/s/<id>/history`: each
earlier version with a unified diff against the current body and a "Restore this
version" button (a POST with the usual CSRF token).

Captured with Flask's test client in an empty temporary directory (the
timestamp and the random CSRF token are replaced by placeholders):

```
POST /new -> 302
POST /s/1/edit -> 302
GET /s/1/history -> 200
<h1>History of Reverse a list</h1>
<p><a href="/s/1">&larr; back to snippet</a></p>
<section class="version">
  <h2>Version 1</h2>
  <p class="muted">saved <timestamp omitted></p>
  <p class="muted">Changes from this version to the current one:</p>
  <pre><code>--- version 1
+++ current
@@ -1 +1 @@
-items[::-1]
+list(reversed(items))
</code></pre>
  <form method="post" action="/s/1/history/1/restore" class="inline"
        onsubmit="return confirm('Restore this version? The current one is kept in history.');">
    <input type="hidden" name="csrf_token" value="<token>">
    <button type="submit">Restore this version</button>
  </form>
</section>
POST /s/1/history/1/restore -> 302 /s/1
```

Databases created by older versions are upgraded automatically on start (the
`snippet_versions` table is added, existing snippets are untouched; history
starts from the next edit).

Captured with Flask's test client in an empty temporary directory (the
`*_at` timestamps are omitted from this output on purpose):

```
$ POST /api/snippets -> 201
{"body": "items[::-1]\n", "id": 1, "language": "python", "tags": ["lists"], "title": "Reverse a list"}
$ PUT /api/snippets/1 (edit) -> 200
{"body": "list(reversed(items))\n", "id": 1, "language": "python", "tags": ["lists"], "title": "Reverse a list"}
$ GET /api/snippets/1/history -> 200
[{"body": "items[::-1]\n", "id": 1, "language": "python", "tags": ["lists"], "title": "Reverse a list"}]
$ GET /api/snippets/1/history/1?diff=1 -> 200
--- version 1
+++ current
@@ -1 +1 @@
-items[::-1]
+list(reversed(items))
$ POST /api/snippets/1/history/1/restore -> 200
{"body": "items[::-1]\n", "id": 1, "language": "python", "tags": ["lists"], "title": "Reverse a list"}
$ GET /api/snippets/1/history (restore is undoable) -> 200
[{"body": "list(reversed(items))\n", "id": 2, "language": "python", "tags": ["lists"], "title": "Reverse a list"}, {"body": "items[::-1]\n", "id": 1, "language": "python", "tags": ["lists"], "title": "Reverse a list"}]
```

### Import dry run

Add `?dry_run=1` to `/api/import` (or tick "Dry run" on the web import page) to
see what an import would do without saving anything. The import is carried out
inside a transaction and rolled back, so the counts are exactly what a real run
would give, including duplicates within the file. The response is 200 (a real
import is 201) and adds `"dry_run": true` plus one `{"title", "language",
"action"}` entry per item, where action is `add`, `skip` or `replace`. Invalid
files are still rejected with 400.

Captured with Flask's test client in an empty temporary directory (one stored
snippet, then a file with a duplicate and a new snippet):

```
$ POST /api/import?on_duplicate=replace&dry_run=1 -> 200
{"dry_run": true, "imported": 1, "items": [{"action": "replace", "language": "python", "title": "reverse a list"}, {"action": "add", "language": "bash", "title": "Find big files"}], "replaced": 1, "skipped": 0}
$ GET /api/snippets (still 1 snippet)
$ POST /api/import?on_duplicate=replace -> 201
{"imported": 1, "replaced": 1, "skipped": 0}
$ GET /api/snippets -> 2 snippets
```

### Duplicate handling on import

Captured with Flask's test client in an empty temporary directory (one stored
snippet, then a two-snippet file whose first entry has the same title and
language, imported with `skip` and then `replace`; the second run reports two
replaced because the first run had already added "Find big files"):

```
$ import 1 snippet: {'imported': 1, 'replaced': 0, 'skipped': 0}
$ import 2 snippets (1 duplicate) ?on_duplicate=skip: {"imported": 1, "replaced": 0, "skipped": 1}
$ import 2 snippets (1 duplicate) ?on_duplicate=replace: {"imported": 0, "replaced": 2, "skipped": 0}
bodies: ['find . -size +100M', 'list(reversed(items))']
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
