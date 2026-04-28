from __future__ import annotations

from collections import Counter
from typing import Any

from litagent.schema import normalize_paper

PAPER_ROLES = {
    "survey_or_review",
    "technical_method",
    "system_paper",
    "benchmark_or_dataset",
    "position_or_perspective",
    "application_case",
    "background_foundation",
}

DOMAIN_ROLE_ALIASES = {
    "foundation_model": "system_paper",
    "frontier_system": "system_paper",
    "multimodal_agent": "system_paper",
    "technical_method": "technical_method",
    "instruction_data": "technical_method",
    "alignment": "technical_method",
    "reasoning": "technical_method",
    "embodied_multimodal": "technical_method",
    "video_understanding": "technical_method",
    "hallucination": "technical_method",
    "efficient_deployment": "technical_method",
    "benchmark": "benchmark_or_dataset",
    "benchmark_analysis": "benchmark_or_dataset",
    "hallucination_benchmark": "benchmark_or_dataset",
    "survey": "survey_or_review",
    "survey_or_review": "survey_or_review",
}

READING_INTENTS = {
    "build_field_map",
    "extract_method",
    "track_frontier",
    "compare_systems",
    "identify_benchmarks",
    "find_research_gap",
    "implementation_reference",
}

ROLE_TO_INTENTS = {
    "survey_or_review": ["build_field_map", "find_research_gap"],
    "technical_method": ["extract_method", "track_frontier", "find_research_gap"],
    "system_paper": [
        "extract_method",
        "track_frontier",
        "compare_systems",
        "implementation_reference",
    ],
    "benchmark_or_dataset": ["identify_benchmarks", "find_research_gap"],
    "position_or_perspective": ["build_field_map", "find_research_gap"],
    "application_case": ["implementation_reference"],
    "background_foundation": ["build_field_map"],
}

APPLICATION_TERMS = [
    "traffic",
    "transportation",
    "swarm",
    "robotics",
    "medical",
    "healthcare",
    "education",
    "finance",
    "financial",
    "smart city",
    "industrial",
    "industry",
    "climate",
]

FOUNDATION_TERMS = [
    "foundation",
    "background",
    "overview",
    "theory",
    "principles",
    "primer",
]


def infer_paper_role(paper: dict[str, Any]) -> tuple[str, str]:
    normalized = normalize_paper(paper)
    paper_type = str(normalized.get("paper_type") or "unknown")
    text = " ".join(
        [
            str(normalized.get("title") or ""),
            str(normalized.get("abstract") or ""),
            str(normalized.get("venue") or ""),
        ]
    ).lower()

    if paper_type == "survey":
        return "survey_or_review", "paper_type=survey"
    if paper_type in {"benchmark", "dataset"}:
        return "benchmark_or_dataset", f"paper_type={paper_type}"
    if paper_type == "system":
        return "system_paper", "paper_type=system"
    if paper_type == "technical":
        return "technical_method", "paper_type=technical"
    if paper_type == "position":
        return "position_or_perspective", "paper_type=position"

    if any(term in text for term in APPLICATION_TERMS):
        return "application_case", "matched application-domain terms"
    if any(term in text for term in FOUNDATION_TERMS):
        return "background_foundation", "matched background/foundation terms"
    if any(term in text for term in ("framework", "system", "workbench", "tool", "platform")):
        return "system_paper", "matched system-oriented title/abstract terms"
    if any(term in text for term in ("we propose", "method", "algorithm", "approach")):
        return "technical_method", "matched technical-method title/abstract terms"
    if any(term in text for term in ("survey", "taxonomy", "review")):
        return "survey_or_review", "matched survey/review title/abstract terms"

    return "background_foundation", "no stronger role signal matched"


def infer_reading_intents(paper_role: str) -> list[str]:
    return list(ROLE_TO_INTENTS.get(paper_role, ROLE_TO_INTENTS["background_foundation"]))


def enrich_paper_role(paper: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_paper(paper)
    current_role = str(paper.get("paper_role") or "")
    domain_role = ""
    if current_role and current_role not in PAPER_ROLES:
        domain_role = current_role
    if current_role in DOMAIN_ROLE_ALIASES:
        paper_role = DOMAIN_ROLE_ALIASES[current_role]
        role_evidence = f"domain paper_role={current_role}"
    elif current_role in PAPER_ROLES and (
        current_role != "background_foundation" or paper.get("role_evidence")
    ):
        paper_role = current_role
        role_evidence = str(normalized.get("role_evidence") or "existing paper_role")
    else:
        paper_role, role_evidence = infer_paper_role(normalized)

    reading_intent = normalized.get("reading_intent")
    if isinstance(reading_intent, list):
        intents = [str(intent) for intent in reading_intent if str(intent) in READING_INTENTS]
    else:
        intents = []
    if not intents:
        intents = infer_reading_intents(paper_role)

    return {
        **normalized,
        "domain_role": normalized.get("domain_role") or domain_role,
        "paper_role": paper_role,
        "reading_intent": intents,
        "role_evidence": role_evidence,
    }


def role_counts(papers: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(enrich_paper_role(paper)["paper_role"] for paper in papers)
    return dict(sorted(counts.items()))


def intent_counts(papers: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for paper in papers:
        for intent in enrich_paper_role(paper).get("reading_intent", []):
            counts[str(intent)] += 1
    return dict(sorted(counts.items()))
