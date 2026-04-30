from pathlib import Path
from uuid import uuid4

from litagent.io import write_json, write_jsonl
from litagent.result_summary import result_summary_markdown, summarize_workspace_result


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_mobile_summary_prioritizes_condensed_knowledge_points() -> None:
    workspace = workspace_path("mllm-result-summary")
    write_json(workspace / "research_plan.json", {"topic": "多模态大模型领域"})
    write_json(
        workspace / "knowledge" / "evidence_table.json",
        {
            "themes": [
                {
                    "evidence_snippets_or_sections": [
                        {"paper_id": "p1", "snippet": "hallucination benchmark"}
                    ]
                }
            ]
        },
    )
    write_jsonl(
        workspace / "data" / "selected_papers.jsonl",
        [
            {
                "paper_id": "p1",
                "title": "Hallucination of Multimodal Large Language Models: A Survey",
                "abstract": "survey of hallucination, benchmarks, and mitigation for MLLMs",
                "paper_role": "survey_or_review",
                "final_score": 0.96,
                "citation_count": 300,
                "year": 2024,
            },
            {
                "paper_id": "p2",
                "title": "Dynamic Token Reweighting for Robust Vision-Language Models",
                "abstract": "inference-time defense for jailbreak attacks and robust VLMs",
                "paper_role": "technical_method",
                "final_score": 0.92,
                "citation_count": 10,
                "year": 2025,
            },
            {
                "paper_id": "p3",
                "title": "MME: A Comprehensive Evaluation Benchmark for MLLMs",
                "abstract": "benchmark and evaluation dataset for multimodal models",
                "paper_role": "benchmark_or_dataset",
                "final_score": 0.9,
                "citation_count": 100,
                "year": 2023,
            },
        ],
    )

    result = summarize_workspace_result(
        workspace,
        job={"id": "job-test", "topic": "多模态大模型领域", "status": "succeeded"},
    )
    summary = result["mobile_summary"]
    rendered = result_summary_markdown(result)

    assert summary[0].startswith("领域边界")
    assert any("技术主线" in line and "可靠性" in line for line in summary)
    assert any("评测体系" in line for line in summary)
    assert not any(line.startswith("领域地图：") for line in summary)
    assert rendered.startswith("知识点摘要：")
    assert rendered.index("知识点摘要") < rendered.index("运行信息")


def test_mobile_long_report_artifacts_are_written() -> None:
    workspace = workspace_path("mobile-report")
    write_json(workspace / "research_plan.json", {"topic": "多模态大模型领域"})
    write_json(
        workspace / "knowledge" / "evidence_table.json",
        {
            "themes": [
                {
                    "theme": "hallucination and evaluation",
                    "claim": "需要把幻觉和评测作为默认质量门禁。",
                    "evidence_snippets_or_sections": [
                        {
                            "paper_id": "p1",
                            "paper_title": "Hallucination of Multimodal Large Language Models",
                            "section": "Evaluation",
                            "snippet": "The paper reviews benchmarks and mitigation methods.",
                            "snippet_score": 0.95,
                        }
                    ],
                }
            ]
        },
    )
    write_jsonl(
        workspace / "data" / "selected_papers.jsonl",
        [
            {
                "paper_id": "p1",
                "title": "Hallucination of Multimodal Large Language Models",
                "abstract": "MLLM hallucination survey with benchmarks and mitigation.",
                "paper_role": "survey_or_review",
                "final_score": 0.96,
                "citation_count": 300,
                "year": 2024,
                "source": ["arxiv"],
            },
            {
                "paper_id": "p2",
                "title": "LVLM-eHub: A Comprehensive Evaluation Benchmark",
                "abstract": "Benchmark and evaluation suite for LVLMs.",
                "paper_role": "benchmark_or_dataset",
                "final_score": 0.9,
                "citation_count": 100,
                "year": 2023,
                "source": ["semantic_scholar"],
            },
        ],
    )

    result = summarize_workspace_result(
        workspace,
        job={"id": "job-report", "topic": "多模态大模型领域", "status": "succeeded"},
        write_report=True,
    )
    artifacts = result["artifacts"]
    markdown_path = Path(artifacts["mobile_report_markdown"]["path"])
    html_path = Path(artifacts["mobile_report_html"]["path"])

    markdown = markdown_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")

    assert markdown_path.is_file()
    assert html_path.is_file()
    assert "# 多模态大模型领域：手机长版调研简报" in markdown
    assert "## Top 论文清单" in markdown
    assert "## 证据摘录" in markdown
    assert "Hallucination of Multimodal Large Language Models" in markdown
    assert "<html" in html
    assert "手机长版调研简报" in html
    assert artifacts["agent_synthesis_pack"]["exists"]
    assert artifacts["agent_synthesis_prompt"]["exists"]
    assert artifacts["mobile_report_markdown"]["source"] == "deterministic_summary"


def test_agent_synthesis_markdown_is_used_when_present() -> None:
    workspace = workspace_path("agent-synthesis-report")
    write_json(workspace / "research_plan.json", {"topic": "多模态大模型领域"})
    write_jsonl(
        workspace / "data" / "selected_papers.jsonl",
        [
            {
                "paper_id": "p1",
                "title": "A Paper About Multimodal Reasoning",
                "abstract": "This paper studies a concrete multimodal reasoning problem.",
                "paper_role": "technical_method",
                "final_score": 0.9,
                "year": 2025,
            }
        ],
    )
    note_path = workspace / "library" / "notes" / "p1.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "\n".join(
            [
                "# A Paper About Multimodal Reasoning",
                "## 3. Parsed Full-Text-Derived Evidence",
                "### Problem Addressed",
                "- Evidence (Introduction, score=0.88): The paper defines the failure mode.",
            ]
        ),
        encoding="utf-8",
    )
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    agent_report = reports_dir / "codex_synthesis.md"
    agent_report.write_text(
        "# Codex 深度综合\n\n## 论文精华卡片\n\n- 背景/问题：由 Codex 基于证据写入。",
        encoding="utf-8",
    )

    result = summarize_workspace_result(
        workspace,
        job={"id": "job-agent", "topic": "多模态大模型领域", "status": "succeeded"},
        write_report=True,
    )
    artifacts = result["artifacts"]
    markdown_path = Path(artifacts["mobile_report_markdown"]["path"])
    pack_path = Path(artifacts["agent_synthesis_pack"]["path"])

    assert artifacts["agent_synthesis_markdown"]["exists"]
    assert artifacts["mobile_report_markdown"]["source"] == "agent_synthesis"
    assert markdown_path.read_text(encoding="utf-8").startswith("# Codex 深度综合")
    pack = pack_path.read_text(encoding="utf-8")
    assert "A Paper About Multimodal Reasoning" in pack
    assert "The paper defines the failure mode" in pack
