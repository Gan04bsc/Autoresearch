from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import date
from difflib import SequenceMatcher
from typing import Any

PAPER_TYPES = {
    "survey",
    "technical",
    "benchmark",
    "dataset",
    "system",
    "position",
    "unknown",
}

PAPER_ROLES = {
    "survey_or_review",
    "technical_method",
    "system_paper",
    "benchmark_or_dataset",
    "position_or_perspective",
    "application_case",
    "background_foundation",
}

PAPER_SCHEMA_DEFAULTS: dict[str, Any] = {
    "paper_id": "",
    "title": "",
    "authors": [],
    "year": None,
    "venue": "",
    "abstract": "",
    "doi": None,
    "arxiv_id": None,
    "semantic_scholar_id": None,
    "openalex_id": None,
    "citation_count": 0,
    "reference_count": 0,
    "url": None,
    "pdf_url": None,
    "local_pdf_path": None,
    "source": [],
    "paper_type": "unknown",
    "paper_role": "background_foundation",
    "reading_intent": [],
    "role_evidence": "",
    "relevance_score": 0.0,
    "importance_score": 0.0,
    "recency_score": 0.0,
    "final_score": 0.0,
    "download_status": "skipped",
    "download_error": None,
}


def normalize_whitespace(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = doi.removeprefix("doi:")
    return doi.strip() or None


def normalize_arxiv_id(value: str | None) -> str | None:
    if not value:
        return None
    arxiv_id = value.strip()
    arxiv_id = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", arxiv_id)
    arxiv_id = arxiv_id.removesuffix(".pdf")
    arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
    return arxiv_id or None


def normalize_title(value: str | None) -> str:
    title = normalize_whitespace(value).lower()
    title = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", title)
    return normalize_whitespace(title)


def safe_slug(value: str, max_length: int = 80) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_length].strip("-") or "paper"


def stable_paper_id(paper: dict[str, Any]) -> str:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        key = f"doi:{doi}"
    else:
        arxiv_id = normalize_arxiv_id(paper.get("arxiv_id"))
        if arxiv_id:
            key = f"arxiv:{arxiv_id.lower()}"
        else:
            key = f"title:{normalize_title(paper.get('title'))}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"p-{digest}"


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def normalize_paper(raw: dict[str, Any]) -> dict[str, Any]:
    paper = dict(PAPER_SCHEMA_DEFAULTS)
    paper.update(raw)
    paper["title"] = normalize_whitespace(str(paper.get("title") or ""))
    paper["authors"] = [
        normalize_whitespace(str(author)) for author in ensure_list(paper.get("authors"))
    ]
    paper["authors"] = [author for author in paper["authors"] if author]
    paper["venue"] = normalize_whitespace(str(paper.get("venue") or ""))
    paper["abstract"] = normalize_whitespace(str(paper.get("abstract") or ""))
    paper["doi"] = normalize_doi(paper.get("doi"))
    paper["arxiv_id"] = normalize_arxiv_id(paper.get("arxiv_id"))
    paper["source"] = sorted({str(source) for source in ensure_list(paper.get("source")) if source})
    paper["paper_type"] = (
        paper.get("paper_type") if paper.get("paper_type") in PAPER_TYPES else "unknown"
    )
    paper["paper_role"] = (
        paper.get("paper_role")
        if paper.get("paper_role") in PAPER_ROLES
        else "background_foundation"
    )
    paper["reading_intent"] = [
        str(intent) for intent in ensure_list(paper.get("reading_intent")) if str(intent)
    ]
    paper["citation_count"] = int(paper.get("citation_count") or 0)
    paper["reference_count"] = int(paper.get("reference_count") or 0)
    for score_field in ("relevance_score", "importance_score", "recency_score", "final_score"):
        paper[score_field] = float(paper.get(score_field) or 0.0)
    if paper.get("year") is not None:
        try:
            paper["year"] = int(paper["year"])
        except (TypeError, ValueError):
            paper["year"] = None
    if not paper.get("paper_id"):
        paper["paper_id"] = stable_paper_id(paper)
    return paper


def title_similarity(left: str | None, right: str | None) -> float:
    left_title = normalize_title(left)
    right_title = normalize_title(right)
    if not left_title or not right_title:
        return 0.0
    if left_title == right_title:
        return 1.0
    return SequenceMatcher(a=left_title, b=right_title).ratio()


def merge_papers(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = normalize_paper(existing)
    incoming = normalize_paper(incoming)

    for field in (
        "title",
        "venue",
        "doi",
        "arxiv_id",
        "semantic_scholar_id",
        "openalex_id",
        "url",
        "pdf_url",
    ):
        if not merged.get(field) and incoming.get(field):
            merged[field] = incoming[field]

    if len(incoming.get("abstract") or "") > len(merged.get("abstract") or ""):
        merged["abstract"] = incoming["abstract"]

    merged["authors"] = sorted({*merged.get("authors", []), *incoming.get("authors", [])})
    merged["source"] = sorted({*merged.get("source", []), *incoming.get("source", [])})
    merged["citation_count"] = max(
        merged.get("citation_count", 0), incoming.get("citation_count", 0)
    )
    merged["reference_count"] = max(
        merged.get("reference_count", 0), incoming.get("reference_count", 0)
    )

    if incoming.get("year") and (not merged.get("year") or incoming["year"] > merged["year"]):
        merged["year"] = incoming["year"]

    for field in (
        "local_pdf_path",
        "download_status",
        "download_error",
        "paper_type",
        "type_evidence",
        "paper_role",
        "reading_intent",
        "role_evidence",
    ):
        if incoming.get(field) and not merged.get(field):
            merged[field] = incoming[field]

    merged["paper_id"] = stable_paper_id(merged)
    return normalize_paper(merged)


def extract_terms(text: str, limit: int = 12) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}|[\u4e00-\u9fff]{2,}", text.lower())
    stopwords = {
        "and",
        "for",
        "with",
        "the",
        "from",
        "into",
        "that",
        "this",
        "using",
        "based",
        "about",
    }
    terms: list[str] = []
    for token in tokens:
        if token in stopwords or token in terms:
            continue
        terms.append(token)
        if len(terms) >= limit:
            break
    return terms


def format_short_citation(paper: dict[str, Any]) -> str:
    authors = paper.get("authors") or []
    author = authors[0] if authors else "Unknown"
    year = paper.get("year") or "n.d."
    return f"{author} et al., {year}"


def current_year() -> int:
    return date.today().year


def missing_paper_fields(paper: dict[str, Any]) -> list[str]:
    required = set(PAPER_SCHEMA_DEFAULTS)
    return sorted(field for field in required if field not in paper)


def has_any_term(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)
