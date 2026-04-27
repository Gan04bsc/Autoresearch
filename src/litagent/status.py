from __future__ import annotations

from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl


def file_state(path: Path) -> dict[str, Any]:
    return {
        "exists": path.exists(),
        "path": str(path),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def workspace_status(workspace: Path) -> dict[str, Any]:
    raw_results = read_jsonl(workspace / "data" / "raw_results.jsonl")
    papers = read_jsonl(workspace / "data" / "papers.jsonl")
    selected = read_jsonl(workspace / "data" / "selected_papers.jsonl")
    downloads = read_jsonl(workspace / "logs" / "downloads.jsonl")
    parsing = read_jsonl(workspace / "logs" / "parsing.jsonl")
    audit_report = workspace / "logs" / "audit_report.md"

    notes_dir = workspace / "library" / "notes"
    markdown_dir = workspace / "library" / "markdown"
    pdf_dir = workspace / "library" / "pdfs"

    download_failures = [
        row for row in downloads if row.get("download_status") in {"failed", "skipped"}
    ]
    historical_parse_failures = [row for row in parsing if not row.get("ok")]
    current_parse_failures = [
        {
            "paper_id": paper.get("paper_id"),
            "title": paper.get("title"),
            "parse_status": paper.get("parse_status"),
            "parse_error": paper.get("parse_error"),
        }
        for paper in selected
        if paper.get("parse_status") in {"failed", "skipped"}
    ]

    return {
        "workspace": str(workspace),
        "files": {
            "research_plan_json": file_state(workspace / "research_plan.json"),
            "research_plan_md": file_state(workspace / "research_plan.md"),
            "raw_results": file_state(workspace / "data" / "raw_results.jsonl"),
            "papers": file_state(workspace / "data" / "papers.jsonl"),
            "selected_papers": file_state(workspace / "data" / "selected_papers.jsonl"),
            "final_report": file_state(workspace / "reports" / "final_report.md"),
            "audit_report": file_state(audit_report),
        },
        "counts": {
            "raw_results": len(raw_results),
            "papers": len(papers),
            "selected_papers": len(selected),
            "pdfs": len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.exists() else 0,
            "parsed_markdown": len(list(markdown_dir.glob("*.md"))) if markdown_dir.exists() else 0,
            "notes": len(list(notes_dir.glob("*.md"))) if notes_dir.exists() else 0,
            "download_failures": len(download_failures),
            "parse_failures": len(current_parse_failures),
            "historical_parse_failures": len(historical_parse_failures),
        },
        "plan": read_json(workspace / "research_plan.json", default={}) or {},
        "selected_preview": [
            {
                "paper_id": paper.get("paper_id"),
                "title": paper.get("title"),
                "year": paper.get("year"),
                "paper_type": paper.get("paper_type"),
                "final_score": paper.get("final_score"),
                "download_status": paper.get("download_status"),
                "parse_status": paper.get("parse_status"),
            }
            for paper in selected[:10]
        ],
        "download_failures": download_failures[-10:],
        "parse_failures": current_parse_failures[:10],
        "historical_parse_failures": historical_parse_failures[-10:],
        "audit_passed": audit_report.exists()
        and "Status: PASS" in audit_report.read_text(encoding="utf-8"),
    }


def workspace_status_markdown(workspace: Path) -> str:
    status = workspace_status(workspace)
    counts = status["counts"]
    lines = [
        "# Litagent Workspace Status",
        "",
        f"Workspace: `{status['workspace']}`",
        f"Topic: {status['plan'].get('topic', 'N/A')}",
        f"Audit passed: {status['audit_passed']}",
        "",
        "## Counts",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in counts.items())
    lines.extend(["", "## Selected Preview", ""])
    if status["selected_preview"]:
        for paper in status["selected_preview"]:
            lines.append(
                f"- {paper.get('paper_id')}: {paper.get('title')} "
                f"({paper.get('year')}, {paper.get('paper_type')})"
            )
    else:
        lines.append("- No selected papers yet.")

    lines.extend(["", "## Recent Failures", ""])
    failures = [*status["download_failures"], *status["parse_failures"]]
    if failures:
        for failure in failures[:10]:
            lines.append(f"- {failure}")
    else:
        lines.append("- None")
    if status["historical_parse_failures"] and not status["parse_failures"]:
        lines.append(
            f"- Historical parse log failures: {counts['historical_parse_failures']} "
            "older attempts; current selected papers do not show parse failure."
        )
    lines.append("")
    return "\n".join(lines)
