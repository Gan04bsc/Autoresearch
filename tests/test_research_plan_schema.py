from pathlib import Path
from uuid import uuid4

from litagent.cli import main
from litagent.io import read_json
from litagent.planner import create_research_plan


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_create_research_plan_matches_prd_schema() -> None:
    plan = create_research_plan("agentic literature review tools", selection_count=5)

    assert plan["topic"] == "agentic literature review tools"
    assert plan["selection_count"] == 5
    assert set(plan["search_queries"]) == {"arxiv", "semantic_scholar", "openalex"}
    assert plan["date_range"]["from"] >= 2018
    assert plan["date_range"]["to"] >= plan["date_range"]["from"]
    assert "ranking_policy" in plan


def test_plan_cli_writes_json_and_markdown() -> None:
    workspace = workspace_path("plan")

    result = main(["plan", "multi-agent literature automation", "--workspace", str(workspace)])

    assert result == 0
    plan = read_json(workspace / "research_plan.json")
    assert plan["topic"] == "multi-agent literature automation"
    assert (
        (workspace / "research_plan.md").read_text(encoding="utf-8").startswith("# Research Plan")
    )


def test_literature_agent_topic_uses_focused_real_mode_terms() -> None:
    plan = create_research_plan("多智能体文献综述自动化工具", selection_count=5)
    queries = "\n".join(query for source in plan["search_queries"].values() for query in source)

    assert "LLM agents" in plan["include_keywords"]
    assert "agentic research assistant" in plan["include_keywords"]
    assert "automated literature review" in plan["include_keywords"]
    assert "论文阅读智能体" in plan["include_keywords"]
    assert "swarm robotics" in plan["exclude_keywords"]
    assert "traffic control" in plan["exclude_keywords"]
    assert "citation-aware synthesis" in queries
    assert "多智能体 文献综述 自动化综述 科研助手 论文阅读智能体" in queries
