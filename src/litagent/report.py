from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from litagent.evidence import THEME_LABELS_ZH
from litagent.io import read_json, read_jsonl
from litagent.schema import format_short_citation, normalize_paper

MIN_REPORT_SNIPPET_SCORE = 0.45


def selected_papers_table(papers: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Paper ID | 论文标题 | 年份 | 类型 | 引用数 | 来源 |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for paper in papers:
        title = markdown_cell(paper.get("title"))
        sources = ", ".join(paper.get("source") or [])
        lines.append(
            f"| {paper['paper_id']} | {title} | {paper.get('year') or ''} | "
            f"{paper.get('paper_type') or 'unknown'} | {paper.get('citation_count') or 0} | "
            f"{sources} |"
        )
    return lines


def grouped_by_type(papers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        grouped[paper.get("paper_type") or "unknown"].append(paper)
    return dict(grouped)


def has_terms(paper: dict[str, Any], terms: list[str]) -> bool:
    text = f"{paper.get('title') or ''} {paper.get('abstract') or ''}".lower()
    return any(term in text for term in terms)


def paper_ref(paper: dict[str, Any]) -> str:
    return f"[{paper['paper_id']}]"


def refs(papers: list[dict[str, Any]], *, limit: int | None = None) -> str:
    chosen = papers[:limit] if limit else papers
    return ", ".join(paper_ref(paper) for paper in chosen) or "[no-papers]"


def first_sentence(text: str | None, *, fallback: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return fallback
    for marker in (". ", "? ", "! "):
        if marker in clean:
            return clean.split(marker, 1)[0].strip() + marker.strip()
    return clean[:260].strip()


def method_role(paper: dict[str, Any]) -> str:
    if has_terms(paper, ["systematic review automation", "screening", "data extraction"]):
        return "系统综述工作流自动化"
    if has_terms(paper, ["paper-reading", "paper reading", "read scientific papers"]):
        return "论文阅读智能体"
    if has_terms(paper, ["citation graph", "citation-aware", "citation quality"]):
        return "引文或证据感知综合"
    if has_terms(paper, ["survey generation", "survey paper generation"]):
        return "科学综述生成"
    if has_terms(paper, ["literature synthesis", "related work drafting"]):
        return "文献综合与相关工作写作"
    if has_terms(paper, ["comparative literature summary", "comparative summary"]):
        return "比较式文献总结"
    if has_terms(paper, ["literature review generation", "review generation"]):
        return "文献综述生成"
    return paper.get("paper_type") or "研究系统"


def why_it_matters(paper: dict[str, Any]) -> str:
    if has_terms(paper, ["multi-agent", "multiple agents", "specialized agents"]):
        return "该论文直接涉及多智能体分工，对拆解综述流程有参考价值。"
    if has_terms(paper, ["citation graph", "citation quality"]):
        return "该论文把综合写作和引文或证据结构连接起来。"
    if has_terms(paper, ["screening", "data extraction"]):
        return "该论文覆盖系统综述中的筛选和信息抽取环节。"
    if has_terms(paper, ["paper-reading", "paper reading"]):
        return "该论文强化了论文阅读和证据抽取子任务。"
    return "该论文与目标主题相关，具体贡献需要结合证据表和 parsed Markdown 复核。"


def core_question_line(question: str) -> str:
    lower = question.lower()
    if "which" in lower and "multi-agent" in lower:
        return "有哪些多智能体或 LLM-agent 系统在自动化文献综述、综述生成或系统综述工作流？"
    if "divide work" in lower or "planning, retrieval" in lower:
        return "这些系统如何拆分规划、检索、论文阅读、引文处理、写作、审阅和修订职责？"
    if "evidence-grounding" in lower or "citation-aware" in lower:
        return "哪些证据 grounding、引文感知综合、评估基准和工作流模式值得 litagent 借鉴？"
    return question if not question.isascii() else f"需要人工翻译和复核的研究问题：{question}"


def markdown_cell(value: str | None) -> str:
    return (value or "").replace("|", "\\|")


def grouped_by_method(papers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in papers:
        grouped[method_role(paper)].append(paper)
    return dict(grouped)


def failed_download_lines(papers: list[dict[str, Any]]) -> list[str]:
    failures = [
        paper
        for paper in papers
        if paper.get("download_status") in {"failed", "skipped"} and not paper.get("local_pdf_path")
    ]
    if not failures:
        return ["- selected papers 中没有失败或跳过的 PDF 下载。"]
    return [
        (
            f"- {paper['paper_id']}: {paper.get('download_status')} - "
            f"{paper.get('download_error') or 'N/A'}"
        )
        for paper in failures
    ]


def load_evidence_rows(workspace: Path) -> list[dict[str, Any]]:
    evidence = read_json(workspace / "knowledge" / "evidence_table.json", default={}) or {}
    rows = evidence.get("themes") or []
    return rows if isinstance(rows, list) else []


def row_refs(row: dict[str, Any]) -> str:
    return ", ".join(f"[{paper_id}]" for paper_id in row.get("supporting_papers", []))


def theme_label(row_or_theme: dict[str, Any] | str) -> str:
    if isinstance(row_or_theme, dict):
        theme = str(row_or_theme.get("theme") or "")
        label = str(row_or_theme.get("theme_label") or THEME_LABELS_ZH.get(theme, theme))
    else:
        theme = row_or_theme
        label = THEME_LABELS_ZH.get(theme, theme)
    return f"{label}（{theme}）" if theme and label != theme else label


def evidence_by_theme(rows: list[dict[str, Any]], theme: str) -> dict[str, Any]:
    for row in rows:
        if row.get("theme") == theme:
            return row
    return {
        "theme": theme,
        "theme_label": THEME_LABELS_ZH.get(theme, theme),
        "claim": "证据表缺少该主题。",
        "supporting_papers": [],
        "evidence_snippets_or_sections": [],
        "gaps_or_uncertainties": ["证据表缺少该主题。"],
    }


def high_quality_snippets(
    row: dict[str, Any],
    *,
    limit: int = 3,
    min_score: float = MIN_REPORT_SNIPPET_SCORE,
) -> list[dict[str, Any]]:
    snippets = row.get("evidence_snippets_or_sections") or []
    usable = [
        item
        for item in snippets
        if float(item.get("snippet_score") or 0.0) >= min_score
        and "noise_section" not in set(item.get("quality_flags") or [])
        and "code_or_prompt" not in set(item.get("quality_flags") or [])
        and "table_like" not in set(item.get("quality_flags") or [])
    ]
    usable.sort(key=lambda item: float(item.get("snippet_score") or 0.0), reverse=True)
    return usable[:limit]


def representative_snippet(row: dict[str, Any]) -> str:
    snippets = high_quality_snippets(row, limit=1)
    if not snippets:
        return "证据不足：该主题没有可直接写入正文的高质量证据片段。"
    item = snippets[0]
    return (
        f"{item.get('snippet')} [{item.get('paper_id')}] "
        f"(section={item.get('section')}, score={float(item.get('snippet_score') or 0.0):.2f})"
    )


def supported_claim(row: dict[str, Any]) -> str:
    refs_text = row_refs(row)
    if not refs_text or not high_quality_snippets(row, limit=1):
        return f"- 证据不足：{row.get('claim')} {refs_text or '[evidence gap]'}"
    return f"- {row.get('claim')} 支撑论文：{refs_text}"


def paper_evidence_summary(paper: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    themes = [
        theme_label(row)
        for row in rows
        if paper["paper_id"] in set(row.get("supporting_papers") or [])
    ]
    return ", ".join(themes[:4]) or "证据表中暂无明确主题支撑"


def evidence_theme_lines(rows: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    if not rows:
        return ["- 证据表缺失；请先运行 `litagent build-evidence WORKSPACE --json`。"]
    for row in rows:
        refs_text = row_refs(row) or "[evidence gap]"
        lines.extend(
            [
                f"### {theme_label(row)}",
                "",
                f"- 综合判断：{row.get('claim')} 支撑论文：{refs_text}",
                f"- 置信度：{row.get('confidence')}",
                f"- 代表性高质量证据：{representative_snippet(row)}",
                f"- 证据缺口：{'; '.join(row.get('gaps_or_uncertainties') or []) or '无'}",
                "",
            ]
        )
        snippets = high_quality_snippets(row, limit=3)
        if snippets:
            lines.append("| Paper ID | Section | Score | Evidence |")
            lines.append("| --- | --- | ---: | --- |")
            for item in snippets:
                lines.append(
                    f"| {item.get('paper_id')} | {item.get('section')} | "
                    f"{float(item.get('snippet_score') or 0.0):.2f} | "
                    f"{markdown_cell(str(item.get('snippet') or ''))} |"
                )
            lines.append("")
        else:
            lines.append("- 当前主题只有低分或噪声风险证据，正文综合应谨慎使用。")
            lines.append("")
    return lines


def generate_final_report(workspace: Path) -> str:
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    papers = [
        normalize_paper(paper) for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    grouped = grouped_by_type(papers)
    method_groups = grouped_by_method(papers)
    evidence_rows = load_evidence_rows(workspace)
    search_queries = plan.get("search_queries") or {}

    architecture = evidence_by_theme(evidence_rows, "multi-agent architecture")
    generation = evidence_by_theme(evidence_rows, "survey/literature review generation")
    systematic = evidence_by_theme(evidence_rows, "systematic review workflow")
    paper_reading = evidence_by_theme(evidence_rows, "paper reading agents")
    citation = evidence_by_theme(evidence_rows, "citation-aware synthesis")
    evaluation = evidence_by_theme(evidence_rows, "evaluation and benchmarks")
    limitations = evidence_by_theme(evidence_rows, "limitations and open problems")
    design = evidence_by_theme(evidence_rows, "design implications for litagent")

    lines = [
        "# 最终研究报告草稿",
        "",
        (
            "本报告由 `litagent report` 基于机器生成笔记和证据表自动生成，定位是中文报告草稿，"
            "不是最终学术判断。Codex / Agent 仍需要复核 selected papers、证据质量和综合结论。"
        ),
        "",
        "## 执行摘要",
        "",
        (
            f"本报告围绕 `{plan.get('topic', '目标主题')}`，使用 {len(papers)} 篇 selected papers "
            f"和证据表进行小规模真实综述草稿生成。代表性论文包括 {refs(papers, limit=5)}。"
        ),
        supported_claim(architecture),
        supported_claim(generation),
        supported_claim(citation),
        "",
        "## 研究背景",
        "",
        supported_claim(generation),
        supported_claim(systematic),
        supported_claim(paper_reading),
        "",
        "## 核心问题",
        "",
        *[f"- {core_question_line(str(question))}" for question in plan.get("core_questions", [])],
        supported_claim(citation),
        supported_claim(evaluation),
        "",
        "## 方法分类",
        "",
    ]
    for method, group in sorted(method_groups.items()):
        lines.append(f"- {method}: {len(group)} 篇论文，包括 {refs(group)}。")

    lines.extend(
        [
            "",
            "## 论文代表性列表",
            "",
            "| Paper ID | 论文标题 | 年份 | 类型 | 证据主题 |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for paper in papers:
        lines.append(
            f"| {paper['paper_id']} | {markdown_cell(paper.get('title'))} | "
            f"{paper.get('year') or ''} | {paper.get('paper_type') or 'unknown'} | "
            f"{markdown_cell(paper_evidence_summary(paper, evidence_rows))} |"
        )

    lines.extend(
        [
            "",
            "## 系统对比",
            "",
            "| Paper ID | 方法角色 | 证据支撑解释 |",
            "| --- | --- | --- |",
        ]
    )
    for paper in papers:
        lines.append(
            f"| {paper['paper_id']} | {method_role(paper)} | "
            f"{markdown_cell(why_it_matters(paper))} {paper_ref(paper)} |"
        )

    lines.extend(
        [
            "",
            "## 论文对照表",
            "",
            *selected_papers_table(papers),
            "",
            "## 证据支撑的主题综合",
            "",
            *evidence_theme_lines(evidence_rows),
            "## 跨论文流程模式",
            "",
            supported_claim(architecture),
            supported_claim(systematic),
            supported_claim(citation),
            "",
            "## 多智能体架构的作用",
            "",
            supported_claim(architecture),
            f"- 代表性证据：{representative_snippet(architecture)}",
            "",
            "## 引文图谱与证据处理模式",
            "",
            supported_claim(citation),
            f"- 代表性证据：{representative_snippet(citation)}",
            "",
            "## 评估方法",
            "",
            supported_claim(evaluation),
            f"- 代表性证据：{representative_snippet(evaluation)}",
            "",
            "## 综述类论文综合",
            "",
        ]
    )
    survey = grouped.get("survey", [])
    if survey:
        lines.extend(
            f"- {paper.get('title')} 为该方向提供综述性背景。{paper_ref(paper)}"
            for paper in survey
        )
    else:
        lines.append(
            "- 当前 selected papers 中没有传统 survey 类型论文；综述层综合主要来自系统、基准和"
            f"方法论文。{row_refs(generation) or refs(papers, limit=5)}"
        )

    technical_like = [
        paper
        for paper in papers
        if paper.get("paper_type") in {"technical", "system", "benchmark", "dataset"}
    ]
    lines.extend(["", "## 技术论文综合", ""])
    if technical_like:
        lines.extend(
            f"- {paper.get('title')} 关联到 `{method_role(paper)}`，证据主题包括 "
            f"{paper_evidence_summary(paper, evidence_rows)}。{paper_ref(paper)}"
            for paper in technical_like
        )
    else:
        lines.append(
            "- 当前 selected papers 中没有明确的 technical/system/benchmark/dataset 类型论文。"
        )

    lines.extend(
        [
            "",
            "## 局限和研究空白",
            "",
            supported_claim(limitations),
            (
                "- 当前证据仍受 selected papers 规模、来源多样性和 PDF 解析质量限制；"
                f"这些结论应作为小规模真实综述草稿使用。{refs(papers, limit=5)}"
            ),
            "",
            "## 明确剩余证据缺口",
            "",
        ]
    )
    for row in evidence_rows:
        for gap in row.get("gaps_or_uncertainties") or []:
            lines.append(f"- {theme_label(row)}: {gap}")
    if not evidence_rows:
        lines.append("- 证据表缺失。")

    lines.extend(
        [
            "",
            "## 对 litagent 的设计启发",
            "",
            supported_claim(design),
            "- 保持 `read -> build-knowledge -> build-evidence -> report -> audit -> "
            "inspect-workspace` "
            f"作为真实综述的首选路径。{row_refs(design) or refs(papers, limit=5)}",
            "- 报告正文应优先使用高 `snippet_score` 证据，低分证据只作为人工复核线索。",
            "",
            "## 下一步路线图",
            "",
            "1. 增强章节感知证据抽取，继续降低 references、appendix、prompt、code、"
            "table 和 layout artifacts 噪声。",
            "2. 完善证据质量评分，让每条 evidence snippet 都有 section、snippet_score、"
            "quality_flags 和质量说明。",
            "3. 改进中文研究级报告草稿，但继续保留 Codex / Agent 二次判断和中文综合职责。",
            "4. 配置 `SEMANTIC_SCHOLAR_API_KEY` 后，再规划 `./demo-real-v4` 的来源多样性验证。",
            "5. 只有当 `review-selection`、解析质量、证据表、audit 和 "
            "inspect-workspace 都保持干净时，再考虑扩大规模。",
            "",
            "## 推荐阅读顺序",
            "",
        ]
    )
    lines.extend(
        f"{index}. {paper.get('title')} - {format_short_citation(paper)} [{paper['paper_id']}]"
        for index, paper in enumerate(papers, start=1)
    )

    lines.extend(["", "## 附录：检索式", ""])
    for source, queries in search_queries.items():
        lines.append(f"### {source}")
        lines.extend(f"- `{query}`" for query in queries)
        lines.append("")

    lines.extend(
        [
            "## 附录：证据表",
            "",
            "- [证据表](../knowledge/evidence_table.md)",
            "- [证据表 JSON](../knowledge/evidence_table.json)",
            "",
            "## 附录：数据源",
            "",
            "- arXiv",
            "- Semantic Scholar",
            "- OpenAlex",
            "- Unpaywall 用于合法开放获取 PDF 查询",
            "",
            "## 附录：下载失败列表",
            "",
            *failed_download_lines(papers),
            "",
            "## 参考文献",
            "",
        ]
    )
    lines.extend(
        f"- [{paper['paper_id']}] {format_short_citation(paper)}. {paper.get('title')}. "
        f"{paper.get('url') or paper.get('doi') or paper.get('arxiv_id') or 'No URL'}"
        for paper in papers
    )
    lines.append("")

    report = "\n".join(lines)
    path = workspace / "reports" / "final_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return report
