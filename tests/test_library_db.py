import sqlite3
from pathlib import Path
from uuid import uuid4

from litagent.cli import main
from litagent.io import write_json, write_jsonl
from litagent.library_db import inspect_library, sync_workspace_to_library
from litagent.workspace import create_workspace


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_workspace() -> Path:
    workspace = workspace_path("library")
    create_workspace(workspace)
    write_json(
        workspace / "research_plan.json",
        {
            "topic": "多模态模型",
            "selection_count": 2,
            "max_results_per_source": 5,
        },
    )
    write_jsonl(
        workspace / "data" / "raw_results.jsonl",
        [
            {"paper_id": "p-survey", "title": "Survey Paper"},
            {"paper_id": "p-system", "title": "System Paper"},
        ],
    )
    write_jsonl(
        workspace / "data" / "selected_papers.jsonl",
        [
            {
                "paper_id": "p-survey",
                "title": "A Survey of Multimodal Foundation Models",
                "authors": ["Ada"],
                "year": 2025,
                "venue": "ACM Computing Surveys",
                "abstract": "A survey and taxonomy for multimodal foundation models.",
                "doi": "10.1234/survey",
                "source": ["semantic_scholar", "openalex"],
                "paper_type": "survey",
                "paper_role": "survey_or_review",
                "reading_intent": ["build_field_map"],
                "relevance_score": 0.8,
                "final_score": 0.91,
                "local_pdf_path": "library/pdfs/p-survey.pdf",
                "parsed_markdown_path": "library/markdown/p-survey.md",
                "score_explanation": {
                    "matched_terms": {"high_value_title": ["multimodal foundation models"]}
                },
            },
            {
                "paper_id": "p-system",
                "title": "A Multimodal Agent System",
                "authors": ["Grace"],
                "year": 2026,
                "venue": "NeurIPS",
                "abstract": "We propose a multimodal agent system with tool use.",
                "arxiv_id": "2601.00001",
                "source": ["arxiv"],
                "paper_type": "system",
                "paper_role": "system_paper",
                "reading_intent": ["track_frontier", "compare_systems"],
                "relevance_score": 0.9,
                "final_score": 0.95,
            },
        ],
    )
    write_json(
        workspace / "knowledge" / "evidence_table.json",
        {
            "themes": [
                {
                    "theme": "field map",
                    "evidence_snippets_or_sections": [
                        {
                            "theme": "field map",
                            "claim": "Surveys define the taxonomy.",
                            "paper_id": "p-survey",
                            "section": "Introduction",
                            "snippet": "The survey organizes multimodal models into families.",
                            "confidence": 0.82,
                            "snippet_score": 0.74,
                            "quality_flags": ["concrete_method_or_taxonomy"],
                            "uncertainty_or_gap": "",
                        }
                    ],
                },
                {
                    "theme": "technical frontier",
                    "evidence_snippets_or_sections": [
                        {
                            "theme": "technical frontier",
                            "claim": "Systems use tool-using agents.",
                            "paper_id": "p-system",
                            "section": "Method",
                            "snippet": (
                                "The system routes image, text, and tool calls through agents."
                            ),
                            "confidence": 0.88,
                            "snippet_score": 0.84,
                            "quality_flags": [],
                            "uncertainty_or_gap": "",
                        }
                    ],
                },
            ]
        },
    )
    write_json(
        workspace / "logs" / "inspect_workspace.json",
        {"quality_label": "source_diverse_real_review"},
    )
    write_json(
        workspace / "data" / "search_runs" / "latest.json",
        {"run_id": "library-test-run"},
    )
    write_json(
        workspace / "run_state.json",
        {
            "status": "succeeded",
            "started_at": "2026-04-29T00:00:00+00:00",
            "finished_at": "2026-04-29T00:10:00+00:00",
        },
    )
    return workspace


def table_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_sync_workspace_to_library_creates_global_tables() -> None:
    workspace = make_workspace()
    db_path = workspace_path("library-db") / "library.db"

    result = sync_workspace_to_library(
        workspace,
        db_path=db_path,
        topic_slug="multimodal-models",
    )

    assert result["papers_synced"] == 2
    assert result["evidence_spans_synced"] == 2
    assert result["topic_id"] == "multimodal-models"
    assert result["run_id"] == "multimodal-models:library-test-run"
    assert table_count(db_path, "papers") == 2
    assert table_count(db_path, "topics") == 1
    assert table_count(db_path, "topic_papers") == 2
    assert table_count(db_path, "runs") == 1
    assert table_count(db_path, "evidence_spans") == 2

    status = inspect_library(db_path)
    assert status["counts"]["papers"] == 2
    assert status["topics"][0]["paper_count"] == 2
    assert status["topics"][0]["evidence_count"] == 2


def test_sync_library_is_idempotent_and_cli_reports_json() -> None:
    workspace = make_workspace()
    db_path = workspace_path("library-db-cli") / "library.db"

    first = main(
        [
            "sync-library",
            str(workspace),
            "--library-db",
            str(db_path),
            "--topic-slug",
            "multimodal-models",
            "--json",
        ]
    )
    second = main(
        [
            "sync-library",
            str(workspace),
            "--library-db",
            str(db_path),
            "--topic-slug",
            "multimodal-models",
            "--json",
        ]
    )
    status = main(["library-status", "--library-db", str(db_path), "--json"])

    assert first == 0
    assert second == 0
    assert status == 0
    assert table_count(db_path, "papers") == 2
    assert table_count(db_path, "topic_papers") == 2
    assert table_count(db_path, "evidence_spans") == 2
