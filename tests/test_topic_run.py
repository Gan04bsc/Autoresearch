from pathlib import Path
from uuid import uuid4

from litagent.cli import main
from litagent.io import read_json, read_jsonl
from litagent.topic_run import TOPIC_RUN_STEPS


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_topic_run_mock_writes_state_log_manifest_and_wiki() -> None:
    workspace = workspace_path("topic-run")

    result = main(
        [
            "topic-run",
            "agentic literature review automation",
            "--workspace",
            str(workspace),
            "--max-papers",
            "5",
            "--mock",
        ]
    )

    assert result == 0
    state = read_json(workspace / "run_state.json")
    assert state["status"] == "succeeded"
    assert state["step_order"] == TOPIC_RUN_STEPS
    assert all(state["steps"][step]["status"] == "succeeded" for step in TOPIC_RUN_STEPS)
    assert state["steps"]["search"]["output_count"] > 0
    assert state["steps"]["download"]["input_count"] == 5

    run_log = read_jsonl(workspace / "run_log.jsonl")
    assert any(row["event"] == "topic_run_succeeded" for row in run_log)
    assert any(row["event"] == "step_succeeded" and row["step"] == "export-wiki" for row in run_log)

    errors = read_json(workspace / "errors.json")
    assert errors == {"errors": []}

    manifest = read_json(workspace / "artifacts_manifest.json")
    manifest_paths = {item["path"] for item in manifest["artifacts"]}
    assert "run_state.json" in manifest_paths
    assert "run_log.jsonl" in manifest_paths
    assert "artifacts_manifest.json" in manifest_paths
    assert "artifacts_manifest.json" not in manifest["missing"]
    assert "wiki-vault/START_HERE.md" in manifest_paths

    assert (workspace / "logs" / "review_selection.json").is_file()
    assert (workspace / "logs" / "inspect_workspace.json").is_file()
    assert (workspace / "wiki-vault" / "START_HERE.md").is_file()
    assert (workspace / "wiki-vault" / "kb" / "source-index.md").is_file()


def test_topic_run_resumes_by_skipping_succeeded_steps() -> None:
    workspace = workspace_path("topic-run-resume")

    first = main(
        [
            "topic-run",
            "agentic literature review automation",
            "--workspace",
            str(workspace),
            "--max-papers",
            "5",
            "--mock",
        ]
    )
    assert first == 0

    second = main(
        [
            "topic-run",
            "agentic literature review automation",
            "--workspace",
            str(workspace),
            "--max-papers",
            "5",
            "--mock",
        ]
    )

    assert second == 0
    run_log = read_jsonl(workspace / "run_log.jsonl")
    skipped = [row for row in run_log if row["event"] == "step_skipped"]
    assert {row["step"] for row in skipped} >= set(TOPIC_RUN_STEPS)
