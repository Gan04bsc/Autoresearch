from __future__ import annotations

from pathlib import Path
from typing import Any

from litagent.evidence_quality import confidence_from_score, score_snippet
from litagent.io import read_json, read_jsonl, write_json
from litagent.reader import extract_paper_evidence, paper_text
from litagent.schema import normalize_paper

THEME_LABELS_ZH: dict[str, str] = {
    "multi-agent architecture": "多智能体架构",
    "survey/literature review generation": "综述生成",
    "systematic review workflow": "系统综述工作流",
    "paper reading agents": "论文阅读智能体",
    "citation-aware synthesis": "引文感知综合",
    "evaluation and benchmarks": "评估与基准",
    "limitations and open problems": "局限与开放问题",
    "design implications for litagent": "对 litagent 的设计启发",
}

THEME_SPECS: dict[str, dict[str, Any]] = {
    "multi-agent architecture": {
        "fields": ["agent_roles", "pipeline_stages"],
        "terms": [
            "multi-agent",
            "multiple agents",
            "specialized agents",
            "agent decomposition",
            "organizer",
            "collector",
            "composer",
            "refiner",
            "reviewer agent",
            "writer agent",
        ],
        "strict_terms": True,
        "claim": "相关系统倾向于用多智能体分工拆解规划、检索、写作、审阅和修订职责。",
    },
    "survey/literature review generation": {
        "fields": ["proposed_system_or_method", "pipeline_stages"],
        "terms": [
            "survey generation",
            "literature review generation",
            "scientific survey generation",
            "review generation",
            "survey writing",
            "literature surveys",
            "related work drafting",
        ],
        "strict_terms": True,
        "claim": "综述和文献回顾生成系统更适合采用分阶段工作流，而不是一次性生成。",
    },
    "systematic review workflow": {
        "fields": ["problem_addressed", "retrieval_search_strategy", "pipeline_stages"],
        "terms": [
            "systematic review",
            "screening",
            "data extraction",
            "eligibility",
            "study selection",
            "relevance scoring",
            "prisma",
        ],
        "strict_terms": True,
        "claim": "系统综述自动化需要支持筛选、评分、信息抽取、验证和迭代审阅等可操作环节。",
    },
    "paper reading agents": {
        "fields": ["agent_roles", "retrieval_search_strategy", "key_findings"],
        "terms": [
            "paper-reading",
            "paper reading",
            "reading agents",
            "read scientific papers",
            "paperguide",
        ],
        "strict_terms": True,
        "claim": "论文阅读智能体是综合写作之前抽取任务相关证据的可复用上游能力。",
    },
    "citation-aware synthesis": {
        "fields": ["citation_or_evidence_handling", "retrieval_search_strategy"],
        "terms": [
            "citation-aware",
            "citation graph",
            "hierarchical citation graph",
            "citation quality",
            "citation precision",
            "citation recall",
            "cited references",
            "evidence handling",
            "grounding",
        ],
        "strict_terms": True,
        "claim": "引文感知综合需要在最终写作前显式处理来源关系、证据片段和引用可靠性。",
    },
    "evaluation and benchmarks": {
        "fields": ["evaluation_setup", "datasets_or_benchmarks", "key_findings"],
        "terms": ["evaluation", "benchmark", "dataset", "metrics", "human evaluation"],
        "claim": "评估应覆盖内容质量、结构质量、引文质量、检索覆盖率和人工判断等多个维度。",
    },
    "limitations and open problems": {
        "fields": ["limitations", "citation_or_evidence_handling"],
        "terms": ["limitation", "challenge", "future work", "hallucination", "gap"],
        "claim": "当前开放问题集中在引文忠实性、检索覆盖率、解析质量和稳健评估上。",
    },
    "design implications for litagent": {
        "fields": [
            "agent_roles",
            "pipeline_stages",
            "citation_or_evidence_handling",
            "evaluation_setup",
        ],
        "terms": ["agent", "pipeline", "citation", "evaluation", "workflow"],
        "claim": "litagent 应保持搜索、选择、解析、证据抽取、综合和审计等环节相互独立且可检查。",
    },
}


def load_paper_evidence(workspace: Path, paper: dict[str, Any]) -> dict[str, Any]:
    metadata = read_json(
        workspace / "library" / "metadata" / f"{paper['paper_id']}.json",
        default={},
    ) or {}
    evidence = metadata.get("paper_evidence")
    if isinstance(evidence, dict) and evidence.get("fields"):
        return evidence
    text, source = paper_text(workspace, paper)
    return extract_paper_evidence(paper, text, source)


def paper_matches_theme(
    paper: dict[str, Any],
    evidence: dict[str, Any],
    spec: dict[str, Any],
) -> bool:
    terms = [str(term).lower() for term in spec["terms"]]
    fields = evidence.get("fields") or {}
    field_snippets: list[str] = []
    for field in spec["fields"]:
        item = fields.get(field) or {}
        field_snippets.extend(
            str(evidence_item.get("snippet") or "")
            for evidence_item in item.get("evidence_items") or []
        )
        field_snippets.extend(str(snippet) for snippet in item.get("snippets") or [])

    searchable = " ".join(
        [
            str(paper.get("title") or ""),
            str(paper.get("abstract") or ""),
            *field_snippets,
        ]
    ).lower()
    if any(term in searchable for term in terms):
        return True
    if spec.get("strict_terms"):
        return False

    for field in spec["fields"]:
        item = fields.get(field) or {}
        if item.get("source") != "missing" and item.get("snippets"):
            return True
    return False


def evidence_items_for_theme(
    paper: dict[str, Any],
    evidence: dict[str, Any],
    spec: dict[str, Any],
    theme: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    fields = evidence.get("fields") or {}
    for field in spec["fields"]:
        item = fields.get(field) or {}
        evidence_items = item.get("evidence_items") or [
            {
                "snippet": snippet,
                "section": "Unknown",
                "snippet_score": 0.0,
                "snippet_score_explanation": "旧版证据片段未记录质量说明。",
                "quality_flags": ["legacy_snippet"],
            }
            for snippet in item.get("snippets") or []
        ]
        for evidence_item in evidence_items:
            scored = score_snippet(
                str(evidence_item.get("snippet") or ""),
                section=str(evidence_item.get("section") or "Unknown"),
                target_terms=[*spec["terms"], theme],
            )
            score = float(scored["snippet_score"])
            if score < 0.12:
                continue
            dedup_key = (paper["paper_id"], scored["snippet"].lower())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            flags = sorted(
                set(scored["quality_flags"])
                | set(str(flag) for flag in evidence_item.get("quality_flags") or [])
            )
            uncertainty = ""
            if score < 0.45:
                uncertainty = "片段质量较低，可能只能作为弱证据或人工复核线索。"
            items.append(
                {
                    "theme": theme,
                    "claim": spec["claim"],
                    "paper_id": paper["paper_id"],
                    "paper_title": paper.get("title") or paper["paper_id"],
                    "title": paper.get("title") or paper["paper_id"],
                    "field": field,
                    "source": item.get("source"),
                    "snippet": scored["snippet"],
                    "section": scored["section"],
                    "snippet_score": score,
                    "snippet_score_explanation": scored["snippet_score_explanation"],
                    "confidence": confidence_from_score(score),
                    "quality_flags": flags,
                    "uncertainty_or_gap": uncertainty,
                }
            )
    items.sort(key=lambda row: float(row.get("snippet_score") or 0.0), reverse=True)
    return items


def confidence_for(items: list[dict[str, Any]], supporting_papers: list[str]) -> str:
    if not items or not supporting_papers:
        return "low"
    high_quality_count = sum(
        1 for item in items if float(item.get("snippet_score") or 0.0) >= 0.65
    )
    medium_quality_count = sum(
        1 for item in items if float(item.get("snippet_score") or 0.0) >= 0.45
    )
    parsed_count = sum(
        1
        for item in items
        if item.get("source") == "parsed-full-text"
        and float(item.get("snippet_score") or 0.0) >= 0.45
    )
    if high_quality_count >= 3 and parsed_count >= 3 and len(supporting_papers) >= 2:
        return "high"
    if medium_quality_count or parsed_count:
        return "medium"
    return "low"


def theme_row(
    theme: str,
    spec: dict[str, Any],
    papers: list[dict[str, Any]],
    evidences: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    supporting: list[str] = []
    snippets: list[dict[str, Any]] = []
    for paper in papers:
        evidence = evidences[paper["paper_id"]]
        if not paper_matches_theme(paper, evidence, spec):
            continue
        paper_items = evidence_items_for_theme(paper, evidence, spec, theme)
        if any(float(item.get("snippet_score") or 0.0) >= 0.35 for item in paper_items):
            supporting.append(paper["paper_id"])
        snippets.extend(paper_items)

    supporting = list(dict.fromkeys(supporting))
    limited_snippets = snippets[:12]
    gaps: list[str] = []
    if not supporting:
        gaps.append("当前 selected papers 没有为该主题提供足够直接的高质量证据。")
    if len(supporting) == 1:
        gaps.append("该主题只有一篇 selected paper 提供支持，扩展前需要人工复核。")
    if not any(
        item.get("source") == "parsed-full-text"
        and float(item.get("snippet_score") or 0.0) >= 0.45
        for item in limited_snippets
    ):
        gaps.append("证据偏 metadata/abstract 或低分片段，需要人工检查 parsed Markdown。")

    return {
        "theme": theme,
        "theme_label": THEME_LABELS_ZH.get(theme, theme),
        "claim": spec["claim"],
        "supporting_papers": supporting,
        "evidence_snippets_or_sections": limited_snippets,
        "confidence": confidence_for(limited_snippets, supporting),
        "gaps_or_uncertainties": gaps,
    }


def markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|")


def evidence_table_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# 证据表",
        "",
        f"Workspace: `{result['workspace']}`",
        "",
        "| 主题 | 综合判断 | 支撑论文 | 置信度 | 缺口或不确定性 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in result["themes"]:
        supporting = ", ".join(f"[{paper_id}]" for paper_id in row["supporting_papers"]) or "None"
        gaps = "; ".join(row["gaps_or_uncertainties"]) or "无"
        theme_label = f"{row.get('theme_label') or row['theme']}（{row['theme']}）"
        lines.append(
            f"| {markdown_cell(theme_label)} | {markdown_cell(row['claim'])} | "
            f"{supporting} | {row['confidence']} | {markdown_cell(gaps)} |"
        )

    lines.extend(["", "## 按主题分组的证据片段", ""])
    for row in result["themes"]:
        lines.extend([f"### {row.get('theme_label') or row['theme']}（{row['theme']}）", ""])
        if row["evidence_snippets_or_sections"]:
            for item in row["evidence_snippets_or_sections"]:
                flags = ", ".join(item.get("quality_flags") or []) or "none"
                lines.append(
                    f"- [{item['paper_id']}] `{item['field']}` / section={item.get('section')} / "
                    f"score={float(item.get('snippet_score') or 0.0):.2f} / "
                    f"confidence={item.get('confidence')}: {item['snippet']}"
                )
                lines.append(
                    f"  - 质量说明：{item.get('snippet_score_explanation') or 'N/A'}"
                )
                lines.append(f"  - 质量标记：{flags}")
                if item.get("uncertainty_or_gap"):
                    lines.append(f"  - 不确定性：{item['uncertainty_or_gap']}")
        else:
            lines.append("- 当前没有抽取到可用证据片段。")
        lines.append("")
    return "\n".join(lines)


def build_evidence_table(workspace: Path) -> dict[str, Any]:
    papers = [
        normalize_paper(paper) for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    evidences = {paper["paper_id"]: load_paper_evidence(workspace, paper) for paper in papers}
    themes = [
        theme_row(theme, spec, papers, evidences)
        for theme, spec in THEME_SPECS.items()
    ]
    result = {
        "workspace": str(workspace),
        "selected_count": len(papers),
        "themes": themes,
    }
    write_json(workspace / "knowledge" / "evidence_table.json", result)
    md = evidence_table_markdown(result)
    path = workspace / "knowledge" / "evidence_table.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    return result
