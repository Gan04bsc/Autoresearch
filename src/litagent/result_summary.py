from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from litagent.inspect import inspect_workspace
from litagent.io import read_json, read_jsonl

KNOWLEDGE_PAGES = [
    ("field_map", "领域地图", Path("knowledge") / "field_map.md"),
    ("technical_frontier", "技术前沿", Path("knowledge") / "technical_frontier.md"),
    ("method_matrix", "方法矩阵", Path("knowledge") / "method_matrix.md"),
    ("benchmark_matrix", "Benchmark / Dataset", Path("knowledge") / "benchmark_matrix.md"),
    ("innovation_opportunities", "创新机会", Path("knowledge") / "innovation_opportunities.md"),
    ("reading_plan", "阅读计划", Path("knowledge") / "reading_plan.md"),
]

ROLE_LABELS = {
    "survey_or_review": "综述/领域地图",
    "technical_method": "技术方法",
    "system_paper": "系统论文",
    "benchmark_or_dataset": "benchmark/dataset",
    "position_or_perspective": "观点/背景",
    "application_case": "应用案例",
    "background_foundation": "背景基础",
}

ROLE_ORDER = [
    "survey_or_review",
    "technical_method",
    "system_paper",
    "benchmark_or_dataset",
    "position_or_perspective",
    "application_case",
    "background_foundation",
]

THEME_RULES = [
    (
        "可靠性、幻觉与安全",
        (
            "hallucination",
            "trust",
            "safety",
            "robust",
            "jailbreak",
            "misinformation",
            "typographic",
            "alignment",
        ),
        "把幻觉、鲁棒性、安全和可信度作为默认质量门禁，而不是只看任务准确率。",
    ),
    (
        "多模态推理与问答",
        (
            "reasoning",
            "question answering",
            "vqa",
            "compositional",
            "instruction following",
            "chart",
            "cognitive",
        ),
        "重点区分感知识别、关系理解、组合推理和长链解释，避免把 VQA 分数当作通用推理能力。",
    ),
    (
        "效率、压缩与部署",
        (
            "efficient",
            "pruning",
            "token",
            "cache",
            "memory",
            "decoding",
            "optimization",
            "attention",
            "small",
        ),
        "关注剪枝、token 重加权、KV cache/attention 优化等路径，判断能否支撑低成本推理。",
    ),
    (
        "评测基准与数据集",
        (
            "benchmark",
            "dataset",
            "evaluation",
            "eval",
            "mme",
            "seed-bench",
            "ocrbench",
            "lvlm-ehub",
            "autotrust",
        ),
        "把 benchmark 按感知、推理、OCR/文档、幻觉、安全和垂直应用拆开，形成评估矩阵。",
    ),
    (
        "视频、时序与长上下文理解",
        ("video", "movie", "temporal", "long-context", "long context"),
        "视频和长上下文方向需要单独看帧采样、时序对齐、记忆机制和推理成本。",
    ),
    (
        "OCR、图表与科学文档理解",
        ("ocr", "chart", "document", "scientific", "arxiv", "table"),
        "OCR、图表和科学文档更接近知识工作流入口，适合作为工具型 agent 的评测重点。",
    ),
    (
        "视觉结构、关系与定位",
        (
            "segmentation",
            "object detection",
            "scene graph",
            "relation",
            "relations",
            "visual relations",
            "saliency",
        ),
        "视觉结构理解决定模型能否从“看见对象”走向“理解关系、位置和可操作证据”。",
    ),
    (
        "垂直领域应用",
        (
            "remote sensing",
            "radiology",
            "autonomous driving",
            "hydrological",
            "animal",
            "emotion",
            "recommendation",
            "medical",
        ),
        "垂直应用要区分通用 VLM 能力迁移与领域数据/评估协议带来的真实增益。",
    ),
    (
        "多语言、个性化与持续学习",
        (
            "multilingual",
            "language confusion",
            "personalized",
            "continual learning",
            "knowledge evolves",
        ),
        "持续学习、个性化和多语言能力是从 demo 走向长期助手的关键风险点。",
    ),
]


def compact_text(value: str, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def strip_markdown(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^[-*]\s+", "", text)
    text = re.sub(r"^#+\s+", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    return compact_text(text)


def useful_markdown_lines(path: Path, *, limit: int = 4) -> list[str]:
    if not path.exists():
        return []
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("|") and set(line.replace("|", "").strip()) <= {"-", ":"}:
            continue
        if line.startswith("|"):
            continue
        if line.startswith("- ") or line.startswith("* "):
            item = strip_markdown(line)
            if len(item) >= 12:
                lines.append(item)
        elif len(line) >= 18:
            lines.append(strip_markdown(line))
        if len(lines) >= limit:
            break
    return [line for line in lines if line]


def markdown_section_lines(
    path: Path,
    headings: set[str],
    *,
    limit: int = 4,
) -> list[str]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    lines: list[str] = []
    for raw_line in content:
        stripped = raw_line.strip()
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            heading = heading_match.group(2).strip().lower()
            if any(target.lower() in heading for target in headings):
                in_section = True
                continue
            if in_section:
                break
        if not in_section or not stripped:
            continue
        if stripped.startswith("|"):
            continue
        if stripped.startswith("- ") or stripped.startswith("* ") or len(stripped) >= 18:
            lines.append(strip_markdown(stripped))
        if len(lines) >= limit:
            break
    return [line for line in lines if line]


def count_evidence_spans(evidence: dict[str, Any]) -> int:
    total = 0
    for theme in evidence.get("themes") or []:
        total += len(theme.get("evidence_snippets_or_sections") or [])
    return total


def workspace_counts(workspace: Path) -> dict[str, int]:
    evidence = read_json(workspace / "knowledge" / "evidence_table.json", default={}) or {}
    return {
        "raw_results": len(read_jsonl(workspace / "data" / "raw_results.jsonl")),
        "selected_papers": len(read_jsonl(workspace / "data" / "selected_papers.jsonl")),
        "parsed_markdown": len(list((workspace / "library" / "markdown").glob("*.md")))
        if (workspace / "library" / "markdown").exists()
        else 0,
        "notes": len(list((workspace / "library" / "notes").glob("*.md")))
        if (workspace / "library" / "notes").exists()
        else 0,
        "evidence_spans": count_evidence_spans(evidence),
    }


def selected_papers(workspace: Path) -> list[dict[str, Any]]:
    return read_jsonl(workspace / "data" / "selected_papers.jsonl")


def paper_score(paper: dict[str, Any]) -> tuple[float, int, int]:
    return (
        float(paper.get("final_score") or 0),
        int(paper.get("citation_count") or 0),
        int(paper.get("year") or 0),
    )


def title_with_year(paper: dict[str, Any], *, limit: int = 72) -> str:
    title = compact_text(str(paper.get("title") or "Untitled"), limit=limit)
    year = paper.get("year")
    return f"《{title}》({year})" if year else f"《{title}》"


def format_examples(papers: list[dict[str, Any]], *, limit: int = 2) -> str:
    ranked = sorted(papers, key=paper_score, reverse=True)[:limit]
    return "、".join(title_with_year(paper) for paper in ranked)


def role_counts_line(papers: list[dict[str, Any]], counts: dict[str, int]) -> str:
    role_counts = Counter(str(paper.get("paper_role") or "unknown") for paper in papers)
    parts = [
        f"{ROLE_LABELS.get(role, role)} {count}"
        for role, count in role_counts.most_common()
        if count
    ][:5]
    return (
        f"文献结构：选中 {counts.get('selected_papers', len(papers))} 篇，"
        f"已解析 {counts.get('parsed_markdown', 0)} 篇，"
        f"证据片段 {counts.get('evidence_spans', 0)} 条；"
        f"类型分布为{'、'.join(parts) if parts else '未知'}。"
    )


def paper_text(paper: dict[str, Any]) -> str:
    return f"{paper.get('title') or ''} {paper.get('abstract') or ''}".lower()


def paper_title_text(paper: dict[str, Any]) -> str:
    return str(paper.get("title") or "").lower()


def paper_matches_theme(
    paper: dict[str, Any],
    label: str,
    keywords: tuple[str, ...],
) -> bool:
    title = paper_title_text(paper)
    role = str(paper.get("paper_role") or "")
    if label == "评测基准与数据集":
        return role == "benchmark_or_dataset" or any(keyword in title for keyword in keywords)
    return any(keyword in paper_text(paper) for keyword in keywords)


def theme_score(paper: dict[str, Any], keywords: tuple[str, ...]) -> tuple[int, float, int, int]:
    title = paper_title_text(paper)
    title_hit = int(any(keyword in title for keyword in keywords))
    final_score, citation_count, year = paper_score(paper)
    return title_hit, final_score, citation_count, year


def cluster_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for label, keywords, implication in THEME_RULES:
        matched = [
            paper
            for paper in papers
            if paper_matches_theme(paper, label, keywords)
        ]
        if matched:
            clusters.append(
                {
                    "label": label,
                    "papers": sorted(
                        matched,
                        key=lambda paper: theme_score(paper, keywords),
                        reverse=True,
                    ),
                    "implication": implication,
                }
            )
    return sorted(
        clusters,
        key=lambda item: (len(item["papers"]), paper_score(item["papers"][0])),
        reverse=True,
    )


def looks_like_mllm_topic(topic: str, papers: list[dict[str, Any]]) -> bool:
    haystack = " ".join(
        [topic, *[str(paper.get("title") or "") for paper in papers[:12]]]
    ).lower()
    markers = [
        "多模态",
        "mllm",
        "lvlm",
        "vlm",
        "vision-language",
        "vision language",
        "multimodal large language model",
        "multimodal foundation model",
    ]
    return any(marker in haystack for marker in markers)


def top_by_role(
    papers: list[dict[str, Any]],
    roles: set[str],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    return sorted(
        [paper for paper in papers if str(paper.get("paper_role") or "") in roles],
        key=paper_score,
        reverse=True,
    )[:limit]


def build_mobile_knowledge_summary(
    workspace: Path,
    *,
    topic: str,
    counts: dict[str, int],
    report_summary: list[str],
) -> list[str]:
    papers = selected_papers(workspace)
    if not papers:
        return report_summary[:6]

    clusters = cluster_papers(papers)
    top_clusters = clusters[:4]
    survey_examples = format_examples(
        top_by_role(papers, {"survey_or_review", "position_or_perspective"}, limit=3),
        limit=2,
    )
    technical_examples = format_examples(
        top_by_role(papers, {"technical_method", "system_paper"}, limit=3),
        limit=2,
    )
    benchmark_examples = format_examples(
        top_by_role(papers, {"benchmark_or_dataset"}, limit=3),
        limit=3,
    )

    summary: list[str] = []
    if looks_like_mllm_topic(topic, papers):
        summary.append(
            "领域边界：多模态大模型（MLLM/LVLM/VLM）以视觉编码器、LLM、"
            "跨模态对齐和指令微调为核心，覆盖图像/视频理解、VQA、caption、"
            "OCR/图表和垂直领域任务。"
        )
    elif top_clusters:
        labels = "、".join(cluster["label"] for cluster in top_clusters[:3])
        summary.append(f"领域边界：本批文献把主题集中到{labels}等方向。")

    summary.append(role_counts_line(papers, counts))

    if top_clusters:
        cluster_text = "、".join(
            f"{cluster['label']}（{len(cluster['papers'])} 篇）"
            for cluster in top_clusters[:3]
        )
        summary.append(f"技术主线：{cluster_text}是本批文献中最集中的三个方向。")
        for cluster in top_clusters[:2]:
            summary.append(f"关键判断：{cluster['implication']}")

    if survey_examples or technical_examples:
        summary.append(
            "代表阅读："
            f"先用{survey_examples or '综述/背景论文'}建领域地图，"
            f"再用{technical_examples or '技术/系统论文'}追踪方法和系统路线。"
        )

    if benchmark_examples:
        summary.append(
            f"评测体系：优先查看 {benchmark_examples}；不要只看通用准确率，"
            "要拆成感知、推理、幻觉、OCR/文档、安全和垂直场景指标。"
        )

    opportunity_parts = [cluster["implication"] for cluster in top_clusters[:3]]
    if opportunity_parts:
        summary.append("可做机会：" + "；".join(opportunity_parts))

    return [compact_text(line, limit=260) for line in summary if line][:8]


def safe_inspect_workspace(workspace: Path) -> dict[str, Any]:
    try:
        return inspect_workspace(workspace)
    except Exception as exc:  # noqa: BLE001 - result summary should degrade gracefully
        return {
            "workspace": str(workspace),
            "quality_label": "unknown",
            "quality_level": "unknown",
            "recommended_next_action": (
                f"inspect-workspace failed: {compact_text(str(exc), limit=180)}"
            ),
        }


def summarize_page(workspace: Path, key: str, title: str, relative_path: Path) -> dict[str, Any]:
    path = workspace / relative_path
    return {
        "key": key,
        "title": title,
        "path": str(path),
        "exists": path.exists(),
        "summary": useful_markdown_lines(path, limit=3),
    }


def markdown_cell(value: Any, *, limit: int = 140) -> str:
    text = compact_text(str(value or ""), limit=limit)
    return text.replace("|", "\\|")


def source_label(source: Any) -> str:
    if isinstance(source, list):
        return "/".join(str(item) for item in source if item) or "unknown"
    return str(source or "unknown")


def matched_terms_line(paper: dict[str, Any], *, limit: int = 110) -> str:
    explanation = paper.get("score_explanation") or {}
    matched_terms = explanation.get("matched_terms") if isinstance(explanation, dict) else {}
    terms: list[str] = []
    if isinstance(matched_terms, dict):
        for key in ("high_value_title", "include_title", "high_value_abstract"):
            values = matched_terms.get(key) or []
            if isinstance(values, list):
                terms.extend(str(value) for value in values[:3])
    unique_terms = list(dict.fromkeys(term for term in terms if term))
    if unique_terms:
        return compact_text("匹配：" + "、".join(unique_terms[:6]), limit=limit)
    abstract = paper.get("abstract") or ""
    return compact_text(str(abstract), limit=limit)


def paper_markdown_link(paper: dict[str, Any]) -> str:
    title = markdown_cell(paper.get("title") or "Untitled", limit=120)
    paper_id = markdown_cell(paper.get("paper_id") or "", limit=40)
    return f"{title} `{paper_id}`" if paper_id else title


def flatten_evidence_rows(workspace: Path) -> list[dict[str, Any]]:
    evidence = read_json(workspace / "knowledge" / "evidence_table.json", default={}) or {}
    rows: list[dict[str, Any]] = []
    for theme in evidence.get("themes") or []:
        if not isinstance(theme, dict):
            continue
        theme_claim = str(theme.get("claim") or theme.get("theme") or "")
        theme_name = str(theme.get("theme") or theme.get("field") or "evidence")
        for snippet in theme.get("evidence_snippets_or_sections") or []:
            if not isinstance(snippet, dict):
                continue
            row = dict(snippet)
            row.setdefault("theme", theme_name)
            row.setdefault("theme_claim", theme_claim)
            rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("snippet_score") or 0),
            str(row.get("paper_title") or row.get("title") or ""),
        ),
        reverse=True,
    )


def read_note_highlights(workspace: Path, paper_id: str, *, limit: int = 3) -> list[str]:
    if not paper_id:
        return []
    note_path = workspace / "library" / "notes" / f"{paper_id}.md"
    if not note_path.exists():
        return []
    lines: list[str] = []
    for raw_line in note_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("- Evidence "):
            continue
        lines.append(strip_markdown(stripped))
        if len(lines) >= limit:
            break
    return lines


def note_pack_lines(workspace: Path, paper_id: str, *, limit: int = 28) -> list[str]:
    if not paper_id:
        return []
    note_path = workspace / "library" / "notes" / f"{paper_id}.md"
    if not note_path.exists():
        return []
    lines: list[str] = []
    current_heading = ""
    for raw_line in note_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        heading_match = re.match(r"^(#{2,3})\s+(.+)$", stripped)
        if heading_match:
            current_heading = heading_match.group(2).strip()
            continue
        if not stripped.startswith("- "):
            continue
        if stripped.startswith(
            (
                "- Source:",
                "- Confidence:",
                "- Quality flags:",
                "- Score explanation:",
                "- Classifier evidence:",
                "- Ranking evidence:",
            )
        ):
            continue
        if not (
            stripped.startswith("- Abstract-derived contribution:")
            or stripped.startswith("- Evidence ")
            or stripped.startswith("- Missing or uncertain:")
        ):
            continue
        prefix = f"{current_heading}: " if current_heading else ""
        line = strip_markdown(stripped)
        if line:
            lines.append(compact_text(prefix + line, limit=520))
        if len(lines) >= limit:
            break
    return lines


def paper_pack_markdown(workspace: Path, paper: dict[str, Any], index: int) -> list[str]:
    paper_id = str(paper.get("paper_id") or "unknown")
    lines = [
        f"## {index}. {paper.get('title') or 'Untitled'}",
        "",
        f"- paper_id: `{paper_id}`",
        f"- year: {paper.get('year') or 'unknown'}",
        f"- role: {paper.get('paper_role') or paper.get('paper_type') or 'unknown'}",
        f"- reading_intent: {paper.get('reading_intent') or []}",
        f"- source: {source_label(paper.get('source'))}",
        f"- final_score: {paper.get('final_score') or ''}",
    ]
    abstract = compact_text(str(paper.get("abstract") or ""), limit=1200)
    if abstract:
        lines.extend(["", "### Abstract", "", abstract])
    note_lines = note_pack_lines(workspace, paper_id, limit=32)
    lines.extend(["", "### Note And Evidence Excerpts", ""])
    if note_lines:
        lines.extend(f"- {line}" for line in note_lines)
    else:
        lines.append(
            "- No note excerpts found; Codex should inspect the note or source file if needed."
        )
    return lines


def agent_synthesis_prompt_markdown(result: dict[str, Any]) -> str:
    workspace = Path(str(result.get("workspace") or "."))
    topic = str(result.get("topic") or "unknown")
    pack_path = workspace / "reports" / "agent_synthesis_pack.md"
    output_path = workspace / "reports" / "codex_synthesis.md"
    lines = [
        f"# Codex 深度调研报告写作任务：{topic}",
        "",
        "你是 Codex / Agent 综合层。`litagent` 已经完成检索、解析、分类、阅读笔记、"
        "证据表和知识页构建；你不能把 `audit PASS` 当作最终质量保证。",
        "",
        "## 输入材料",
        "",
        f"- 证据包：`{pack_path}`",
        f"- workspace：`{workspace}`",
        "- 优先使用 `library/notes/*.md`、`knowledge/evidence_table.*`、"
        "`knowledge/*.md` 和 `data/selected_papers.jsonl`。",
        "",
        "## 输出文件",
        "",
        f"- 请把最终中文深度报告写入：`{output_path}`",
        "- 写完后再运行 `/research result <job_id>` 或 "
        "`litagent job result <job_id> --write-report --pdf --json` 生成手机端 HTML/PDF。",
        "",
        "## 写作要求",
        "",
        "- 不要写成流程日志，不要只罗列论文类别。",
        "- 报告必须解释这个领域的背景、核心问题、主要技术路线、评测体系、争议和机会。",
        "- 每篇 selected paper 都要有一张精华卡片，至少覆盖：背景/问题、核心思路、方法/系统、"
        "实验/评测、结论/发现、局限/未来、研究启示。",
        "- 60 篇论文不能孤立排列；需要形成体系：主题簇、共性、差异、互补关系、矛盾或张力、"
        "阅读路径和研究切入点。",
        "- 关键判断必须尽量绑定 paper_id 或论文标题；没有证据时明确标注需要复核。",
        "- 默认使用中文，必要英文术语保留原文并解释。",
        "- 不要编造不存在的实验结果、结论、数据集或引用。",
    ]
    return "\n".join(lines).rstrip() + "\n"


def agent_synthesis_pack_markdown(result: dict[str, Any]) -> str:
    workspace = Path(str(result.get("workspace") or "."))
    topic = str(result.get("topic") or "unknown")
    counts = result.get("counts") or {}
    papers = sorted(selected_papers(workspace), key=paper_score, reverse=True)
    lines: list[str] = [
        f"# Agent Synthesis Pack: {topic}",
        "",
        "这个文件是给 Codex/Agent 的证据包，不是最终报告。它只汇总可用材料，"
        "不负责替 Agent 下研究判断。",
        "",
        "## Workspace",
        "",
        f"- workspace: `{workspace}`",
        f"- job_id: `{result.get('job_id') or 'workspace-only'}`",
        f"- quality_label: `{result.get('quality_label') or 'unknown'}`",
        (
            "- counts: "
            f"selected={counts.get('selected_papers', 0)}, "
            f"parsed={counts.get('parsed_markdown', 0)}, "
            f"notes={counts.get('notes', 0)}, "
            f"evidence={counts.get('evidence_spans', 0)}"
        ),
        "",
        "## Agent Task",
        "",
        "- 基于本证据包和 workspace 原始产物写研究级中文手机长报告。",
        "- 不要把本文件当最终结论；它只是上下文压缩层。",
        "",
        "## Knowledge Pages",
        "",
    ]
    for page in result.get("knowledge_pages") or []:
        if not page.get("exists"):
            continue
        lines.append(f"### {page.get('title') or page.get('key')}")
        lines.append(f"- path: `{page.get('path')}`")
        for item in page.get("summary") or []:
            lines.append(f"- {compact_text(str(item), limit=420)}")
        lines.append("")

    evidence_rows = flatten_evidence_rows(workspace)
    if evidence_rows:
        lines.extend(["## Evidence Table Excerpts", ""])
        for row in evidence_rows[:80]:
            title = row.get("paper_title") or row.get("title") or row.get("paper_id") or "unknown"
            snippet = compact_text(str(row.get("snippet") or ""), limit=420)
            lines.append(
                "- "
                f"`{row.get('paper_id') or 'unknown'}` "
                f"{compact_text(str(title), limit=120)} | "
                f"field={row.get('field') or 'unknown'} | "
                f"section={row.get('section') or 'unknown'} | "
                f"score={row.get('snippet_score') or 'n/a'} | "
                f"{snippet}"
            )
        lines.append("")

    lines.extend(["## Selected Papers", ""])
    for index, paper in enumerate(papers, start=1):
        lines.extend(paper_pack_markdown(workspace, paper, index))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_agent_synthesis_inputs(workspace: Path, result: dict[str, Any]) -> dict[str, Any]:
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = reports_dir / "agent_synthesis_prompt.md"
    pack_path = reports_dir / "agent_synthesis_pack.md"
    prompt_path.write_text(agent_synthesis_prompt_markdown(result), encoding="utf-8")
    pack_path.write_text(agent_synthesis_pack_markdown(result), encoding="utf-8")
    return {
        "agent_synthesis_prompt": {
            "exists": prompt_path.exists(),
            "path": str(prompt_path),
            "format": "markdown",
        },
        "agent_synthesis_pack": {
            "exists": pack_path.exists(),
            "path": str(pack_path),
            "format": "markdown",
        },
    }


def table_for_papers(papers: list[dict[str, Any]], *, limit: int = 24) -> list[str]:
    rows = [
        "| paper | year | role | source | score | why read |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for paper in sorted(papers, key=paper_score, reverse=True)[:limit]:
        rows.append(
            "| "
            + " | ".join(
                [
                    paper_markdown_link(paper),
                    markdown_cell(paper.get("year") or ""),
                    markdown_cell(ROLE_LABELS.get(str(paper.get("paper_role") or ""), "unknown")),
                    markdown_cell(source_label(paper.get("source"))),
                    markdown_cell(f"{float(paper.get('final_score') or 0):.3f}"),
                    markdown_cell(matched_terms_line(paper), limit=150),
                ]
            )
            + " |"
        )
    return rows


def role_grouped_paper_lines(papers: list[dict[str, Any]], *, per_role: int = 8) -> list[str]:
    lines: list[str] = []
    for role in ROLE_ORDER:
        role_papers = [
            paper for paper in papers if str(paper.get("paper_role") or "") == role
        ]
        if not role_papers:
            continue
        lines.append(f"### {ROLE_LABELS.get(role, role)}（{len(role_papers)} 篇）")
        for paper in sorted(role_papers, key=paper_score, reverse=True)[:per_role]:
            why = matched_terms_line(paper, limit=130)
            lines.append(
                "- "
                f"{title_with_year(paper, limit=100)} "
                f"[{paper.get('paper_id') or 'unknown'}]：{why}"
            )
        lines.append("")
    return lines


def evidence_markdown_lines(
    workspace: Path,
    *,
    max_themes: int = 6,
    per_theme: int = 5,
) -> list[str]:
    rows = flatten_evidence_rows(workspace)
    if not rows:
        return ["暂无 evidence_table.json 证据摘录。"]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        theme = str(row.get("theme") or "evidence")
        grouped.setdefault(theme, []).append(row)

    ordered = sorted(
        grouped.items(),
        key=lambda item: (len(item[1]), float(item[1][0].get("snippet_score") or 0)),
        reverse=True,
    )
    lines: list[str] = []
    for theme, theme_rows in ordered[:max_themes]:
        lines.append(f"### {theme}")
        claim = compact_text(str(theme_rows[0].get("theme_claim") or ""), limit=240)
        if claim:
            lines.append(f"- 主题判断：{claim}")
        for row in theme_rows[:per_theme]:
            title = row.get("paper_title") or row.get("title") or row.get("paper_id") or "unknown"
            snippet = compact_text(str(row.get("snippet") or ""), limit=260)
            section = row.get("section") or "unknown-section"
            score = row.get("snippet_score")
            score_text = f"{float(score):.2f}" if isinstance(score, int | float) else "n/a"
            lines.append(
                "- "
                f"{markdown_cell(title, limit=110)}；section={section}；score={score_text}。"
                f"证据：{snippet}"
            )
        lines.append("")
    return lines


def knowledge_page_excerpt_lines(result: dict[str, Any], *, per_page: int = 5) -> list[str]:
    lines: list[str] = []
    for page in result.get("knowledge_pages") or []:
        if not page.get("exists"):
            continue
        summary = [str(item) for item in page.get("summary") or [] if item]
        if not summary:
            continue
        lines.append(f"### {page.get('title') or page.get('key')}")
        lines.extend(f"- {compact_text(item, limit=240)}" for item in summary[:per_page])
        lines.append(f"- 文件：`{page.get('path')}`")
        lines.append("")
    return lines


def mobile_report_markdown(result: dict[str, Any]) -> str:
    workspace = Path(str(result.get("workspace") or "."))
    topic = str(result.get("topic") or "unknown")
    counts = result.get("counts") or {}
    papers = selected_papers(workspace)
    clusters = cluster_papers(papers)
    role_counts = Counter(str(paper.get("paper_role") or "unknown") for paper in papers)

    lines: list[str] = [
        f"# {topic}：手机长版调研简报",
        "",
        "> 这是一份由 litagent 生成的研究工作台简报，用于手机端快速阅读。"
        "它整合 selected papers、notes、knowledge pages 和 evidence table；"
        "不等同于最终学术综述，关键结论仍需要人工复核原文。",
        "",
        "## 运行概览",
        "",
        f"- job_id：`{result.get('job_id') or 'workspace-only'}`",
        f"- 状态：`{result.get('job_status') or 'unknown'}`",
        f"- 质量标签：`{result.get('quality_label') or 'unknown'}`",
        f"- 工作区：`{result.get('workspace') or ''}`",
        (
            "- 规模："
            f"selected {counts.get('selected_papers', 0)}，"
            f"parsed {counts.get('parsed_markdown', 0)}，"
            f"notes {counts.get('notes', 0)}，"
            f"evidence {counts.get('evidence_spans', 0)}"
        ),
        "",
        "## 一页结论",
        "",
    ]

    mobile_summary = result.get("mobile_summary") or []
    if mobile_summary:
        lines.extend(f"- {line}" for line in mobile_summary)
    else:
        lines.append("- 暂无可用的一页结论。")

    lines.extend(["", "## 领域结构", ""])
    if role_counts:
        lines.append(
            "- 论文角色分布："
            + "；".join(
                f"{ROLE_LABELS.get(role, role)} {count}"
                for role, count in role_counts.most_common()
            )
            + "。"
        )
    if clusters:
        lines.append("- 主题簇：")
        for cluster in clusters[:8]:
            examples = format_examples(cluster["papers"], limit=3)
            lines.append(
                f"  - {cluster['label']}：{len(cluster['papers'])} 篇。"
                f"判断：{cluster['implication']} 代表论文：{examples}"
            )
    else:
        lines.append("- 暂未形成稳定主题簇。")

    lines.extend(["", "## 关键论文速读", ""])
    lines.extend(role_grouped_paper_lines(papers, per_role=8))

    lines.extend(["", "## Top 论文清单", ""])
    lines.extend(table_for_papers(papers, limit=30))

    benchmark_papers = top_by_role(papers, {"benchmark_or_dataset"}, limit=12)
    if benchmark_papers:
        lines.extend(["", "## 评测与 Benchmark 地图", ""])
        for paper in benchmark_papers:
            lines.append(
                "- "
                f"{title_with_year(paper, limit=110)} [{paper.get('paper_id') or 'unknown'}]："
                f"{matched_terms_line(paper, limit=180)}"
            )

    lines.extend(["", "## 证据摘录", ""])
    lines.extend(evidence_markdown_lines(workspace, max_themes=6, per_theme=5))

    lines.extend(["", "## 知识页摘录", ""])
    page_lines = knowledge_page_excerpt_lines(result, per_page=5)
    lines.extend(page_lines or ["- 暂无可用知识页摘录。"])

    lines.extend(["", "## 建议阅读路径", ""])
    reading_plan = workspace / "knowledge" / "reading_plan.md"
    reading_lines = useful_markdown_lines(reading_plan, limit=18)
    if reading_lines:
        lines.extend(f"- {line}" for line in reading_lines)
    else:
        lines.append(
            "- 先读综述/背景建领域地图，再读技术/系统论文追踪方法，"
            "最后读 benchmark/dataset 建评测矩阵。"
        )

    lines.extend(["", "## 文件入口", ""])
    wiki = result.get("wiki_start_here") or {}
    if wiki.get("exists"):
        lines.append(f"- Obsidian/AutoWiki 入口：`{wiki.get('path')}`")
    report = result.get("report") or {}
    if report.get("exists"):
        lines.append(f"- 可选中文草稿：`{report.get('path')}`")
    for relative in [
        "knowledge/evidence_table.md",
        "knowledge/evidence_table.json",
        "data/selected_papers.jsonl",
        "run_log.jsonl",
    ]:
        path = workspace / relative
        if path.exists():
            lines.append(f"- `{path}`")

    recommended = result.get("recommended_next_action")
    if recommended:
        lines.extend(["", "## 后续动作", "", f"- {recommended}"])

    return "\n".join(lines).rstrip() + "\n"


def inline_markdown_to_html(text: str) -> str:
    html = escape(text)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)
    return html


def split_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def markdown_to_html(markdown: str, *, title: str) -> str:
    body: list[str] = []
    in_list = False
    in_table = False
    table_header_written = False

    def close_blocks() -> None:
        nonlocal in_list, in_table, table_header_written
        if in_list:
            body.append("</ul>")
            in_list = False
        if in_table:
            body.append("</table>")
            in_table = False
            table_header_written = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            close_blocks()
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            close_blocks()
            level = len(heading.group(1))
            body.append(f"<h{level}>{inline_markdown_to_html(heading.group(2))}</h{level}>")
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = split_markdown_table_row(stripped)
            if cells and all(set(cell) <= {"-", ":"} for cell in cells):
                continue
            if in_list:
                body.append("</ul>")
                in_list = False
            if not in_table:
                body.append("<table>")
                in_table = True
                table_header_written = False
            tag = "td" if table_header_written else "th"
            table_header_written = True
            body.append(
                "<tr>"
                + "".join(f"<{tag}>{inline_markdown_to_html(cell)}</{tag}>" for cell in cells)
                + "</tr>"
            )
            continue

        if stripped.startswith("- "):
            if in_table:
                body.append("</table>")
                in_table = False
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{inline_markdown_to_html(stripped[2:])}</li>")
            continue

        close_blocks()
        if stripped.startswith("> "):
            body.append(f"<blockquote>{inline_markdown_to_html(stripped[2:])}</blockquote>")
        else:
            body.append(f"<p>{inline_markdown_to_html(stripped)}</p>")

    close_blocks()
    return (
        "<!doctype html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        "<style>\n"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;"
        "line-height:1.65;margin:0 auto;padding:24px;max-width:980px;color:#111827;}\n"
        "h1{font-size:1.7rem;border-bottom:2px solid #111827;padding-bottom:.4rem;}"
        "h2{font-size:1.35rem;margin-top:2rem;border-bottom:1px solid #e5e7eb;"
        "padding-bottom:.25rem;}"
        "h3{font-size:1.05rem;margin-top:1.25rem;color:#1f2937;}"
        "blockquote{background:#f8fafc;border-left:4px solid #64748b;"
        "margin:1rem 0;padding:.75rem 1rem;}"
        "code{background:#f3f4f6;border-radius:4px;padding:.08rem .25rem;}"
        "table{border-collapse:collapse;width:100%;font-size:.86rem;display:block;overflow-x:auto;}"
        "th,td{border:1px solid #d1d5db;padding:.45rem;vertical-align:top;}th{background:#f3f4f6;}"
        "li{margin:.28rem 0;}@media print{body{max-width:none;padding:12mm;}a{color:#111827;}}\n"
        "</style>\n"
        "</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )


def find_headless_browser() -> Path | None:
    for command in ("msedge", "chrome", "chromium", "google-chrome"):
        found = shutil.which(command)
        if found:
            return Path(found)
    for candidate in [
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ]:
        if candidate.exists():
            return candidate
    return None


def render_pdf_from_html(html_path: Path, pdf_path: Path) -> dict[str, Any]:
    browser = find_headless_browser()
    if browser is None:
        return {
            "exists": False,
            "path": str(pdf_path),
            "format": "pdf",
            "error": (
                "未找到 Edge/Chrome、pandoc、wkhtmltopdf 或 weasyprint；"
                "已保留 HTML/Markdown。"
            ),
        }

    profile_root = Path.cwd() / ".tmp" / "browser-profiles"
    profile_root.mkdir(parents=True, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="litagent-browser-profile-", dir=profile_root)
    try:
        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-breakpad",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={temp_dir}",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ]
        completed = subprocess.run(
            command,
            cwd=html_path.parent,
            capture_output=True,
            timeout=90,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace")
            stdout = completed.stdout.decode("utf-8", errors="replace")
            detail = stderr.strip() or stdout.strip() or f"exit code {completed.returncode}"
            return {
                "exists": pdf_path.exists(),
                "path": str(pdf_path),
                "format": "pdf",
                "renderer": str(browser),
                "error": compact_text(detail, limit=260),
            }
    except Exception as exc:  # noqa: BLE001 - artifact generation should degrade
        return {
            "exists": pdf_path.exists(),
            "path": str(pdf_path),
            "format": "pdf",
            "error": compact_text(str(exc), limit=260),
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "exists": pdf_path.exists(),
        "path": str(pdf_path),
        "format": "pdf",
        "renderer": str(browser),
        "error": "" if pdf_path.exists() else "浏览器执行完成但 PDF 文件未生成。",
    }


def write_mobile_report_artifacts(
    workspace: Path,
    result: dict[str, Any],
    *,
    render_pdf: bool = False,
) -> dict[str, Any]:
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_dir / "mobile_brief.md"
    html_path = reports_dir / "mobile_brief.html"
    pdf_path = reports_dir / "mobile_brief.pdf"
    agent_markdown_path = reports_dir / "codex_synthesis.md"

    agent_inputs = write_agent_synthesis_inputs(workspace, result)
    report_source = "agent_synthesis" if agent_markdown_path.exists() else "deterministic_summary"
    if agent_markdown_path.exists():
        markdown = agent_markdown_path.read_text(encoding="utf-8")
    else:
        markdown = mobile_report_markdown(result)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(
        markdown_to_html(markdown, title=f"{result.get('topic') or 'topic'}：手机长版调研简报"),
        encoding="utf-8",
    )

    artifacts: dict[str, Any] = {
        **agent_inputs,
        "agent_synthesis_markdown": {
            "exists": agent_markdown_path.exists(),
            "path": str(agent_markdown_path),
            "format": "markdown",
        },
        "mobile_report_markdown": {
            "exists": markdown_path.exists(),
            "path": str(markdown_path),
            "format": "markdown",
            "source": report_source,
        },
        "mobile_report_html": {
            "exists": html_path.exists(),
            "path": str(html_path),
            "format": "html",
            "source": report_source,
        },
        "mobile_report_pdf": {
            "exists": pdf_path.exists(),
            "path": str(pdf_path),
            "format": "pdf",
            "skipped": not render_pdf,
            "source": report_source,
        },
    }
    if render_pdf:
        artifacts["mobile_report_pdf"] = render_pdf_from_html(html_path, pdf_path)
    return artifacts


def summarize_workspace_result(
    workspace: Path,
    *,
    job: dict[str, Any] | None = None,
    write_report: bool = False,
    render_pdf: bool = False,
) -> dict[str, Any]:
    workspace = Path(workspace)
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    inspect = safe_inspect_workspace(workspace)
    counts = workspace_counts(workspace)
    pages = [
        summarize_page(workspace, key, title, relative)
        for key, title, relative in KNOWLEDGE_PAGES
    ]
    report_path = workspace / "reports" / "final_report.md"
    report_summary = markdown_section_lines(
        report_path,
        {"执行摘要", "executive summary"},
        limit=4,
    )
    if not report_summary:
        report_summary = useful_markdown_lines(report_path, limit=3)

    topic = str(job.get("topic") if job else plan.get("topic", "unknown"))
    mobile_summary = build_mobile_knowledge_summary(
        workspace,
        topic=topic,
        counts=counts,
        report_summary=report_summary,
    )
    if not mobile_summary:
        mobile_summary = report_summary[:6]

    wiki_start = workspace / "wiki-vault" / "START_HERE.md"
    result = {
        "topic": topic,
        "job_id": job.get("id") if job else None,
        "job_status": job.get("status") if job else None,
        "mode": "mock" if (job or {}).get("payload", {}).get("mock") else "real_or_workspace",
        "workspace": str(workspace),
        "quality_label": inspect.get("quality_label") or inspect.get("quality_level") or "unknown",
        "recommended_next_action": inspect.get("recommended_next_action") or "",
        "counts": counts,
        "mobile_summary": mobile_summary[:8],
        "report": {
            "exists": report_path.exists(),
            "path": str(report_path),
            "summary": report_summary,
        },
        "knowledge_pages": pages,
        "wiki_start_here": {
            "exists": wiki_start.exists(),
            "path": str(wiki_start),
            "summary": useful_markdown_lines(wiki_start, limit=3),
        },
        "inspect": {
            "quality_label": (
                inspect.get("quality_label") or inspect.get("quality_level") or "unknown"
            ),
            "recommended_next_action": inspect.get("recommended_next_action") or "",
        },
        "artifacts": {},
    }
    if write_report or render_pdf:
        result["artifacts"] = write_mobile_report_artifacts(
            workspace,
            result,
            render_pdf=render_pdf,
        )
    return result


def result_summary_markdown(result: dict[str, Any]) -> str:
    counts = result.get("counts") or {}
    lines = ["知识点摘要："]
    summary = result.get("mobile_summary") or []
    if summary:
        lines.extend(f"- {line}" for line in summary[:8])
    else:
        lines.append("- 暂未生成可用知识点摘要；请检查 workspace 的 selected papers 和知识页。")

    lines.extend(
        [
            "",
            "运行信息：",
            f"- job_id: {result.get('job_id') or 'workspace-only'}",
            f"- 主题: {result.get('topic') or 'unknown'}",
            f"- 状态: {result.get('job_status') or 'unknown'}",
            f"- 质量标签: {result.get('quality_label') or 'unknown'}",
            (
                "- 规模: "
                f"selected {counts.get('selected_papers', 0)}, "
                f"parsed {counts.get('parsed_markdown', 0)}, "
                f"notes {counts.get('notes', 0)}, "
                f"evidence {counts.get('evidence_spans', 0)}"
            ),
        ]
    )

    wiki = result.get("wiki_start_here") or {}
    if wiki.get("exists"):
        lines.extend(["", "可查看文件：", f"- wiki: {wiki.get('path')}"])

    artifacts = result.get("artifacts") or {}
    report_md = artifacts.get("mobile_report_markdown") or {}
    report_html = artifacts.get("mobile_report_html") or {}
    report_pdf = artifacts.get("mobile_report_pdf") or {}
    agent_prompt = artifacts.get("agent_synthesis_prompt") or {}
    agent_pack = artifacts.get("agent_synthesis_pack") or {}
    agent_synthesis = artifacts.get("agent_synthesis_markdown") or {}
    if report_md.get("exists") or report_html.get("exists") or report_pdf.get("exists"):
        lines.extend(["", "长版手机报告："])
        if report_md.get("source"):
            lines.append(f"- source: {report_md.get('source')}")
        if report_pdf.get("exists"):
            lines.append(f"- PDF: {report_pdf.get('path')}")
        if report_html.get("exists"):
            lines.append(f"- HTML: {report_html.get('path')}")
        if report_md.get("exists"):
            lines.append(f"- Markdown: {report_md.get('path')}")
        if report_pdf.get("error"):
            lines.append(f"- PDF 生成提示: {report_pdf.get('error')}")
    if agent_prompt.get("exists") or agent_pack.get("exists") or agent_synthesis.get("exists"):
        lines.extend(["", "Agent 综合材料："])
        if agent_synthesis.get("exists"):
            lines.append(f"- Codex synthesis: {agent_synthesis.get('path')}")
        if agent_pack.get("exists"):
            lines.append(f"- evidence pack: {agent_pack.get('path')}")
        if agent_prompt.get("exists"):
            lines.append(f"- prompt: {agent_prompt.get('path')}")

    if result.get("recommended_next_action"):
        lines.append(f"- 下一步: {result['recommended_next_action']}")
    return "\n".join(lines)
