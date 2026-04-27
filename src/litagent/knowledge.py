from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl
from litagent.schema import extract_terms, format_short_citation, normalize_paper


def paper_link(paper: dict[str, Any]) -> str:
    note_path = paper.get("note_path") or str(Path("library") / "notes" / f"{paper['paper_id']}.md")
    return f"[{paper.get('title') or paper['paper_id']}]({note_path})"


def reading_order(papers: list[dict[str, Any]]) -> list[str]:
    return [
        f"{index}. {paper_link(paper)} - {format_short_citation(paper)} [{paper['paper_id']}]"
        for index, paper in enumerate(papers, start=1)
    ]


def group_by_type(papers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        grouped[paper.get("paper_type") or "unknown"].append(paper)
    return dict(grouped)


def write_base_knowledge(
    workspace: Path, plan: dict[str, Any], papers: list[dict[str, Any]]
) -> None:
    topic = plan.get("topic", "Research topic")
    terms = extract_terms(
        " ".join([topic, *[paper.get("abstract", "") for paper in papers]]), limit=20
    )
    routes = sorted(group_by_type(papers))
    content = [
        "# Base Knowledge",
        "",
        "## One-Sentence Definition",
        "",
        f"{topic} is a research area organized here through traceable papers, notes, methods, "
        "evaluation artifacts, and open questions.",
        "",
        "## Why This Field Matters",
        "",
        "It matters because researchers and builders need faster literature entry, better evidence "
        "tracking, and reusable knowledge structures grounded in source papers.",
        "",
        "## Key Terms",
        "",
        *[f"- {term}" for term in terms],
        "",
        "## Prerequisites",
        "",
        "- Academic search APIs and metadata quality",
        "- Literature review methodology",
        "- Citation and evidence tracking",
        "- Basic evaluation design for AI systems",
        "",
        "## Core Questions",
        "",
        *[f"- {question}" for question in plan.get("core_questions", [])],
        "",
        "## Main Technical Routes",
        "",
        *[
            f"- {route}: {len(group_by_type(papers).get(route, []))} selected papers"
            for route in routes
        ],
        "",
        "## Representative Reading Order",
        "",
        *reading_order(papers),
        "",
        "## 1 Day / 1 Week / 1 Month Learning Route",
        "",
        "- 1 day: read the top survey, topic map, and final report executive summary.",
        "- 1 week: read all selected notes, then compare system, benchmark, and dataset papers.",
        "- 1 month: reproduce search/ranking/audit workflows and design a focused follow-up study.",
        "",
    ]
    (workspace / "knowledge" / "base_knowledge.md").write_text("\n".join(content), encoding="utf-8")


def write_topic_map(workspace: Path, plan: dict[str, Any], papers: list[dict[str, Any]]) -> None:
    topic = plan.get("topic", "Research topic")
    grouped = group_by_type(papers)
    lines = [
        "# Topic Map",
        "",
        f"- {topic}",
    ]
    for paper_type, group in sorted(grouped.items()):
        lines.append(f"  - {paper_type}")
        lines.append(f"    - Representative questions and methods for {paper_type}")
        for paper in group:
            lines.append(f"      - {paper_link(paper)} [{paper['paper_id']}]")
    lines.append("")
    (workspace / "knowledge" / "topic_map.md").write_text("\n".join(lines), encoding="utf-8")


def write_glossary(workspace: Path, plan: dict[str, Any], papers: list[dict[str, Any]]) -> None:
    terms = extract_terms(
        " ".join([plan.get("topic", ""), *[paper.get("abstract", "") for paper in papers]]), 24
    )
    lines = ["# Glossary", ""]
    for term in terms:
        lines.append(f"- **{term}**: Term extracted from the topic or selected paper abstracts.")
    lines.append("")
    (workspace / "knowledge" / "glossary.md").write_text("\n".join(lines), encoding="utf-8")


def write_index(workspace: Path, papers: list[dict[str, Any]]) -> None:
    lines = [
        "# Knowledge Index",
        "",
        "## Core Files",
        "",
        "- [Base Knowledge](base_knowledge.md)",
        "- [Topic Map](topic_map.md)",
        "- [Glossary](glossary.md)",
        "- [Final Report](../reports/final_report.md)",
        "",
        "## Paper Notes",
        "",
    ]
    lines.extend(f"- {paper_link(paper)} [{paper['paper_id']}]" for paper in papers)
    lines.append("")
    (workspace / "knowledge" / "index.md").write_text("\n".join(lines), encoding="utf-8")


def build_knowledge(workspace: Path) -> list[dict[str, Any]]:
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    papers = [
        normalize_paper(paper) for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    write_base_knowledge(workspace, plan, papers)
    write_topic_map(workspace, plan, papers)
    write_glossary(workspace, plan, papers)
    write_index(workspace, papers)
    return papers
