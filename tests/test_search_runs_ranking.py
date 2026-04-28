from pathlib import Path
from uuid import uuid4

from litagent.dedup import dedup_and_rank, score_paper
from litagent.io import read_jsonl, write_jsonl
from litagent.planner import write_research_plan
from litagent.search import execute_search, provider_error_details, provider_error_message


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
    assert relevant_score["relevance_score"] >= 0.25
    assert relevant_score["score_explanation"]["matched_terms"]["high_value_title"]
    assert off_topic_score["score_explanation"]["matched_terms"]["negative_title"]
    assert off_topic_score["exclusion_score"] > 0


def test_plan_specific_high_value_phrases_affect_ranking() -> None:
    plan = {
        "include_keywords": ["multimodal large language model"],
        "high_value_phrases": ["BLIP-2"],
        "date_range": {"from": 2018, "to": 2026},
    }
    paper = {
        "title": "BLIP-2: Bootstrapping Language-Image Pre-training",
        "abstract": "A foundational vision-language model.",
        "year": 2023,
        "citation_count": 10,
        "pdf_url": "https://arxiv.org/pdf/1.pdf",
        "source": ["arxiv"],
    }

    scored = score_paper(paper, plan)

    assert scored["score_explanation"]["matched_terms"]["high_value_title"] == ["blip-2"]
    assert scored["score_explanation"]["component_scores"]["high_value_phrase"] > 0


def test_semantic_scholar_429_error_mentions_key_configuration() -> None:
    message = provider_error_message("semantic_scholar", RuntimeError("HTTP Error 429"))

    assert "SEMANTIC_SCHOLAR_API_KEY" in message
    assert "SEMANTIC_SCHOLAR_API_BASE_URL" in message


def test_semantic_scholar_403_error_details_are_actionable(monkeypatch) -> None:
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "search-log-secret")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_BASE_URL", "https://s2api.example.test/s2")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_AUTH_MODE", "authorization_bearer")

    details = provider_error_details("semantic_scholar", RuntimeError("HTTP Error 403: Forbidden"))
    message = provider_error_message("semantic_scholar", RuntimeError("HTTP Error 403: Forbidden"))

    assert details["status_code"] == 403
    assert details["error_type"] == "forbidden"
    assert details["auth_mode"] == "authorization_bearer"
    assert details["base_url_type"] == "custom"
    assert details["key_present"] is True
    assert "endpoint" in details
    assert "search-log-secret" not in str(details)
    assert "auth header mode" in message
    assert "search-log-secret" not in message
