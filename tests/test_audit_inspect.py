from pathlib import Path
from uuid import uuid4

from litagent.audit import REQUIRED_REPORT_SECTIONS, audit_workspace
from litagent.inspect import inspect_workspace
from litagent.io import write_json, write_jsonl
from litagent.schema import normalize_paper


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_minimal_review_workspace(workspace: Path) -> dict:
    plan = {
        "topic": "agentic literature review tools",
        "goal": "Build a traceable literature workbench",
        "core_questions": ["What is the field?"],
        "include_keywords": ["agentic", "literature", "review"],
        "exclude_keywords": ["swarm robotics"],
        "search_queries": {"arxiv": ["agentic literature review"], "semantic_scholar": []},
        "date_range": {"from": 2018, "to": 2026},
        "max_results_per_source": 10,
        "selection_count": 1,
        "ranking_policy": "test ranking policy",
    }
    paper = normalize_paper(
        {
            "paper_id": "p-123456789abc",
            "title": "Agentic Literature Review Tool",
            "authors": ["A"],
            "year": 2025,
            "venue": "Test Venue",
            "abstract": "A test abstract.",
            "doi": "10.1234/example",
            "citation_count": 3,
            "reference_count": 5,
            "url": "https://example.org/paper",
            "pdf_url": "mock://pdf/test",
            "local_pdf_path": "library/pdfs/p-123456789abc.pdf",
            "source": ["semantic_scholar"],
            "paper_type": "system",
            "relevance_score": 0.8,
            "download_status": "success",
            "download_error": None,
        }
    )

    write_json(workspace / "research_plan.json", plan)
    (workspace / "research_plan.md").write_text("# Research Plan\n", encoding="utf-8")
    write_jsonl(workspace / "data" / "raw_results.jsonl", [{**paper, "source_query": "mock"}])
    write_jsonl(workspace / "data" / "papers.jsonl", [paper])
    write_jsonl(workspace / "data" / "selected_papers.jsonl", [paper])
    write_jsonl(
        workspace / "logs" / "downloads.jsonl",
        [{"paper_id": paper["paper_id"], "download_status": "success"}],
    )
    pdf_path = workspace / "library" / "pdfs" / "p-123456789abc.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4\n% test\n")
    note_path = workspace / "library" / "notes" / "p-123456789abc.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Note\n\nText source: abstract fallback\n", encoding="utf-8")
    write_json(
        workspace / "library" / "metadata" / "p-123456789abc.json",
        {**paper, "text_source": "abstract fallback (test)"},
    )
    (workspace / "knowledge").mkdir(parents=True, exist_ok=True)
    (workspace / "knowledge" / "base_knowledge.md").write_text("# Base\n", encoding="utf-8")
    (workspace / "knowledge" / "topic_map.md").write_text("# Topic\n", encoding="utf-8")
    (workspace / "knowledge" / "index.md").write_text("# Index\n", encoding="utf-8")
    report = ["# Final Research Report", ""]
    report.extend(f"## {section}\n\n[p-123456789abc]\n" for section in REQUIRED_REPORT_SECTIONS)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "reports" / "final_report.md").write_text("\n".join(report), encoding="utf-8")
    return paper


def test_audit_fails_when_downloaded_pdfs_have_no_parsed_markdown() -> None:
    workspace = workspace_path("audit")
    write_minimal_review_workspace(workspace)

    result = audit_workspace(workspace)

    assert result["passed"] is False
    assert result["parse_quality"]["selected_count"] == 1
    assert result["parse_quality"]["downloaded_pdf_count"] == 1
    assert result["parse_quality"]["parsed_markdown_count"] == 0
    assert result["parse_quality"]["parse_success_rate"] == 0.0
    assert any("No parsed Markdown files" in issue for issue in result["issues"])
    audit_report = (workspace / "logs" / "audit_report.md").read_text(encoding="utf-8")
    assert "Downloaded PDFs: 1" in audit_report
    assert "Parsed Markdown files: 0" in audit_report
    assert "Parse success rate: 0%" in audit_report
    assert "Notes from abstract fallback: 1" in audit_report


def test_inspect_workspace_recommends_fixing_parse_quality() -> None:
    workspace = workspace_path("inspect")
    write_minimal_review_workspace(workspace)
    audit_workspace(workspace)

    result = inspect_workspace(workspace)

    assert result["quality_level"] == "smoke_test_run"
    assert "Fix PDF parsing" in result["recommended_next_action"]
    assert any(
        "Downloaded PDFs exist" in concern
        for concern in result["parse_report_audit_quality"]["concerns"]
    )
