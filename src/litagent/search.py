from __future__ import annotations

from pathlib import Path
from typing import Any

from litagent.io import append_jsonl, read_json, write_jsonl
from litagent.providers import SearchProvider, default_providers, mock_search_results
from litagent.schema import normalize_paper
from litagent.workspace import create_workspace


def load_plan(workspace: Path) -> dict[str, Any]:
    plan = read_json(workspace / "research_plan.json")
    if not plan:
        msg = f"Missing research plan: {workspace / 'research_plan.json'}"
        raise FileNotFoundError(msg)
    return plan


def execute_search(
    workspace: Path,
    *,
    providers: dict[str, SearchProvider] | None = None,
    mock: bool = False,
) -> list[dict[str, Any]]:
    create_workspace(workspace)
    plan = load_plan(workspace)

    if mock:
        rows = [
            normalize_paper(
                {
                    **paper,
                    "query": plan["topic"],
                    "source_query": "mock",
                }
            )
            for paper in mock_search_results(plan["topic"])
        ]
        write_jsonl(workspace / "data" / "raw_results.jsonl", rows)
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
        for query in queries:
            try:
                for paper in provider.search(query, max_results):
                    raw_rows.append(
                        normalize_paper(
                            {
                                **paper,
                                "query": plan["topic"],
                                "source_query": query,
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

    write_jsonl(workspace / "data" / "raw_results.jsonl", raw_rows)
    return raw_rows
