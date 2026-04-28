from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from litagent.io import read_jsonl, write_jsonl
from litagent.paper_roles import enrich_paper_role
from litagent.schema import normalize_paper

DATASET_TERMS = ["dataset", "corpus", "data set", "open dataset", "benchmark dataset"]

BENCHMARK_TERMS = [
    "benchmark",
    "benchmarking",
    "leaderboard",
    "evaluation suite",
    "evaluation protocol",
]

POSITION_TERMS = [
    "position paper",
    "perspective",
    "opinion",
    "agenda",
    "roadmap",
    "research agenda",
    "future directions",
    "conceptual argument",
    "argues that",
    "we argue",
]

SURVEY_TERMS = [
    "survey",
    "taxonomy",
    "systematic literature review",
    "scoping review",
    "state-of-the-art review",
    "comprehensive review",
    "review of",
    "review on",
    "综述",
]

SYSTEM_TERMS = [
    "system",
    "software system",
    "implemented system",
    "workbench",
    "platform",
    "tool",
    "toolkit",
    "framework",
    "architecture",
    "pipeline",
    "open-source",
    "open source",
]

TITLE_SYSTEM_TERMS = [
    "agent",
    "agents",
    "framework",
    "system",
    "workbench",
    "platform",
    "tool",
    "toolkit",
    "pipeline",
    "generation",
    "writing",
]

TECHNICAL_TERMS = [
    "method",
    "approach",
    "algorithm",
    "model",
    "we propose",
    "we introduce",
    "architecture",
    "pipeline",
]


def contains_term(text: str, term: str) -> bool:
    if term.isascii():
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        return bool(re.search(pattern, text))
    return term in text


def first_matching_term(text: str, terms: list[str]) -> str | None:
    for term in terms:
        if contains_term(text, term):
            return term
    return None


def title_is_survey(title: str) -> str | None:
    survey_patterns = [
        (r"(?<![a-z0-9])a survey(?![a-z0-9])", "a survey"),
        (r"(?<![a-z0-9])survey of(?![a-z0-9])", "survey of"),
        (r"(?<![a-z0-9])survey on(?![a-z0-9])", "survey on"),
        (r"(?<![a-z0-9])systematic literature review(?![a-z0-9])", "systematic literature review"),
        (r"(?<![a-z0-9])scoping review(?![a-z0-9])", "scoping review"),
    ]
    for pattern, evidence in survey_patterns:
        if re.search(pattern, title):
            return evidence
    return None


def classify_paper(paper: dict[str, Any]) -> tuple[str, str]:
    title = str(paper.get("title", "")).lower()
    abstract = str(paper.get("abstract", "")).lower()
    venue = str(paper.get("venue", "")).lower()
    text = f"{title} {abstract} {venue}"

    if term := first_matching_term(text, POSITION_TERMS):
        return "position", f"matched position keyword `{term}` in title/abstract/venue"

    for paper_type, terms in (("dataset", DATASET_TERMS), ("benchmark", BENCHMARK_TERMS)):
        if term := first_matching_term(title, terms):
            return paper_type, f"matched {paper_type} keyword `{term}` in title"

    if term := title_is_survey(title):
        return "survey", f"matched survey title pattern `{term}`"

    if term := first_matching_term(title, TITLE_SYSTEM_TERMS):
        return "system", f"matched system keyword `{term}` in title"

    if term := first_matching_term(text, SURVEY_TERMS):
        return "survey", f"matched survey keyword `{term}` in title/abstract/venue"

    if term := first_matching_term(text, SYSTEM_TERMS):
        return "system", f"matched system keyword `{term}` in title/abstract/venue"

    for term in TECHNICAL_TERMS:
        if term in text:
            return "technical", f"matched technical keyword `{term}`"

    for paper_type, terms in (("dataset", DATASET_TERMS), ("benchmark", BENCHMARK_TERMS)):
        if term := first_matching_term(text, terms):
            return paper_type, f"matched {paper_type} keyword `{term}` in title/abstract/venue"

    return "unknown", "no deterministic rule matched"


def classify_papers(workspace: Path) -> list[dict[str, Any]]:
    selected_path = workspace / "data" / "selected_papers.jsonl"
    papers_path = workspace / "data" / "papers.jsonl"
    selected = [normalize_paper(paper) for paper in read_jsonl(selected_path)]
    all_papers = [normalize_paper(paper) for paper in read_jsonl(papers_path)]

    classified: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for paper in selected:
        paper_type, evidence = classify_paper(paper)
        role_input = {
            key: value
            for key, value in paper.items()
            if key not in {"paper_role", "reading_intent", "role_evidence"}
        }
        current_role = str(paper.get("paper_role") or "")
        if current_role and current_role not in {
            "survey_or_review",
            "technical_method",
            "system_paper",
            "benchmark_or_dataset",
            "position_or_perspective",
            "application_case",
            "background_foundation",
        }:
            role_input["domain_role"] = current_role
        updated = enrich_paper_role(
            {**role_input, "paper_type": paper_type, "type_evidence": evidence}
        )
        classified.append(updated)
        by_id[updated["paper_id"]] = updated

    all_papers = [by_id.get(paper["paper_id"], paper) for paper in all_papers]
    write_jsonl(selected_path, classified)
    write_jsonl(papers_path, all_papers)
    return classified
