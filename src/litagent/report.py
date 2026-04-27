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


def generate_final_report(workspace: Path) -> str:
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    papers = [
        normalize_paper(paper) for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    grouped = grouped_by_type(papers)
    method_groups = grouped_by_method(papers)
    top_ids = refs(papers, limit=5)
    search_queries = plan.get("search_queries") or {}
    systems = [paper for paper in papers if paper.get("paper_type") == "system"] or papers
    citation_graph_papers = [
        paper for paper in papers if has_terms(paper, ["citation graph", "citation-aware"])
    ]
    evaluation_papers = [
        paper
        for paper in papers
        if has_terms(paper, ["benchmark", "evaluation", "evaluated", "dataset", "baselines"])
    ]
    paper_reading = [
        paper for paper in papers if has_terms(paper, ["paper-reading", "paper reading"])
    ]

    lines = [
        "# Final Research Report",
        "",
        "## Executive Summary",
        "",
        f"This report summarizes `{plan.get('topic', 'the topic')}` using {len(papers)} selected "
        f"papers. The strongest evidence base in this run is {top_ids}.",
        "",
        (
            "The selected set is best read as a map of agentic literature-review systems: "
            "papers decompose review work into retrieval, screening, reading, planning, "
            "evidence organization, writing, critique, and citation-aware synthesis."
        ),
        "",
        "## Field Background",
        "",
        (
            "Literature review automation is shifting from one-shot summarization toward "
            "orchestrated workflows. In the selected papers, the important design question is "
            "how systems preserve search coverage, citation grounding, long-form coherence, "
            "and human inspectability while using LLMs or agents to reduce manual review work."
        ),
        "",
        "## Core Problems",
        "",
        *[f"- {question}" for question in plan.get("core_questions", [])],
        "- How should literature review work be split across retrieval, reading, planning, "
        f"writing, evidence checking, and revision agents? {top_ids}",
        "- How can generated synthesis remain traceable to source papers and citations? "
        f"{refs(citation_graph_papers or papers, limit=4)}",
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
            "- Plan-and-write systems generate outlines, sections, reviews, and revisions as "
            f"separate stages. {refs(systems, limit=5)}",
            "- Evidence-structured systems organize citations, graphs, minigraphs, or extracted "
            f"claims before final synthesis. {refs(citation_graph_papers or papers, limit=4)}",
            "- Review-workflow systems emphasize screening, relevance scoring, extraction, "
            f"rounds, and human feedback. {refs(papers, limit=4)}",
            "- Paper-reading and comparative-summary agents isolate reusable subtasks that can "
            f"feed larger review pipelines. {refs(paper_reading or papers, limit=3)}",
            "",
            "## Representative Papers",
            "",
            "| Paper ID | Title | Year | Role in This Review | Why It Matters |",
            "| --- | --- | ---: | --- | --- |",
            *[
                (
                    f"| {paper['paper_id']} | {markdown_cell(paper.get('title'))} | "
                    f"{paper.get('year') or ''} | {method_role(paper)} | {why_it_matters(paper)} |"
                )
                for paper in papers
            ],
            "",
            "## Comparison Of Selected Systems",
            "",
            *[
                (
                    f"- {paper.get('title')} is treated as `{method_role(paper)}`. "
                    f"{first_sentence(paper.get('abstract'), fallback='No abstract available.')} "
                    f"{paper_ref(paper)}"
                )
                for paper in papers
            ],
            "",
            "## Pipeline Patterns Across Papers",
            "",
            (
                "- Retrieval and screening appear as upstream gates: weak search or inclusion "
                f"choices limit every downstream synthesis step. {top_ids}"
            ),
            (
                "- Planning and outline construction are recurring controls for long-form "
                f"coherence. {refs(papers, limit=5)}"
            ),
            (
                "- Writing, reviewing, and revision are increasingly separate stages rather "
                f"than a single prompt. {refs(systems, limit=5)}"
            ),
            (
                "- Evidence organization through citation graphs, minigraphs, or extracted "
                f"paper elements is a key route to traceable synthesis. "
                f"{refs(citation_graph_papers or papers, limit=4)}"
            ),
            "",
            "## Role Of Multi-Agent Architecture",
            "",
            (
                "The multi-agent pattern is useful when roles have different failure modes: "
                "retrieval agents can miss papers, reader agents can miss evidence, writer "
                "agents can overgeneralize, and reviewer agents can catch coherence or citation "
                f"errors. The selected systems use this decomposition to make review work more "
                f"modular and inspectable. {refs(systems, limit=6)}"
            ),
            "",
            "## Citation Graph / Evidence Handling Patterns",
            "",
            (
                "- Citation-aware and graph-based systems attempt to preserve relationships "
                f"among papers before synthesis. {refs(citation_graph_papers or papers, limit=4)}"
            ),
            (
                "- Systems that only generate fluent prose still need external checks for "
                f"claim-to-paper support and citation coverage. {top_ids}"
            ),
            "",
            "## Evaluation Methods",
            "",
            *[
                (
                    f"- {paper.get('title')} reports or motivates evaluation around benchmarks, "
                    f"datasets, baselines, citation quality, extraction quality, or generated "
                    f"review quality. {paper_ref(paper)}"
                )
                for paper in (evaluation_papers or papers[:5])
            ],
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
            "- No traditional survey paper was selected; this run is mostly system-oriented. "
            f"The method taxonomy above is synthesized from selected system papers. {top_ids}"
        )

    lines.extend(["", "## Technical Paper Synthesis", ""])
    technical_like = [
        paper
        for paper in papers
        if paper.get("paper_type") in {"technical", "system", "benchmark", "dataset"}
    ]
    if technical_like:
        lines.extend(
            f"- {paper.get('title')} contributes to `{method_role(paper)}`. {paper_ref(paper)}"
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
                "- Evaluation remains fragmented across generation quality, citation quality, "
                f"retrieval coverage, screening/extraction quality, and human preference. "
                f"{refs(evaluation_papers or papers, limit=5)}"
            ),
            (
                "- Complex PDFs, tables, equations, and OCR-heavy documents still require parser "
                "fallback decisions before synthesis can be trusted."
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
            "## Limitations And Research Gaps",
            "",
            (
                "- The selected set may overrepresent sources that are available through the "
                "current academic APIs; rate limits or source imbalance can hide relevant work."
            ),
            (
                "- Deterministic extraction can identify themes, but human review is still needed "
                "for nuanced claims, detailed metrics, and implementation comparisons."
            ),
            "",
            "## Design Implications For Our Tool",
            "",
            (
                "- Keep the Codex/orchestrator loop: search terms, selected papers, parse logs, "
                "notes, and reports should remain inspectable before acceptance."
            ),
            (
                "- Add selection review before download so off-topic high-citation papers do not "
                "consume parse and synthesis time."
            ),
            (
                "- Store search runs separately and make dedup scope explicit to avoid stale "
                "refinement results contaminating the selected set."
            ),
            (
                "- Treat citation/evidence structures as first-class artifacts, not just final "
                "report references."
            ),
            "",
            "## Recommended Roadmap",
            "",
            "1. Run a small real review with source-aware search, explicit selection review, and "
            "local pypdf parsing first.",
            "2. Add human decisions for questionable papers and rerun dedup if subtopics are "
            "missing.",
            "3. Parse with MinerU only for OCR, complex layout, or table-heavy PDFs where pypdf "
            "is insufficient.",
            "4. Generate a synthesis report and inspect it for shallow claims, missing citations, "
            "and weak method comparisons.",
            "5. Scale to a source-diverse review only after the small review has stable selected "
            "papers and usable parsed Markdown.",
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
