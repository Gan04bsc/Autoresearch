from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl
from litagent.schema import missing_paper_fields, normalize_paper

REQUIRED_REPORT_SECTIONS = [
    "Executive Summary",
    "Field Background",
    "Core Problems",
    "Technical Route Categories",
    "Representative Papers",
    "Survey Paper Synthesis",
    "Technical Paper Synthesis",
    "Unresolved Problems",
    "Future Research / Innovation Directions",
    "Recommended Reading Order",
    "References",
]


def nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def parse_quality_metrics(workspace: Path, selected: list[dict[str, Any]]) -> dict[str, Any]:
    downloaded_pdf_count = 0
    parsed_markdown_count = 0
    notes_from_parsed_markdown = 0
    notes_from_pdf_text = 0
    notes_from_abstract_fallback = 0
    notes_with_unknown_source = 0

    for paper in selected:
        local_pdf_path = paper.get("local_pdf_path")
        if local_pdf_path and nonempty_file(workspace / str(local_pdf_path)):
            downloaded_pdf_count += 1

        parsed_markdown_path = paper.get("parsed_markdown_path")
        has_parsed_markdown = bool(
            parsed_markdown_path and nonempty_file(workspace / str(parsed_markdown_path))
        )
        if has_parsed_markdown:
            parsed_markdown_count += 1

        metadata = read_json(
            workspace / "library" / "metadata" / f"{paper['paper_id']}.json",
            default={},
        ) or {}
        text_source = str(metadata.get("text_source") or "")
        note_path = workspace / "library" / "notes" / f"{paper['paper_id']}.md"
        if not note_path.exists():
            continue
        if has_parsed_markdown and text_source and not text_source.startswith("abstract"):
            notes_from_parsed_markdown += 1
        elif text_source == "pdf":
            notes_from_pdf_text += 1
        elif text_source.startswith("abstract") or text_source == "":
            notes_from_abstract_fallback += 1
        else:
            notes_with_unknown_source += 1

    parse_success_rate = (
        parsed_markdown_count / downloaded_pdf_count if downloaded_pdf_count else 0.0
    )
    return {
        "selected_count": len(selected),
        "downloaded_pdf_count": downloaded_pdf_count,
        "parsed_markdown_count": parsed_markdown_count,
        "parse_success_rate": round(parse_success_rate, 4),
        "notes_from_parsed_markdown": notes_from_parsed_markdown,
        "notes_from_pdf_text": notes_from_pdf_text,
        "notes_from_abstract_fallback": notes_from_abstract_fallback,
        "notes_with_unknown_source": notes_with_unknown_source,
    }


def audit_workspace(workspace: Path) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    required_files = [
        "research_plan.json",
        "research_plan.md",
        "data/raw_results.jsonl",
        "data/papers.jsonl",
        "data/selected_papers.jsonl",
        "knowledge/base_knowledge.md",
        "knowledge/topic_map.md",
        "knowledge/index.md",
        "reports/final_report.md",
        "logs/downloads.jsonl",
    ]
    for relative_path in required_files:
        if not (workspace / relative_path).exists():
            issues.append(f"Missing required file: {relative_path}")

    plan = read_json(workspace / "research_plan.json", default={}) or {}
    for field in (
        "topic",
        "goal",
        "core_questions",
        "include_keywords",
        "exclude_keywords",
        "search_queries",
        "date_range",
        "max_results_per_source",
        "selection_count",
        "ranking_policy",
    ):
        if field not in plan:
            issues.append(f"research_plan.json missing field: {field}")

    selected = [
        normalize_paper(paper) for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    if not selected:
        issues.append("No selected papers found.")

    for paper in selected:
        missing = missing_paper_fields(paper)
        if missing:
            issues.append(
                f"{paper.get('paper_id', 'unknown')} missing paper schema fields: {missing}"
            )
        note_path = workspace / "library" / "notes" / f"{paper['paper_id']}.md"
        metadata_path = workspace / "library" / "metadata" / f"{paper['paper_id']}.json"
        if not note_path.exists():
            issues.append(
                f"Missing note for {paper['paper_id']}: {note_path.relative_to(workspace)}"
            )
        if not metadata_path.exists():
            issues.append(
                f"Missing metadata for {paper['paper_id']}: {metadata_path.relative_to(workspace)}"
            )
        if paper.get("download_status") in {"failed", "skipped"}:
            warnings.append(
                f"{paper['paper_id']} PDF download {paper.get('download_status')}: "
                f"{paper.get('download_error') or 'no reason recorded'}"
            )

    parse_quality = parse_quality_metrics(workspace, selected)
    downloaded_pdf_count = parse_quality["downloaded_pdf_count"]
    parsed_markdown_count = parse_quality["parsed_markdown_count"]
    notes_from_abstract_fallback = parse_quality["notes_from_abstract_fallback"]

    if downloaded_pdf_count and parsed_markdown_count == 0:
        issues.append(
            "No parsed Markdown files were produced for downloaded selected PDFs; "
            "real-review quality is not acceptable."
        )
    elif downloaded_pdf_count and parsed_markdown_count < downloaded_pdf_count:
        warnings.append(
            f"Parsed Markdown coverage is incomplete: "
            f"{parsed_markdown_count}/{downloaded_pdf_count} downloaded PDFs."
        )

    if notes_from_abstract_fallback:
        warnings.append(
            f"{notes_from_abstract_fallback} notes were generated from abstract fallback; "
            "inspect before using the report as a real review."
        )

    report_path = workspace / "reports" / "final_report.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    for section in REQUIRED_REPORT_SECTIONS:
        if f"## {section}" not in report_text:
            issues.append(f"final_report.md missing section: {section}")

    if selected and not re.search(r"\[p-[a-f0-9]{12}\]", report_text):
        issues.append("final_report.md does not include traceable paper_id citations.")

    result = {
        "passed": not issues,
        "issues": issues,
        "warnings": warnings,
        "selected_count": len(selected),
        "parse_quality": parse_quality,
    }
    write_audit_report(workspace, result)
    return result


def write_audit_report(workspace: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Audit Report",
        "",
        f"Status: {'PASS' if result['passed'] else 'FAIL'}",
        f"Selected papers: {result.get('selected_count', 0)}",
        f"Downloaded PDFs: {result.get('parse_quality', {}).get('downloaded_pdf_count', 0)}",
        f"Parsed Markdown files: {result.get('parse_quality', {}).get('parsed_markdown_count', 0)}",
        f"Parse success rate: {result.get('parse_quality', {}).get('parse_success_rate', 0.0):.0%}",
        (
            "Notes from parsed Markdown: "
            f"{result.get('parse_quality', {}).get('notes_from_parsed_markdown', 0)}"
        ),
        (
            "Notes from abstract fallback: "
            f"{result.get('parse_quality', {}).get('notes_from_abstract_fallback', 0)}"
        ),
        "",
        "## Issues",
        "",
    ]
    issues = result.get("issues") or []
    lines.extend(f"- {issue}" for issue in issues)
    if not issues:
        lines.append("- None")

    lines.extend(["", "## Warnings", ""])
    warnings = result.get("warnings") or []
    lines.extend(f"- {warning}" for warning in warnings)
    if not warnings:
        lines.append("- None")
    lines.append("")

    path = workspace / "logs" / "audit_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
