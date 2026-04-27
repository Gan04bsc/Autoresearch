from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl, write_jsonl
from litagent.schema import (
    merge_papers,
    normalize_arxiv_id,
    normalize_doi,
    normalize_paper,
    normalize_title,
    stable_paper_id,
    title_similarity,
)


def dedup_key(paper: dict[str, Any]) -> tuple[str, str] | None:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return ("doi", doi)
    arxiv_id = normalize_arxiv_id(paper.get("arxiv_id"))
    if arxiv_id:
        return ("arxiv", arxiv_id.lower())
    title = normalize_title(paper.get("title"))
    if title:
        return ("title", title)
    return None


def find_duplicate_index(papers: list[dict[str, Any]], incoming: dict[str, Any]) -> int | None:
    incoming_key = dedup_key(incoming)
    for index, paper in enumerate(papers):
        paper_key = dedup_key(paper)
        if incoming_key and paper_key and incoming_key == paper_key:
            return index
        if title_similarity(paper.get("title"), incoming.get("title")) >= 0.92:
            return index
    return None


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    for row in rows:
        incoming = normalize_paper(row)
        duplicate_index = find_duplicate_index(papers, incoming)
        if duplicate_index is None:
            papers.append(incoming)
        else:
            papers[duplicate_index] = merge_papers(papers[duplicate_index], incoming)
    return papers


def keyword_relevance(paper: dict[str, Any], keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    haystack = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    matches = 0
    for keyword in keywords:
        keyword = str(keyword).lower().strip()
        if keyword and keyword in haystack:
            matches += 1
    title_bonus = (
        0.15
        if any(str(keyword).lower() in paper.get("title", "").lower() for keyword in keywords)
        else 0
    )
    return min(1.0, matches / max(1, min(len(keywords), 10)) + title_bonus)


def importance_score(paper: dict[str, Any]) -> float:
    citations = max(0, int(paper.get("citation_count") or 0))
    references = max(0, int(paper.get("reference_count") or 0))
    citation_component = min(1.0, math.log10(citations + 1) / 3.0)
    reference_component = min(0.2, math.log10(references + 1) / 10.0)
    return min(1.0, citation_component + reference_component)


def recency_score(paper: dict[str, Any], from_year: int, to_year: int) -> float:
    year = paper.get("year")
    if not isinstance(year, int):
        return 0.0
    if to_year <= from_year:
        return 1.0
    return max(0.0, min(1.0, (year - from_year) / (to_year - from_year)))


def score_paper(paper: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    scored = normalize_paper(paper)
    date_range = plan.get("date_range") or {}
    from_year = int(date_range.get("from") or 2018)
    to_year = int(date_range.get("to") or from_year + 8)

    relevance = keyword_relevance(
        scored, [str(value) for value in plan.get("include_keywords", [])]
    )
    exclusion = keyword_relevance(
        scored, [str(value) for value in plan.get("exclude_keywords", [])]
    )
    importance = importance_score(scored)
    recency = recency_score(scored, from_year, to_year)
    pdf_bonus = 1.0 if scored.get("pdf_url") else 0.0
    final = 0.50 * relevance + 0.25 * importance + 0.20 * recency + 0.05 * pdf_bonus
    final = max(0.0, final - 0.35 * exclusion)

    scored["relevance_score"] = round(relevance, 4)
    scored["exclusion_score"] = round(exclusion, 4)
    scored["importance_score"] = round(importance, 4)
    scored["recency_score"] = round(recency, 4)
    scored["final_score"] = round(final, 4)
    scored["paper_id"] = stable_paper_id(scored)
    return scored


def dedup_and_rank(workspace: Path, *, selection_count: int | None = None) -> list[dict[str, Any]]:
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    raw_rows = read_jsonl(workspace / "data" / "raw_results.jsonl")
    existing_rows = read_jsonl(workspace / "data" / "papers.jsonl")

    deduped = deduplicate([*existing_rows, *raw_rows])
    scored = [score_paper(paper, plan) for paper in deduped]
    scored.sort(
        key=lambda paper: (
            paper.get("final_score") or 0.0,
            paper.get("citation_count") or 0,
            paper.get("year") or 0,
            paper.get("title") or "",
        ),
        reverse=True,
    )

    count = selection_count or int(plan.get("selection_count") or 30)
    selected = scored[:count]
    write_jsonl(workspace / "data" / "papers.jsonl", scored)
    write_jsonl(workspace / "data" / "selected_papers.jsonl", selected)
    return selected
