from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl
from litagent.schema import format_short_citation, normalize_paper


def selected_papers_table(papers: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Paper ID | Title | Year | Type | Citations | Sources |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for paper in papers:
        title = (paper.get("title") or "").replace("|", "\\|")
        sources = ", ".join(paper.get("source") or [])
        lines.append(
            f"| {paper['paper_id']} | {title} | {paper.get('year') or ''} | "
            f"{paper.get('paper_type') or 'unknown'} | {paper.get('citation_count') or 0} | "
            f"{sources} |"
        )
    return lines


def grouped_by_type(papers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        grouped[paper.get("paper_type") or "unknown"].append(paper)
    return dict(grouped)


def failed_download_lines(papers: list[dict[str, Any]]) -> list[str]:
    failures = [
        paper
        for paper in papers
        if paper.get("download_status") in {"failed", "skipped"} and not paper.get("local_pdf_path")
    ]
    if not failures:
        return ["- No failed or skipped downloads in the selected set."]
    return [
        (
            f"- {paper['paper_id']}: {paper.get('download_status')} - "
            f"{paper.get('download_error') or 'N/A'}"
        )
        for paper in failures
    ]


def generate_final_report(workspace: Path) -> str:
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    papers = [
        normalize_paper(paper) for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    grouped = grouped_by_type(papers)
    top_ids = ", ".join(f"[{paper['paper_id']}]" for paper in papers[:5]) or "[no-papers]"
    search_queries = plan.get("search_queries") or {}

    lines = [
        "# Final Research Report",
        "",
        "## Executive Summary",
        "",
        f"This report summarizes `{plan.get('topic', 'the topic')}` using {len(papers)} selected "
        f"papers. The strongest evidence base in this run is {top_ids}.",
        "",
        "## Field Background",
        "",
        "The selected papers define the field through survey framing, technical systems, "
        "benchmarks, datasets, and position arguments. All conclusions in this MVP report are "
        "grounded in metadata, abstracts, generated notes, and paper IDs.",
        "",
        "## Core Problems",
        "",
        *[f"- {question}" for question in plan.get("core_questions", [])],
        "",
        "## Technical Route Categories",
        "",
    ]
    for paper_type, group in sorted(grouped.items()):
        refs = ", ".join(f"[{paper['paper_id']}]" for paper in group)
        lines.append(f"- {paper_type}: {len(group)} papers, including {refs}.")

    lines.extend(
        [
            "",
            "## Representative Papers",
            "",
            *selected_papers_table(papers),
            "",
            "## Survey Paper Synthesis",
            "",
        ]
    )
    survey = grouped.get("survey", [])
    if survey:
        lines.extend(
            (
                f"- {paper.get('title')} frames the area and should be read first. "
                f"[{paper['paper_id']}]"
            )
            for paper in survey
        )
    else:
        lines.append("- No survey paper was selected in this run.")

    lines.extend(["", "## Technical Paper Synthesis", ""])
    technical_like = [
        paper
        for paper in papers
        if paper.get("paper_type") in {"technical", "system", "benchmark", "dataset"}
    ]
    if technical_like:
        lines.extend(
            f"- {paper.get('title')} contributes to the {paper.get('paper_type')} branch. "
            f"[{paper['paper_id']}]"
            for paper in technical_like
        )
    else:
        lines.append("- No technical/system/benchmark/dataset papers were selected.")

    lines.extend(
        [
            "",
            "## Unresolved Problems",
            "",
            (
                "- Evidence traceability and hallucination control need stronger audit loops. "
                f"{top_ids}"
            ),
            (
                "- Cross-source metadata duplication and inconsistent identifiers need robust "
                f"merging. {top_ids}"
            ),
            (
                "- Benchmarks for end-to-end literature research agents are still immature. "
                f"{top_ids}"
            ),
            "",
            "## Future Research / Innovation Directions",
            "",
            f"- Build citation-faithfulness benchmarks for final reports. {top_ids}",
            (
                "- Add human-in-the-loop review for paper inclusion, classification, and claims. "
                f"{top_ids}"
            ),
            f"- Improve PDF parsing, section extraction, and claim-to-source alignment. {top_ids}",
            f"- Integrate Zotero/Obsidian workflows and incremental updates. {top_ids}",
            (
                "- Compare agentic search strategies across arXiv, Semantic Scholar, and "
                f"OpenAlex. {top_ids}"
            ),
            "",
            "## Recommended Reading Order",
            "",
        ]
    )
    lines.extend(
        f"{index}. {paper.get('title')} - {format_short_citation(paper)} [{paper['paper_id']}]"
        for index, paper in enumerate(papers, start=1)
    )

    lines.extend(
        [
            "",
            "## Appendix: Search Queries",
            "",
        ]
    )
    for source, queries in search_queries.items():
        lines.append(f"### {source}")
        lines.extend(f"- `{query}`" for query in queries)
        lines.append("")

    lines.extend(
        [
            "## Appendix: Data Sources",
            "",
            "- arXiv",
            "- Semantic Scholar",
            "- OpenAlex",
            "- Unpaywall for legal open-access PDF lookup",
            "",
            "## Appendix: Failed Download List",
            "",
            *failed_download_lines(papers),
            "",
            "## References",
            "",
        ]
    )
    lines.extend(
        f"- [{paper['paper_id']}] {format_short_citation(paper)}. {paper.get('title')}. "
        f"{paper.get('url') or paper.get('doi') or paper.get('arxiv_id') or 'No URL'}"
        for paper in papers
    )
    lines.append("")

    report = "\n".join(lines)
    path = workspace / "reports" / "final_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return report
