from __future__ import annotations

from pathlib import Path
from typing import Any

from litagent.io import write_json
from litagent.schema import current_year, extract_terms
from litagent.workspace import create_workspace

CHINESE_TERM_MAP = {
    "多智能体": ["multi-agent", "agentic"],
    "智能体": ["agent", "agentic"],
    "文献": ["literature"],
    "综述": ["review", "survey"],
    "调研": ["research", "survey"],
    "自动化": ["automation"],
    "工具": ["tools", "systems"],
    "论文": ["papers"],
    "知识": ["knowledge"],
    "开源": ["open source"],
    "检索": ["retrieval", "search"],
}

GENERIC_RESEARCH_TERMS = [
    "survey",
    "systematic review",
    "benchmark",
    "dataset",
    "framework",
    "open source",
    "tool",
]

LITERATURE_AGENT_TOPIC_MARKERS = [
    "多智能体",
    "文献综述",
    "自动化综述",
    "论文阅读",
    "智能体",
    "agentic literature",
    "literature review automation",
    "automated literature review",
    "research assistant",
    "paper reading agent",
]

LITERATURE_AGENT_FOCUSED_TERMS = [
    "LLM agents",
    "agentic research assistant",
    "automated literature review",
    "systematic review automation",
    "survey generation",
    "paper reading agent",
    "scientific discovery agent",
    "research workflow automation",
    "multi-agent research system",
    "citation-aware synthesis",
    "多智能体",
    "文献综述",
    "自动化综述",
    "科研助手",
    "论文阅读智能体",
]

LITERATURE_AGENT_EXCLUDE_TERMS = [
    "generic robotics multi-agent",
    "traffic control",
    "swarm robotics",
    "game theory only",
    "reinforcement learning only",
]


def translate_topic_terms(topic: str) -> list[str]:
    terms = extract_terms(topic, limit=8)
    translated: list[str] = []
    for chinese, english_terms in CHINESE_TERM_MAP.items():
        if chinese in topic:
            translated.extend(english_terms)
    translated.extend(term for term in terms if term.isascii())
    if not translated:
        translated.append(topic)

    unique: list[str] = []
    for term in translated:
        if term and term not in unique:
            unique.append(term)
    return unique


def is_literature_agent_topic(topic: str) -> bool:
    lowered = topic.lower()
    return any(marker.lower() in lowered for marker in LITERATURE_AGENT_TOPIC_MARKERS)


def build_seed_query(topic: str) -> str:
    if is_literature_agent_topic(topic):
        return "LLM agents automated literature review citation-aware synthesis"
    terms = translate_topic_terms(topic)
    if len(terms) == 1 and terms[0] == topic:
        return topic
    return " ".join(terms[:8])


def build_search_queries(topic: str, seed_query: str) -> dict[str, list[str]]:
    if is_literature_agent_topic(topic):
        return {
            "arxiv": [
                'all:"LLM agents" AND all:"automated literature review"',
                'all:"agentic research assistant" AND all:"citation-aware synthesis"',
                '(ti:"paper reading agent" OR abs:"multi-agent research system")',
            ],
            "semantic_scholar": [
                "LLM agents automated literature review citation-aware synthesis",
                "agentic research assistant paper reading agent survey generation",
                "multi-agent research system research workflow automation",
                "多智能体 文献综述 自动化综述 科研助手 论文阅读智能体",
            ],
            "openalex": [
                "LLM agents automated literature review citation-aware synthesis",
                "systematic review automation agentic research assistant",
                "scientific discovery agent research workflow automation",
                "多智能体 文献综述 自动化综述 科研助手 论文阅读智能体",
            ],
        }
    return {
        "arxiv": [
            f'all:"{seed_query}"',
            f'(ti:"{seed_query}" OR abs:"{seed_query}")',
        ],
        "semantic_scholar": [
            seed_query,
            f"{seed_query} survey benchmark system",
        ],
        "openalex": [
            seed_query,
            f"{seed_query} literature review",
        ],
    }


def create_research_plan(
    topic: str,
    *,
    max_results_per_source: int = 50,
    selection_count: int = 30,
    from_year: int | None = None,
    to_year: int | None = None,
) -> dict[str, Any]:
    topic = topic.strip()
    if not topic:
        msg = "Topic must not be empty."
        raise ValueError(msg)

    seed_query = build_seed_query(topic)
    focused_terms = LITERATURE_AGENT_FOCUSED_TERMS if is_literature_agent_topic(topic) else []
    include_keywords = [*focused_terms, *translate_topic_terms(topic), *GENERIC_RESEARCH_TERMS]
    include_keywords = list(dict.fromkeys(include_keywords))
    exclude_keywords = [
        "paywalled full text",
        "non-academic blog-only content",
        "untraceable claims",
    ]
    if is_literature_agent_topic(topic):
        exclude_keywords.extend(LITERATURE_AGENT_EXCLUDE_TERMS)
    exclude_keywords = list(dict.fromkeys(exclude_keywords))
    to_year = to_year or current_year()
    from_year = from_year or max(2018, to_year - 8)

    return {
        "topic": topic,
        "goal": f"Build a traceable literature workbench for: {topic}",
        "core_questions": [
            "What problem space and user needs define this research area?",
            (
                "Which survey papers, technical papers, datasets, benchmarks, "
                "and systems are representative?"
            ),
            (
                "What methods, evidence, limitations, and open research directions "
                "appear across the papers?"
            ),
        ],
        "include_keywords": include_keywords,
        "exclude_keywords": exclude_keywords,
        "search_queries": build_search_queries(topic, seed_query),
        "date_range": {
            "from": from_year,
            "to": to_year,
        },
        "max_results_per_source": max_results_per_source,
        "selection_count": selection_count,
        "ranking_policy": (
            "final_score = 0.50 relevance + 0.25 importance + 0.20 recency "
            "+ 0.05 open-pdf availability; deduplicate by DOI, arXiv ID, then title similarity."
        ),
    }


def research_plan_markdown(plan: dict[str, Any]) -> str:
    queries = plan["search_queries"]
    lines = [
        "# Research Plan",
        "",
        "## Topic",
        "",
        plan["topic"],
        "",
        "## Goal",
        "",
        plan["goal"],
        "",
        "## Core Questions",
        "",
        *[f"- {question}" for question in plan["core_questions"]],
        "",
        "## Keywords",
        "",
        "Include: " + ", ".join(plan["include_keywords"]),
        "",
        "Exclude: " + ", ".join(plan["exclude_keywords"]),
        "",
        "## English Search Queries",
        "",
    ]
    for source, source_queries in queries.items():
        lines.append(f"### {source}")
        lines.extend(f"- `{query}`" for query in source_queries)
        lines.append("")

    lines.extend(
        [
            "## 中文解释",
            "",
            "该计划会先围绕主题生成英文检索式，再从 arXiv、Semantic Scholar 和 OpenAlex "
            "检索元数据。后续步骤会按 DOI、arXiv ID 和标题相似度去重，并综合相关性、引用量、"
            "发表年份和开放 PDF 可用性排序。",
            "",
            "## Expected Subtopics",
            "",
            "- Survey and taxonomy papers",
            "- Technical methods and system papers",
            "- Benchmarks, datasets, and evaluation methodology",
            "- Open-source tools and reproducible workflows",
            "- Limitations, traceability, and future innovation opportunities",
            "",
            "## Sources",
            "",
            "- arXiv",
            "- Semantic Scholar",
            "- OpenAlex",
            "- Unpaywall for legal open-access PDF resolution",
            "",
            "## Ranking Strategy",
            "",
            plan["ranking_policy"],
            "",
            "## Manual Editing",
            "",
            (
                "You may edit this file for human readability. "
                "The pipeline reads `research_plan.json`."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_research_plan(
    workspace: Path,
    topic: str,
    *,
    max_results_per_source: int = 50,
    selection_count: int = 30,
) -> dict[str, Any]:
    create_workspace(workspace)
    plan = create_research_plan(
        topic,
        max_results_per_source=max_results_per_source,
        selection_count=selection_count,
    )
    write_json(workspace / "research_plan.json", plan)
    (workspace / "research_plan.md").write_text(research_plan_markdown(plan), encoding="utf-8")
    return plan
