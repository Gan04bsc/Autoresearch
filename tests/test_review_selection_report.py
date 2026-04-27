from pathlib import Path
from uuid import uuid4

from litagent.audit import audit_workspace
from litagent.inspect import inspect_workspace
from litagent.io import write_json, write_jsonl
from litagent.report import generate_final_report
from litagent.review_selection import review_selection
from litagent.schema import normalize_paper


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def selected_papers() -> list[dict]:
    return [
        normalize_paper(
            {
                "paper_id": "p-111111111111",
                "title": "LiRA: A Multi-Agent Framework for Literature Review Generation",
                "authors": ["A"],
                "year": 2025,
                "abstract": (
                    "A multi-agent system for literature review generation and citation quality."
                ),
                "doi": "10.1234/lira",
                "citation_count": 2,
                "pdf_url": "https://arxiv.org/pdf/1.pdf",
                "source": ["arxiv"],
                "paper_type": "system",
                "relevance_score": 0.8,
                "final_score": 0.7,
                "download_status": "success",
                "local_pdf_path": "library/pdfs/p-111111111111.pdf",
                "parsed_markdown_path": "library/markdown/p-111111111111.md",
                "score_explanation": {
                    "matched_terms": {
                        "high_value_title": ["literature review generation"],
                        "high_value_abstract": [],
                        "include_title": ["multi-agent"],
                        "include_abstract": [],
                        "negative_title": [],
                        "negative_abstract": [],
                    }
                },
            }
        ),
        normalize_paper(
            {
                "paper_id": "p-222222222222",
                "title": "Traffic Robotics for Medical Education",
                "authors": ["B"],
                "year": 2024,
                "abstract": "A traffic robotics benchmark.",
                "doi": "10.1234/offtopic",
                "citation_count": 200,
                "pdf_url": "https://example.org/offtopic.pdf",
                "source": ["openalex"],
                "paper_type": "benchmark",
                "relevance_score": 0.2,
                "exclusion_score": 0.5,
                "final_score": 0.1,
                "download_status": "success",
                "score_explanation": {
                    "matched_terms": {
                        "high_value_title": [],
                        "high_value_abstract": [],
                        "include_title": [],
                        "include_abstract": [],
                        "negative_title": ["traffic", "robotics", "medical"],
                        "negative_abstract": [],
                    }
                },
            }
        ),
    ]


def write_review_workspace(workspace: Path, *, source_diverse: bool = False) -> None:
    papers = selected_papers()[:1]
    raw_rows = [
        {**papers[0], "source_query": "real", "source": ["arxiv"]},
        {**papers[0], "paper_id": "p-333333333333", "source_query": "real", "source": ["openalex"]},
    ]
    if source_diverse:
        raw_rows.append({**papers[0], "paper_id": "p-444444444444", "source": ["semantic_scholar"]})
    write_json(
        workspace / "research_plan.json",
        {
            "topic": "agentic literature review tools",
            "goal": "test",
            "core_questions": ["What systems exist?"],
            "include_keywords": ["literature review generation", "multi-agent"],
            "exclude_keywords": ["traffic"],
            "search_queries": {"arxiv": ["test"]},
            "date_range": {"from": 2018, "to": 2026},
            "max_results_per_source": 10,
            "selection_count": 1,
            "ranking_policy": "test",
        },
    )
    (workspace / "research_plan.md").write_text("# Plan\n", encoding="utf-8")
    write_jsonl(workspace / "data" / "raw_results.jsonl", raw_rows)
    write_jsonl(workspace / "data" / "papers.jsonl", papers)
    write_jsonl(workspace / "data" / "selected_papers.jsonl", papers)
    write_jsonl(
        workspace / "logs" / "downloads.jsonl",
        [{"paper_id": papers[0]["paper_id"], "download_status": "success"}],
    )
    for relative in (
        "library/pdfs/p-111111111111.pdf",
        "library/markdown/p-111111111111.md",
        "library/notes/p-111111111111.md",
    ):
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("parsed text", encoding="utf-8")
    write_json(
        workspace / "library" / "metadata" / "p-111111111111.json",
        {**papers[0], "text_source": "local"},
    )
    for relative in (
        "knowledge/base_knowledge.md",
        "knowledge/topic_map.md",
        "knowledge/index.md",
    ):
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# ok\n", encoding="utf-8")


def test_review_selection_flags_off_topic_papers() -> None:
    workspace = workspace_path("review-selection")
    write_jsonl(workspace / "data" / "selected_papers.jsonl", selected_papers())

    result = review_selection(workspace)

    assert result["selected_count"] == 2
    assert len(result["likely_relevant"]) == 1
    assert len(result["likely_off_topic"]) == 1
    assert result["source_distribution"] == {"arxiv": 1, "openalex": 1}


def test_report_contains_synthesis_sections() -> None:
    workspace = workspace_path("report")
    write_review_workspace(workspace)

    report = generate_final_report(workspace)

    assert "## Taxonomy Of Methods" in report
    assert "## Comparison Of Selected Systems" in report
    assert "## Pipeline Patterns Across Papers" in report
    assert "## Design Implications For Our Tool" in report
    assert "## Recommended Roadmap" in report


def test_inspect_labels_successful_real_run_as_small_real_review() -> None:
    workspace = workspace_path("inspect-small-real")
    write_review_workspace(workspace)
    generate_final_report(workspace)
    audit_workspace(workspace)

    result = inspect_workspace(workspace)

    assert result["quality_level"] == "small_real_review"
