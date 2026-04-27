from __future__ import annotations

import os
import shutil
from pathlib import Path

HOST_CODEX = Path("/mnt/host-codex")
CONTAINER_CODEX = Path(os.environ.get("CODEX_HOME", "/home/vscode/.codex"))

COPY_ENTRIES = [
    "auth.json",
    "config.toml",
    "version.json",
    "installation_id",
    "history.jsonl",
    "session_index.jsonl",
    "sessions",
    "memories",
    "rules",
    "skills",
]

EXCLUDED_SUFFIXES = (".sqlite", ".sqlite-shm", ".sqlite-wal")


def should_skip(path: Path) -> bool:
    name = path.name
    return (
        name.startswith(".sandbox")
        or name in {".tmp", "tmp", "log", "shell_snapshots"}
        or name.endswith(EXCLUDED_SUFFIXES)
    )


def copy_file(source: Path, target: Path) -> None:
    if target.exists() and os.environ.get("CODEX_SYNC_OVERWRITE") != "1":
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    for child in source.rglob("*"):
        if should_skip(child):
            continue
        relative = child.relative_to(source)
        destination = target / relative
        if child.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif child.is_file():
            copy_file(child, destination)


def main() -> int:
    if not HOST_CODEX.exists():
        print(f"Host Codex directory not mounted: {HOST_CODEX}")
        return 0

    CONTAINER_CODEX.mkdir(parents=True, exist_ok=True)
    for entry in COPY_ENTRIES:
        source = HOST_CODEX / entry
        target = CONTAINER_CODEX / entry
        if not source.exists() or should_skip(source):
            continue
        if source.is_dir():
            copy_tree(source, target)
        elif source.is_file():
            copy_file(source, target)

    print(f"Synced safe Codex state from {HOST_CODEX} to {CONTAINER_CODEX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
