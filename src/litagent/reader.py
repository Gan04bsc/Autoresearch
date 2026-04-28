from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from litagent.evidence_quality import confidence_from_score, score_snippet, sectioned_units
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


def extract_matching_evidence_items(
    text: str,
    terms: list[str],
    *,
    limit: int = 3,
    default_section: str | None = None,
) -> list[dict[str, Any]]:
    items: list[tuple[float, int, dict[str, Any]]] = []
    seen: set[str] = set()
    lower_terms = [term.lower() for term in terms]
    for unit in sectioned_units(text):
        section = unit["section"]
        if section == "Unknown" and default_section:
            section = default_section
        scored = score_snippet(unit["text"], section=section, target_terms=terms)
        clean = scored["snippet"]
        lower = clean.lower()
        if not clean or scored["snippet_score"] < 0.15:
            continue
        matched_count = sum(1 for term in lower_terms if term in lower)
        if matched_count == 0:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append((float(scored["snippet_score"]), matched_count, scored))
    items.sort(key=lambda item: (item[0], item[1], len(item[2]["snippet"])), reverse=True)
    return [item for _, _, item in items[:limit]]


def extract_matching_snippets(text: str, terms: list[str], *, limit: int = 3) -> list[str]:
    return [
        item["snippet"]
        for item in extract_matching_evidence_items(text, terms, limit=limit)
    ]


def field_from_sources(
    *,
    field: str,
    text: str,
    text_source: str,
    abstract: str,
) -> dict[str, Any]:
    spec = EVIDENCE_FIELDS[field]
    full_text_available = bool(text.strip()) and not text_source.startswith("abstract")
    full_text_items = (
        extract_matching_evidence_items(text, spec["terms"], limit=3)
        if full_text_available
        else []
    )
    if full_text_items:
        best_score = max(float(item["snippet_score"]) for item in full_text_items)
        return {
            "title": spec["title"],
            "source": "parsed-full-text",
            "snippets": [item["snippet"] for item in full_text_items],
            "evidence_items": full_text_items,
            "confidence": confidence_from_score(best_score),
        }

    abstract_items = extract_matching_evidence_items(
        abstract,
        spec["terms"],
        limit=1,
        default_section="Abstract",
    )
    if abstract_items:
        return {
            "title": spec["title"],
            "source": "metadata/abstract",
            "snippets": [item["snippet"] for item in abstract_items],
            "evidence_items": abstract_items,
            "confidence": "low",
        }
    return {
        "title": spec["title"],
        "source": "missing",
        "snippets": [],
        "evidence_items": [],
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
        evidence_items = item.get("evidence_items") or [
            {
                "snippet": snippet,
                "section": "Unknown",
                "snippet_score": 0.0,
                "snippet_score_explanation": "旧版证据片段未记录质量说明。",
                "quality_flags": ["legacy_snippet"],
            }
            for snippet in item.get("snippets") or []
        ]
        for evidence_item in evidence_items:
            lines.append(
                "- Evidence "
                f"({evidence_item.get('section', 'Unknown')}, "
                f"score={float(evidence_item.get('snippet_score') or 0.0):.2f}): "
                f"{evidence_item.get('snippet')}"
            )
            flags = ", ".join(evidence_item.get("quality_flags") or []) or "none"
            lines.append(f"- Quality flags: {flags}")
            lines.append(
                "- Score explanation: "
                f"{evidence_item.get('snippet_score_explanation') or 'N/A'}"
            )
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
