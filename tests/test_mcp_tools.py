from pathlib import Path
from uuid import uuid4

from litagent.io import read_jsonl
from litagent.mcp_server import handle_request
from litagent.mcp_tools import call_tool, tool_definitions


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_tool_definitions_include_agent_workflow_tools() -> None:
    names = {tool["name"] for tool in tool_definitions()}

    assert "litagent_plan" in names
    assert "litagent_search" in names
    assert "litagent_status" in names
    assert "litagent_audit" in names
    assert "litagent_inspect_workspace" in names
    assert "litagent_review_selection" in names
    assert "litagent_build_evidence" in names
    assert "litagent_export_wiki" in names
    assert "litagent_sync_library" in names
    assert "litagent_library_status" in names
    assert "litagent_job_create" in names
    assert "litagent_job_status" in names
    assert "litagent_job_cancel" in names
    assert "litagent_job_run_next" in names


def test_mcp_call_tool_runs_mock_plan_search_dedup_status() -> None:
    workspace = workspace_path("mcp")

    plan = call_tool(
        "litagent_plan",
        {"topic": "agentic literature review tools", "workspace": str(workspace), "max_papers": 3},
    )
    search = call_tool(
        "litagent_search",
        {"workspace": str(workspace), "mock": True, "run_id": "mcp-run"},
    )
    dedup = call_tool("litagent_dedup", {"workspace": str(workspace), "max_papers": 3})
    review = call_tool("litagent_review_selection", {"workspace": str(workspace)})
    status = call_tool("litagent_status", {"workspace": str(workspace)})
    inspection = call_tool("litagent_inspect_workspace", {"workspace": str(workspace)})
    library = call_tool(
        "litagent_sync_library",
        {
            "workspace": str(workspace),
            "library_db": str(workspace / "library.db"),
            "topic_slug": "mcp-topic",
        },
    )
    library_status = call_tool(
        "litagent_library_status",
        {"library_db": str(workspace / "library.db")},
    )

    assert plan["ok"]
    assert search["raw_results"] >= 5
    assert search["search_run_id"] == "mcp-run"
    assert dedup["selected"] == 3
    assert review["selected_count"] == 3
    assert status["counts"]["selected_papers"] == 3
    assert inspection["quality_level"] == "smoke_test_run"
    assert "recommended_next_action" in inspection
    assert library["papers_synced"] == 3
    assert library_status["counts"]["papers"] == 3
    assert len(read_jsonl(workspace / "data" / "selected_papers.jsonl")) == 3


def test_mcp_job_tools_create_status_cancel() -> None:
    workspace = workspace_path("mcp-jobs")
    jobs_db = workspace / "jobs.db"

    created = call_tool(
        "litagent_job_create",
        {
            "topic": "agentic literature review tools",
            "workspace": str(workspace / "topic"),
            "jobs_db": str(jobs_db),
            "max_papers": 3,
            "mock": True,
        },
    )
    job_id = created["job"]["id"]
    status = call_tool("litagent_job_status", {"jobs_db": str(jobs_db), "job_id": job_id})
    listed = call_tool("litagent_job_list", {"jobs_db": str(jobs_db)})
    cancelled = call_tool("litagent_job_cancel", {"jobs_db": str(jobs_db), "job_id": job_id})

    assert created["job"]["status"] == "queued"
    assert status["job"]["id"] == job_id
    assert listed["jobs"][0]["id"] == job_id
    assert cancelled["job"]["status"] == "cancelled"


def test_mcp_server_handles_initialize_and_tools_list() -> None:
    initialize = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    tools = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert initialize is not None
    assert initialize["result"]["serverInfo"]["name"] == "litagent-mcp"
    assert tools is not None
    assert any(tool["name"] == "litagent_status" for tool in tools["result"]["tools"])


def test_mcp_server_handles_tool_call() -> None:
    workspace = workspace_path("mcp-server")
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "litagent_plan",
                "arguments": {"topic": "test topic", "workspace": str(workspace)},
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is False
    assert "test topic" in response["result"]["content"][0]["text"]
