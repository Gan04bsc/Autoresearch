from pathlib import Path
from uuid import uuid4

from litagent.cli import main
from litagent.workspace import WORKSPACE_DIRS, create_workspace


def make_workspace_path(name: str) -> Path:
    root = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_create_workspace_generates_prd_directories() -> None:
    workspace = make_workspace_path("demo")

    create_workspace(workspace)

    for directory in WORKSPACE_DIRS:
        assert (workspace / directory).is_dir()
    assert (workspace / "config" / "sources.yaml").is_file()
    assert (workspace / "config" / "prompts" / "planner.md").is_file()


def test_init_cli_creates_workspace() -> None:
    workspace = make_workspace_path("cli-demo")

    result = main(["init", str(workspace)])

    assert result == 0
    assert (workspace / "data").is_dir()
    assert (workspace / "reports").is_dir()
