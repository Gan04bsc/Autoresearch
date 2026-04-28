from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl, write_json
from litagent.paper_roles import enrich_paper_role
from litagent.schema import normalize_paper, safe_slug

DEFAULT_TOPICS = [
    "survey-generation",
    "citation-aware-synthesis",
    "paper-reading-agents",
    "systematic-review-automation",
    "multi-agent-research-system",
    "evidence-grounded-synthesis",
]

ROLE_LABELS = {
    "survey_or_review": "综述 / 领域地图",
    "technical_method": "技术方法",
    "system_paper": "系统论文",
    "benchmark_or_dataset": "Benchmark / Dataset",
    "position_or_perspective": "观点 / 路线图",
    "application_case": "应用案例",
    "background_foundation": "背景基础",
}

SECRET_FIELD_PATTERNS = ("key", "token", "secret", "password", ".env")


def wikilink(slug: str) -> str:
    return f"[[{slug}]]"


def topic_links() -> str:
    return ", ".join(wikilink(topic) for topic in DEFAULT_TOPICS)


def clean_filename(value: str) -> str:
    return safe_slug(value, max_length=72)


def escape_markdown_table(value: str | None, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text.replace("|", "\\|") or "待补充"


def strip_secret_fields(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lower = str(key).lower()
            if any(pattern in lower for pattern in SECRET_FIELD_PATTERNS):
                continue
            cleaned[str(key)] = strip_secret_fields(item)
        return cleaned
    if isinstance(value, list):
        return [strip_secret_fields(item) for item in value]
    if isinstance(value, str) and any(
        pattern in value.lower() for pattern in SECRET_FIELD_PATTERNS
    ):
        return "[redacted]"
    return value


def read_evidence_by_paper(workspace: Path) -> dict[str, list[dict[str, Any]]]:
    evidence_path = workspace / "knowledge" / "evidence_table.json"
    evidence = read_json(evidence_path, default={}) or {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for theme in evidence.get("themes") or []:
        theme_name = str(theme.get("theme") or "unknown")
        for item in theme.get("evidence_snippets_or_sections") or []:
            paper_id = str(item.get("paper_id") or "")
            if not paper_id:
                continue
            grouped[paper_id].append({**item, "theme": theme_name})
    for snippets in grouped.values():
        snippets.sort(key=lambda item: float(item.get("snippet_score") or 0.0), reverse=True)
    return dict(grouped)


def chinese_paper_summary(paper: dict[str, Any]) -> str:
    role = paper.get("paper_role") or "background_foundation"
    abstract = re.sub(r"\s+", " ", str(paper.get("abstract") or "")).strip()
    if len(abstract) > 260:
        abstract = abstract[:259].rstrip() + "…"
    if not abstract:
        abstract = "当前 workspace 中没有可用摘要，需要从 notes 或 parsed Markdown 继续补充。"
    return (
        f"该论文在当前工作台中被标记为“{ROLE_LABELS.get(role, role)}”。"
        f"阅读时应优先服务于：{', '.join(paper.get('reading_intent') or []) or '待判断'}。"
        f"摘要线索：{abstract}"
    )


def note_excerpt(workspace: Path, paper_id: str, limit: int = 500) -> str:
    path = workspace / "library" / "notes" / f"{paper_id}.md"
    if not path.exists():
        return "未找到对应阅读笔记。"
    text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8")).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text or "阅读笔记为空。"


def source_page_content(
    workspace: Path, paper: dict[str, Any], evidence_items: list[dict[str, Any]]
) -> str:
    paper_id = paper["paper_id"]
    role = paper.get("paper_role") or "background_foundation"
    intents = paper.get("reading_intent") or []
    sources = ", ".join(paper.get("source") or []) or "unknown"
    tags = [f"paper-role/{role}"]
    if paper.get("year"):
        tags.append(f"year/{paper['year']}")
    evidence_lines = []
    for item in evidence_items[:8]:
        theme_slug = clean_filename(str(item.get("theme") or "evidence"))
        score = float(item.get("snippet_score") or 0.0)
        snippet = escape_markdown_table(str(item.get("snippet") or ""), 220)
        evidence_lines.append(
            f"- {wikilink(theme_slug)}，section={item.get('section') or 'Unknown'}，"
            f"score={score:.2f}: {snippet}"
        )
    if not evidence_lines:
        evidence_lines.append("- 当前没有证据表片段，需要运行或检查 `litagent build-evidence`。")

    frontmatter = [
        "---",
        f"paper_id: {paper_id}",
        f"paper_role: {role}",
        "reading_intent:",
        *[f"  - {intent}" for intent in intents],
        f"year: {paper.get('year') or ''}",
        f"source: {sources}",
        "tags:",
        *[f"  - {tag}" for tag in tags],
        "---",
        "",
    ]
    body = [
        f"# {paper.get('title') or paper_id}",
        "",
        f"- Paper ID: `{paper_id}`",
        f"- 年份: {paper.get('year') or 'n.d.'}",
        f"- 来源: {sources}",
        f"- 论文角色: `{role}`（{ROLE_LABELS.get(role, role)}）",
        f"- 阅读意图: {', '.join(intents) or '待判断'}",
        f"- 主题链接: {topic_links()}",
        "",
        "## 摘要式中文说明",
        "",
        chinese_paper_summary(paper),
        "",
        "## 关键证据",
        "",
        *evidence_lines,
        "",
        "## 阅读笔记摘录",
        "",
        note_excerpt(workspace, paper_id),
        "",
        "## 工作台定位",
        "",
        "- 综述论文主要用于构建领域地图。",
        "- 技术和系统论文主要用于追踪前沿方法、比较系统设计和寻找创新点。",
        "- Benchmark / dataset 论文主要用于评估体系建设。",
        "- 背景和观点论文只能提供语境，不应单独主导技术路线判断。",
        "",
    ]
    return "\n".join([*frontmatter, *body])


def write_raw_paper_pages(
    workspace: Path,
    out_dir: Path,
    papers: list[dict[str, Any]],
    evidence_by_paper: dict[str, list[dict[str, Any]]],
) -> None:
    for paper in papers:
        paper_dir = out_dir / "raw" / paper["paper_id"]
        paper_dir.mkdir(parents=True, exist_ok=True)
        evidence_items = evidence_by_paper.get(paper["paper_id"], [])
        (paper_dir / "source.md").write_text(
            source_page_content(workspace, paper, evidence_items),
            encoding="utf-8",
        )
        write_json(paper_dir / "metadata.json", strip_secret_fields(paper))
        write_json(paper_dir / "evidence.json", strip_secret_fields(evidence_items))


def role_groups(papers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        grouped[paper["paper_role"]].append(paper)
    return dict(grouped)


def paper_link(paper: dict[str, Any]) -> str:
    return f"[{paper['paper_id']}](../../raw/{paper['paper_id']}/source.md)"


def write_index(out_dir: Path, papers: list[dict[str, Any]]) -> None:
    counts = Counter(paper["paper_role"] for paper in papers)
    lines = [
        "# 文献工作台入口",
        "",
        "这是由 `litagent export-wiki` 生成的 AutoWiki-compatible 知识库。"
        "它用于长期阅读、管理和复用，不替代 `litagent` 的检索、筛选、"
        "下载、解析和证据抽取。",
        "",
        "## 关键页面",
        "",
        "- [[field-map]]",
        "- [[technical-frontier]]",
        "- [[method-matrix]]",
        "- [[benchmark-matrix]]",
        "- [[innovation-opportunities]]",
        "- [[reading-plan]]",
        "",
        "## 主题入口",
        "",
        f"- {topic_links()}",
        "",
        "## 论文角色分布",
        "",
        *[f"- `{role}`: {count}" for role, count in sorted(counts.items())],
        "",
        "## 推荐使用方式",
        "",
        "- 先读 [[field-map]] 建立领域地图。",
        "- 再读 [[technical-frontier]] 和 [[method-matrix]] 追踪技术路线。",
        "- 最后读 [[benchmark-matrix]] 和 [[innovation-opportunities]] 规划评估与创新点。",
        "",
    ]
    (out_dir / "kb" / "index.md").write_text("\n".join(lines), encoding="utf-8")


def write_field_map(out_dir: Path, grouped: dict[str, list[dict[str, Any]]]) -> None:
    papers = [
        *grouped.get("survey_or_review", []),
        *grouped.get("background_foundation", []),
        *grouped.get("position_or_perspective", []),
    ]
    lines = [
        "# 领域地图",
        "",
        "本页主要使用综述、背景和观点论文构建领域划分、核心术语和代表性方向。",
        "",
        "## 支撑论文",
        "",
    ]
    lines.extend(f"- {paper_link(paper)} {paper.get('title')}" for paper in papers)
    if not papers:
        lines.append("- 当前没有明确的综述或背景论文。")
    lines.extend(
        [
            "",
            "## 主题节点",
            "",
            f"- {topic_links()}",
            "",
        ]
    )
    (out_dir / "kb" / "field-map.md").write_text("\n".join(lines), encoding="utf-8")


def write_technical_frontier(out_dir: Path, grouped: dict[str, list[dict[str, Any]]]) -> None:
    papers = [*grouped.get("system_paper", []), *grouped.get("technical_method", [])]
    lines = [
        "# 技术前沿",
        "",
        "本页使用技术论文和系统论文追踪前沿方法、系统架构、agent 设计和可复用模块。",
        "",
        "## 系统与方法",
        "",
    ]
    lines.extend(f"- {paper_link(paper)} {paper.get('title')}" for paper in papers)
    if not papers:
        lines.append("- 当前没有明确技术/系统论文。")
    lines.append("")
    (out_dir / "kb" / "technical-frontier.md").write_text("\n".join(lines), encoding="utf-8")


def write_method_matrix(out_dir: Path, grouped: dict[str, list[dict[str, Any]]]) -> None:
    papers = [*grouped.get("system_paper", []), *grouped.get("technical_method", [])]
    lines = [
        "# 方法矩阵",
        "",
        "| paper_id | 系统名 / 方法名 | 任务 | 输入 | 输出 | 核心模块 | "
        "agent 分工 | 证据处理方式 | 评估方式 | 局限 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for paper in papers:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{paper['paper_id']}`",
                    escape_markdown_table(paper.get("title"), 80),
                    "文献调研 / 综述生成 / 科研工作流",
                    "用户问题、论文集合、全文或元数据",
                    "证据、阅读笔记、草稿或系统决策",
                    escape_markdown_table(paper.get("abstract"), 96),
                    "见 source.md 和 evidence.json",
                    "[[citation-aware-synthesis]]",
                    "见 notes / evidence",
                    "见 notes / evidence",
                ]
            )
            + " |"
        )
    if not papers:
        lines.append(
            "| 待补充 | 当前没有明确技术/系统论文 | 待补充 | 待补充 | "
            "待补充 | 待补充 | 待补充 | 待补充 | 待补充 | 待补充 |"
        )
    lines.append("")
    (out_dir / "kb" / "matrices" / "method-matrix.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_benchmark_matrix(out_dir: Path, grouped: dict[str, list[dict[str, Any]]]) -> None:
    papers = grouped.get("benchmark_or_dataset", [])
    lines = [
        "# Benchmark 矩阵",
        "",
        "| paper_id | benchmark 名称 | 评估对象 | 数据来源 | 指标 | baseline | 适用性 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for paper in papers:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{paper['paper_id']}`",
                    escape_markdown_table(paper.get("title"), 80),
                    "文献阅读、综述生成、引用质量或科研工作流能力",
                    escape_markdown_table(paper.get("venue") or "待补充"),
                    "见 source.md / evidence.json",
                    "见 source.md / evidence.json",
                    "可用于设计 litagent 评估，但需人工确认。",
                ]
            )
            + " |"
        )
    if not papers:
        lines.append(
            "| 待补充 | 当前没有明确 benchmark/dataset 论文 | 待补充 | "
            "待补充 | 待补充 | 待补充 | 需要后续补充 |"
        )
    lines.append("")
    (out_dir / "kb" / "matrices" / "benchmark-matrix.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_innovation_opportunities(
    out_dir: Path,
    grouped: dict[str, list[dict[str, Any]]],
    evidence_by_paper: dict[str, list[dict[str, Any]]],
) -> None:
    papers = [
        *grouped.get("system_paper", []),
        *grouped.get("technical_method", []),
        *grouped.get("benchmark_or_dataset", []),
    ]
    lines = [
        "# 创新机会",
        "",
        "本页从技术论文、系统论文和 benchmark/dataset 论文中提炼线索。证据支持与推测必须分开看。",
        "",
        "## 证据支持的机会",
        "",
    ]
    for paper in papers:
        snippets = evidence_by_paper.get(paper["paper_id"], [])
        top = snippets[0] if snippets else {}
        score = float(top.get("snippet_score") or 0.0)
        support = f"最高证据 score={score:.2f}" if snippets else "当前缺少 evidence_table 支撑"
        lines.append(
            f"- {paper_link(paper)}：围绕 `{paper.get('paper_role')}` "
            f"检查可复用模块、评估缺口和工程风险；{support}。"
        )
    if not papers:
        lines.append("- 当前缺少技术/系统/benchmark 论文，无法形成可靠创新线索。")
    lines.extend(
        [
            "",
            "## 推测性机会",
            "",
            "- 让综述论文服务于领域地图，技术论文服务于方法追踪，benchmark 论文服务于评估体系。",
            "- 将 [[evidence-grounded-synthesis]] 与 [[citation-aware-synthesis]] "
            "作为 litagent 后续质量门禁。",
            "",
        ]
    )
    (out_dir / "kb" / "innovation-opportunities.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_reading_plan(out_dir: Path, grouped: dict[str, list[dict[str, Any]]]) -> None:
    sections = [
        ("先读综述建立地图", grouped.get("survey_or_review", [])),
        (
            "再读系统论文追踪前沿",
            [*grouped.get("system_paper", []), *grouped.get("technical_method", [])],
        ),
        ("最后读 benchmark / paper-reading agent 论文", grouped.get("benchmark_or_dataset", [])),
        (
            "背景和观点论文仅作语境",
            [
                *grouped.get("background_foundation", []),
                *grouped.get("position_or_perspective", []),
            ],
        ),
    ]
    lines = ["# 阅读计划", ""]
    for heading, papers in sections:
        lines.extend([f"## {heading}", ""])
        if papers:
            lines.extend(f"- {paper_link(paper)} {paper.get('title')}" for paper in papers)
        else:
            lines.append("- 当前没有对应论文。")
        lines.append("")
    (out_dir / "kb" / "reading-plan.md").write_text("\n".join(lines), encoding="utf-8")


def write_topic_system_benchmark_pages(
    out_dir: Path,
    grouped: dict[str, list[dict[str, Any]]],
) -> None:
    for topic in DEFAULT_TOPICS:
        (out_dir / "kb" / "topics" / f"{topic}.md").write_text(
            "\n".join(
                [
                    f"# {topic}",
                    "",
                    "该主题页由 AutoWiki-compatible export 初始化，"
                    "用于后续人工或 AutoWiki-skill 继续维护。",
                    "",
                    "## 相关页面",
                    "",
                    "- [[field-map]]",
                    "- [[technical-frontier]]",
                    "- [[method-matrix]]",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    for paper in [*grouped.get("system_paper", []), *grouped.get("technical_method", [])]:
        slug = clean_filename(paper.get("title") or paper["paper_id"])
        (out_dir / "kb" / "systems" / f"{slug}.md").write_text(
            (
                f"# {paper.get('title')}\n\n"
                f"- 来源论文: {paper_link(paper)}\n"
                f"- 角色: `{paper['paper_role']}`\n"
            ),
            encoding="utf-8",
        )
    for paper in grouped.get("benchmark_or_dataset", []):
        slug = clean_filename(paper.get("title") or paper["paper_id"])
        (out_dir / "kb" / "benchmarks" / f"{slug}.md").write_text(
            (
                f"# {paper.get('title')}\n\n"
                f"- 来源论文: {paper_link(paper)}\n"
                f"- 角色: `{paper['paper_role']}`\n"
            ),
            encoding="utf-8",
        )


def write_kb_pages(
    out_dir: Path,
    papers: list[dict[str, Any]],
    evidence_by_paper: dict[str, list[dict[str, Any]]],
) -> None:
    for relative in ("kb/topics", "kb/systems", "kb/benchmarks", "kb/matrices"):
        (out_dir / relative).mkdir(parents=True, exist_ok=True)
    grouped = role_groups(papers)
    write_index(out_dir, papers)
    write_field_map(out_dir, grouped)
    write_technical_frontier(out_dir, grouped)
    write_method_matrix(out_dir, grouped)
    write_benchmark_matrix(out_dir, grouped)
    write_innovation_opportunities(out_dir, grouped, evidence_by_paper)
    write_reading_plan(out_dir, grouped)
    write_topic_system_benchmark_pages(out_dir, grouped)


def export_wiki(
    workspace: Path, out_dir: Path, *, export_format: str = "autowiki"
) -> dict[str, Any]:
    if export_format != "autowiki":
        msg = f"Unsupported wiki export format: {export_format}"
        raise ValueError(msg)
    out_dir.mkdir(parents=True, exist_ok=True)
    papers = [
        enrich_paper_role(normalize_paper(paper))
        for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    evidence_by_paper = read_evidence_by_paper(workspace)
    write_raw_paper_pages(workspace, out_dir, papers, evidence_by_paper)
    write_kb_pages(out_dir, papers, evidence_by_paper)
    role_distribution = dict(sorted(Counter(paper["paper_role"] for paper in papers).items()))
    result = {
        "ok": True,
        "workspace": str(workspace),
        "out_dir": str(out_dir),
        "format": export_format,
        "paper_count": len(papers),
        "role_distribution": role_distribution,
        "generated_files": [
            "kb/index.md",
            "kb/field-map.md",
            "kb/technical-frontier.md",
            "kb/matrices/method-matrix.md",
            "kb/matrices/benchmark-matrix.md",
            "kb/innovation-opportunities.md",
            "kb/reading-plan.md",
        ],
    }
    write_json(out_dir / "export_manifest.json", result)
    return result
