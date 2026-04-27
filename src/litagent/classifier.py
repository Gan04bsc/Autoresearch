from __future__ import annotations

from pathlib import Path
from typing import Any

from litagent.io import read_jsonl, write_jsonl
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
    "vision",
    "agenda",
    "roadmap",
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


def first_matching_term(text: str, terms: list[str]) -> str | None:
    for term in terms:
        if term in text:
            return term
    return None


def classify_paper(paper: dict[str, Any]) -> tuple[str, str]:
    title = str(paper.get("title", "")).lower()
    abstract = str(paper.get("abstract", "")).lower()
    venue = str(paper.get("venue", "")).lower()
    text = f"{title} {abstract} {venue}"

    # Dataset and benchmark labels are artifact types, so classify them before broad system terms.
    for paper_type, terms in (("dataset", DATASET_TERMS), ("benchmark", BENCHMARK_TERMS)):
        if term := first_matching_term(text, terms):
            return paper_type, f"matched {paper_type} keyword `{term}` in title/abstract/venue"

    if term := first_matching_term(text, POSITION_TERMS):
        return "position", f"matched position keyword `{term}` in title/abstract/venue"

    if term := first_matching_term(text, SURVEY_TERMS):
        return "survey", f"matched survey keyword `{term}` in title/abstract/venue"

    if term := first_matching_term(text, SYSTEM_TERMS):
        return "system", f"matched system keyword `{term}` in title/abstract/venue"

    for term in TECHNICAL_TERMS:
        if term in text:
            return "technical", f"matched technical keyword `{term}`"

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
        updated = normalize_paper({**paper, "paper_type": paper_type, "type_evidence": evidence})
        classified.append(updated)
        by_id[updated["paper_id"]] = updated

    all_papers = [by_id.get(paper["paper_id"], paper) for paper in all_papers]
    write_jsonl(selected_path, classified)
    write_jsonl(papers_path, all_papers)
    return classified
