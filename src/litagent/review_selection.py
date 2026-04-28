from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl

COVERAGE_TARGETS = {
    "literature review generation": ["literature review generation", "review generation"],
    "automated literature review": ["automated literature review", "review automation"],
    "systematic review automation": ["systematic review automation", "systematic review"],
    "survey generation": ["survey generation", "scientific survey generation"],
    "paper reading agent": ["paper reading agent", "paper-reading agent", "paperguide"],
    "citation-aware synthesis": ["citation-aware", "citation graph", "citation quality"],
    "multi-agent research system": ["multi-agent", "multi agent", "agents"],
}


def paper_text(paper: dict[str, Any]) -> str:
    return f"{paper.get('title') or ''} {paper.get('abstract') or ''}".lower()


def score_reason(paper: dict[str, Any]) -> str:
    terms = matched_terms(paper)
    high_value = [*terms.get("high_value_title", []), *terms.get("high_value_abstract", [])]
    include = [*terms.get("include_title", []), *terms.get("include_abstract", [])]
    negative = [*terms.get("negative_title", []), *terms.get("negative_abstract", [])]
    parts: list[str] = []
    if paper.get("curation_reason"):
        parts.append("curated selection: " + str(paper["curation_reason"]))
    if high_value:
        parts.append("high-value phrase match: " + ", ".join(high_value[:4]))
    if include:
        parts.append("include keyword match: " + ", ".join(include[:4]))
    if negative:
        parts.append("negative term match: " + ", ".join(negative[:4]))
    if not parts:
        parts.append("limited explainable keyword evidence")
    return "; ".join(parts)


def matched_terms(paper: dict[str, Any]) -> dict[str, list[str]]:
    explanation = paper.get("score_explanation") or {}
    terms = (explanation.get("matched_terms") or {}) if isinstance(explanation, dict) else {}
    return {
        "high_value_title": list(terms.get("high_value_title", [])),
        "high_value_abstract": list(terms.get("high_value_abstract", [])),
        "include_title": list(terms.get("include_title", [])),
        "include_abstract": list(terms.get("include_abstract", [])),
        "negative_title": list(terms.get("negative_title", [])),
        "negative_abstract": list(terms.get("negative_abstract", [])),
    }


def classify_selection_concern(paper: dict[str, Any]) -> tuple[str, list[str]]:
    relevance = float(paper.get("relevance_score") or 0.0)
    negative = float(paper.get("exclusion_score") or 0.0)
    terms = matched_terms(paper)
    positive_matches = [
        *terms["high_value_title"],
        *terms["high_value_abstract"],
        *terms["include_title"],
        *terms["include_abstract"],
    ]
    reasons = [score_reason(paper)]
    curated = bool(paper.get("curation_reason"))

    if not paper.get("abstract"):
        reasons.append("missing abstract")
    if not (paper.get("doi") or paper.get("arxiv_id") or paper.get("semantic_scholar_id")):
        reasons.append("missing DOI/arXiv/Semantic Scholar identifier")
    if negative >= 0.25:
        reasons.append(f"negative-term score is high ({negative:.2f})")
        return "likely_off_topic", reasons
    if curated:
        if negative >= 0.15:
            reasons.append(f"curated paper still needs inspection: negative={negative:.2f}")
            return "questionable", reasons
        return "likely_relevant", reasons
    if not positive_matches and relevance < 0.20:
        reasons.append(f"low relevance score ({relevance:.2f}) with no positive term evidence")
        return "likely_off_topic", reasons
    if relevance < 0.15:
        reasons.append(f"low relevance score ({relevance:.2f})")
        return "likely_off_topic", reasons
    if relevance < 0.25 or negative >= 0.15:
        reasons.append(f"needs inspection: relevance={relevance:.2f}, negative={negative:.2f}")
        return "questionable", reasons
    return "likely_relevant", reasons


def distribution_by_source(papers: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for paper in papers:
        for source in paper.get("source") or []:
            counts[str(source)] += 1
    return dict(sorted(counts.items()))


def distribution_by_year(papers: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(paper.get("year") or "unknown") for paper in papers)
    return dict(sorted(counts.items()))


def coverage_targets_from_plan(plan: dict[str, Any]) -> dict[str, list[str]]:
    raw_targets = plan.get("coverage_targets")
    if isinstance(raw_targets, dict):
        targets: dict[str, list[str]] = {}
        for label, terms in raw_targets.items():
            if isinstance(terms, list):
                targets[str(label)] = [str(term).lower() for term in terms if str(term).strip()]
            elif str(terms).strip():
                targets[str(label)] = [str(terms).lower()]
        if targets:
            return targets
    return COVERAGE_TARGETS


def missing_subtopics(
    papers: list[dict[str, Any]], plan: dict[str, Any] | None = None
) -> list[str]:
    joined = "\n".join(paper_text(paper) for paper in papers)
    missing: list[str] = []
    for label, terms in coverage_targets_from_plan(plan or {}).items():
        if not any(term in joined for term in terms):
            missing.append(label)
    return missing


def paper_preview(paper: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "paper_id": paper.get("paper_id"),
        "title": paper.get("title"),
        "year": paper.get("year"),
        "sources": paper.get("source") or [],
        "relevance_score": paper.get("relevance_score"),
        "final_score": paper.get("final_score"),
        "exclusion_score": paper.get("exclusion_score"),
        "reasons": reasons,
    }


def review_selection(workspace: Path) -> dict[str, Any]:
    papers = read_jsonl(workspace / "data" / "selected_papers.jsonl")
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    grouped: dict[str, list[dict[str, Any]]] = {
        "likely_relevant": [],
        "questionable": [],
        "likely_off_topic": [],
    }
    for paper in papers:
        label, reasons = classify_selection_concern(paper)
        grouped[label].append(paper_preview(paper, reasons))

    missing = missing_subtopics(papers, plan)
    if grouped["likely_off_topic"]:
        recommended = "Refine the research plan or ranking terms and rerun dedup before download."
    elif grouped["questionable"]:
        recommended = "Inspect questionable papers before download; rerun dedup if they are weak."
    elif missing:
        recommended = (
            "Selection is usable, but consider an additional targeted search for missing "
            "subtopics."
        )
    else:
        recommended = "Accept the selected papers and continue to download/parse."

    return {
        "workspace": str(workspace),
        "topic": plan.get("topic"),
        "selected_count": len(papers),
        "likely_relevant": grouped["likely_relevant"],
        "questionable": grouped["questionable"],
        "likely_off_topic": grouped["likely_off_topic"],
        "source_distribution": distribution_by_source(papers),
        "year_distribution": distribution_by_year(papers),
        "missing_subtopics": missing,
        "recommended_next_action": recommended,
    }


def review_selection_markdown(workspace: Path) -> str:
    result = review_selection(workspace)
    lines = [
        "# Selection Review",
        "",
        f"Workspace: `{result['workspace']}`",
        f"Topic: {result.get('topic') or 'N/A'}",
        f"Selected papers: {result['selected_count']}",
        f"Recommended next action: {result['recommended_next_action']}",
        "",
        "## Distributions",
        "",
        f"- Sources: {result['source_distribution']}",
        f"- Years: {result['year_distribution']}",
        f"- Missing subtopics: {result['missing_subtopics'] or 'None'}",
        "",
    ]
    for key, heading in (
        ("likely_relevant", "Likely Relevant"),
        ("questionable", "Questionable"),
        ("likely_off_topic", "Likely Off Topic"),
    ):
        lines.extend([f"## {heading}", ""])
        rows = result[key]
        if rows:
            for row in rows:
                lines.append(
                    f"- {row['paper_id']}: {row['title']} "
                    f"(relevance={row.get('relevance_score')}, final={row.get('final_score')})"
                )
                lines.append(f"  Reason: {'; '.join(row['reasons'])}")
        else:
            lines.append("- None")
        lines.append("")
    return "\n".join(lines)
