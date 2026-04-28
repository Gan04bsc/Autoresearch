from pathlib import Path
from uuid import uuid4

from litagent.audit import audit_workspace
from litagent.inspect import inspect_workspace
from litagent.io import write_json, write_jsonl
from litagent.paper_roles import enrich_paper_role
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
        path.write_text("Source: parsed-full-text\nparsed text", encoding="utf-8")
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
    write_json(
        workspace / "knowledge" / "evidence_table.json",
        {
            "workspace": str(workspace),
            "selected_count": 1,
            "themes": [
                {
                    "theme": "multi-agent architecture",
                    "claim": "The system uses multi-agent decomposition.",
                    "supporting_papers": ["p-111111111111"],
                    "evidence_snippets_or_sections": [
                        {
                            "paper_id": "p-111111111111",
                            "paper_title": (
                                "LiRA: A Multi-Agent Framework for Literature Review Generation"
                            ),
                            "field": "agent_roles",
                            "source": "parsed-full-text",
                            "snippet": (
                                "We propose a multi-agent framework with planner agent, "
                                "collector agent, writer agent, and reviewer agent."
                            ),
                            "section": "Method",
                            "snippet_score": 0.82,
                            "snippet_score_explanation": "加分：Method 章节、agent_roles；扣分：无",
                            "confidence": "high",
                            "quality_flags": [],
                            "uncertainty_or_gap": "",
                        }
                    ],
                    "confidence": "medium",
                    "gaps_or_uncertainties": [],
                }
            ],
        },
    )
    (workspace / "knowledge" / "evidence_table.md").write_text("# Evidence\n", encoding="utf-8")


def test_review_selection_flags_off_topic_papers() -> None:
    workspace = workspace_path("review-selection")
    write_jsonl(workspace / "data" / "selected_papers.jsonl", selected_papers())

    result = review_selection(workspace)

    assert result["selected_count"] == 2
    assert len(result["likely_relevant"]) == 1
    assert len(result["likely_off_topic"]) == 1
    assert result["source_distribution"] == {"arxiv": 1, "openalex": 1}


def test_review_selection_uses_plan_coverage_targets() -> None:
    workspace = workspace_path("review-selection-coverage")
    write_json(
        workspace / "research_plan.json",
        {
            "topic": "multimodal large language models",
            "coverage_targets": {
                "survey map": ["survey"],
                "benchmark evaluation": ["benchmark"],
            },
        },
    )
    write_jsonl(workspace / "data" / "selected_papers.jsonl", selected_papers()[:1])

    result = review_selection(workspace)

    assert set(result["missing_subtopics"]) == {"survey map", "benchmark evaluation"}
    assert "literature review generation" not in result["missing_subtopics"]


def test_review_selection_respects_curated_selection_reason() -> None:
    workspace = workspace_path("review-selection-curated")
    paper = normalize_paper(
        {
            "paper_id": "p-curated",
            "title": "Multimodal Chain-of-Thought Reasoning in Language Models",
            "abstract": "A foundational reasoning paper selected by the agent.",
            "year": 2023,
            "source": ["openalex"],
            "relevance_score": 0.05,
            "exclusion_score": 0.0,
            "final_score": 0.1,
            "curation_reason": "highly cited background for multimodal reasoning",
            "score_explanation": {"matched_terms": {"high_value_title": [], "include_title": []}},
        }
    )
    write_jsonl(workspace / "data" / "selected_papers.jsonl", [paper])

    result = review_selection(workspace)

    assert len(result["likely_relevant"]) == 1
    assert not result["likely_off_topic"]
    assert "curated selection" in result["likely_relevant"][0]["reasons"][0]


def test_domain_specific_paper_roles_map_to_workspace_roles() -> None:
    foundation = enrich_paper_role({"paper_id": "p-a", "paper_role": "foundation_model"})
    benchmark = enrich_paper_role({"paper_id": "p-b", "paper_role": "hallucination_benchmark"})
    method = enrich_paper_role({"paper_id": "p-c", "paper_role": "instruction_data"})

    assert foundation["paper_role"] == "system_paper"
    assert foundation["domain_role"] == "foundation_model"
    assert benchmark["paper_role"] == "benchmark_or_dataset"
    assert method["paper_role"] == "technical_method"


def test_report_contains_synthesis_sections() -> None:
    workspace = workspace_path("report")
    write_review_workspace(workspace)

    report = generate_final_report(workspace)

    assert "## 方法分类" in report
    assert "## 系统对比" in report
    assert "## 跨论文流程模式" in report
    assert "## 对 litagent 的设计启发" in report
    assert "## 下一步路线图" in report
    assert "最终研究报告草稿" in report


def test_inspect_labels_successful_real_run_as_small_real_review() -> None:
    workspace = workspace_path("inspect-small-real")
    write_review_workspace(workspace)
    generate_final_report(workspace)
    audit_workspace(workspace)

    result = inspect_workspace(workspace)

    assert result["quality_level"] == "small_real_review"


def test_inspect_reports_research_workspace_quality_signals() -> None:
    workspace = workspace_path("inspect-workspace-quality")
    write_review_workspace(workspace)
    generate_final_report(workspace)
    audit_workspace(workspace)

    result = inspect_workspace(workspace)

    workspace_quality = result["research_workspace_quality"]
    assert workspace_quality["paper_role_counts"] == {"system_paper": 1}
    assert workspace_quality["reading_intent_counts"]["track_frontier"] == 1
    assert workspace_quality["workspace_artifacts"]["field_map"] is False
    assert any(
        "Research workspace artifacts" in warning for warning in workspace_quality["warnings"]
    )


def test_inspect_does_not_downgrade_curated_low_score_selection() -> None:
    workspace = workspace_path("inspect-curated-low-score")
    write_review_workspace(workspace, source_diverse=True)
    papers = selected_papers()[:1]
    papers[0]["relevance_score"] = 0.05
    papers[0]["curation_reason"] = "field-shaping system paper selected by Codex"
    write_jsonl(workspace / "data" / "selected_papers.jsonl", papers)
    write_jsonl(
        workspace / "data" / "raw_results.jsonl",
        [
            {**papers[0], "paper_id": "p-r1", "source": ["arxiv"], "source_query": "real"},
            {**papers[0], "paper_id": "p-r2", "source": ["openalex"], "source_query": "real"},
            {
                **papers[0],
                "paper_id": "p-r3",
                "source": ["semantic_scholar"],
                "source_query": "real",
            },
            {**papers[0], "paper_id": "p-r4", "source": ["arxiv"], "source_query": "real"},
            {**papers[0], "paper_id": "p-r5", "source": ["openalex"], "source_query": "real"},
            {
                **papers[0],
                "paper_id": "p-r6",
                "source": ["semantic_scholar"],
                "source_query": "real",
            },
            {**papers[0], "paper_id": "p-r7", "source": ["arxiv"], "source_query": "real"},
            {**papers[0], "paper_id": "p-r8", "source": ["openalex"], "source_query": "real"},
        ],
    )
    generate_final_report(workspace)
    audit_workspace(workspace)

    result = inspect_workspace(workspace)

    assert not any(
        "low deterministic relevance" in concern
        for concern in result["selected_paper_relevance"]["concerns"]
    )
