from __future__ import annotations

import math
from collections import defaultdict
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
from litagent.search import latest_search_run_metadata, search_run_dir

HIGH_VALUE_PHRASES = [
    "literature review generation",
    "automated literature review",
    "systematic review automation",
    "survey generation",
    "paper reading agent",
    "paper-reading agent",
    "research assistant agent",
    "research assistant agents",
    "citation-aware synthesis",
    "multi-agent research system",
    "literature synthesis",
    "scientific survey generation",
    "comparative literature summary",
]

DEFAULT_NEGATIVE_TERMS = [
    "robotics-only",
    "traffic-only",
    "swarm-only",
    "game-theory-only",
    "reinforcement-learning-only",
    "medical-only",
    "education-only",
    "industry-only",
    "robotics",
    "traffic",
    "swarm",
    "game theory",
    "reinforcement learning",
    "medical",
    "biomedical",
    "healthcare",
    "health care",
    "education",
    "industry 4.0",
    "manufacturing",
]


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


def title_buckets(title: str | None) -> set[str]:
    normalized = normalize_title(title)
    if not normalized:
        return set()
    tokens = normalized.split()
    buckets = {f"exact:{normalized}", f"prefix:{normalized[:40]}"}
    if len(tokens) >= 3:
        buckets.add(f"first3:{' '.join(tokens[:3])}")
    if len(tokens) >= 5:
        buckets.add(f"first5:{' '.join(tokens[:5])}")
    if len(tokens) >= 6:
        buckets.add(f"ends:{tokens[0]} {' '.join(tokens[-3:])}")
    return buckets


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    exact_index: dict[tuple[str, str], int] = {}
    bucket_index: dict[str, set[int]] = defaultdict(set)

    def index_paper(index: int, paper: dict[str, Any]) -> None:
        key = dedup_key(paper)
        if key:
            exact_index[key] = index
        for bucket in title_buckets(paper.get("title")):
            bucket_index[bucket].add(index)

    for row in rows:
        incoming = normalize_paper(row)
        duplicate_index = None
        incoming_key = dedup_key(incoming)
        if incoming_key:
            duplicate_index = exact_index.get(incoming_key)

        if duplicate_index is None:
            candidate_indexes: set[int] = set()
            for bucket in title_buckets(incoming.get("title")):
                candidate_indexes.update(bucket_index.get(bucket, set()))
            for index in sorted(candidate_indexes):
                if title_similarity(papers[index].get("title"), incoming.get("title")) >= 0.92:
                    duplicate_index = index
                    break

        if duplicate_index is None:
            papers.append(incoming)
            index_paper(len(papers) - 1, incoming)
        else:
            papers[duplicate_index] = merge_papers(papers[duplicate_index], incoming)
            index_paper(duplicate_index, papers[duplicate_index])
    return papers


def unique_terms(terms: list[str]) -> list[str]:
    unique: list[str] = []
    for term in terms:
        clean = str(term).lower().strip()
        if clean and clean not in unique:
            unique.append(clean)
    return unique


def weighted_term_matches(
    paper: dict[str, Any],
    terms: list[str],
    *,
    max_terms: int = 12,
) -> tuple[float, list[str], list[str]]:
    terms = unique_terms(terms)
    if not terms:
        return 0.0, [], []

    title = str(paper.get("title") or "").lower()
    abstract = str(paper.get("abstract") or "").lower()
    title_matches: list[str] = []
    abstract_matches: list[str] = []
    weighted = 0.0

    for term in terms:
        if term in title:
            title_matches.append(term)
            weighted += 2.0
        elif term in abstract:
            abstract_matches.append(term)
            weighted += 1.0

    denominator = max(1.0, min(len(terms), max_terms) * 2.0)
    return min(1.0, weighted / denominator), title_matches, abstract_matches


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


def score_explanation(
    *,
    keyword_score: float,
    high_value_score: float,
    exclusion_score: float,
    importance: float,
    recency: float,
    pdf_bonus: float,
    final: float,
    keyword_title_matches: list[str],
    keyword_abstract_matches: list[str],
    high_value_title_matches: list[str],
    high_value_abstract_matches: list[str],
    negative_title_matches: list[str],
    negative_abstract_matches: list[str],
) -> dict[str, Any]:
    return {
        "ranking_mode": "topic_sensitive_v2",
        "formula": (
            "0.45 keyword_overlap + 0.25 high_value_phrase + 0.15 recency "
            "+ 0.10 citation_importance + 0.05 open_pdf - 0.45 negative_terms"
        ),
        "component_scores": {
            "keyword_overlap": round(keyword_score, 4),
            "high_value_phrase": round(high_value_score, 4),
            "negative_terms": round(exclusion_score, 4),
            "citation_importance": round(importance, 4),
            "recency": round(recency, 4),
            "open_pdf": round(pdf_bonus, 4),
            "final": round(final, 4),
        },
        "matched_terms": {
            "include_title": keyword_title_matches[:20],
            "include_abstract": keyword_abstract_matches[:20],
            "high_value_title": high_value_title_matches[:20],
            "high_value_abstract": high_value_abstract_matches[:20],
            "negative_title": negative_title_matches[:20],
            "negative_abstract": negative_abstract_matches[:20],
        },
    }


def score_paper(paper: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    scored = normalize_paper(paper)
    date_range = plan.get("date_range") or {}
    from_year = int(date_range.get("from") or 2018)
    to_year = int(date_range.get("to") or from_year + 8)

    keyword_score, keyword_title_matches, keyword_abstract_matches = weighted_term_matches(
        scored,
        [str(value) for value in plan.get("include_keywords", [])],
        max_terms=4,
    )
    plan_high_value_phrases = [str(value) for value in plan.get("high_value_phrases", [])]
    high_value_score, high_value_title_matches, high_value_abstract_matches = (
        weighted_term_matches(scored, [*HIGH_VALUE_PHRASES, *plan_high_value_phrases], max_terms=4)
    )
    negative_terms = [*DEFAULT_NEGATIVE_TERMS, *[str(v) for v in plan.get("exclude_keywords", [])]]
    exclusion, negative_title_matches, negative_abstract_matches = weighted_term_matches(
        scored, negative_terms, max_terms=4
    )
    importance = importance_score(scored)
    recency = recency_score(scored, from_year, to_year)
    pdf_bonus = 1.0 if scored.get("pdf_url") else 0.0
    relevance = min(1.0, 0.65 * keyword_score + 0.35 * high_value_score)
    final = (
        0.45 * keyword_score
        + 0.25 * high_value_score
        + 0.15 * recency
        + 0.10 * importance
        + 0.05 * pdf_bonus
    )
    final = max(0.0, final - 0.45 * exclusion)

    scored["relevance_score"] = round(relevance, 4)
    scored["exclusion_score"] = round(exclusion, 4)
    scored["importance_score"] = round(importance, 4)
    scored["recency_score"] = round(recency, 4)
    scored["final_score"] = round(final, 4)
    scored["score_explanation"] = score_explanation(
        keyword_score=keyword_score,
        high_value_score=high_value_score,
        exclusion_score=exclusion,
        importance=importance,
        recency=recency,
        pdf_bonus=pdf_bonus,
        final=final,
        keyword_title_matches=keyword_title_matches,
        keyword_abstract_matches=keyword_abstract_matches,
        high_value_title_matches=high_value_title_matches,
        high_value_abstract_matches=high_value_abstract_matches,
        negative_title_matches=negative_title_matches,
        negative_abstract_matches=negative_abstract_matches,
    )
    scored["paper_id"] = stable_paper_id(scored)
    return scored


def raw_rows_for_scope(
    workspace: Path,
    *,
    search_scope: str = "latest",
    search_run_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    search_runs_root = workspace / "data" / "search_runs"
    if search_scope == "latest":
        metadata = latest_search_run_metadata(workspace)
        run_id = metadata.get("run_id")
        if run_id:
            rows = read_jsonl(search_run_dir(workspace, str(run_id)) / "raw_results.jsonl")
            if rows:
                return rows
        return read_jsonl(workspace / "data" / "raw_results.jsonl")

    if search_scope == "all":
        rows: list[dict[str, Any]] = []
        if search_runs_root.exists():
            for run_dir in sorted(path for path in search_runs_root.iterdir() if path.is_dir()):
                rows.extend(read_jsonl(run_dir / "raw_results.jsonl"))
        return rows or read_jsonl(workspace / "data" / "raw_results.jsonl")

    if search_scope == "selected":
        if not search_run_ids:
            msg = "--search-run-id is required when --search-scope selected"
            raise ValueError(msg)
        rows = []
        for run_id in search_run_ids:
            rows.extend(read_jsonl(search_run_dir(workspace, run_id) / "raw_results.jsonl"))
        return rows

    msg = f"Unknown search scope: {search_scope}"
    raise ValueError(msg)


def dedup_and_rank(
    workspace: Path,
    *,
    selection_count: int | None = None,
    search_scope: str = "latest",
    search_run_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    raw_rows = raw_rows_for_scope(
        workspace,
        search_scope=search_scope,
        search_run_ids=search_run_ids,
    )

    deduped = deduplicate(raw_rows)
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
