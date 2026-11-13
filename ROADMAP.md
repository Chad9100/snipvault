# Roadmap

Ideas for after v0.1, roughly in priority order.

1. **Real full-text search.** Use SQLite FTS5 (when available) with ranking and
   snippet highlighting instead of the current `LIKE` matching.
2. **Syntax highlighting.** Highlight on the server (Pygments as an optional
   extra) or with a small vendored script, keeping the no-framework approach.
3. **Collections and favourites.** Pin snippets, group them, and sort by
   recently used.
4. **Command line client.** `snipvault add`, `snipvault get`, `snipvault search`
   talking to the local database or the REST API.
5. **Import from other tools.** GitHub Gists and plain folders of files.
Done: fuzzy duplicate detection by body similarity (`snipvault duplicates`,
`/api/duplicates`); `snipvault export-dir` / `import-dir` (folder of files with a small
header); optional shared access token (`--token` / `$SNIPVAULT_TOKEN`, login page
and bearer header) with a "Log out" button in the page header; `snipvault backup` (SQLite backup API); duplicate handling on import
(`on_duplicate=add|skip|replace`); import dry run (`dry_run=1`); snippet history in the REST API (versions on edit,
unified diff, restore) and in the web UI (History page with diffs and restore).
