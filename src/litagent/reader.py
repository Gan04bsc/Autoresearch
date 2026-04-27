from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from litagent.io import read_jsonl, write_json, write_jsonl
from litagent.schema import format_short_citation, normalize_paper


def clean_extracted_text(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


def extract_pdf_text(path: Path) -> tuple[str, str | None]:
    if not path.exists():
        return "", "PDF file is missing"
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return "", "pypdf is not installed; using abstract-only fallback"

    try:
        reader = PdfReader(str(path))
        pages = [clean_extracted_text(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        return "", f"PDF text extraction failed: {exc}"
    return "\n".join(page for page in pages if page.strip()), None


def paper_text(workspace: Path, paper: dict[str, Any]) -> tuple[str, str]:
    parsed_markdown_path = paper.get("parsed_markdown_path")
    if parsed_markdown_path:
        path = workspace / parsed_markdown_path
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if text.strip():
                provider = paper.get("parse_provider") or "parsed-markdown"
                return text, provider

    local_pdf_path = paper.get("local_pdf_path")
    if local_pdf_path:
        extracted, error = extract_pdf_text(workspace / local_pdf_path)
        if extracted.strip():
            return extracted, "pdf"
        if error:
            return paper.get("abstract") or "", f"abstract fallback ({error})"
    return paper.get("abstract") or "", "abstract"


def metadata_block(paper: dict[str, Any]) -> str:
    return json.dumps(paper, ensure_ascii=False, indent=2, sort_keys=True)


def survey_note(paper: dict[str, Any], text_source: str) -> str:
    citation = f"[{paper['paper_id']}]"
    abstract = paper.get("abstract") or "Original abstract is unavailable."
    evidence = paper.get("type_evidence", "the classifier marked it as survey")
    lines = [
        f"# {paper.get('title') or paper['paper_id']}",
        "",
        "## 1. Basic Information",
        f"- Title: {paper.get('title') or 'Unknown'}",
        f"- Authors: {', '.join(paper.get('authors') or []) or 'Unknown'}",
        f"- Year: {paper.get('year') or 'Unknown'}",
        "- Paper type: survey",
        f"- Short citation: {format_short_citation(paper)} {citation}",
        f"- Text source: {text_source}",
        "",
        "## 2. Field Boundary",
        f"This paper is treated as a survey because {evidence}.",
        f"Its abstract indicates coverage of: {abstract} {citation}",
        "",
        "## 3. Foundational Concepts",
        f"- Core area: {paper.get('title') or 'the target field'} {citation}",
        "- Key terms: survey, taxonomy, methods, evidence, open problems.",
        (
            '- Missing source detail: mark as "original text insufficient" when the '
            "abstract does not provide section-level evidence."
        ),
        "",
        "## 4. Survey Organization Framework",
        (
            "The available metadata suggests a taxonomy-oriented overview. Original text "
            f"insufficient for a chapter-by-chapter framework. {citation}"
        ),
        "",
        "## 5. Representative Work",
        (
            "Representative work should be traced from the paper references. Candidate "
            f"follow-up papers come from selected papers and the final report. {citation}"
        ),
        "",
        "## 6. Evolution",
        (
            "The abstract supports an evolution from manual literature review toward "
            f"agentic search, ranking, reading, synthesis, and audit workflows. {citation}"
        ),
        "",
        "## 7. Debates And Open Problems",
        f"- Citation faithfulness and evidence traceability remain central risks. {citation}",
        (
            "- Evaluation benchmarks and reproducible workflows are needed for reliable "
            f"comparisons. {citation}"
        ),
        "",
        "## 8. Reading Value For Beginners",
        (
            "Read this paper first because it frames the boundary, taxonomy, and open "
            f"problems. {citation}"
        ),
        "",
        "## 9. Traceable References And Search Terms",
        f"- Paper ID: {paper['paper_id']}",
        f"- DOI: {paper.get('doi') or 'N/A'}",
        f"- arXiv ID: {paper.get('arxiv_id') or 'N/A'}",
        "- Search terms: survey; taxonomy; literature research agents; traceable synthesis.",
        "",
        "## Original Metadata",
        "```json",
        metadata_block(paper),
        "```",
        "",
    ]
    return "\n".join(lines)


def technical_note(paper: dict[str, Any], text_source: str) -> str:
    citation = f"[{paper['paper_id']}]"
    abstract = paper.get("abstract") or "Original abstract is unavailable."
    paper_type = paper.get("paper_type") or "technical"
    lines = [
        f"# {paper.get('title') or paper['paper_id']}",
        "",
        "## 1. Basic Information",
        f"- Title: {paper.get('title') or 'Unknown'}",
        f"- Authors: {', '.join(paper.get('authors') or []) or 'Unknown'}",
        f"- Year: {paper.get('year') or 'Unknown'}",
        f"- Paper type: {paper_type}",
        f"- One-sentence contribution: {abstract} {citation}",
        f"- Text source: {text_source}",
        "",
        "## 2. Problem / Scenario",
        f"The paper addresses the scenario implied by its title and abstract: {abstract}",
        citation,
        "",
        "## 3. Why Existing Methods Are Insufficient",
        (
            "Original text insufficient for detailed baseline criticism unless the full text "
            "states it explicitly."
        ),
        (
            "The metadata suggests a need for better automation, evaluation, traceability, "
            f"or reusable artifacts. {citation}"
        ),
        "",
        "## 4. Core Idea",
        (
            "The core idea is summarized from the abstract and should be verified against "
            f"the full paper before publication-grade use. {citation}"
        ),
        "",
        "## 5. Method / System Design",
        (
            "Original text insufficient for exact algorithms, module diagrams, or "
            f"implementation details when the PDF text is unavailable. {citation}"
        ),
        "",
        "## 6. Experiments And Evidence",
        (
            "Do not infer experiment numbers from metadata. Use the full paper for "
            f"datasets, baselines, and metrics. {citation}"
        ),
        "",
        "## 7. Conclusions",
        (
            "The metadata supports only a conservative conclusion: this work contributes "
            f"to {paper_type} understanding of the target field. {citation}"
        ),
        "",
        "## 8. Limitations",
        "- Author-stated limitations require full-text evidence.",
        (
            "- Inference: automated literature agents can fail through weak retrieval, "
            "duplicate metadata, and unsupported synthesis; this is a pipeline-level risk, "
            f"not necessarily an author claim. {citation}"
        ),
        "",
        "## 9. Follow-up Research / Innovation Directions",
        f"- Improve traceable citations and auditability. {citation}",
        "- Add stronger benchmarks and reproducible evaluation.",
        "- Support human review for ambiguous classifications and claims.",
        "",
        "## 10. Contribution To Knowledge System",
        (
            f"Place this paper under the `{paper_type}` branch of the topic map and link "
            f"it to methods, artifacts, and evaluation issues. {citation}"
        ),
        "",
        "## Original Metadata",
        "```json",
        metadata_block(paper),
        "```",
        "",
    ]
    return "\n".join(lines)


def note_for_paper(workspace: Path, paper: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    text, source = paper_text(workspace, paper)
    metadata = {
        **paper,
        "text_source": source,
        "text_excerpt": text[:4000],
    }
    if paper.get("paper_type") == "survey":
        return survey_note(paper, source), metadata
    return technical_note(paper, source), metadata


def generate_notes(workspace: Path) -> list[dict[str, Any]]:
    selected_path = workspace / "data" / "selected_papers.jsonl"
    papers = [normalize_paper(paper) for paper in read_jsonl(selected_path)]
    updated: list[dict[str, Any]] = []

    for paper in papers:
        note, metadata = note_for_paper(workspace, paper)
        note_path = workspace / "library" / "notes" / f"{paper['paper_id']}.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(note, encoding="utf-8")
        write_json(workspace / "library" / "metadata" / f"{paper['paper_id']}.json", metadata)
        updated.append(
            normalize_paper(
                {
                    **paper,
                    "note_path": str(Path("library") / "notes" / f"{paper['paper_id']}.md"),
                    "metadata_path": str(
                        Path("library") / "metadata" / f"{paper['paper_id']}.json"
                    ),
                }
            )
        )

    write_jsonl(selected_path, updated)
    return updated
