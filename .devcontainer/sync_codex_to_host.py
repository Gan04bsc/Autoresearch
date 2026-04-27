from __future__ import annotations

import os
import shutil
from pathlib import Path

HOST_CODEX = Path("/mnt/host-codex")
CONTAINER_CODEX = Path(os.environ.get("CODEX_HOME", "/home/vscode/.codex"))

SYNC_ENTRIES = [
    "history.jsonl",
    "session_index.jsonl",
    "sessions",
]


def copy_if_newer(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and source.stat().st_mtime <= target.stat().st_mtime:
        return
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    for child in source.rglob("*"):
        relative = child.relative_to(source)
        destination = target / relative
        if child.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif child.is_file():
            copy_if_newer(child, destination)


def main() -> int:
    if not HOST_CODEX.exists():
        print(f"Host Codex directory not mounted: {HOST_CODEX}")
        return 0

    for entry in SYNC_ENTRIES:
        source = CONTAINER_CODEX / entry
        target = HOST_CODEX / entry
        if not source.exists():
            continue
        if source.is_dir():
            copy_tree(source, target)
        elif source.is_file():
            copy_if_newer(source, target)

    print(f"Synced Codex sessions from {CONTAINER_CODEX} to {HOST_CODEX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
