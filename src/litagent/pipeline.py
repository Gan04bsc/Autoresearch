from __future__ import annotations

from pathlib import Path
from typing import Any

from litagent.audit import audit_workspace
from litagent.classifier import classify_papers
from litagent.dedup import dedup_and_rank
from litagent.downloader import download_pdfs
from litagent.evidence import build_evidence_table
from litagent.io import append_jsonl
from litagent.knowledge import build_knowledge
from litagent.mineru import parse_selected_pdfs
from litagent.planner import write_research_plan
from litagent.reader import generate_notes
from litagent.report import generate_final_report
from litagent.search import execute_search
from litagent.workspace import create_workspace


def run_pipeline(
    topic: str,
    workspace: Path,
    *,
    max_papers: int = 30,
    max_results_per_source: int = 50,
    mock: bool = False,
    mineru_mode: str = "off",
    mineru_timeout: int = 300,
) -> dict[str, Any]:
    create_workspace(workspace)
    run_log = workspace / "logs" / "runs.jsonl"
    append_jsonl(run_log, {"event": "run_started", "topic": topic, "mock": mock})

    plan = write_research_plan(
        workspace,
        topic,
        max_results_per_source=max_results_per_source,
        selection_count=max_papers,
    )
    append_jsonl(run_log, {"event": "plan_written", "selection_count": max_papers})

    raw_results = execute_search(workspace, mock=mock)
    append_jsonl(run_log, {"event": "search_completed", "raw_results": len(raw_results)})

    selected = dedup_and_rank(workspace, selection_count=max_papers)
    append_jsonl(run_log, {"event": "dedup_completed", "selected": len(selected)})

    downloaded = download_pdfs(workspace)
    append_jsonl(run_log, {"event": "download_completed", "papers": len(downloaded)})

    parsed = parse_selected_pdfs(workspace, mode=mineru_mode, timeout=mineru_timeout)
    append_jsonl(
        run_log,
        {
            "event": "parse_completed",
            "papers": len(parsed),
            "mineru_mode": mineru_mode,
        },
    )

    classified = classify_papers(workspace)
    append_jsonl(run_log, {"event": "classification_completed", "papers": len(classified)})

    notes = generate_notes(workspace)
    append_jsonl(run_log, {"event": "notes_completed", "papers": len(notes)})

    build_knowledge(workspace)
    append_jsonl(run_log, {"event": "knowledge_completed"})

    build_evidence_table(workspace)
    append_jsonl(run_log, {"event": "evidence_completed"})

    generate_final_report(workspace)
    append_jsonl(run_log, {"event": "report_completed"})

    audit = audit_workspace(workspace)
    append_jsonl(run_log, {"event": "audit_completed", "passed": audit["passed"]})

    return {
        "plan": plan,
        "raw_results": len(raw_results),
        "selected": len(selected),
        "audit": audit,
    }
