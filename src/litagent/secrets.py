from __future__ import annotations

import os
from pathlib import Path


def default_env_files() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [Path.cwd() / ".env", repo_root / ".env"]
    unique: list[Path] = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    return unique


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def get_config_value(name: str, *, env_files: list[Path] | None = None) -> str | None:
    value = os.environ.get(name)
    if value:
        return value

    for path in env_files or default_env_files():
        value = parse_env_file(path).get(name)
        if value:
            return value
    return None

