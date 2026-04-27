from pathlib import Path
from uuid import uuid4

from litagent.dedup import dedup_and_rank, score_paper
from litagent.io import read_jsonl, write_jsonl
from litagent.planner import write_research_plan
from litagent.search import execute_search


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_search_runs_are_isolated_and_dedup_defaults_to_latest() -> None:
    workspace = workspace_path("search-runs")
    write_research_plan(workspace, "old topic", selection_count=3)
    execute_search(workspace, mock=True, run_id="run-old")
    write_research_plan(workspace, "new topic", selection_count=3)
    execute_search(workspace, mock=True, run_id="run-new")

    selected = dedup_and_rank(workspace, selection_count=3)

    assert (workspace / "data" / "search_runs" / "run-old" / "raw_results.jsonl").is_file()
    assert (workspace / "data" / "search_runs" / "run-new" / "raw_results.jsonl").is_file()
    assert selected
    latest_run_ids = {
        paper["search_run_id"] for paper in read_jsonl(workspace / "data" / "papers.jsonl")
    }
    assert latest_run_ids == {"run-new"}

    old_rows = read_jsonl(workspace / "data" / "search_runs" / "run-old" / "raw_results.jsonl")
    old_rows.append(
        {
            **old_rows[0],
            "paper_id": "p-oldunique000",
            "title": "Old Unique Literature Review Agent",
            "search_run_id": "run-old",
            "doi": "10.1234/old-unique",
        }
    )
    write_jsonl(workspace / "data" / "search_runs" / "run-old" / "raw_results.jsonl", old_rows)
    dedup_and_rank(workspace, selection_count=20, search_scope="all")
    assert {"run-old", "run-new"} <= {
        paper["search_run_id"] for paper in read_jsonl(workspace / "data" / "papers.jsonl")
    }


def test_topic_sensitive_ranking_explains_positive_and_negative_matches() -> None:
    plan = {
        "include_keywords": [
            "literature review generation",
            "multi-agent research system",
            "paper reading agent",
        ],
        "exclude_keywords": ["traffic", "robotics", "medical"],
        "date_range": {"from": 2018, "to": 2026},
    }
    relevant = {
        "title": "LiRA: A Multi-Agent Framework for Literature Review Generation",
        "abstract": "A multi-agent research system for citation-aware synthesis.",
        "year": 2025,
        "citation_count": 1,
        "pdf_url": "https://arxiv.org/pdf/1.pdf",
        "source": ["arxiv"],
    }
    off_topic = {
        "title": "Traffic Robotics with Reinforcement Learning",
        "abstract": "A medical education benchmark unrelated to literature review generation.",
        "year": 2025,
        "citation_count": 500,
        "pdf_url": "https://example.org/paper.pdf",
        "source": ["openalex"],
    }

    relevant_score = score_paper(relevant, plan)
    off_topic_score = score_paper(off_topic, plan)

    assert relevant_score["final_score"] > off_topic_score["final_score"]
    assert relevant_score["score_explanation"]["matched_terms"]["high_value_title"]
    assert off_topic_score["score_explanation"]["matched_terms"]["negative_title"]
    assert off_topic_score["exclusion_score"] > 0
