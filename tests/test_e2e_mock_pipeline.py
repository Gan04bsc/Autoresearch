from pathlib import Path
from uuid import uuid4

from litagent.cli import main
from litagent.io import read_jsonl


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_mock_run_generates_full_workspace_outputs() -> None:
    workspace = workspace_path("run")

    result = main(
        [
            "run",
            "agentic literature review automation",
            "--workspace",
            str(workspace),
            "--max-papers",
            "5",
            "--mock",
        ]
    )

    assert result == 0
    selected = read_jsonl(workspace / "data" / "selected_papers.jsonl")
    assert len(selected) == 5
    assert all(
        (workspace / "library" / "notes" / f"{paper['paper_id']}.md").is_file()
        for paper in selected
    )
    assert (workspace / "knowledge" / "base_knowledge.md").is_file()
    assert (workspace / "knowledge" / "topic_map.md").is_file()
    assert (workspace / "knowledge" / "index.md").is_file()
    report = (workspace / "reports" / "final_report.md").read_text(encoding="utf-8")
    assert "## 执行摘要" in report
    assert "## 参考文献" in report
    assert report.count("[p-") >= 5
    audit = (workspace / "logs" / "audit_report.md").read_text(encoding="utf-8")
    assert "Status: PASS" in audit
