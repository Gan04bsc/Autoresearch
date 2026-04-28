from pathlib import Path
from uuid import uuid4

from litagent import reader as reader_module
from litagent.audit import REQUIRED_REPORT_SECTIONS, audit_workspace
from litagent.evidence import THEME_SPECS, build_evidence_table, paper_matches_theme
from litagent.evidence_quality import clean_snippet, normalize_section_title, score_snippet
from litagent.inspect import inspect_workspace
from litagent.io import read_json, write_json, write_jsonl
from litagent.knowledge import build_knowledge
from litagent.reader import generate_notes
from litagent.report import generate_final_report
from litagent.schema import normalize_paper


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def evidence_paper() -> dict:
    return normalize_paper(
        {
            "paper_id": "p-aaaaaaaaaaaa",
            "title": "AgentReview: A Multi-Agent Literature Review Generation System",
            "authors": ["A"],
            "year": 2025,
            "venue": "arXiv",
            "abstract": (
                "We introduce a multi-agent system for literature review generation with "
                "citation-aware synthesis."
            ),
            "doi": "10.1234/agentreview",
            "citation_count": 2,
            "reference_count": 10,
            "url": "https://example.org/agentreview",
            "pdf_url": "mock://pdf/agentreview",
            "local_pdf_path": "library/pdfs/p-aaaaaaaaaaaa.pdf",
            "parsed_markdown_path": "library/markdown/p-aaaaaaaaaaaa.md",
            "source": ["arxiv"],
            "paper_type": "system",
            "relevance_score": 0.9,
            "download_status": "success",
            "parse_status": "success",
            "parse_provider": "local",
        }
    )


def write_evidence_workspace(workspace: Path, *, with_evidence_report: bool = False) -> dict:
    paper = evidence_paper()
    plan = {
        "topic": "agentic literature review tools",
        "goal": "test",
        "core_questions": ["How do systems ground review generation?"],
        "include_keywords": ["multi-agent", "literature review generation"],
        "exclude_keywords": ["traffic"],
        "search_queries": {"arxiv": ["multi-agent literature review generation"]},
        "date_range": {"from": 2018, "to": 2026},
        "max_results_per_source": 10,
        "selection_count": 1,
        "ranking_policy": "test",
    }
    write_json(workspace / "research_plan.json", plan)
    (workspace / "research_plan.md").write_text("# Plan\n", encoding="utf-8")
    write_jsonl(workspace / "data" / "raw_results.jsonl", [{**paper, "source_query": "real"}])
    write_jsonl(workspace / "data" / "papers.jsonl", [paper])
    write_jsonl(workspace / "data" / "selected_papers.jsonl", [paper])
    write_jsonl(
        workspace / "logs" / "downloads.jsonl",
        [{"paper_id": paper["paper_id"], "download_status": "success"}],
    )
    pdf = workspace / "library" / "pdfs" / "p-aaaaaaaaaaaa.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4\n% test\n")
    markdown = workspace / "library" / "markdown" / "p-aaaaaaaaaaaa.md"
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(
        "\n".join(
            [
                "# AgentReview",
                "## Introduction",
                "The problem is that manual literature review is labor-intensive.",
                "## Method",
                "We propose a framework with planner agent, collector agent, writer agent, "
                "and reviewer agent.",
                "## Pipeline",
                "The pipeline includes retrieval, screening, outline planning, writing, "
                "citation checking, and revision stages.",
                "The retrieval strategy searches candidate papers and reranks them for "
                "source selection.",
                "Citation evidence is handled by a citation graph and grounding checks.",
                "## Evaluation",
                "The evaluation uses a benchmark dataset, baselines, metrics, and human "
                "evaluation.",
                "Results show the system outperforms baselines and improves citation quality.",
                "## Limitations",
                "Limitations include hallucination risk and incomplete retrieval coverage.",
                "## References",
                "[1] Smith, J. arXiv preprint about unrelated agent references.",
            ]
        ),
        encoding="utf-8",
    )
    build_knowledge(workspace)
    if with_evidence_report:
        generate_notes(workspace)
        build_evidence_table(workspace)
        generate_final_report(workspace)
    else:
        report = ["# Final Research Report", ""]
        report.extend(f"## {section}\n\n[p-aaaaaaaaaaaa]\n" for section in REQUIRED_REPORT_SECTIONS)
        (workspace / "reports").mkdir(parents=True, exist_ok=True)
        (workspace / "reports" / "final_report.md").write_text(
            "\n".join(report),
            encoding="utf-8",
        )
        write_json(
            workspace / "library" / "metadata" / "p-aaaaaaaaaaaa.json",
            {**paper, "text_source": "local"},
        )
        note = workspace / "library" / "notes" / "p-aaaaaaaaaaaa.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("# Note\n\nMetadata / Abstract-Derived Content\n", encoding="utf-8")
    return paper


def test_read_extracts_parsed_markdown_evidence() -> None:
    workspace = workspace_path("reader-evidence")
    paper = write_evidence_workspace(workspace)

    generate_notes(workspace)

    note = (workspace / "library" / "notes" / f"{paper['paper_id']}.md").read_text(
        encoding="utf-8"
    )
    metadata = read_json(workspace / "library" / "metadata" / f"{paper['paper_id']}.json")
    assert "## 3. Parsed Full-Text-Derived Evidence" in note
    assert "### Agent Roles" in note
    assert "planner agent" in note
    assert "(Method, score=" in note
    assert "score=" in note
    assert metadata["paper_evidence"]["fields"]["agent_roles"]["source"] == "parsed-full-text"
    item = metadata["paper_evidence"]["fields"]["agent_roles"]["evidence_items"][0]
    assert item["section"] == "Method"
    assert item["snippet_score"] >= 0.45
    assert "snippet_score_explanation" in item
    assert "quality_flags" in item


def test_reader_reuses_sectioned_units_per_paper(monkeypatch) -> None:
    workspace = workspace_path("reader-section-cache")
    paper = write_evidence_workspace(workspace)
    original_sectioned_units = reader_module.sectioned_units
    calls: list[int] = []

    def counted_sectioned_units(text: str) -> list[dict[str, str]]:
        calls.append(len(text))
        return original_sectioned_units(text)

    monkeypatch.setattr(reader_module, "sectioned_units", counted_sectioned_units)

    generate_notes(workspace)

    assert (workspace / "library" / "notes" / f"{paper['paper_id']}.md").is_file()
    assert len(calls) == 2


def test_section_recognition_and_snippet_scoring() -> None:
    assert normalize_section_title("2. Methodology") == "Method"
    assert normalize_section_title("## Evaluation") == "Evaluation"
    assert normalize_section_title("Limitations") == "Limitations"
    assert normalize_section_title("References") == "References"
    assert normalize_section_title("Appendix A") == "Appendix"

    method = score_snippet(
        "We propose a framework with planner agent, collector agent, retrieval stage, "
        "citation checking, benchmark dataset, metrics, and human evaluation.",
        section="Method",
        target_terms=["framework", "agent", "citation"],
    )
    reference = score_snippet(
        "[12] Smith, J. arXiv preprint 2024. https://example.org/paper",
        section="References",
        target_terms=["reference"],
    )
    unknown = score_snippet(
        "The system discusses review generation but provides limited implementation detail.",
        section="Unknown",
        target_terms=["review generation"],
    )

    assert method["snippet_score"] > 0.7
    assert reference["snippet_score"] < 0.35
    assert unknown["snippet_score"] < method["snippet_score"]
    assert "加分" in method["snippet_score_explanation"]
    assert "扣分" in reference["snippet_score_explanation"]


def test_snippet_cleaning_marks_noise() -> None:
    url_clean, url_flags = clean_snippet("https://example.org/a https://example.org/b")
    ref_clean, ref_flags = clean_snippet("[3] Doe, J. arXiv preprint 2024.")
    prompt_clean, prompt_flags = clean_snippet("Prompt template: You are a helpful reviewer.")
    table_clean, table_flags = clean_snippet("Method | Score | Dataset | Metric")
    short_clean, short_flags = clean_snippet("Too short.")
    long_clean, long_flags = clean_snippet("word " * 200)

    assert url_clean == ""
    assert "url_heavy" in url_flags
    assert "reference_like" in ref_flags
    assert "code_or_prompt" in prompt_flags
    assert "table_like" in table_flags
    assert "too_short" in short_flags
    assert "too_long" in long_flags
    assert len(long_clean) <= 700


def test_build_evidence_table_generates_json_and_markdown() -> None:
    workspace = workspace_path("evidence-table")
    write_evidence_workspace(workspace)
    generate_notes(workspace)

    result = build_evidence_table(workspace)

    assert (workspace / "knowledge" / "evidence_table.md").is_file()
    assert (workspace / "knowledge" / "evidence_table.json").is_file()
    themes = {row["theme"]: row for row in result["themes"]}
    assert "multi-agent architecture" in themes
    assert themes["multi-agent architecture"]["supporting_papers"] == ["p-aaaaaaaaaaaa"]
    snippet = themes["multi-agent architecture"]["evidence_snippets_or_sections"][0]
    assert snippet["section"] == "Method"
    assert "snippet_score" in snippet
    assert "snippet_score_explanation" in snippet
    assert "quality_flags" in snippet


def test_build_evidence_table_uses_plan_coverage_targets_when_available() -> None:
    workspace = workspace_path("evidence-table-coverage")
    write_evidence_workspace(workspace)
    plan = read_json(workspace / "research_plan.json")
    plan["coverage_targets"] = {
        "foundation models and systems": ["framework", "agent"],
        "benchmark and evaluation": ["benchmark", "evaluation"],
    }
    write_json(workspace / "research_plan.json", plan)
    generate_notes(workspace)

    result = build_evidence_table(workspace)

    themes = {row["theme"]: row for row in result["themes"]}
    assert set(themes) == {"foundation models and systems", "benchmark and evaluation"}
    assert themes["foundation models and systems"]["supporting_papers"] == [
        "p-aaaaaaaaaaaa"
    ]


def test_strict_evidence_themes_require_theme_specific_terms() -> None:
    paper = normalize_paper(
        {
            "paper_id": "p-bbbbbbbbbbbb",
            "title": "Generic Agent Workflow For Traffic Signals",
            "authors": ["B"],
            "year": 2024,
            "abstract": "An agent retrieves data and evaluates a traffic signal workflow.",
            "source": ["openalex"],
        }
    )
    evidence = {
        "fields": {
            "agent_roles": {
                "source": "parsed-full-text",
                "snippets": ["The agent coordinates a generic workflow."],
            },
            "retrieval_search_strategy": {
                "source": "parsed-full-text",
                "snippets": ["The agent retrieves traffic observations."],
            },
            "key_findings": {
                "source": "parsed-full-text",
                "snippets": ["Results improve signal timing."],
            },
            "citation_or_evidence_handling": {
                "source": "parsed-full-text",
                "snippets": ["The article includes references."],
            },
        }
    }

    assert not paper_matches_theme(paper, evidence, THEME_SPECS["paper reading agents"])
    assert not paper_matches_theme(paper, evidence, THEME_SPECS["citation-aware synthesis"])


def test_report_uses_evidence_table_claims() -> None:
    workspace = workspace_path("evidence-report")
    write_evidence_workspace(workspace, with_evidence_report=True)

    report = (workspace / "reports" / "final_report.md").read_text(encoding="utf-8")

    assert "## 证据支撑的主题综合" in report
    assert "多智能体架构" in report
    assert "[p-aaaaaaaaaaaa]" in report
    assert "score=" in report
    assert "arXiv preprint about unrelated agent references" not in report
    assert "证据表" in report


def test_audit_and_inspect_warn_when_evidence_is_missing_or_shallow() -> None:
    workspace = workspace_path("missing-evidence")
    write_evidence_workspace(workspace)

    audit = audit_workspace(workspace)
    inspection = inspect_workspace(workspace)

    assert audit["passed"] is True
    assert any("Evidence table is missing" in warning for warning in audit["warnings"])
    assert any(
        "Evidence table is missing" in concern
        for concern in inspection["parse_report_audit_quality"]["concerns"]
    )


def test_audit_and_inspect_warn_for_low_quality_evidence() -> None:
    workspace = workspace_path("low-quality-evidence")
    write_evidence_workspace(workspace)
    low_quality_item = {
        "theme": "citation-aware synthesis",
        "claim": "低质量测试证据。",
        "paper_id": "p-aaaaaaaaaaaa",
        "paper_title": "AgentReview",
        "field": "citation_or_evidence_handling",
        "source": "parsed-full-text",
        "snippet": "[1] Smith, J. arXiv preprint. https://example.org",
        "section": "References",
        "snippet_score": 0.05,
        "snippet_score_explanation": "加分：无；扣分：References 属于噪声章节",
        "confidence": "low",
        "quality_flags": ["noise_section", "reference_like"],
        "uncertainty_or_gap": "片段质量较低。",
    }
    write_json(
        workspace / "knowledge" / "evidence_table.json",
        {
            "workspace": str(workspace),
            "selected_count": 1,
            "themes": [
                {
                    "theme": "citation-aware synthesis",
                    "claim": "低质量测试证据。",
                    "supporting_papers": [],
                    "evidence_snippets_or_sections": [low_quality_item],
                    "confidence": "low",
                    "gaps_or_uncertainties": ["证据不足。"],
                }
            ],
        },
    )
    (workspace / "knowledge" / "evidence_table.md").write_text("# 证据表\n", encoding="utf-8")

    audit = audit_workspace(workspace)
    inspection = inspect_workspace(workspace)

    assert audit["passed"] is True
    assert any("low-score" in warning for warning in audit["warnings"])
    assert any(
        "low-score" in warning
        for warning in inspection["parse_report_audit_quality"]["warnings"]
    )
