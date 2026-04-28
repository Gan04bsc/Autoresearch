from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl
from litagent.paper_roles import enrich_paper_role, intent_counts, role_counts
from litagent.schema import extract_terms, format_short_citation, normalize_paper


def paper_link(paper: dict[str, Any]) -> str:
    note_path = paper.get("note_path") or str(Path("library") / "notes" / f"{paper['paper_id']}.md")
    return f"[{paper.get('title') or paper['paper_id']}]({note_path})"


def reading_order(papers: list[dict[str, Any]]) -> list[str]:
    return [
        f"{index}. {paper_link(paper)} - {format_short_citation(paper)} [{paper['paper_id']}]"
        for index, paper in enumerate(papers, start=1)
    ]


def group_by_type(papers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        grouped[paper.get("paper_type") or "unknown"].append(paper)
    return dict(grouped)


def group_by_role(papers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        enriched = enrich_paper_role(paper)
        grouped[enriched["paper_role"]].append(enriched)
    return dict(grouped)


def short_text(value: str | None, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def matrix_cell(value: str | None, limit: int = 96) -> str:
    return short_text(value, limit).replace("|", "\\|") or "待补充"


def paper_bullet(paper: dict[str, Any]) -> str:
    role = paper.get("paper_role") or "background_foundation"
    intents = ", ".join(paper.get("reading_intent") or [])
    return (
        f"- {paper_link(paper)} [{paper['paper_id']}]，{paper.get('year') or 'n.d.'}，"
        f"角色：`{role}`，阅读意图：{intents or '待判断'}。"
    )


def write_base_knowledge(
    workspace: Path, plan: dict[str, Any], papers: list[dict[str, Any]]
) -> None:
    topic = plan.get("topic", "Research topic")
    terms = extract_terms(
        " ".join([topic, *[paper.get("abstract", "") for paper in papers]]), limit=20
    )
    routes = sorted(group_by_type(papers))
    content = [
        "# Base Knowledge",
        "",
        "## One-Sentence Definition",
        "",
        f"{topic} is a research area organized here through traceable papers, notes, methods, "
        "evaluation artifacts, and open questions.",
        "",
        "## Why This Field Matters",
        "",
        "It matters because researchers and builders need faster literature entry, better evidence "
        "tracking, and reusable knowledge structures grounded in source papers.",
        "",
        "## Key Terms",
        "",
        *[f"- {term}" for term in terms],
        "",
        "## Prerequisites",
        "",
        "- Academic search APIs and metadata quality",
        "- Literature review methodology",
        "- Citation and evidence tracking",
        "- Basic evaluation design for AI systems",
        "",
        "## Core Questions",
        "",
        *[f"- {question}" for question in plan.get("core_questions", [])],
        "",
        "## Main Technical Routes",
        "",
        *[
            f"- {route}: {len(group_by_type(papers).get(route, []))} selected papers"
            for route in routes
        ],
        "",
        "## Representative Reading Order",
        "",
        *reading_order(papers),
        "",
        "## 1 Day / 1 Week / 1 Month Learning Route",
        "",
        "- 1 day: read the top survey, topic map, and final report executive summary.",
        "- 1 week: read all selected notes, then compare system, benchmark, and dataset papers.",
        "- 1 month: reproduce search/ranking/audit workflows and design a focused follow-up study.",
        "",
    ]
    (workspace / "knowledge" / "base_knowledge.md").write_text("\n".join(content), encoding="utf-8")


def write_topic_map(workspace: Path, plan: dict[str, Any], papers: list[dict[str, Any]]) -> None:
    topic = plan.get("topic", "Research topic")
    grouped = group_by_type(papers)
    lines = [
        "# Topic Map",
        "",
        f"- {topic}",
    ]
    for paper_type, group in sorted(grouped.items()):
        lines.append(f"  - {paper_type}")
        lines.append(f"    - Representative questions and methods for {paper_type}")
        for paper in group:
            lines.append(f"      - {paper_link(paper)} [{paper['paper_id']}]")
    lines.append("")
    (workspace / "knowledge" / "topic_map.md").write_text("\n".join(lines), encoding="utf-8")


def write_glossary(workspace: Path, plan: dict[str, Any], papers: list[dict[str, Any]]) -> None:
    terms = extract_terms(
        " ".join([plan.get("topic", ""), *[paper.get("abstract", "") for paper in papers]]), 24
    )
    lines = ["# Glossary", ""]
    for term in terms:
        lines.append(f"- **{term}**: Term extracted from the topic or selected paper abstracts.")
    lines.append("")
    (workspace / "knowledge" / "glossary.md").write_text("\n".join(lines), encoding="utf-8")


def write_index(workspace: Path, papers: list[dict[str, Any]]) -> None:
    lines = [
        "# Knowledge Index",
        "",
        "## Core Files",
        "",
        "- [Base Knowledge](base_knowledge.md)",
        "- [Topic Map](topic_map.md)",
        "- [Glossary](glossary.md)",
        "- [Field Map](field_map.md)",
        "- [Technical Frontier](technical_frontier.md)",
        "- [Method Matrix](method_matrix.md)",
        "- [Benchmark Matrix](benchmark_matrix.md)",
        "- [Innovation Opportunities](innovation_opportunities.md)",
        "- [Reading Plan](reading_plan.md)",
        "- [Final Report](../reports/final_report.md)",
        "",
        "## Paper Role Distribution",
        "",
        *[f"- `{role}`: {count}" for role, count in role_counts(papers).items()],
        "",
        "## Reading Intent Distribution",
        "",
        *[f"- `{intent}`: {count}" for intent, count in intent_counts(papers).items()],
        "",
        "## Paper Notes",
        "",
    ]
    lines.extend(f"- {paper_link(paper)} [{paper['paper_id']}]" for paper in papers)
    lines.append("")
    (workspace / "knowledge" / "index.md").write_text("\n".join(lines), encoding="utf-8")


def write_field_map(workspace: Path, plan: dict[str, Any], papers: list[dict[str, Any]]) -> None:
    grouped = group_by_role(papers)
    survey_like = [
        *grouped.get("survey_or_review", []),
        *grouped.get("background_foundation", []),
        *grouped.get("position_or_perspective", []),
    ]
    terms = extract_terms(
        " ".join([plan.get("topic", ""), *[paper.get("abstract", "") for paper in survey_like]]),
        24,
    )
    lines = [
        "# 领域地图",
        "",
        "本页主要由综述、背景和观点论文支持，用于建立领域划分和核心术语，不直接替代技术路线判断。",
        "",
        "## 核心术语",
        "",
        *[f"- {term}" for term in terms],
        "",
        "## 支撑论文",
        "",
    ]
    lines.extend(paper_bullet(paper) for paper in survey_like)
    if not survey_like:
        lines.append(
            "- 当前 selected set 缺少明确的综述或背景论文，"
            "领域地图需要 Codex / Agent 补充。"
        )
    lines.extend(
        [
            "",
            "## 需要人工复核的问题",
            "",
            "- 当前领域划分是否被少数生成式综述系统过度主导。",
            "- 是否缺少传统 systematic review automation、citation analysis "
            "或 evidence synthesis 背景文献。",
            "",
        ]
    )
    (workspace / "knowledge" / "field_map.md").write_text("\n".join(lines), encoding="utf-8")


def write_technical_frontier(workspace: Path, papers: list[dict[str, Any]]) -> None:
    grouped = group_by_role(papers)
    technical = [*grouped.get("technical_method", []), *grouped.get("system_paper", [])]
    lines = [
        "# 技术前沿",
        "",
        "本页主要由技术论文和系统论文支持，用于追踪最新方法、系统架构、agent 分工和可复用模块。",
        "",
        "## 技术 / 系统论文",
        "",
    ]
    lines.extend(paper_bullet(paper) for paper in technical)
    if not technical:
        lines.append("- 当前 selected set 缺少明确技术或系统论文，不能支撑技术前沿判断。")
    lines.extend(
        [
            "",
            "## 关注问题",
            "",
            "- 系统解决的具体问题是什么。",
            "- 核心模块、输入输出和 agent 分工是什么。",
            "- 证据处理、引用校验和评估方式是否可复用到 litagent。",
            "",
        ]
    )
    (workspace / "knowledge" / "technical_frontier.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_method_matrix(workspace: Path, papers: list[dict[str, Any]]) -> None:
    grouped = group_by_role(papers)
    methods = [*grouped.get("technical_method", []), *grouped.get("system_paper", [])]
    lines = [
        "# 方法矩阵",
        "",
        "| paper_id | 系统/方法 | 任务 | 输入 | 输出 | 核心模块 | "
        "agent 分工 | 证据处理 | 评估方式 | 局限 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for paper in methods:
        abstract = paper.get("abstract") or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{paper['paper_id']}`",
                    matrix_cell(paper.get("title"), 80),
                    matrix_cell("文献调研、综述生成或科研工作流自动化"),
                    matrix_cell("用户问题、检索结果、论文全文或元数据"),
                    matrix_cell("阅读笔记、证据、草稿或系统建议"),
                    matrix_cell(abstract, 96),
                    matrix_cell("见 notes / evidence_table 中 agent_roles 字段"),
                    matrix_cell("见 evidence_table 中 citation/evidence themes"),
                    matrix_cell("见 notes 中 evaluation 字段"),
                    matrix_cell("见 notes 中 limitations 字段"),
                ]
            )
            + " |"
        )
    if not methods:
        lines.append(
            "| 待补充 | 当前没有明确技术/系统论文 | 待补充 | 待补充 | "
            "待补充 | 待补充 | 待补充 | 待补充 | 待补充 | 待补充 |"
        )
    lines.append("")
    (workspace / "knowledge" / "method_matrix.md").write_text("\n".join(lines), encoding="utf-8")


def write_benchmark_matrix(workspace: Path, papers: list[dict[str, Any]]) -> None:
    grouped = group_by_role(papers)
    benchmarks = grouped.get("benchmark_or_dataset", [])
    lines = [
        "# Benchmark / Dataset 矩阵",
        "",
        "| paper_id | benchmark / dataset | 评估对象 | 数据来源 | 指标 | "
        "baseline | 对 litagent 的适用性 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for paper in benchmarks:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{paper['paper_id']}`",
                    matrix_cell(paper.get("title"), 80),
                    matrix_cell("文献阅读、综述生成、引用质量或科研工作流能力"),
                    matrix_cell(paper.get("venue") or "待从全文确认"),
                    matrix_cell("见 notes 中 evaluation / datasets_or_benchmarks 字段"),
                    matrix_cell("见 notes 中 evaluation 字段"),
                    matrix_cell("可用于设计 litagent 的评估任务，但需人工确认指标覆盖。"),
                ]
            )
            + " |"
        )
    if not benchmarks:
        lines.append(
            "| 待补充 | 当前没有明确 benchmark/dataset 论文 | 待补充 | "
            "待补充 | 待补充 | 待补充 | 需要后续补充 |"
        )
    lines.append("")
    (workspace / "knowledge" / "benchmark_matrix.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_innovation_opportunities(workspace: Path, papers: list[dict[str, Any]]) -> None:
    grouped = group_by_role(papers)
    technical = [
        *grouped.get("technical_method", []),
        *grouped.get("system_paper", []),
        *grouped.get("benchmark_or_dataset", []),
    ]
    lines = [
        "# 创新机会",
        "",
        "本页从技术论文、系统论文和 benchmark/dataset 论文中提炼可做方向。"
        "每条机会都应回到 notes 和 evidence table 复核。",
        "",
        "## 证据支持的线索",
        "",
    ]
    for paper in technical:
        lines.append(
            f"- [{paper['paper_id']}] {paper.get('title')}: "
            "检查其方法、评估和局限，可提炼为 litagent 的功能、评估或工程改进机会。"
        )
    if not technical:
        lines.append("- 当前没有足够技术/benchmark 论文支撑创新线索。")
    lines.extend(
        [
            "",
            "## 推测性机会，需要人工复核",
            "",
            "- 将综述论文用于领域地图，将技术论文用于方法抽取和创新点追踪。",
            "- 把 evidence quality、source diversity 和 method matrix 作为研究工作台质量门禁。",
            "",
        ]
    )
    (workspace / "knowledge" / "innovation_opportunities.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_reading_plan(workspace: Path, papers: list[dict[str, Any]]) -> None:
    grouped = group_by_role(papers)
    ordered = [
        ("先读综述 / 背景，建立领域地图", grouped.get("survey_or_review", [])),
        (
            "再读系统 / 技术论文，追踪前沿方法",
            [*grouped.get("system_paper", []), *grouped.get("technical_method", [])],
        ),
        ("最后读 benchmark / dataset，建立评估体系", grouped.get("benchmark_or_dataset", [])),
        (
            "背景和观点论文只作为语境，不主导技术路线",
            [
                *grouped.get("position_or_perspective", []),
                *grouped.get("background_foundation", []),
            ],
        ),
    ]
    lines = ["# 阅读计划", ""]
    for heading, group in ordered:
        lines.extend([f"## {heading}", ""])
        if group:
            lines.extend(paper_bullet(paper) for paper in group)
        else:
            lines.append("- 当前没有对应论文。")
        lines.append("")
    (workspace / "knowledge" / "reading_plan.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def build_knowledge(workspace: Path) -> list[dict[str, Any]]:
    (workspace / "knowledge").mkdir(parents=True, exist_ok=True)
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    papers = [
        enrich_paper_role(normalize_paper(paper))
        for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    write_base_knowledge(workspace, plan, papers)
    write_topic_map(workspace, plan, papers)
    write_glossary(workspace, plan, papers)
    write_index(workspace, papers)
    write_field_map(workspace, plan, papers)
    write_technical_frontier(workspace, papers)
    write_method_matrix(workspace, papers)
    write_benchmark_matrix(workspace, papers)
    write_innovation_opportunities(workspace, papers)
    write_reading_plan(workspace, papers)
    return papers
