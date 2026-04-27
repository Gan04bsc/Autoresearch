from __future__ import annotations

from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl, write_json
from litagent.reader import extract_paper_evidence, paper_text
from litagent.schema import normalize_paper

THEME_SPECS: dict[str, dict[str, Any]] = {
    "multi-agent architecture": {
        "fields": ["agent_roles", "pipeline_stages"],
        "terms": [
            "multi-agent",
            "multiple agents",
            "specialized agents",
            "agent decomposition",
            "organizer",
            "collector",
            "composer",
            "refiner",
            "reviewer agent",
            "writer agent",
        ],
        "strict_terms": True,
        "claim": (
            "The literature uses multi-agent decomposition to separate planning, retrieval, "
            "writing, review, and refinement responsibilities."
        ),
    },
    "survey/literature review generation": {
        "fields": ["proposed_system_or_method", "pipeline_stages"],
        "terms": [
            "survey generation",
            "literature review generation",
            "scientific survey generation",
            "review generation",
            "survey writing",
            "literature surveys",
            "related work drafting",
        ],
        "strict_terms": True,
        "claim": (
            "Survey and literature-review generation systems increasingly use staged workflows "
            "instead of one-shot generation."
        ),
    },
    "systematic review workflow": {
        "fields": ["problem_addressed", "retrieval_search_strategy", "pipeline_stages"],
        "terms": [
            "systematic review",
            "screening",
            "data extraction",
            "eligibility",
            "study selection",
            "relevance scoring",
            "prisma",
        ],
        "strict_terms": True,
        "claim": (
            "Systematic-review automation requires operational support for screening, scoring, "
            "extraction, validation, and iterative review rounds."
        ),
    },
    "paper reading agents": {
        "fields": ["agent_roles", "retrieval_search_strategy", "key_findings"],
        "terms": [
            "paper-reading",
            "paper reading",
            "reading agents",
            "read scientific papers",
            "paperguide",
        ],
        "strict_terms": True,
        "claim": (
            "Paper-reading agents are a reusable upstream capability for extracting task-relevant "
            "evidence before synthesis."
        ),
    },
    "citation-aware synthesis": {
        "fields": ["citation_or_evidence_handling", "retrieval_search_strategy"],
        "terms": [
            "citation-aware",
            "citation graph",
            "hierarchical citation graph",
            "citation quality",
            "citation precision",
            "citation recall",
            "cited references",
            "evidence handling",
            "grounding",
        ],
        "strict_terms": True,
        "claim": (
            "Citation-aware synthesis needs source relationships and evidence handling before "
            "the final prose-writing step."
        ),
    },
    "evaluation and benchmarks": {
        "fields": ["evaluation_setup", "datasets_or_benchmarks", "key_findings"],
        "terms": ["evaluation", "benchmark", "dataset", "metrics", "human evaluation"],
        "claim": (
            "Evaluation is multi-dimensional, spanning content quality, structure, citation "
            "quality, retrieval coverage, and human judgment."
        ),
    },
    "limitations and open problems": {
        "fields": ["limitations", "citation_or_evidence_handling"],
        "terms": ["limitation", "challenge", "future work", "hallucination", "gap"],
        "claim": (
            "Open problems remain around citation faithfulness, retrieval coverage, parser "
            "quality, and robust evaluation."
        ),
    },
    "design implications for litagent": {
        "fields": [
            "agent_roles",
            "pipeline_stages",
            "citation_or_evidence_handling",
            "evaluation_setup",
        ],
        "terms": ["agent", "pipeline", "citation", "evaluation", "workflow"],
        "claim": (
            "litagent should keep search, selection, parsing, evidence extraction, synthesis, "
            "and audit as separate inspectable artifacts."
        ),
    },
}


def load_paper_evidence(workspace: Path, paper: dict[str, Any]) -> dict[str, Any]:
    metadata = read_json(
        workspace / "library" / "metadata" / f"{paper['paper_id']}.json",
        default={},
    ) or {}
    evidence = metadata.get("paper_evidence")
    if isinstance(evidence, dict) and evidence.get("fields"):
        return evidence
    text, source = paper_text(workspace, paper)
    return extract_paper_evidence(paper, text, source)


def paper_matches_theme(
    paper: dict[str, Any],
    evidence: dict[str, Any],
    spec: dict[str, Any],
) -> bool:
    terms = [str(term).lower() for term in spec["terms"]]
    fields = evidence.get("fields") or {}
    field_snippets: list[str] = []
    for field in spec["fields"]:
        item = fields.get(field) or {}
        field_snippets.extend(str(snippet) for snippet in item.get("snippets") or [])

    searchable = " ".join(
        [
            str(paper.get("title") or ""),
            str(paper.get("abstract") or ""),
            *field_snippets,
        ]
    ).lower()
    if any(term in searchable for term in terms):
        return True
    if spec.get("strict_terms"):
        return False

    for field in spec["fields"]:
        item = fields.get(field) or {}
        if item.get("source") != "missing" and item.get("snippets"):
            return True
    return False


def evidence_items_for_theme(
    paper: dict[str, Any],
    evidence: dict[str, Any],
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    fields = evidence.get("fields") or {}
    for field in spec["fields"]:
        item = fields.get(field) or {}
        for snippet in item.get("snippets") or []:
            items.append(
                {
                    "paper_id": paper["paper_id"],
                    "title": paper.get("title"),
                    "field": field,
                    "source": item.get("source"),
                    "snippet": snippet,
                }
            )
    return items


def confidence_for(items: list[dict[str, Any]], supporting_papers: list[str]) -> str:
    parsed_count = sum(1 for item in items if item.get("source") == "parsed-full-text")
    if parsed_count >= 3 and len(supporting_papers) >= 2:
        return "high"
    if parsed_count or supporting_papers:
        return "medium"
    return "low"


def theme_row(
    theme: str,
    spec: dict[str, Any],
    papers: list[dict[str, Any]],
    evidences: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    supporting: list[str] = []
    snippets: list[dict[str, Any]] = []
    for paper in papers:
        evidence = evidences[paper["paper_id"]]
        if not paper_matches_theme(paper, evidence, spec):
            continue
        supporting.append(paper["paper_id"])
        snippets.extend(evidence_items_for_theme(paper, evidence, spec))

    limited_snippets = snippets[:12]
    gaps: list[str] = []
    if not supporting:
        gaps.append("No selected paper provided direct evidence for this theme.")
    if len(supporting) == 1:
        gaps.append("Only one selected paper supports this theme; broaden search before scaling.")
    if not any(item.get("source") == "parsed-full-text" for item in limited_snippets):
        gaps.append("Evidence is metadata/abstract-heavy; inspect parsed Markdown manually.")

    return {
        "theme": theme,
        "claim": spec["claim"],
        "supporting_papers": supporting,
        "evidence_snippets_or_sections": limited_snippets,
        "confidence": confidence_for(limited_snippets, supporting),
        "gaps_or_uncertainties": gaps,
    }


def evidence_table_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Evidence Table",
        "",
        f"Workspace: `{result['workspace']}`",
        "",
        "| Theme | Claim | Supporting Papers | Confidence | Gaps / Uncertainties |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in result["themes"]:
        supporting = ", ".join(f"[{paper_id}]" for paper_id in row["supporting_papers"]) or "None"
        gaps = "; ".join(row["gaps_or_uncertainties"]) or "None"
        lines.append(
            f"| {row['theme']} | {row['claim']} | {supporting} | {row['confidence']} | {gaps} |"
        )

    lines.extend(["", "## Evidence Snippets", ""])
    for row in result["themes"]:
        lines.extend([f"### {row['theme']}", ""])
        if row["evidence_snippets_or_sections"]:
            for item in row["evidence_snippets_or_sections"]:
                lines.append(
                    f"- [{item['paper_id']}] `{item['field']}` ({item['source']}): "
                    f"{item['snippet']}"
                )
        else:
            lines.append("- No snippets extracted.")
        lines.append("")
    return "\n".join(lines)


def build_evidence_table(workspace: Path) -> dict[str, Any]:
    papers = [
        normalize_paper(paper) for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    evidences = {paper["paper_id"]: load_paper_evidence(workspace, paper) for paper in papers}
    themes = [
        theme_row(theme, spec, papers, evidences)
        for theme, spec in THEME_SPECS.items()
    ]
    result = {
        "workspace": str(workspace),
        "selected_count": len(papers),
        "themes": themes,
    }
    write_json(workspace / "knowledge" / "evidence_table.json", result)
    md = evidence_table_markdown(result)
    path = workspace / "knowledge" / "evidence_table.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    return result
