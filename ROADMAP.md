# Roadmap

Ideas for after v0.1, roughly in priority order.

1. **Real full-text search.** Use SQLite FTS5 (when available) with ranking and
   snippet highlighting instead of the current `LIKE` matching.
2. **Syntax highlighting.** Highlight on the server (Pygments as an optional
   extra) or with a small vendored script, keeping the no-framework approach.
3. **Snippet history.** Keep previous versions of a snippet on every edit with a
   simple diff view and restore.
4. **Collections and favourites.** Pin snippets, group them, and sort by
   recently used.
5. **Optional access token.** A single shared token so `--allow-remote` can be
   used more safely on a trusted network.
6. **Command line client.** `snipvault add`, `snipvault get`, `snipvault search`
   talking to the local database or the REST API.
7. **Import from other tools.** GitHub Gists and plain folders of files.
8. **Duplicate detection** on import, with a skip/replace choice.
9. **Backups.** `snipvault backup` using the SQLite backup API.
