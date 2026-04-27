from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from litagent.io import read_jsonl, write_json, write_jsonl
from litagent.schema import format_short_citation, normalize_paper

EVIDENCE_FIELDS: dict[str, dict[str, Any]] = {
    "problem_addressed": {
        "title": "Problem Addressed",
        "terms": [
            "problem",
            "challenge",
            "difficult",
            "labor-intensive",
            "manual",
            "growth of scientific",
            "increasingly difficult",
            "bottleneck",
        ],
    },
    "proposed_system_or_method": {
        "title": "Proposed System Or Method",
        "terms": [
            "we propose",
            "we present",
            "we introduce",
            "framework",
            "system",
            "method",
            "architecture",
        ],
    },
    "agent_roles": {
        "title": "Agent Roles",
        "terms": [
            "agent",
            "agents",
            "reviewer agent",
            "reflector",
            "collector",
            "composer",
            "organizer",
            "writer agent",
            "editor agent",
            "interpreter",
            "refiner",
        ],
    },
    "pipeline_stages": {
        "title": "Pipeline Stages",
        "terms": [
            "pipeline",
            "workflow",
            "stage",
            "step",
            "outline",
            "planning",
            "draft",
            "writing",
            "revision",
            "screening",
            "extraction",
        ],
    },
    "retrieval_search_strategy": {
        "title": "Retrieval / Search Strategy",
        "terms": [
            "retrieval",
            "search",
            "rerank",
            "re-rank",
            "query",
            "screening",
            "candidate papers",
            "source selection",
        ],
    },
    "citation_or_evidence_handling": {
        "title": "Citation Or Evidence Handling",
        "terms": [
            "citation",
            "citations",
            "evidence",
            "grounding",
            "graph",
            "reference",
            "references",
            "faithful",
            "hallucination",
        ],
    },
    "evaluation_setup": {
        "title": "Evaluation Setup",
        "terms": [
            "evaluation",
            "evaluate",
            "experiment",
            "experiments",
            "human evaluation",
            "llm-as",
            "baseline",
            "metric",
            "metrics",
        ],
    },
    "datasets_or_benchmarks": {
        "title": "Datasets Or Benchmarks",
        "terms": [
            "dataset",
            "benchmark",
            "corpus",
            "test set",
            "scireviewgen",
            "surveyscope",
            "surge",
        ],
    },
    "key_findings": {
        "title": "Key Findings",
        "terms": [
            "outperform",
            "outperforms",
            "results show",
            "we find",
            "findings",
            "demonstrate",
            "improves",
            "achieves",
        ],
    },
    "limitations": {
        "title": "Limitations",
        "terms": [
            "limitation",
            "limitations",
            "future work",
            "fail",
            "failure",
            "challenge",
            "still need",
            "not address",
        ],
    },
    "relevance_to_multi_agent_lit_review_automation": {
        "title": "Relevance To Multi-Agent Literature Review Automation",
        "terms": [
            "multi-agent",
            "literature review",
            "survey generation",
            "systematic review",
            "paper-reading",
            "paper reading",
            "research assistant",
            "citation",
        ],
    },
}


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


def normalize_evidence_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()


def candidate_units(text: str) -> list[str]:
    units: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_evidence_text(raw_line)
        if not line:
            continue
        if len(line) <= 700:
            units.append(line)
        else:
            units.extend(
                normalize_evidence_text(part)
                for part in re.split(r"(?<=[.!?])\s+", line)
                if normalize_evidence_text(part)
            )
    return units


def is_probably_reference(unit: str) -> bool:
    lower = unit.lower()
    return (
        lower.startswith("references")
        or lower.startswith("bibliography")
        or bool(re.match(r"^\[\d+\]", unit))
        or ("arxiv preprint" in lower and len(unit) < 240)
    )


def extract_matching_snippets(text: str, terms: list[str], *, limit: int = 3) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    lower_terms = [term.lower() for term in terms]
    for unit in candidate_units(text):
        clean = normalize_evidence_text(unit)
        lower = clean.lower()
        if len(clean) < 45 or is_probably_reference(clean):
            continue
        if not any(term in lower for term in lower_terms):
            continue
        score = sum(1 for term in lower_terms if term in lower)
        prefix = ""
        if re.match(r"^(#+\s+|\d+(\.\d+)*\s+|[A-Z][A-Za-z /-]{3,60}$)", clean):
            prefix = "Section: "
        snippet = f"{prefix}{clean[:500]}"
        key = snippet.lower()
        if key in seen:
            continue
        seen.add(key)
        snippets.append((score, snippet))
    snippets.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    return [snippet for _, snippet in snippets[:limit]]


def field_from_sources(
    *,
    field: str,
    text: str,
    text_source: str,
    abstract: str,
) -> dict[str, Any]:
    spec = EVIDENCE_FIELDS[field]
    full_text_available = bool(text.strip()) and not text_source.startswith("abstract")
    full_text_snippets = (
        extract_matching_snippets(text, spec["terms"], limit=3) if full_text_available else []
    )
    if full_text_snippets:
        return {
            "title": spec["title"],
            "source": "parsed-full-text",
            "snippets": full_text_snippets,
            "confidence": "medium" if len(full_text_snippets) == 1 else "high",
        }

    abstract_snippets = extract_matching_snippets(abstract, spec["terms"], limit=1)
    if abstract_snippets:
        return {
            "title": spec["title"],
            "source": "metadata/abstract",
            "snippets": abstract_snippets,
            "confidence": "low",
        }
    return {
        "title": spec["title"],
        "source": "missing",
        "snippets": [],
        "confidence": "unknown",
    }


def extract_paper_evidence(
    paper: dict[str, Any], text: str, text_source: str
) -> dict[str, Any]:
    abstract = paper.get("abstract") or ""
    fields = {
        field: field_from_sources(
            field=field,
            text=text,
            text_source=text_source,
            abstract=abstract,
        )
        for field in EVIDENCE_FIELDS
    }
    return {
        "paper_id": paper["paper_id"],
        "title": paper.get("title") or paper["paper_id"],
        "text_source": text_source,
        "fields": fields,
    }


def note_field_lines(evidence: dict[str, Any], *, source: str) -> list[str]:
    lines: list[str] = []
    for field in EVIDENCE_FIELDS:
        item = evidence["fields"][field]
        if item["source"] != source:
            continue
        lines.append(f"### {item['title']}")
        lines.append("")
        lines.append(f"- Source: {item['source']}")
        lines.append(f"- Confidence: {item['confidence']}")
        for snippet in item["snippets"]:
            lines.append(f"- Evidence: {snippet}")
        lines.append("")
    return lines


def structured_note(paper: dict[str, Any], text_source: str, evidence: dict[str, Any]) -> str:
    citation = f"[{paper['paper_id']}]"
    abstract = paper.get("abstract") or "Original abstract is unavailable."
    paper_type = paper.get("paper_type") or "technical"
    missing_fields = [
        item["title"]
        for item in evidence["fields"].values()
        if item["source"] == "missing"
    ]
    lines = [
        f"# {paper.get('title') or paper['paper_id']}",
        "",
        "## 1. Basic Information",
        f"- Title: {paper.get('title') or 'Unknown'}",
        f"- Authors: {', '.join(paper.get('authors') or []) or 'Unknown'}",
        f"- Year: {paper.get('year') or 'Unknown'}",
        f"- Paper type: {paper_type}",
        f"- Short citation: {format_short_citation(paper)} {citation}",
        f"- Text source: {text_source}",
        "",
        "## 2. Metadata / Abstract-Derived Content",
        "",
        f"- Abstract-derived contribution: {abstract} {citation}",
        f"- Classifier evidence: {paper.get('type_evidence') or 'N/A'}",
        f"- Ranking evidence: {paper.get('score_explanation') or 'N/A'}",
        "",
        "## 3. Parsed Full-Text-Derived Evidence",
        "",
    ]
    parsed_lines = note_field_lines(evidence, source="parsed-full-text")
    if parsed_lines:
        lines.extend(parsed_lines)
    else:
        lines.append("- No parsed-full-text evidence was extracted for the target fields.")
        lines.append("")

    lines.extend(
        [
            "## 4. Abstract-Derived Evidence Fields",
            "",
        ]
    )
    abstract_lines = note_field_lines(evidence, source="metadata/abstract")
    if abstract_lines:
        lines.extend(abstract_lines)
    else:
        lines.append(
            "- None; target evidence fields were either found in parsed full text or missing."
        )
        lines.append("")

    lines.extend(
        [
            "## 5. Uncertain Or Missing Information",
            "",
        ]
    )
    if missing_fields:
        lines.extend(f"- Missing or uncertain: {field}" for field in missing_fields)
    else:
        lines.append("- No target evidence fields are completely missing.")
    lines.extend(
        [
            "",
            "## 6. Relevance To Multi-Agent Literature Review Automation",
            "",
        ]
    )
    relevance = evidence["fields"]["relevance_to_multi_agent_lit_review_automation"]
    if relevance["snippets"]:
        lines.extend(f"- {snippet} {citation}" for snippet in relevance["snippets"])
    else:
        lines.append(
            "- Relevance is inferred from title/abstract metadata and should be manually "
            f"checked. {citation}"
        )
    lines.extend(
        [
            "",
            "## Original Metadata",
            "```json",
            metadata_block(paper),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def note_for_paper(workspace: Path, paper: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    text, source = paper_text(workspace, paper)
    evidence = extract_paper_evidence(paper, text, source)
    metadata = {
        **paper,
        "text_source": source,
        "text_excerpt": text[:4000],
        "paper_evidence": evidence,
    }
    return structured_note(paper, source, evidence), metadata


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
