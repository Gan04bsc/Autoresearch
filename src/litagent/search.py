from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from litagent.io import append_jsonl, read_json, write_json, write_jsonl
from litagent.providers import SearchProvider, default_providers, mock_search_results
from litagent.schema import normalize_paper
from litagent.workspace import create_workspace


def load_plan(workspace: Path) -> dict[str, Any]:
    plan = read_json(workspace / "research_plan.json")
    if not plan:
        msg = f"Missing research plan: {workspace / 'research_plan.json'}"
        raise FileNotFoundError(msg)
    return plan


def new_search_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex[:8]}"


def search_run_dir(workspace: Path, run_id: str) -> Path:
    return workspace / "data" / "search_runs" / run_id


def latest_search_run_metadata(workspace: Path) -> dict[str, Any]:
    return read_json(workspace / "data" / "search_runs" / "latest.json", default={}) or {}


def write_search_outputs(
    workspace: Path,
    rows: list[dict[str, Any]],
    *,
    run_id: str,
    created_at: str,
    mock: bool,
    plan: dict[str, Any],
) -> None:
    metadata = {
        "run_id": run_id,
        "created_at": created_at,
        "mock": mock,
        "topic": plan.get("topic"),
        "raw_results": len(rows),
        "search_queries": plan.get("search_queries") or {},
    }
    run_dir = search_run_dir(workspace, run_id)
    write_jsonl(run_dir / "raw_results.jsonl", rows)
    write_json(run_dir / "metadata.json", metadata)
    write_json(workspace / "data" / "search_runs" / "latest.json", metadata)
    # Backward-compatible view of the latest search run for agent inspection.
    write_jsonl(workspace / "data" / "raw_results.jsonl", rows)


def execute_search(
    workspace: Path,
    *,
    providers: dict[str, SearchProvider] | None = None,
    mock: bool = False,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    create_workspace(workspace)
    plan = load_plan(workspace)
    run_id = run_id or new_search_run_id()
    created_at = datetime.now(UTC).isoformat()

    if mock:
        rows = [
            normalize_paper(
                {
                    **paper,
                    "query": plan["topic"],
                    "source_query": "mock",
                    "search_source": "mock",
                    "search_run_id": run_id,
                    "search_created_at": created_at,
                }
            )
            for paper in mock_search_results(plan["topic"])
        ]
        write_search_outputs(
            workspace,
            rows,
            run_id=run_id,
            created_at=created_at,
            mock=True,
            plan=plan,
        )
        return rows

    providers = providers or default_providers()
    raw_rows: list[dict[str, Any]] = []
    errors_path = workspace / "logs" / "search_errors.jsonl"
    max_results = int(plan.get("max_results_per_source") or 50)

    for source, queries in plan.get("search_queries", {}).items():
        provider = providers.get(source)
        if provider is None:
            append_jsonl(
                errors_path,
                {"source": source, "error": "provider is not configured", "recoverable": True},
            )
            continue
        for query_index, query in enumerate(queries):
            try:
                for paper in provider.search(query, max_results):
                    raw_rows.append(
                        normalize_paper(
                            {
                                **paper,
                                "query": plan["topic"],
                                "source_query": query,
                                "source_query_index": query_index,
                                "search_source": source,
                                "search_run_id": run_id,
                                "search_created_at": created_at,
                            }
                        )
                    )
            except Exception as exc:  # noqa: BLE001 - provider failures must not stop pipeline
                append_jsonl(
                    errors_path,
                    {
                        "source": source,
                        "query": query,
                        "error": str(exc),
                        "recoverable": True,
                    },
                )

    write_search_outputs(
        workspace,
        raw_rows,
        run_id=run_id,
        created_at=created_at,
        mock=False,
        plan=plan,
    )
    return raw_rows
