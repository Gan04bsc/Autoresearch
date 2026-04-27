from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from litagent.audit import parse_quality_metrics
from litagent.io import read_jsonl
from litagent.status import workspace_status


def source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        sources = row.get("source") or []
        if not isinstance(sources, list):
            sources = [sources]
        for source in sources:
            if source:
                counts[str(source)] += 1
    return dict(sorted(counts.items()))


def report_has_traceable_citations(report_text: str) -> bool:
    return bool(re.search(r"\[p-[a-f0-9]{12}\]", report_text))


def inspect_workspace(workspace: Path) -> dict[str, Any]:
    status = workspace_status(workspace)
    plan = status.get("plan") or {}
    raw_results = read_jsonl(workspace / "data" / "raw_results.jsonl")
    papers = read_jsonl(workspace / "data" / "papers.jsonl")
    selected = read_jsonl(workspace / "data" / "selected_papers.jsonl")
    audit_report = workspace / "logs" / "audit_report.md"
    audit_text = audit_report.read_text(encoding="utf-8") if audit_report.exists() else ""
    report_path = workspace / "reports" / "final_report.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""

    search_concerns: list[str] = []
    selected_concerns: list[str] = []
    quality_concerns: list[str] = []

    selection_count = int(plan.get("selection_count") or 0)
    if not raw_results:
        search_concerns.append("No raw search results are available.")
    elif selection_count and len(raw_results) < selection_count:
        search_concerns.append(
            "Raw results underfill the requested selection count: "
            f"{len(raw_results)}/{selection_count}."
        )
    elif raw_results and len(raw_results) < 10:
        search_concerns.append(
            f"Only {len(raw_results)} raw results are available; this is usually smoke-test depth."
        )

    counts_by_source = source_counts(raw_results)
    if counts_by_source:
        dominant_source, dominant_count = max(counts_by_source.items(), key=lambda item: item[1])
        if dominant_count / max(1, len(raw_results)) > 0.8:
            search_concerns.append(
                f"Search results are dominated by {dominant_source}: "
                f"{dominant_count}/{len(raw_results)} records."
            )

    if any(str(row.get("source_query")) == "mock" for row in raw_results):
        search_concerns.append("Results came from mock providers, not real academic APIs.")

    if not selected:
        selected_concerns.append("No selected papers are available.")
    else:
        low_relevance = [
            row for row in selected if float(row.get("relevance_score") or 0.0) < 0.35
        ]
        if low_relevance:
            selected_concerns.append(
                f"{len(low_relevance)} selected papers have low deterministic relevance scores."
            )
        unknown_types = [row for row in selected if row.get("paper_type") == "unknown"]
        if unknown_types:
            selected_concerns.append(f"{len(unknown_types)} selected papers are unclassified.")
        missing_abstracts = [row for row in selected if not row.get("abstract")]
        if missing_abstracts:
            selected_concerns.append(f"{len(missing_abstracts)} selected papers lack abstracts.")
        missing_ids = [
            row
            for row in selected
            if not (row.get("doi") or row.get("arxiv_id") or row.get("semantic_scholar_id"))
        ]
        if missing_ids:
            selected_concerns.append(
                f"{len(missing_ids)} selected papers lack DOI, arXiv ID, or Semantic Scholar ID."
            )

    parse_quality = parse_quality_metrics(workspace, selected)
    downloaded_pdf_count = parse_quality["downloaded_pdf_count"]
    parsed_markdown_count = parse_quality["parsed_markdown_count"]
    if downloaded_pdf_count and parsed_markdown_count == 0:
        quality_concerns.append("Downloaded PDFs exist, but no parsed Markdown was produced.")
    elif downloaded_pdf_count and parsed_markdown_count < downloaded_pdf_count:
        quality_concerns.append(
            f"Parsed Markdown coverage is partial: {parsed_markdown_count}/{downloaded_pdf_count}."
        )
    if parse_quality["notes_from_abstract_fallback"]:
        quality_concerns.append(
            f"{parse_quality['notes_from_abstract_fallback']} notes used abstract fallback."
        )

    if audit_report.exists() and "Status: FAIL" in audit_text:
        quality_concerns.append("The last audit failed.")
    elif not audit_report.exists():
        quality_concerns.append("No audit report exists yet.")

    if report_path.exists():
        if not report_has_traceable_citations(report_text):
            quality_concerns.append("Final report lacks traceable paper_id citations.")
        if "Original text insufficient" in report_text or "metadata, abstracts" in report_text:
            quality_concerns.append(
                "Final report appears shallow or metadata-heavy; inspect synthesis before real use."
            )
    else:
        quality_concerns.append("No final report exists yet.")

    all_concerns = [*search_concerns, *selected_concerns, *quality_concerns]
    is_mock = any(str(row.get("source_query")) == "mock" for row in raw_results)
    real_review_ready = (
        bool(selected)
        and bool(report_text)
        and not is_mock
        and not all_concerns
        and parse_quality["parse_success_rate"] >= 0.8
    )
    quality_level = "real-review quality" if real_review_ready else "smoke-test quality"

    if not plan:
        recommended_next_action = "Create a research plan."
    elif not raw_results:
        recommended_next_action = "Run search and inspect raw results."
    elif not selected:
        recommended_next_action = "Run deduplication and inspect selected papers."
    elif downloaded_pdf_count and parsed_markdown_count == 0:
        recommended_next_action = "Fix PDF parsing, rerun parse, then regenerate notes and report."
    elif parse_quality["notes_from_abstract_fallback"]:
        recommended_next_action = (
            "Regenerate notes after successful parsing and rerun report/audit."
        )
    elif is_mock:
        recommended_next_action = "Treat this workspace as a smoke test; prepare a real API run."
    elif not status.get("audit_passed"):
        recommended_next_action = "Fix audit issues and rerun audit."
    elif quality_concerns:
        recommended_next_action = "Review quality concerns before using the report."
    else:
        recommended_next_action = "Proceed with human inspection of the final report."

    return {
        "workspace": str(workspace),
        "quality_level": quality_level,
        "search_result_quality": {
            "raw_results": len(raw_results),
            "deduplicated_papers": len(papers),
            "source_counts": counts_by_source,
            "concerns": search_concerns,
        },
        "selected_paper_relevance": {
            "selected_count": len(selected),
            "average_relevance_score": round(
                sum(float(row.get("relevance_score") or 0.0) for row in selected)
                / max(1, len(selected)),
                4,
            ),
            "type_counts": dict(Counter(str(row.get("paper_type")) for row in selected)),
            "concerns": selected_concerns,
        },
        "parse_report_audit_quality": {
            **parse_quality,
            "audit_passed": status.get("audit_passed"),
            "final_report_exists": report_path.exists(),
            "concerns": quality_concerns,
        },
        "recommended_next_action": recommended_next_action,
    }


def inspect_workspace_markdown(workspace: Path) -> str:
    result = inspect_workspace(workspace)
    search = result["search_result_quality"]
    selected = result["selected_paper_relevance"]
    quality = result["parse_report_audit_quality"]
    lines = [
        "# Litagent Workspace Inspection",
        "",
        f"Workspace: `{result['workspace']}`",
        f"Quality level: {result['quality_level']}",
        f"Recommended next action: {result['recommended_next_action']}",
        "",
        "## Search Result Quality",
        "",
        f"- Raw results: {search['raw_results']}",
        f"- Deduplicated papers: {search['deduplicated_papers']}",
        f"- Source counts: {search['source_counts']}",
        "",
        "## Selected Paper Relevance",
        "",
        f"- Selected papers: {selected['selected_count']}",
        f"- Average relevance score: {selected['average_relevance_score']}",
        f"- Type counts: {selected['type_counts']}",
        "",
        "## Parse / Report / Audit Quality",
        "",
        f"- Downloaded PDFs: {quality['downloaded_pdf_count']}",
        f"- Parsed Markdown files: {quality['parsed_markdown_count']}",
        f"- Parse success rate: {quality['parse_success_rate']:.0%}",
        f"- Notes from parsed Markdown: {quality['notes_from_parsed_markdown']}",
        f"- Notes from abstract fallback: {quality['notes_from_abstract_fallback']}",
        f"- Audit passed: {quality['audit_passed']}",
        "",
        "## Concerns",
        "",
    ]
    concerns = [
        *search["concerns"],
        *selected["concerns"],
        *quality["concerns"],
    ]
    lines.extend(f"- {concern}" for concern in concerns)
    if not concerns:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)
