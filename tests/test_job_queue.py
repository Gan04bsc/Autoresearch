from pathlib import Path
from uuid import uuid4

from litagent.cli import main
from litagent.job_queue import (
    cancel_job,
    create_job,
    job_logs,
    list_jobs,
    run_next_job,
)


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_job_create_list_and_cancel_queued_job() -> None:
    root = workspace_path("jobs")
    jobs_db = root / "jobs.db"
    workspace = root / "topic"

    created = create_job(
        jobs_db=jobs_db,
        topic="多模态模型",
        workspace=workspace,
        max_papers=5,
        mock=True,
    )
    job_id = created["job"]["id"]
    listed = list_jobs(jobs_db=jobs_db)
    cancelled = cancel_job(job_id, jobs_db=jobs_db)
    logs = job_logs(job_id, jobs_db=jobs_db)

    assert created["job"]["status"] == "queued"
    assert listed["jobs"][0]["id"] == job_id
    assert cancelled["job"]["status"] == "cancelled"
    assert any(event["event"] == "job_cancelled" for event in logs["events"])


def test_job_run_next_runs_mock_topic_run_and_syncs_library() -> None:
    root = workspace_path("jobs-run")
    jobs_db = root / "jobs.db"
    library_db = root / "library.db"
    workspace = root / "topic"

    created = create_job(
        jobs_db=jobs_db,
        topic="agentic literature review automation",
        workspace=workspace,
        max_papers=5,
        mock=True,
        sync_library=True,
        library_db=library_db,
        topic_slug="agentic-lit-review",
    )
    result = run_next_job(jobs_db=jobs_db)
    logs = job_logs(created["job"]["id"], jobs_db=jobs_db)

    assert result["ok"] is True
    assert result["job"]["status"] == "succeeded"
    assert result["sync_result"]["papers_synced"] == 5
    assert (workspace / "run_state.json").is_file()
    assert (workspace / "wiki-vault" / "START_HERE.md").is_file()
    assert any(event["event"] == "job_succeeded" for event in logs["events"])
    assert any(row["event"] == "topic_run_succeeded" for row in logs["run_log"])


def test_job_cli_create_status_list_cancel() -> None:
    root = workspace_path("jobs-cli")
    jobs_db = root / "jobs.db"
    workspace = root / "topic"

    created = main(
        [
            "job",
            "create",
            "--jobs-db",
            str(jobs_db),
            "--topic",
            "多模态模型",
            "--workspace",
            str(workspace),
            "--max-papers",
            "5",
            "--mock",
            "--json",
        ]
    )
    jobs = list_jobs(jobs_db=jobs_db)
    job_id = jobs["jobs"][0]["id"]
    status = main(["job", "status", "--jobs-db", str(jobs_db), job_id, "--json"])
    listed = main(["job", "list", "--jobs-db", str(jobs_db), "--json"])
    cancelled = main(["job", "cancel", "--jobs-db", str(jobs_db), job_id, "--json"])

    assert created == 0
    assert status == 0
    assert listed == 0
    assert cancelled == 0
    assert cancel_job(job_id, jobs_db=jobs_db)["job"]["status"] == "cancelled"
