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


def has_terms(paper: dict[str, Any], terms: list[str]) -> bool:
    text = f"{paper.get('title') or ''} {paper.get('abstract') or ''}".lower()
    return any(term in text for term in terms)


def paper_ref(paper: dict[str, Any]) -> str:
    return f"[{paper['paper_id']}]"


def refs(papers: list[dict[str, Any]], *, limit: int | None = None) -> str:
    chosen = papers[:limit] if limit else papers
    return ", ".join(paper_ref(paper) for paper in chosen) or "[no-papers]"


def first_sentence(text: str | None, *, fallback: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return fallback
    for marker in (". ", "? ", "! "):
        if marker in clean:
            return clean.split(marker, 1)[0].strip() + marker.strip()
    return clean[:260].strip()


def method_role(paper: dict[str, Any]) -> str:
    if has_terms(paper, ["systematic review automation", "screening", "data extraction"]):
        return "Systematic review workflow automation"
    if has_terms(paper, ["paper-reading", "paper reading", "read scientific papers"]):
        return "Paper-reading agent"
    if has_terms(paper, ["citation graph", "citation-aware", "citation quality"]):
        return "Citation/evidence-aware synthesis"
    if has_terms(paper, ["survey generation", "survey paper generation"]):
        return "Scientific survey generation"
    if has_terms(paper, ["literature synthesis", "related work drafting"]):
        return "Literature synthesis and related-work drafting"
    if has_terms(paper, ["comparative literature summary", "comparative summary"]):
        return "Comparative literature summarization"
    if has_terms(paper, ["literature review generation", "review generation"]):
        return "Literature review generation"
    return paper.get("paper_type") or "Research system"


def why_it_matters(paper: dict[str, Any]) -> str:
    if has_terms(paper, ["multi-agent", "multiple agents", "specialized agents"]):
        return "Uses agent decomposition for review work."
    if has_terms(paper, ["citation graph", "citation quality"]):
        return "Connects synthesis to citation/evidence structure."
    if has_terms(paper, ["screening", "data extraction"]):
        return "Automates formal systematic-review stages."
    if has_terms(paper, ["paper-reading", "paper reading"]):
        return "Improves the paper-reading subtask."
    return first_sentence(paper.get("abstract"), fallback="Provides evidence for the target field.")


def markdown_cell(value: str | None) -> str:
    return (value or "").replace("|", "\\|")


def grouped_by_method(papers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        grouped[method_role(paper)].append(paper)
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


def load_evidence_rows(workspace: Path) -> list[dict[str, Any]]:
    evidence = read_json(workspace / "knowledge" / "evidence_table.json", default={}) or {}
    rows = evidence.get("themes") or []
    return rows if isinstance(rows, list) else []


def row_refs(row: dict[str, Any]) -> str:
    return ", ".join(f"[{paper_id}]" for paper_id in row.get("supporting_papers", []))


def evidence_by_theme(rows: list[dict[str, Any]], theme: str) -> dict[str, Any]:
    for row in rows:
        if row.get("theme") == theme:
            return row
    return {"theme": theme, "claim": "Evidence table missing this theme.", "supporting_papers": []}


def representative_snippet(row: dict[str, Any]) -> str:
    snippets = row.get("evidence_snippets_or_sections") or []
    if not snippets:
        return "No extracted snippet."
    item = snippets[0]
    return f"{item.get('snippet')} [{item.get('paper_id')}]"


def supported_claim(row: dict[str, Any]) -> str:
    refs_text = row_refs(row)
    return f"- {row.get('claim')} {refs_text or '[evidence gap]'}"


def paper_evidence_summary(paper: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    themes = [
        row["theme"]
        for row in rows
        if paper["paper_id"] in set(row.get("supporting_papers") or [])
    ]
    return ", ".join(themes[:4]) or "No evidence-table theme"


def generate_final_report(workspace: Path) -> str:
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    papers = [
        normalize_paper(paper) for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    grouped = grouped_by_type(papers)
    method_groups = grouped_by_method(papers)
    evidence_rows = load_evidence_rows(workspace)
    search_queries = plan.get("search_queries") or {}

    architecture = evidence_by_theme(evidence_rows, "multi-agent architecture")
    generation = evidence_by_theme(evidence_rows, "survey/literature review generation")
    systematic = evidence_by_theme(evidence_rows, "systematic review workflow")
    paper_reading = evidence_by_theme(evidence_rows, "paper reading agents")
    citation = evidence_by_theme(evidence_rows, "citation-aware synthesis")
    evaluation = evidence_by_theme(evidence_rows, "evaluation and benchmarks")
    limitations = evidence_by_theme(evidence_rows, "limitations and open problems")
    design = evidence_by_theme(evidence_rows, "design implications for litagent")

    lines = [
        "# Final Research Report",
        "",
        "## Executive Summary",
        "",
        f"This report summarizes `{plan.get('topic', 'the topic')}` using {len(papers)} selected "
        f"papers and the generated evidence table. {refs(papers, limit=5)}",
        supported_claim(architecture),
        supported_claim(generation),
        supported_claim(citation),
        "",
        "## Field Background",
        "",
        supported_claim(generation),
        supported_claim(systematic),
        supported_claim(paper_reading),
        "",
        "## Core Problems",
        "",
        *[f"- {question}" for question in plan.get("core_questions", [])],
        supported_claim(citation),
        supported_claim(evaluation),
        "",
        "## Technical Route Categories",
        "",
    ]
    for method, group in sorted(method_groups.items()):
        lines.append(f"- {method}: {len(group)} papers, including {refs(group)}.")

    lines.extend(
        [
            "",
            "## Taxonomy Of Methods",
            "",
            supported_claim(architecture),
            supported_claim(generation),
            supported_claim(systematic),
            supported_claim(paper_reading),
            supported_claim(citation),
            supported_claim(evaluation),
            "",
            "## Representative Papers",
            "",
            "| Paper ID | Title | Year | Type | Evidence Themes |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for paper in papers:
        lines.append(
            f"| {paper['paper_id']} | {markdown_cell(paper.get('title'))} | "
            f"{paper.get('year') or ''} | {paper.get('paper_type') or 'unknown'} | "
            f"{markdown_cell(paper_evidence_summary(paper, evidence_rows))} |"
        )

    lines.extend(
        [
            "",
            "## Comparison Of Selected Systems",
            "",
            "| Paper ID | Role | Evidence-Backed Interpretation |",
            "| --- | --- | --- |",
        ]
    )
    for paper in papers:
        lines.append(
            f"| {paper['paper_id']} | {method_role(paper)} | "
            f"{markdown_cell(why_it_matters(paper))} {paper_ref(paper)} |"
        )

    lines.extend(
        [
            "",
            "## Paper Comparison Table",
            "",
            *selected_papers_table(papers),
            "",
            "## Evidence-Backed Synthesis Themes",
            "",
        ]
    )
    if evidence_rows:
        for row in evidence_rows:
            refs_text = row_refs(row) or "[evidence gap]"
            lines.extend(
                [
                    f"### {row.get('theme')}",
                    "",
                    f"- Claim: {row.get('claim')} {refs_text}",
                    f"- Confidence: {row.get('confidence')}",
                    f"- Representative evidence: {representative_snippet(row)}",
                    f"- Gaps: {'; '.join(row.get('gaps_or_uncertainties') or []) or 'None'}",
                    "",
                ]
            )
    else:
        lines.append("- Evidence table is missing; run `litagent build-evidence WORKSPACE --json`.")
        lines.append("")

    lines.extend(
        [
            "## Pipeline Patterns Across Papers",
            "",
            supported_claim(architecture),
            supported_claim(systematic),
            supported_claim(citation),
            "",
            "## Role Of Multi-Agent Architecture",
            "",
            supported_claim(architecture),
            f"- Representative snippet: {representative_snippet(architecture)}",
            "",
            "## Citation Graph / Evidence Handling Patterns",
            "",
            supported_claim(citation),
            f"- Representative snippet: {representative_snippet(citation)}",
            "",
            "## Evaluation Methods",
            "",
            supported_claim(evaluation),
            f"- Representative snippet: {representative_snippet(evaluation)}",
            "",
            "## Survey Paper Synthesis",
            "",
        ]
    )
    survey = grouped.get("survey", [])
    if survey:
        lines.extend(
            f"- {paper.get('title')} frames part of the area. {paper_ref(paper)}"
            for paper in survey
        )
    else:
        lines.append(
            "- No traditional survey paper was selected; the survey-level synthesis is built "
            f"from system and benchmark papers. {row_refs(generation) or refs(papers, limit=5)}"
        )

    technical_like = [
        paper
        for paper in papers
        if paper.get("paper_type") in {"technical", "system", "benchmark", "dataset"}
    ]
    lines.extend(["", "## Technical Paper Synthesis", ""])
    lines.extend(
        f"- {paper.get('title')} contributes to `{method_role(paper)}` and is linked to "
        f"{paper_evidence_summary(paper, evidence_rows)}. {paper_ref(paper)}"
        for paper in technical_like
    )
    if not technical_like:
        lines.append("- No technical/system/benchmark/dataset papers were selected.")

    lines.extend(
        [
            "",
            "## Unresolved Problems",
            "",
            supported_claim(limitations),
            "",
            "## Future Research / Innovation Directions",
            "",
            "- Build claim-to-evidence tables before writing long-form synthesis. "
            f"{row_refs(design) or refs(papers, limit=5)}",
            "- Add citation graph extraction and citation-neighborhood expansion. "
            f"{row_refs(citation) or refs(papers, limit=5)}",
            "- Evaluate report quality with citation faithfulness, retrieval coverage, and "
            f"human revision cost. {row_refs(evaluation) or refs(papers, limit=5)}",
            "",
            "## Limitations Of Current Literature",
            "",
            supported_claim(limitations),
            (
                "- Current evidence remains partial when the selected set is small or source "
                f"diversity is limited. {refs(papers, limit=5)}"
            ),
            "",
            "## Explicit Remaining Evidence Gaps",
            "",
        ]
    )
    for row in evidence_rows:
        for gap in row.get("gaps_or_uncertainties") or []:
            lines.append(f"- {row.get('theme')}: {gap}")
    if not evidence_rows:
        lines.append("- Evidence table is missing.")

    lines.extend(
        [
            "",
            "## Design Implications For Our Tool",
            "",
            supported_claim(design),
            "- Keep `read -> build-knowledge -> build-evidence -> report -> audit -> inspect` "
            f"as the preferred real-review path. {row_refs(design) or refs(papers, limit=5)}",
            "",
            "## Recommended Roadmap",
            "",
            "1. Improve parsed-Markdown section extraction for agent roles, methods, datasets, "
            "metrics, and limitations.",
            "2. Store evidence snippets and claim support before report generation.",
            "3. Add citation graph extraction and source-quality scoring.",
            "4. Configure Semantic Scholar API access before a larger real review.",
            "5. Scale only after `review-selection`, parse quality, evidence table, audit, and "
            "inspect-workspace all remain clean.",
            "",
            "## Recommended Reading Order",
            "",
        ]
    )
    lines.extend(
        f"{index}. {paper.get('title')} - {format_short_citation(paper)} [{paper['paper_id']}]"
        for index, paper in enumerate(papers, start=1)
    )

    lines.extend(["", "## Appendix: Search Queries", ""])
    for source, queries in search_queries.items():
        lines.append(f"### {source}")
        lines.extend(f"- `{query}`" for query in queries)
        lines.append("")

    lines.extend(
        [
            "## Appendix: Evidence Table",
            "",
            "- [Evidence Table](../knowledge/evidence_table.md)",
            "- [Evidence Table JSON](../knowledge/evidence_table.json)",
            "",
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
