"""Export snippets to, and import them from, a folder of plain files.

Each snippet becomes one file named after its title. The file starts with a
small header so nothing is lost::

    ---
    title: Reverse a list
    language: python
    tags: lists, python
    ---
    items[::-1]

On import a file without that header still works: the title is the file name
and the language is guessed from the extension.
"""
import os
import re

from . import db

EXTENSIONS = {
    "python": "py", "javascript": "js", "typescript": "ts", "bash": "sh",
    "shell": "sh", "sql": "sql", "html": "html", "css": "css", "json": "json",
    "yaml": "yaml", "go": "go", "rust": "rs", "c": "c", "cpp": "cpp",
    "java": "java", "ruby": "rb", "php": "php", "markdown": "md", "text": "txt",
}
_BY_EXT = {}
for _lang, _ext in EXTENSIONS.items():
    _BY_EXT.setdefault(_ext, _lang)
_BY_EXT.update({"yml": "yaml", "py": "python", "sh": "bash", "md": "markdown"})

_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} \
    | {f"lpt{i}" for i in range(1, 10)}


class FolderError(Exception):
    pass


def _slug(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-")
    if not s:
        s = "snippet"
    if s in _RESERVED:
        s += "-snippet"
    return s


def _extension(language):
    if language in EXTENSIONS:
        return EXTENSIONS[language]
    if re.fullmatch(r"[a-z0-9]{1,10}", language or ""):
        return language
    return "txt"


def render(snippet):
    title = " ".join(snippet["title"].split())
    lines = ["---", f"title: {title}", f"language: {snippet['language']}",
             f"tags: {', '.join(snippet['tags'])}", "---"]
    return "\n".join(lines) + "\n" + snippet["body"]


def export_folder(conn, dest, overwrite=False):
    """Write every snippet to ``dest``; return the list of file names written."""
    snippets = db.export_all(conn)
    used = set()
    plan = []
    for s in snippets:
        base = _slug(s["title"])
        ext = _extension(s["language"])
        name, n = f"{base}.{ext}", 2
        while name.lower() in used:
            name, n = f"{base}-{n}.{ext}", n + 1
        used.add(name.lower())
        plan.append((name, s))
    if os.path.exists(dest) and not os.path.isdir(dest):
        raise FolderError(f"not a folder: {dest}")
    clashes = [n for n, _ in plan if os.path.exists(os.path.join(dest, n))]
    if clashes and not overwrite:
        raise FolderError(f"{len(clashes)} file(s) already exist in {dest}, "
                          f"e.g. {clashes[0]} (use --force to overwrite)")
    os.makedirs(dest, exist_ok=True)
    for name, s in plan:
        with open(os.path.join(dest, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(render(s))
    return [n for n, _ in plan]


def parse_file(name, text):
    """Turn file text into a snippet dict (see the module docstring)."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    stem, _, ext = name.rpartition(".")
    if not stem:
        stem, ext = name, ""
    item = {"title": stem.replace("_", " ").replace("-", " ").strip() or name,
            "language": _BY_EXT.get(ext.lower(), ""), "body": text, "tags": []}
    if text.startswith("---\n"):
        end = text.find("\n---\n", 3)
        if end == -1 and text.endswith("\n---"):
            end = len(text) - 4
        if end != -1:
            for line in text[4:end].split("\n"):
                key, sep, value = line.partition(":")
                key = key.strip().lower()
                if sep and key in ("title", "language", "tags"):
                    item[key] = value.strip()
            item["body"] = text[end + 5:]
    return item


def read_folder(src):
    """Return (items, skipped) from the files under ``src``.

    Hidden files and folders are ignored; files that are not UTF-8 text are
    reported in ``skipped`` instead of failing the whole import."""
    if not os.path.isdir(src):
        raise FolderError(f"folder not found: {src}")
    items, skipped = [], []
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.startswith("."):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, src).replace(os.sep, "/")
            try:
                with open(path, "r", encoding="utf-8", newline="") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                skipped.append(rel)
                continue
            if "\x00" in text:
                skipped.append(rel)
                continue
            items.append(parse_file(name, text))
    return items, skipped
